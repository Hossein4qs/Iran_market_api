#!/usr/bin/env python3
"""استخراج قیمت از chande.net -> data/prices.json   (+ فایل‌های دیباگ در data/debug)"""
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
OUT = Path("data")
DEBUG = OUT / "debug"
TEHRAN = timezone(timedelta(hours=3, minutes=30))
LOADING_TEXT = "در حال بارگذاری نسخه تعاملی"
UNITS = ("تومان", "ریال", "دلار", "USD", "$")

FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫٬،−", "01234567890123456789.,,-")
NUM_RE = re.compile(r"[0-9۰-۹٠-٩][0-9۰-۹٠-٩,٬.٫]{2,}")      # عدد حداقل ۳ کاراکتری
PURE_NUM = re.compile(r"^[+\-−]?\s*[0-9۰-۹٠-٩][0-9۰-۹٠-٩,٬.٫]*\s*%?$")
FA_LETTER = re.compile(r"[آ-ی]")


def to_number(text):
    t = text.translate(FA).replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", t)
    if not m:
        return None
    v = float(m.group())
    return int(v) if v.is_integer() else v


# ---------- استخراج کارت‌ها از DOM (فقط کارت‌های کوچک؛ متن‌های سئو رد می‌شوند) ----------
DOM_JS = r"""
() => {
  const NUM = /[0-9۰-۹٠-٩][0-9۰-۹٠-٩,٬.٫]{2,}/;
  const lines = el => (el.innerText || '').split('\n').map(s => s.trim()).filter(Boolean);
  const out = [], seen = new Set();
  document.querySelectorAll('a[href*="/chart/"], [data-symbol], [data-code]').forEach(a => {
    let symbol = a.getAttribute('data-symbol') || a.getAttribute('data-code');
    if (!symbol) {
      const m = (a.getAttribute('href') || '').match(/\/chart\/([^/?#]+)/);
      if (!m) return;
      symbol = decodeURIComponent(m[1]);
    }
    if (seen.has(symbol)) return;
    let el = a, best = null;
    for (let i = 0; i < 6 && el && el !== document.body; i++) {
      const L = lines(el);
      if (L.length > 8) break;                 // خیلی بزرگ = کانتینر/متن سئو
      if (L.some(l => NUM.test(l))) { best = L; break; }
      el = el.parentElement;
    }
    if (!best) return;
    seen.add(symbol);
    out.push({symbol, lines: best});
  });
  return out;
}
"""


def parse_card(item):
    lines = item["lines"]
    name = next(
        (l for l in lines
         if FA_LETTER.search(l) and not re.search(r"[0-9۰-۹]", l)
         and len(l) <= 30 and l not in UNITS),
        None,
    )
    price = None
    change = None
    for l in lines:
        if "%" in l or "٪" in l:
            if change is None:
                change = to_number(l)
            continue
        if price is None and NUM_RE.search(l):
            price = to_number(l)
    return {
        "symbol": item["symbol"],
        "name": name,
        "price": price,
        "change_percent": change,
    }


# ---------- روش پشتیبان: خواندن متن صفحه ----------
def parse_text_fallback(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    items, seen = [], set()
    for i, l in enumerate(lines):
        if not PURE_NUM.match(l) or "%" in l or not NUM_RE.search(l):
            continue
        for back in (1, 2):
            if i - back < 0:
                break
            cand = lines[i - back]
            if FA_LETTER.search(cand) and len(cand) <= 30 and not re.search(r"[0-9۰-۹]", cand):
                if cand in seen:
                    break
                seen.add(cand)
                change = None
                if i + 1 < len(lines) and ("%" in lines[i + 1] or "٪" in lines[i + 1]):
                    change = to_number(lines[i + 1])
                items.append({"symbol": None, "name": cand, "price": to_number(l),
                              "change_percent": change})
                break
    return items


def scrape_category(page, slug):
    url = f"{BASE}/category/{slug}"
    print(f"→ {url}", file=sys.stderr)
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    # صبر تا نسخه‌ی تعاملی جایگزین متن «در حال بارگذاری» شود
    try:
        page.wait_for_function(
            "t => !document.body.innerText.includes(t)", arg=LOADING_TEXT, timeout=30_000)
    except Exception:
        print("  ! نسخه تعاملی در ۳۰ ثانیه بالا نیامد", file=sys.stderr)
    # صبر تا اعداد قیمتی ظاهر شوند
    try:
        page.wait_for_function(
            r"() => /[0-9۰-۹]{1,3}[,٬][0-9۰-۹]{3}/.test(document.body.innerText)", timeout=30_000)
    except Exception:
        print("  ! عدد قیمتی دیده نشد", file=sys.stderr)
    page.wait_for_timeout(2500)

    body_text = page.inner_text("body")
    (DEBUG / f"{slug}.txt").write_text(body_text, encoding="utf-8")
    (DEBUG / f"{slug}.html").write_text(page.content()[:300_000], encoding="utf-8")

    items = [parse_card(c) for c in page.evaluate(DOM_JS)]
    items = [i for i in items if i["price"] is not None]
    method = "dom"
    if not items:
        items = parse_text_fallback(body_text)
        method = "text"
    print(f"  {len(items)} مورد ({method})", file=sys.stderr)
    return {"title": CATEGORIES[slug], "method": method, "items": items}


def main():
    OUT.mkdir(exist_ok=True)
    DEBUG.mkdir(exist_ok=True)
    for f in DEBUG.glob("*"):
        f.unlink()

    net_log, ws_log = [], []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            locale="fa-IR", timezone_id="Asia/Tehran",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
        )
        page = ctx.new_page()

        def on_response(resp):
            try:
                rtype = resp.request.resource_type
                if rtype not in ("fetch", "xhr"):
                    return
                entry = {"url": resp.url, "status": resp.status, "type": rtype}
                body = resp.text()
                entry["size"] = len(body)
                entry["preview"] = body[:1500]
                net_log.append(entry)
            except Exception:
                pass

        def on_ws(ws):
            rec = {"url": ws.url, "frames": []}
            ws_log.append(rec)
            ws.on("framereceived",
                  lambda payload: rec["frames"].append(str(payload)[:1500])
                  if len(rec["frames"]) < 10 else None)

        page.on("response", on_response)
        page.on("websocket", on_ws)

        result = {}
        for slug in CATEGORIES:
            try:
                result[slug] = scrape_category(page, slug)
            except Exception as e:
                print(f"خطا در {slug}: {e}", file=sys.stderr)
                result[slug] = {"title": CATEGORIES[slug], "items": [], "error": str(e)[:300]}
        browser.close()

    (DEBUG / "network.json").write_text(
        json.dumps({"xhr_fetch": net_log[:60], "websockets": ws_log[:5]},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    total = sum(len(c["items"]) for c in result.values())
    if total == 0:
        print("هیچ قیمتی استخراج نشد؛ prices.json تغییر نکرد (فایل‌های debug را ببینید).",
              file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc)
    (OUT / "prices.json").write_text(json.dumps({
        "source": BASE,
        "updated_at_utc": now.isoformat(timespec="seconds"),
        "updated_at_tehran": now.astimezone(TEHRAN).isoformat(timespec="seconds"),
        "categories": result,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {total} قیمت ذخیره شد.", file=sys.stderr)


if __name__ == "__main__":
    main()
