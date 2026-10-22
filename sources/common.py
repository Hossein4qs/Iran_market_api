"""ابزارهای مشترک بین پارسرهای منابع مختلف."""
import re
import sys

from bs4 import BeautifulSoup

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


def link_slug(row, marker):
    a = row.find("a", href=re.compile(re.escape(marker) + r"/[^/?#]+"))
    if not a:
        return None
    return a["href"].split("?")[0].rstrip("/").split("/")[-1]



def parse_table_page(html, parse_row):
    """همه‌ی <tr> های صفحه را با parse_row می‌خواند -> (آیتم‌ها، زمان به‌روزرسانی سایت)."""
    soup = BeautifulSoup(html, "lxml")
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
