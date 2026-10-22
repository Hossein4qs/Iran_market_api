#!/usr/bin/env python3
"""استخراج قیمت از alanchand.com -> data/prices.json

صفحه‌های الان‌چند سمت سرور رندر می‌شوند، پس نیازی به مرورگر نیست؛
فقط جدول‌های HTML خوانده می‌شود.
"""
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://alanchand.com"
PAGES = {
    "currency": ("ارز", "/currencies-price"),
    "gold": ("طلا و سکه", "/gold-price"),
    "crypto": ("ارز دیجیتال", "/crypto-price"),
}
OUT = Path("data")
DEBUG = Path("debug")
TEHRAN = timezone(timedelta(hours=3, minutes=30))
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.5",
}

# حداقل تعداد ردیف‌های قابل‌قبول؛ کمتر از این یعنی ساختار صفحه عوض شده
MIN_ITEMS = {"currency": 10, "gold": 4, "crypto": 10}

# ---------- ابزارهای عددی / متنی ----------
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫٬،−", "01234567890123456789.,,-")
NUM = r"\d[\d,]*(?:\.\d+)?"
PCT_RE = re.compile(rf"(?:%\s*{NUM}|{NUM}\s*%)")
NUM_RE = re.compile(NUM)
FA_RE = re.compile(r"[\u0600-\u06FF]")


def ascii_digits(s):
    return s.translate(DIGITS)


def to_number(s):
    """'۲۶۷,۱۰۰' -> 267100 ، '۰.۸۹۰' -> 0.89 ، '-' -> None"""
    m = NUM_RE.search(ascii_digits(s or ""))
    if not m:
        return None
    v = float(m.group().replace(",", ""))
    return int(v) if v.is_integer() else v


def norm(name):
    """نرمال‌سازی نام برای جستجو در دیکشنری‌ها"""
    s = ascii_digits(name).replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"[\s\u200c()]+", "", s)


def cell_text(el):
    t = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
    return t.replace("ي", "ی").replace("ك", "ک")   # یکدست‌سازی حروف عربی/فارسی


def split_price_cell(text):
    """'۲۷۰,۷۹۱ تومان ۲.۱۰%' یا '%۱.۶۹ $۸۱,۹۴۰' -> (قیمت، درصد، واحد)"""
    t = ascii_digits(text)
    pct = None
    m = PCT_RE.search(t)
    if m:
        pct = to_number(m.group())
        t = t[:m.start()] + " " + t[m.end():]
    unit = "usd" if "$" in t else ("toman" if "تومان" in t else None)
    return to_number(t), pct, unit


def direction(el, text, pct):
    """جهت تغییر را از علامت منفی، فلش یا کلاس CSS حدس می‌زند؛ اگر نشد None."""
    if pct == 0:
        return "flat"
    if "-" in ascii_digits(text) or "▼" in text or "↓" in text:
        return "down"
    if "▲" in text or "↑" in text or "+" in text:
        return "up"
    classes = []
    for node in [el, *el.find_all(True)]:
        classes += node.get("class", [])
    joined = " ".join(classes).lower()
    if re.search(r"(?:^|[\s_-])(down|red|negative|fall|danger|bearish|decrease)(?:$|[\s_-])", joined):
        return "down"
    if re.search(r"(?:^|[\s_-])(up|green|positive|rise|success|bullish|increase)(?:$|[\s_-])", joined):
        return "up"
    return None


def signed(pct, d):
    """درصد با علامت؛ اگر جهت معلوم نباشد None (مقدار خام در *_abs می‌ماند)."""
    if pct is None or d is None:
        return None
    return -abs(pct) if d == "down" else abs(pct)


