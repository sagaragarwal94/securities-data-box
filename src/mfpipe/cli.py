import argparse
import csv
import gzip
import os
import sys
import time
from datetime import date

from . import amfi, attrs, history, match, ter

SNAP_COLS = ["scheme_code", "scheme_name", "plan", "option", "isin_growth", "isin_reinv", "nav",
             "nav_date", "amc_name", "scheme_type", "category"]


def _write(path, cols, rows, gz=False):
    opener = gzip.open if gz else open
    n = 0
    with opener(path, "wt", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
            n += 1
    print(f"wrote {path}: {n} rows")
    return n


def _read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cmd_nav(a):
    os.makedirs(a.out, exist_ok=True)
    snap = list(amfi.parse(amfi.http_get(amfi.NAV_ALL_URL)))
    if len(snap) < a.min_rows:
        sys.exit(f"NAVAll returned only {len(snap)} rows (< {a.min_rows}); refusing to publish")
    _write(os.path.join(a.out, "scheme_snapshot.csv"), SNAP_COLS, snap)

    seen, days_ok = {}, 0
    for r in snap:
        seen[(r["scheme_code"], r["nav_date"])] = r["nav"]
    for d in amfi.daterange(a.days):
        text = amfi.fetch_day(d)
        time.sleep(a.delay)
        if text is None:
            continue
        days_ok += 1
        for r in amfi.parse(text):
            seen[(r["scheme_code"], r["nav_date"])] = r["nav"]
    print(f"days with data: {days_ok}/{a.days + 1}")
    rows = ({"scheme_code": c, "nav_date": d, "nav": n} for (c, d), n in sorted(seen.items()))
    _write(os.path.join(a.out, "nav_delta.csv.gz"), ["scheme_code", "nav_date", "nav"], rows, gz=True)


def cmd_ter(a):
    os.makedirs(a.out, exist_ok=True)
    rows = list(ter.fetch_rows())
    if len(rows) < a.min_rows:
        sys.exit(f"TER source returned {len(rows)} rows (< {a.min_rows}); refusing to publish")
    _write(os.path.join(a.out, "ter.csv"), ter.OUT_COLS, rows)


def cmd_attrs(a):
    os.makedirs(a.out, exist_ok=True)
    _write(os.path.join(a.out, "attrs.csv"), attrs.OUT_COLS, attrs.fetch_rows())


def cmd_match(a):
    ter_rows = _read(os.path.join(a.out, "ter.csv"))
    snap = _read(os.path.join(a.out, "scheme_snapshot.csv"))
    cands = match.candidates(ter_rows, snap)
    _write(os.path.join(a.out, "nsdl_map_candidates.csv"),
           ["nsdl_code", "ter_name", "scheme_code", "amfi_name", "plan", "match_type", "score"], cands)
    from collections import Counter
    c = Counter()
    seen = set()
    for r in cands:
        if r["nsdl_code"] not in seen:
            seen.add(r["nsdl_code"])
            c[r["match_type"]] += 1
    print("TER rows by match type:", dict(c))


def cmd_history(a):
    db = a.db or history.download(a.workdir)
    live = None
    if not a.all_schemes:
        live = {r["scheme_code"] for r in _read(os.path.join(a.out, "scheme_snapshot.csv"))}
    counts, skipped = history.export(db, os.path.join(a.out, "history"), live)
    print("rows per year:", dict(sorted(counts.items())), "| dropped bad NAVs:", skipped)


def main(argv=None):
    p = argparse.ArgumentParser(prog="mfpipe")
    p.add_argument("--out", default="out")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("nav", help="latest snapshot + NAV delta for the last N days")
    s.add_argument("--days", type=int, default=7)
    s.add_argument("--delay", type=float, default=0.3)
    s.add_argument("--min-rows", type=int, default=5000)
    s.set_defaults(f=cmd_nav)
    s = sub.add_parser("ter", help="expense ratios")
    s.add_argument("--min-rows", type=int, default=1000)
    s.set_defaults(f=cmd_ter)
    sub.add_parser("attrs", help="seed attributes (AUM/launch date/min amount)").set_defaults(f=cmd_attrs)
    sub.add_parser("match", help="build NSDL->AMFI candidate map").set_defaults(f=cmd_match)
    s = sub.add_parser("history", help="one-time NAV history export from funds.db")
    s.add_argument("--db")
    s.add_argument("--workdir", default="work")
    s.add_argument("--all-schemes", action="store_true", help="include closed schemes (large)")
    s.set_defaults(f=cmd_history)
    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
