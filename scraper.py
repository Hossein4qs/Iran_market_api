#!/usr/bin/env python3
"""استخراج قیمت ارز، طلا، سکه و کریپتو از chande.net و ذخیره در data/prices.json

سایت chande.net با جاوااسکریپت رندر می‌شود، پس از Playwright استفاده می‌کنیم.
دو روش هم‌زمان کار می‌کند:
  1) شنود پاسخ‌های JSON که خود سایت از API می‌گیرد (data/raw/*.json)
  2) خواندن کارت‌های قیمت از DOM (لینک‌های /chart/SYMBOL)
"""
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://chande.net"
CATEGORIES = {
    "currency": "ارز",
    "gold": "طلا و سکه",
    "crypto": "ارز دیجیتال",
    "commodity": "کالا",
}
OUT_DIR = Path("data")
RAW_DIR = OUT_DIR / "raw"
TEHRAN = timezone(timedelta(hours=3, minutes=30))

FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫٬،", "01234567890123456789.,,")


def to_number(text):
    """'۱۲۳,۴۵۶' -> 123456"""
    t = text.translate(FA_DIGITS).replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    if not m:
        return None
    v = float(m.group())
    return int(v) if v.is_integer() else v


# DOM extraction (JS runs in browser)
DOM_JS = r"""
() => {
  const out = [];
  const seen = new Set();
  document.querySelectorAll('a[href^="/chart/"], a[href*="chande.net/chart/"]').forEach(a => {
    const m = a.getAttribute('href').match(/\/chart\/([^/?#]+)/);
    if (!m) return;
    const symbol = decodeURIComponent(m[1]);
    if (seen.has(symbol)) return;
    // بالا می‌رویم تا کارتی که عدد دارد پیدا شود
    let el = a, text = '';
    for (let i = 0; i < 5 && el; i++) {
      text = (el.innerText || '').trim();
      if (/[0-9۰-۹]/.test(text) && text.length > 3) break;
      el = el.parentElement;
    }
    if (!text) return;
    seen.add(symbol);
    out.push({symbol, lines: text.split('\n').map(s => s.trim()).filter(Boolean)});
  });
  return out;
}
"""


def parse_dom_item(item):
    lines = item["lines"]
    name = next((l for l in lines if re.search(r"[آ-ی]", l) and not re.search(r"[0-9۰-۹]", l)), None)
    numbers = [to_number(l) for l in lines if re.search(r"[0-9۰-۹]", l)]
    numbers = [n for n in numbers if n is not None]
    pct = next((l for l in lines if "%" in l or "٪" in l), None)
    return {
        "symbol": item["symbol"],
        "name": name,
        "price": numbers[0] if numbers else None,
        "change_percent": to_number(pct) if pct else None,
        "raw": lines,
    }


def scrape_category(page, slug, api_payloads):
    url = f"{BASE}/category/{slug}"
    print(f"→ {url}", file=sys.stderr)
    page.goto(url, wait_until="networkidle", timeout=60_000)
    try:
        page.wait_for_selector('a[href^="/chart/"]', timeout=20_000)
    except Exception:
        pass
    page.wait_for_timeout(3000)  # برای رسیدن قیمت‌های زنده
    items = [parse_dom_item(i) for i in page.evaluate(DOM_JS)]
    # لینک‌های SEO که قیمت ندارند را حذف کن
    items = [i for i in items if i["price"] is not None]
    return items


def main():
    OUT_DIR.mkdir(exist_ok=True)
    RAW_DIR.mkdir(exist_ok=True)
    api_payloads = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(locale="fa-IR", timezone_id="Asia/Tehran")
        page = ctx.new_page()

        def on_response(resp):
            try:
                ct = resp.headers.get("content-type", "")
                if "json" in ct and "chande" in resp.url and resp.status == 200:
                    api_payloads.append({"url": resp.url, "data": resp.json()})
            except Exception:
                pass

        page.on("response", on_response)

        result = {}
        for slug, title in CATEGORIES.items():
            try:
                result[slug] = {"title": title, "items": scrape_category(page, slug, api_payloads)}
            except Exception as e:
                print(f"خطا در {slug}: {e}", file=sys.stderr)
                result[slug] = {"title": title, "items": [], "error": str(e)}
        browser.close()

    # ذخیره پاسخ‌های API برای دیباگ/تنظیم (فقط آخرین اجرا)
    for old in RAW_DIR.glob("*.json"):
        old.unlink()
    for i, pl in enumerate(api_payloads[:30]):
        (RAW_DIR / f"{i:02d}.json").write_text(
            json.dumps(pl, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    total = sum(len(c["items"]) for c in result.values())
    if total == 0:
        print("هیچ قیمتی استخراج نشد؛ فایل خروجی تغییر نکرد.", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc)
    output = {
        "source": BASE,
        "updated_at_utc": now.isoformat(timespec="seconds"),
        "updated_at_tehran": now.astimezone(TEHRAN).isoformat(timespec="seconds"),
        "unit": "تومان (طبق نمایش سایت)",
        "categories": result,
    }
    (OUT_DIR / "prices.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✓ {total} قیمت ذخیره شد.", file=sys.stderr)


if __name__ == "__main__":
    main()