# ---------- نگاشت نام فارسی -> نماد ----------
# (نماد، تعداد واحد)  ← «صد ین» یعنی قیمت برای ۱۰۰ واحد است
CURRENCIES = {
    "دلارآمریکا": ("usd", 1), "دلاراستانبول": ("usd_istanbul", 1),
    "دلارسلیمانیه": ("usd_sulaymaniyah", 1), "دلارهرات": ("usd_herat", 1),
    "حوالهدلارآمریکا": ("usd_hawala", 1),
    "یورو": ("eur", 1), "حوالهیورو": ("eur_hawala", 1), "یورواستانبول": ("eur_istanbul", 1),
    "درهم": ("aed", 1), "لیرترکیه": ("try", 1), "پوندانگلیس": ("gbp", 1),
    "یوانچین": ("cny", 1), "دلارکانادا": ("cad", 1), "دلاراسترالیا": ("aud", 1),
    "روبلروسیه": ("rub", 1), "صددینارعراق": ("iqd", 100), "رینگیتمالزی": ("myr", 1),
    "لاریگرجستان": ("gel", 1), "منات‌آذربایجان".replace("\u200c", ""): ("azn", 1),
    "صددرامارمنستان": ("amd", 100), "باتتایلند": ("thb", 1), "ریالعمان": ("omr", 1),
    "روپیههند": ("inr", 1), "صدینژاپن": ("jpy", 100), "افغانی": ("afn", 1),
    "روپیهپاکستان": ("pkr", 1), "ریالعربستان": ("sar", 1), "کرونسوئد": ("sek", 1),
    "فرانکسوئیس": ("chf", 1), "ریالقطر": ("qar", 1), "صدوونکرهجنوبی": ("krw", 100),
    "کروننروژ": ("nok", 1), "دلارنیوزلند": ("nzd", 1),
    "دلارسنگاپور": ("sgd", 1), "دلارهنگکنگ": ("hkd", 1), "دینارکویت": ("kwd", 1),
    "کروندانمارک": ("dkk", 1), "دیناربحرین": ("bhd", 1),
    "سامانیتاجیکستان": ("tjs", 1), "منات‌ترکمنستان".replace("\u200c", ""): ("tmt", 1),
    "سومقرقیزستان": ("kgs", 1), "صدپوندسوریه": ("syp", 100), "رئالبرزیل": ("brl", 1),
    "پزوآرژانتین": ("ars", 1),
}

# اگر لینک ردیف slug داشته باشد همان استفاده می‌شود؛ این فقط جایگزین است
GOLD = {
    "آبشدهمثقالطلا": "abshodeh", "گرمطلای18عیار": "18ayar",
    "سکهامامیطرحجدید": "sekkeh", "سکهبهارآزادی": "sekkeh_bahar",
    "نیمسکه": "nim", "ربعسکه": "rob", "سکهگرمی": "gerami",
    "انسطلا": "usd_xau", "انسنقره": "usd_xag", "انسپلاتین": "usd_xpt",
    "انسپالادیوم": "usd_xpd", "انسرودیوم": "usd_xrh",
}


def link_slug(row, marker):
    a = row.find("a", href=re.compile(re.escape(marker) + r"/[^/?#]+"))
    if not a:
        return None
    return a["href"].split("?")[0].rstrip("/").split("/")[-1]


# ---------- پارسرهای هر دسته (هر کدام یک <tr> می‌گیرند؛ ردیف نامربوط -> None) ----------
def parse_currency_row(row, cells):
    if len(cells) < 3:
        return None
    name = cell_text(cells[0])
    buy, sell = to_number(cell_text(cells[1])), to_number(cell_text(cells[2]))
    if not name or buy is None or sell is None:
        return None
    key = norm(name)
    if key in CURRENCIES:
        symbol, qty = CURRENCIES[key]
    else:
        print(f"  ! ارز ناشناخته (نماد حدسی): {name}", file=sys.stderr)
        symbol, qty = key, 1
    per_usd = to_number(cell_text(cells[3])) if len(cells) > 3 else None
    avg = (buy + sell) / 2
    return {"symbol": symbol, "name": name, "quantity": qty,
            "buy": buy, "sell": sell,
            "average": int(avg) if float(avg).is_integer() else avg,
            "per_usd": per_usd}


def parse_gold_row(row, cells):
    if len(cells) < 2:
        return None
    name = cell_text(cells[0])
    ptxt = cell_text(cells[1])
    price, pct, unit = split_price_cell(ptxt)
    if not name or price is None:
        return None
    d = direction(cells[1], ptxt, pct)
    symbol = link_slug(row, "/gold-price") or GOLD.get(norm(name))
    if not symbol:
        print(f"  ! آیتم طلای ناشناخته (نماد حدسی): {name}", file=sys.stderr)
        symbol = norm(name)
    real = bubble = bubble_pct = None
    if len(cells) > 2:
        real = to_number(cell_text(cells[2]))
    if len(cells) > 3:
        btxt = ascii_digits(cell_text(cells[3]))
        nums = NUM_RE.findall(btxt)
        if len(nums) >= 2:
            bubble, bubble_pct = to_number(nums[0]), to_number(nums[1])
    return {"symbol": symbol, "name": name, "price": price,
            "unit": unit or "toman", "change_percent": signed(pct, d),
            "change_percent_abs": pct, "real_price": real,
            "bubble": bubble, "bubble_percent": bubble_pct}


