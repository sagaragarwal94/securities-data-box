"""One-time/seed attributes from InertExpert2911/Mutual-Fund-Data (MIT).

Its snapshot can be stale (NAV dates stopped in Aug 2026, AUM is a single old
quarter, Closure_Date is unreliable) so only fields that are stable are kept.
"""
import csv
import io
import re

from .amfi import http_get

URL = "https://raw.githubusercontent.com/InertExpert2911/Mutual-Fund-Data/main/mutual_fund_data.csv"
OUT_COLS = ["scheme_code", "scheme_name", "launch_date", "min_amount", "aum_cr", "aaum_quarter"]


def _clean(v):
    v = (v or "").strip()
    return "" if v.lower() in ("nan", "-", "none") else v


def _amount(v):
    """Source is free text ("Rs 5000 and in multiples of Re 1", "5000/-", "Rs"). Keep the first number."""
    m = re.search(r"\d[\d,]*", v or "")
    return m.group(0).replace(",", "") if m else ""


def fetch_rows():
    for r in csv.DictReader(io.StringIO(http_get(URL))):
        yield {
            "scheme_code": _clean(r.get("Scheme_Code")),
            "scheme_name": _clean(r.get("Scheme_Name")),
            "launch_date": _clean(r.get("Launch_Date")),
            "min_amount": _amount(_clean(r.get("Scheme_Min_Amt"))),
            "aum_cr": _clean(r.get("Average_AUM_Cr")),
            "aaum_quarter": _clean(r.get("AAUM_Quarter")),
        }
