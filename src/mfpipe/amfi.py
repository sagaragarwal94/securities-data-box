"""AMFI NAV file parsing and fetching.

AMFI's daily file is a ';'-separated text file with section lines in between:
  * a scheme-category heading  e.g. "Open Ended Schemes ( Equity Scheme - Multi Cap Fund )"
  * an AMC heading             e.g. "Aditya Birla Sun Life Mutual Fund"
Rows are parsed by header name because the column layout changed over the years.
"""
import re
import time
import urllib.request
from datetime import date, timedelta

UA = "mf-pipeline/0.1 (+personal data pipeline)"
NAV_ALL_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
HISTORY_URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?frmdt={d}"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
NAV_MAX = 100000  # values above this in the public data are errors

HEADING = re.compile(r"^(?P<type>.+?Schemes?)\s*\(\s*(?P<cat>.*?)\s*\)\s*$", re.I)
ISIN_OK = re.compile(r"^INF[0-9A-Z]{9}$")


def fmt_date(d: date) -> str:
    return f"{d.day:02d}-{MONTHS[d.month - 1]}-{d.year}"


def parse_date(s: str):
    try:
        dd, mon, yy = s.strip().split("-")
        return date(int(yy), MONTHS.index(mon.title()) + 1, int(dd)).isoformat()
    except (ValueError, IndexError):
        return None


def normalize_isin(raw: str) -> str:
    """Repair the common AMFI ISIN typos (same rules as historical-mf-data)."""
    s = (raw or "").strip().upper()
    if not s or s in ("-", "NA", "NOTAPP"):
        return ""
    if s.startswith("IIN"):
        s = s[1:]
    if s.startswith("NF"):
        s = "I" + s
    if s.startswith("IN9"):
        s = "INF9" + s[3:]
    return s if ISIN_OK.match(s) else ""


def parse_nav(raw: str):
    try:
        v = float(raw.strip().replace(",", "").replace("`", ""))
    except ValueError:
        return None
    return v if 0 < v <= NAV_MAX else None


def parse(text: str):
    """Yield one dict per scheme row."""
    cols = None
    scheme_type = category = amc = ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if ";" not in line:
            m = HEADING.match(line)
            if m:
                scheme_type = re.sub(r"\s*Schemes?$", "", m["type"], flags=re.I).strip()
                category = m["cat"]
            else:
                amc = line
            continue
        parts = [p.strip() for p in line.split(";")]
        if parts[0].lower() == "scheme code":
            cols = {name.lower(): i for i, name in enumerate(parts)}
            continue
        if cols is None or len(parts) < len(cols):
            continue

        def get(*names):
            for n in names:
                for key, i in cols.items():
                    if key.startswith(n):
                        return parts[i]
            return ""

        code = parts[cols["scheme code"]]
        nav = parse_nav(get("net asset value"))
        nav_date = parse_date(get("date"))
        if not code.isdigit() or nav is None or nav_date is None:
            continue
        yield {
            "scheme_code": code,
            "scheme_name": get("nav name", "scheme name"),
            "plan": get("plan"),
            "option": get("option"),
            "isin_growth": normalize_isin(get("isin div payout")),
            "isin_reinv": normalize_isin(get("isin div reinvestment")),
            "nav": nav,
            "nav_date": nav_date,
            "amc_name": amc,
            "scheme_type": scheme_type,
            "category": category,
        }


def http_get(url: str, retries: int = 3, timeout: int = 90):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001 - retry on any network error
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"GET failed for {url}: {last}")


def fetch_day(d: date):
    """Return the AMFI report for a day, or None if there is none (holiday etc.)."""
    text = http_get(HISTORY_URL.format(d=fmt_date(d)))
    if "<html" in text.lower() or "scheme code" not in text.lower():
        return None
    return text


def daterange(days: int, end: date = None):
    end = end or date.today()
    for i in range(days, -1, -1):
        yield end - timedelta(days=i)
