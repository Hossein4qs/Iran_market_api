#!/usr/bin/env python3
"""وارد کردن تاریخچه‌ی ریال نرخ از endpoint صفحه‌ی نمودارش به history/rialnerkh/*.csv

اجرا از ریشه‌ی پروژه؛ بدون نیاز به GitHub یا data/rialnerkh.json:
    python import_rialnerkh.py                 # همه‌ی کدها
    python import_rialnerkh.py --only USD,EUR  # فقط چند کد (برای تست)

قالب خروجی همان history/<منبع>/<دسته>_<نماد>.csv با ستون‌های ts,price است.
نقطه‌ها فقط *قبل از* اولین ردیف فایل‌های موجود اضافه می‌شوند؛ پس اجرای دوباره
(یا اجرا بعد از backfill.py) بی‌خطر است.
"""
import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SRC = "rialnerkh"
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


def fetch_json(code, days, retries=4):
    """دریافت JSON با تلاش مجدد برای خطاهای موقت شبکه/TLS."""
    url = API.format(code=code.lower(), days=days)
    last_error = None

    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, ssl.SSLError, TimeoutError,
                ConnectionError, OSError, json.JSONDecodeError) as e:
            last_error = e
            if attempt < retries:
                wait = min(2 ** attempt, 15)
                print(
                    f"! {code}: خطای موقت دریافت ({e}); "
                    f"تلاش دوباره در {wait} ثانیه "
                    f"({attempt + 1}/{retries})",
                    file=sys.stderr,
                )
                time.sleep(wait)

    raise last_error


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


# نگاشت مستقل کدهای API به tag خروجی؛ نیازی به data/rialnerkh.json یا GitHub نیست.
# برای کدهای معمول، نام فایل از category و کد ساخته می‌شود.
CURRENCY_CODES = set("""
USD EUR GBP AED_NOTE TRY JPY AUD NZD CAD SGD CHF PKR AZN NOK SEK DKK KWD OMR RUB BRL THB AFN INR CNY MYR GEL
USD_SHERKAT USD_SHAKHS AED EUR_HAV GBP_HAV HAV_CAD_CHEQUE AUD_HAV MYR_HAV CNY_HAV TRY_HAV JPY_HAV
""".split())
CRYPTO_CODES = set("""
BTC ETH XRP BCH EOS BNB USDT
""".split())
GOLD_CODES = set("""
XAU USD_XAU 18AYAR SEKKEH BAHAR NIM ROB ABSHODEH GERAMI
BUB_SEKKEH BUB_BAHAR BUB_NIM BUB_ROB BUB_18AYAR BUB_GERAMI
""".split())

def match_tag(code, tags=None):
    """ساخت tag به‌صورت محلی، بدون فایل جانبی یا اتصال به GitHub."""
    if code in ALIASES:
        return ALIASES[code]
    if code in CURRENCY_CODES:
        category = "currency"
    elif code in CRYPTO_CODES or code.startswith("MEX_"):
        category = "crypto"
    elif code in GOLD_CODES:
        category = "gold"
    else:
        return None
    return f"{category}:{code.lower()}"

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
    ap.add_argument("--no-retry-failed", action="store_true",
                    help="فایل خطاهای اجرای قبلی را به فهرست اضافه نکن")
    args = ap.parse_args()

    failed_file = Path("data") / "failed_imports.json"
    codes = [c.strip().upper() for c in args.only.split(",")] if args.only else list(CODES)

    # اگر اجرای قبلی کدی را نتوانسته دریافت کند، در اجرای بعدی دوباره امتحانش کن.
    if not args.only and not args.no_retry_failed and failed_file.exists():
        try:
            saved = json.loads(failed_file.read_text(encoding="utf-8"))
            previous_codes = saved.get("codes", []) if isinstance(saved, dict) else []
            codes.extend(c for c in previous_codes if c not in codes)
        except (OSError, json.JSONDecodeError, AttributeError):
            print(f"! فایل {failed_file} قابل خواندن نیست؛ از آن صرف‌نظر شد.",
                  file=sys.stderr)

    unmatched, failed, total = [], {}, 0

    def import_one(code, retries=4):
        nonlocal total
        tag = match_tag(code)
        if tag is None:
            unmatched.append(code)
            return True
        try:
            pts = parse_rows(fetch_json(code, args.days, retries=retries))
        except (urllib.error.URLError, ssl.SSLError, ValueError, TimeoutError,
                ConnectionError, OSError) as e:
            failed[code] = str(e)
            print(f"! {code}: دریافت ناموفق ماند: {e}", file=sys.stderr)
            return False

        path = Path("history") / SRC / (tag.replace(":", "_") + ".csv")
        n = merge_write(path, pts)
        total += n
        print(f"{code:>16} -> {tag:<28} {len(pts):5d} نقطه‌ی خام، {n:4d} اضافه شد",
              file=sys.stderr)
        failed.pop(code, None)
        return True

    # دور اصلی
    for code in codes:
        import_one(code)
        time.sleep(PAUSE)

    # یک دور کوتاه دیگر فقط برای کدهایی که در همین اجرا شکست خوردند.
    if failed:
        retry_codes = list(failed)
        print("\nتلاش دوباره فقط برای کدهای ناموفق: " + ", ".join(retry_codes),
              file=sys.stderr)
        for code in retry_codes:
            time.sleep(PAUSE)
            import_one(code, retries=2)

    print(f"\nجمعاً {total} نقطه اضافه شد.", file=sys.stderr)
    if unmatched:
        print("جور نشد با هیچ tag (در ALIASES دستی وصل کن یا نادیده بگیر): " +
              ", ".join(unmatched), file=sys.stderr)

    # فقط کدهای هنوز ناموفق را نگه دار تا اجرای بعدی دوباره امتحان شوند.
    try:
        if failed:
            failed_file.parent.mkdir(parents=True, exist_ok=True)
            failed_file.write_text(
                json.dumps({"codes": list(failed), "errors": failed},
                           ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print("کدهای ناموفق برای اجرای بعدی ذخیره شدند: " + str(failed_file),
                  file=sys.stderr)
            print("خطاهای نهایی: " + "; ".join(
                f"{code} ({error})" for code, error in failed.items()),
                file=sys.stderr)
        elif failed_file.exists():
            failed_file.unlink()
            print("همه‌ی دریافت‌ها موفق شدند؛ فایل خطاهای قبلی پاک شد.",
                  file=sys.stderr)
    except OSError as e:
        print(f"! نتوانستم فایل خطاها را ذخیره/پاک کنم: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
