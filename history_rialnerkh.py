#!/usr/bin/env python3
"""وارد کردن تاریخچه‌ی ریال نرخ از endpoint صفحه‌ی نمودارش به history/rialnerkh/*.csv

اجرا (در ریشه‌ی ریپو، بعد از اینکه data/rialnerkh.json وجود دارد):
    python import_rialnerkh.py                 # همه‌ی کدها
    python import_rialnerkh.py --only USD,EUR  # فقط چند کد (برای تست)

قالب خروجی همان history/<منبع>/<دسته>_<نماد>.csv با ستون‌های ts,price است.
نقطه‌ها فقط *قبل از* اولین ردیف فایل‌های موجود اضافه می‌شوند؛ پس اجرای دوباره
(یا اجرا بعد از backfill.py) بی‌خطر است.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SRC = "rialnerkh"
RAW_URL = "https://raw.githubusercontent.com/Hossein4qs/Iran_market_api/main/data/rialnerkh.json"
API = "https://www.rialnerkh.com/wp-json/rialnerkh/v1/navasan-history/{code}?days={days}"
EVERY_MIN = 60   # باید با HISTORY_EVERY_MIN در scraper.py یکی باشد
PAUSE = 1.5      # ثانیه بین درخواست‌ها (مودبانه به سرور)
HEADERS = {"User-Agent": "Mozilla/5.0 (history-import)", "Accept": "application/json"}

# کدهای صفحه‌ی https://www.rialnerkh.com/chart/
CODES = """
USD EUR GBP AED_NOTE TRY JPY AUD NZD CAD SGD CHF PKR AZN NOK SEK DKK KWD OMR RUB BRL THB AFN INR CNY MYR GEL
USD_SHERKAT USD_SHAKHS AED EUR_HAV GBP_HAV HAV_CAD_CHEQUE AUD_HAV MYR_HAV CNY_HAV TRY_HAV JPY_HAV
BTC ETH XRP BCH EOS BNB USDT MEX_USD_SELL MEX_USD_BUY MEX_EUR_SELL MEX_EUR_BUY
XAU USD_XAU 18AYAR SEKKEH BAHAR NIM ROB ABSHODEH GERAMI
BUB_SEKKEH BUB_BAHAR BUB_NIM BUB_ROB BUB_18AYAR BUB_GERAMI
""".split()

# اگر نام یک کد با tag پروژه خودکار جور نشد، اینجا دستی وصلش کن، مثلاً:
# "USD_SHERKAT": "currency:usd_hawala_sherkat"
ALIASES = {}


def fetch_json(code, days):
    req = urllib.request.Request(API.format(code=code.lower(), days=days), headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_rows(rows):
    """-> [(ts, price)] مرتب‌شده؛ captured_at به وقت UTC است"""
    out = {}
    for r in rows:
        try:
            ts = int(datetime.strptime(r["captured_at"], "%Y-%m-%d %H:%M:%S")
                     .replace(tzinfo=timezone.utc).timestamp())
            v = float(r["value"])
        except Exception:
            continue
        if v > 0:  # صفر یعنی «قیمت موجود نیست»
            out[ts] = int(v) if v == int(v) else v
    return sorted(out.items())


def _tags_from_json(text):
    cats = json.loads(text)["categories"]
    return [it["tag"] for c in cats.values() for it in c.get("items", []) if it.get("tag")]


def known_tags():
    """tagها را از data/rialnerkh.json می‌خواند؛ اگر نبود یا خراب بود، از گیت‌هاب"""
    path = Path("data") / f"{SRC}.json"
    if path.exists():
        try:
            return _tags_from_json(path.read_text(encoding="utf-8-sig"))
        except Exception as e:
            print(f"! {path} خالی یا خراب است ({e.__class__.__name__}) → از گیت‌هاب می‌خوانم",
                  file=sys.stderr)
    try:
        req = urllib.request.Request(RAW_URL, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as r:
            return _tags_from_json(r.read().decode("utf-8-sig"))
    except Exception as e:
        sys.exit(f"فایل tagها را نتوانستم بخوانم ({e}).\n"
                 "اسکریپت را داخل پوشه‌ی کلون‌شده‌ی ریپو اجرا کن یا اینترنت را بررسی کن.")


def match_tag(code, tags):
    if code in ALIASES:
        return ALIASES[code]
    hits = [t for t in tags if t.split(":", 1)[-1].lower() == code.lower()]
    return hits[0] if len(hits) == 1 else None


def merge_write(path, pts):
    existing = []
    if path.exists():
        existing = [l for l in path.read_text(encoding="utf-8").splitlines()[1:] if l.strip()]
    cutoff = int(existing[0].split(",")[0]) if existing else float("inf")
    gap = EVERY_MIN * 60 - 300
    new, last = [], 0
    for ts, price in pts:
        if ts >= cutoff or ts - last < gap:
            continue
        new.append(f"{ts},{price}")
        last = ts
    if new:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ts,price\n" + "\n".join(new + existing) + "\n", encoding="utf-8")
    return len(new)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="کدها با کاما، مثل USD,EUR")
    ap.add_argument("--days", type=int, default=365)
    args = ap.parse_args()

    codes = [c.strip().upper() for c in args.only.split(",")] if args.only else CODES
    tags = known_tags()
    unmatched, failed, total = [], [], 0
    for code in codes:
        tag = match_tag(code, tags)
        if tag is None:
            unmatched.append(code)
            continue
        try:
            pts = parse_rows(fetch_json(code, args.days))
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            failed.append(f"{code} ({e})")
            time.sleep(PAUSE)
            continue
        n = merge_write(Path("history") / SRC / (tag.replace(":", "_") + ".csv"), pts)
        total += n
        print(f"{code:>16} -> {tag:<28} {len(pts):5d} نقطه‌ی خام، {n:4d} اضافه شد", file=sys.stderr)
        time.sleep(PAUSE)

    print(f"\nجمعاً {total} نقطه اضافه شد.", file=sys.stderr)
    if unmatched:
        print("جور نشد با هیچ tag (در ALIASES دستی وصل کن یا نادیده بگیر): " + ", ".join(unmatched),
              file=sys.stderr)
    if failed:
        print("خطا در دریافت: " + "; ".join(failed), file=sys.stderr)


if __name__ == "__main__":
    main()
