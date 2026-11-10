"""One-time NAV history export from captn3m0/historical-mf-data's funds.db release."""
import csv
import gzip
import os
import sqlite3
import subprocess
import urllib.request

from .amfi import NAV_MAX, UA

RELEASE_URL = "https://github.com/captn3m0/historical-mf-data/releases/latest/download/funds.db.zst"


def download(workdir: str) -> str:
    """Download + decompress the release (about 383 MB -> 1.2 GB). Needs the zstd CLI."""
    os.makedirs(workdir, exist_ok=True)
    zst, db = os.path.join(workdir, "funds.db.zst"), os.path.join(workdir, "funds.db")
    if not os.path.exists(db):
        req = urllib.request.Request(RELEASE_URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req) as r, open(zst, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        subprocess.run(["zstd", "-d", "-q", "-f", zst, "-o", db], check=True)
    return db


def export(db_path: str, out_dir: str, live_codes=None):
    """Write nav_history_<year>.csv.gz (scheme_code,nav_date,nav). live_codes=None exports all."""
    os.makedirs(out_dir, exist_ok=True)
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    if live_codes is not None:
        con.execute("CREATE TEMP TABLE codes (c INTEGER PRIMARY KEY)")
        con.executemany("INSERT OR IGNORE INTO codes VALUES (?)", [(int(c),) for c in live_codes])
        sql = "SELECT n.scheme_code, n.date, n.nav FROM nav n JOIN codes c ON c.c = n.scheme_code"
    else:
        sql = "SELECT scheme_code, date, nav FROM nav"
    writers, files, counts, skipped = {}, {}, {}, 0
    for code, d, nav in con.execute(sql):
        if not nav or nav <= 0 or nav > NAV_MAX:
            skipped += 1
            continue
        y = d[:4]
        if y not in writers:
            files[y] = gzip.open(os.path.join(out_dir, f"nav_history_{y}.csv.gz"), "wt", newline="")
            writers[y] = csv.writer(files[y])
            writers[y].writerow(["scheme_code", "nav_date", "nav"])
        writers[y].writerow([code, d, nav])
        counts[y] = counts.get(y, 0) + 1
    for f in files.values():
        f.close()
    return counts, skipped
