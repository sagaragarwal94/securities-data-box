"""Expense ratios from captn3m0/india-mutual-fund-ter-tracker (MIT)."""
import csv
import io
import re

from .amfi import http_get

URL = "https://raw.githubusercontent.com/captn3m0/india-mutual-fund-ter-tracker/main/data.csv"
OUT_COLS = [
    "nsdl_code", "scheme_name",
    "reg_ber", "reg_brokerage", "reg_txn_cost", "reg_levies", "reg_total",
    "dir_ber", "dir_brokerage", "dir_txn_cost", "dir_levies", "dir_total",
]


def fetch_rows():
    text = http_get(URL)
    reader = csv.reader(io.StringIO(text))
    next(reader)  # header: positional, see README of the source repo
    rows = {}
    for r in reader:
        if len(r) < 12 or not r[0].strip():
            continue
        row = dict(zip(OUT_COLS, [c.strip() for c in r[:12]]))
        # Source has dirty codes ("MOTO/O/O /FOD/..", trailing "?"): normalise, keep last
        row["nsdl_code"] = re.sub(r"[\s?]", "", row["nsdl_code"])
        rows[row["nsdl_code"]] = row
    yield from rows.values()
