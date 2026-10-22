#!/usr/bin/env python3
"""اجرای همه‌ی منابع قیمت (پوشه‌ی sources/) -> برای هر منبع یک فایل data/<id>.json

تگ هر قیمت  <دسته>:<نماد>  است (مثل currency:usd) و بین همه‌ی منابع یکسان است.
"""
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from sources import SOURCES
from sources.tags import make_tag

OUT = Path("data")
DEBUG = Path("debug")
TEHRAN = timezone(timedelta(hours=3, minutes=30))
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.5",
}


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


def load_previous(src_id):
    try:
        return json.loads((OUT / f"{src_id}.json").read_text(encoding="utf-8"))["categories"]
    except Exception:
        return {}


def scrape_source(session, src):
    """-> (دیکشنری فایل منبع، تعداد دسته‌های ناموفق)"""
    prev_cats = load_previous(src.ID)
    categories, failed = {}, 0
    for category, (title, path) in src.PAGES.items():
        url = src.BASE + path
        print(f"→ [{src.ID}] {url}", file=sys.stderr)
        try:
            html = fetch(session, url)
            items, site_updated = src.parse_page(category, html)
            min_items = src.MIN_ITEMS.get(category, 1)
            if len(items) < min_items:
                DEBUG.mkdir(exist_ok=True)
                (DEBUG / f"{src.ID}_{category}.html").write_text(html, encoding="utf-8")
                raise RuntimeError(f"فقط {len(items)} ردیف پیدا شد (حداقل {min_items}) "
                                   "؛ ساختار صفحه احتمالاً عوض شده")
            # tag همیشه اولین کلید آیتم است
            items = [{"tag": make_tag(category, it["symbol"]), **it} for it in items]
            categories[category] = {"title": title, "url": url,
                                    "site_updated": site_updated, "items": items}
            print(f"  {len(items)} مورد", file=sys.stderr)
        except Exception as e:
            print(f"::warning::{src.ID}/{category}: {e}", file=sys.stderr)
            failed += 1
            old = prev_cats.get(category, {"title": title, "items": []})
            categories[category] = {**old, "stale": True, "error": str(e)[:300]}
        time.sleep(1.5)
    return categories, failed


def check_unique_tags(src_id, categories):
    seen = set()
    for cat, c in categories.items():
        for it in c["items"]:
            if it["tag"] in seen:
                print(f"::warning::[{src_id}] tag تکراری: {it['tag']}", file=sys.stderr)
            seen.add(it["tag"])
    return len(seen)


def main():
    OUT.mkdir(exist_ok=True)
    dead = []          # منابعی که هیچ دسته‌شان خوانده نشد (فایل‌شان دست نمی‌خورد)
    with requests.Session() as session:
        for src in SOURCES:
            categories, failed = scrape_source(session, src)
            if failed == len(src.PAGES):
                dead.append(src.ID)
                print(f"::error::[{src.ID}] هیچ دسته‌ای خوانده نشد؛ data/{src.ID}.json تغییر نکرد.",
                      file=sys.stderr)
                continue
            total = check_unique_tags(src.ID, categories)
            now = datetime.now(timezone.utc)
            (OUT / f"{src.ID}.json").write_text(json.dumps({
                "source": {"id": src.ID, "name": src.NAME, "url": src.BASE},
                "unit": "تومان (مگر آنکه در آیتم unit=usd باشد)",
                "updated_at_utc": now.isoformat(timespec="seconds"),
                "updated_at_tehran": now.astimezone(TEHRAN).isoformat(timespec="seconds"),
                "categories": categories,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"✓ [{src.ID}] {total} قیمت ذخیره شد"
                  + (f" ({failed} دسته ناموفق)" if failed else ""), file=sys.stderr)
    if dead:
        sys.exit(1)    # بعد از ذخیره‌ی منابع سالم، اجرا را قرمز کن تا خبردار شوی


if __name__ == "__main__":
    main()
