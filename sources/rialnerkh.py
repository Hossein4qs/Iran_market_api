"""منبع: rialnerkh.com  (وردپرس؛ همه‌ی نرخ‌ها در صفحه‌ی اصلی و هر ردیف یک لینک /rate/<slug>/ است)

هر دسته (currency/gold/crypto/official) از همان یک صفحه خوانده می‌شود.
نماد (بخش دوم tag) از slug لینک ردیف و جدول SLUGS ساخته می‌شود و عمداً با نمادهای
sources/tags.py (مثلاً eur_hawala, sekkeh_bahar, usd_xau) یکی است.
"""
import re
import sys

from bs4 import BeautifulSoup

from .common import FA_RE, ascii_digits, cell_text

ID = "rialnerkh"
NAME = "ریال نرخ"
BASE = "https://www.rialnerkh.com"
_PAGE = "/?lang=fa"
PAGES = {
    "currency": ("ارز و حواله", _PAGE),
    "gold": ("طلا و سکه", _PAGE),
    "crypto": ("ارز دیجیتال", _PAGE),
    "official": ("نرخ‌های رسمی", _PAGE),
}
MIN_ITEMS = {"currency": 10, "gold": 4, "crypto": 3, "official": 2}

# slug ردیف -> (دسته، نماد)  ← فقط مواردی که از قاعده‌ی عمومی پیروی نمی‌کنند
SLUGS = {
    # ارز نقدی با نام متفاوت
    "aed_note": ("currency", "aed"),
    # حواله
    "aed": ("currency", "aed_hawala"),
    "usd_sherkat": ("currency", "usd_hawala_sherkat"),
    "usd_shakhs": ("currency", "usd_hawala_shakhs"),
    "hav_cad_cheque": ("currency", "cad_hawala"),
    # طلا و سکه
    "xau": ("gold", "xau_toman"),
    "usd_xau": ("gold", "usd_xau"),
    "18ayar": ("gold", "18ayar"),
    "sekkeh": ("gold", "sekkeh"),
    "bahar": ("gold", "sekkeh_bahar"),
    "nim": ("gold", "nim"),
    "rob": ("gold", "rob"),
    "gerami": ("gold", "gerami"),
    "abshodeh": ("gold", "abshodeh"),
}
CRYPTO = {"btc", "eth", "xrp", "bch", "eos", "bnb", "usdt", "ltc", "trx", "ada", "doge", "sol"}
GOLD_BUBBLE = {"sekkeh": "sekkeh", "bahar": "sekkeh_bahar", "nim": "nim", "rob": "rob",
               "gerami": "gerami", "18ayar": "18ayar"}     # bub_<slug> -> نماد آیتم طلا

TIME_RE = re.compile(r"(?<!\d)\d{1,2}:\d{2}(?!\d)")
SIGNED_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def classify(slug):
    """slug -> (دسته، نماد) یا ('bubble', نماد-طلا) یا None"""
    if slug in SLUGS:
        return SLUGS[slug]
    m = re.fullmatch(r"bub_(\w+)", slug)
    if m:
        return ("bubble", GOLD_BUBBLE[m.group(1)]) if m.group(1) in GOLD_BUBBLE else None
    m = re.fullmatch(r"mex_([a-z]{3})_(buy|sell)", slug)
    if m:
        return ("official", f"{m.group(1)}_{m.group(2)}")
    m = re.fullmatch(r"([a-z]{3})_hav", slug)
    if m:
        return ("currency", f"{m.group(1)}_hawala")
    if slug in CRYPTO:
        return ("crypto", slug)
    if re.fullmatch(r"[a-z]{3}", slug):
        return ("currency", slug)
    return None


def parse_row_text(text, slug):
    """متن یک ردیف -> (نام، قیمت، تغییر مطلق با علامت، ساعت) یا None.

    متن به شکل  «<آیکن> <نام> <CODE> <قیمت> ▲|▼ <تغییر> <ساعت>»  است و CODE همان slug بزرگ است.
    """
    t = ascii_digits(text)
    m = re.search(rf"(?<![A-Za-z0-9_]){re.escape(slug.upper())}(?![A-Za-z0-9_])", t)
    if not m:
        return None
    head, rest = t[:m.start()], t[m.end():]
    toks = head.split()
    i = next((k for k, w in enumerate(toks) if FA_RE.search(w)), None)   # آیکن‌های لاتین/نمادی حذف شوند
    name = " ".join(toks[i:]) if i is not None else " ".join(toks)
    tm = TIME_RE.search(rest)
    clock = tm.group() if tm else None
    if tm:
        rest = rest[:tm.start()] + " " + rest[tm.end():]
    nums = SIGNED_NUM.findall(rest)
    if not nums or not name:
        return None
    price = float(nums[0].replace(",", ""))
    if price <= 0 or nums[0].startswith("-"):
        return None
    change = None
    if len(nums) > 1:
        change = float(nums[1].replace(",", ""))
        if "▼" in rest or nums[1].startswith("-"):
            change = -abs(change)
        elif "▲" not in rest and change == 0:
            change = 0
        elif "▲" not in rest:
            change = None          # عدد بدون جهت معلوم
    fix = lambda v: None if v is None else (int(v) if float(v).is_integer() else v)
    return name, fix(price), fix(change), clock


def collect_rows(html):
    """-> {slug: (نام، قیمت، تغییر، ساعت)}؛ اگر یک slug چند بار آمده باشد، ردیفِ دارای ساعت ترجیح دارد."""
    soup = BeautifulSoup(html, "lxml")
    rows = {}
    for a in soup.find_all("a", href=re.compile(r"/rate/[^/?#]+")):
        slug = re.search(r"/rate/([^/?#]+)", a["href"]).group(1).lower()
        try:
            parsed = parse_row_text(cell_text(a), slug)
        except Exception as e:
            print(f"  ! ردیف {slug} خوانده نشد: {e}", file=sys.stderr)
            continue
        if parsed and (slug not in rows or (rows[slug][3] is None and parsed[3])):
            rows[slug] = parsed
    m = re.search(r"آخرین\s*داده\s*دریافت.شده\s*([\d\-/: ]{10,25})", ascii_digits(soup.get_text(" ")))
    return rows, (m.group(1).strip() if m else None)


def pct(price, change):
    """درصد تغییر (محاسبه‌شده): تغییر / قیمت قبلی."""
    if change is None:
        return None
    prev = price - change
    return round(change / prev * 100, 2) if prev else None


def parse_page(category, html):
    rows, site_updated = collect_rows(html)
    bubbles = {}
    items = []
    for slug, (name, price, change, clock) in rows.items():
        kind = classify(slug)
        if not kind:
            print(f"  ! نرخ ناشناخته نادیده گرفته شد: {slug} ({name})", file=sys.stderr)
            continue
        cat, symbol = kind
        if cat == "bubble":
            bubbles[symbol] = price
            continue
        if cat != category:
            continue
        item = {"symbol": symbol, "name": name, "price": price,
                "unit": "usd" if symbol == "usd_xau" else "toman",
                "change": change, "change_percent": pct(price, change), "time": clock}
        if category == "currency":
            item["quantity"] = 1                 # قیمت همیشه برای یک واحد است
        items.append(item)
    if category == "gold":                  # حباب هر سکه داخل خود آیتم (مثل الان‌چند)
        for it in items:
            it["bubble"] = bubbles.get(it["symbol"])
    return items, site_updated