def parse_crypto_row(row, cells):
    if len(cells) < 3:
        return None
    img = cells[0].find("img", src=re.compile(r"/crypto/[^/]+\.\w+"))
    toman_txt, usd_txt = cell_text(cells[1]), cell_text(cells[2])
    p_toman, pct_toman, _ = split_price_cell(toman_txt)
    p_usd, pct_usd, _ = split_price_cell(usd_txt)
    if p_usd is None and p_toman is None:
        return None
    tokens = cell_text(cells[0]).split()
    fa, en = [], []
    for t in tokens:
        (en if (en or not FA_RE.search(t)) else fa).append(t)
    symbol = None
    if img:
        symbol = re.search(r"/crypto/([^/.]+)\.", img["src"]).group(1).upper()
    elif en:
        symbol = en[-1].upper()
    if not symbol:
        return None
    if en and en[-1].upper() == symbol:
        en = en[:-1]
    d_t, d_u = direction(cells[1], toman_txt, pct_toman), direction(cells[2], usd_txt, pct_usd)
    return {"symbol": symbol, "name": " ".join(fa) or None, "name_en": " ".join(en) or None,
            # قیمت تومانی ۰ یعنی بازار داخلی آن را پوشش نمی‌دهد
            "price_toman": p_toman or None,
            "change_percent_toman": signed(pct_toman, d_t), "change_percent_toman_abs": pct_toman,
            "price_usd": p_usd,
            "change_percent_usd": signed(pct_usd, d_u), "change_percent_usd_abs": pct_usd}


ROW_PARSERS = {"currency": parse_currency_row, "gold": parse_gold_row, "crypto": parse_crypto_row}


# ---------- دریافت و استخراج ----------
def fetch(session, url, attempts=3):
    last = None
    for i in range(attempts):
        try:
            r = session.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            r.encoding = "utf-8"
            return r.text
        except requests.RequestException as e:
            last = e
            print(f"  ! تلاش {i + 1}/{attempts} ناموفق: {e}", file=sys.stderr)
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"دریافت {url} ممکن نشد: {last}")


def parse_page(slug, html):
    soup = BeautifulSoup(html, "lxml")
    parse_row = ROW_PARSERS[slug]
    items, seen = [], set()
    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if not cells:
            continue
        try:
            item = parse_row(row, cells)
        except Exception as e:  # یک ردیف خراب نباید کل صفحه را بیندازد
            print(f"  ! ردیف خوانده نشد: {e}", file=sys.stderr)
            continue
        if item and item["symbol"] not in seen:
            seen.add(item["symbol"])
            items.append(item)
    m = re.search(r"آخرین\s*بروز\s*رسانی\s*:?\s*([^\n<]{5,60})", soup.get_text("\n"))
    site_updated = ascii_digits(m.group(1)).strip() if m else None
    return items, site_updated


def load_previous():
    try:
        return json.loads((OUT / "prices.json").read_text(encoding="utf-8"))["categories"]
    except Exception:
        return {}


def main():
    OUT.mkdir(exist_ok=True)
    DEBUG.mkdir(exist_ok=True)
    previous = load_previous()
    result, failed = {}, []

    with requests.Session() as session:
        for slug, (title, path) in PAGES.items():
            url = BASE + path
            print(f"→ {url}", file=sys.stderr)
            try:
                html = fetch(session, url)
                items, site_updated = parse_page(slug, html)
                if len(items) < MIN_ITEMS[slug]:
                    (DEBUG / f"{slug}.html").write_text(html, encoding="utf-8")
                    raise RuntimeError(f"فقط {len(items)} ردیف پیدا شد (حداقل {MIN_ITEMS[slug]}) "
                                       "؛ ساختار صفحه احتمالاً عوض شده")
                result[slug] = {"title": title, "url": url,
                                "site_updated": site_updated, "items": items}
                print(f"  {len(items)} مورد", file=sys.stderr)
            except Exception as e:
                print(f"::warning::{slug}: {e}", file=sys.stderr)
                failed.append(slug)
                old = previous.get(slug, {"title": title, "items": []})
                result[slug] = {**old, "stale": True, "error": str(e)[:300]}
            time.sleep(1.5)

    if len(failed) == len(PAGES):
        print("هیچ دسته‌ای خوانده نشد؛ prices.json تغییر نکرد.", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc)
    (OUT / "prices.json").write_text(json.dumps({
        "source": BASE,
        "unit": "تومان (مگر آنکه در آیتم unit=usd باشد)",
        "updated_at_utc": now.isoformat(timespec="seconds"),
        "updated_at_tehran": now.astimezone(TEHRAN).isoformat(timespec="seconds"),
        "categories": result,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(c["items"]) for c in result.values())
    print(f"✓ {total} قیمت ذخیره شد" + (f" (ناموفق: {', '.join(failed)})" if failed else ""),
          file=sys.stderr)


if __name__ == "__main__":
    main()
