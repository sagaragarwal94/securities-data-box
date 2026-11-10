"""One-command sync: fetch every source, then load it into Postgres.

The database connection is NEVER stored in this repo. It comes from the environment or a
git-ignored `.env` file on the machine that runs the sync. The SQL itself is not in this
repo either: MF_SQL_DIR points at the internal loader folder (load.sh, backup.sh, ...).
"""
import os
import re
import shutil
import subprocess
import sys
import time
from argparse import Namespace
from pathlib import Path

from . import cli, history


def load_env(path=".env", environ=None):
    """KEY=VALUE lines from `path`, overridden by real environment variables."""
    env = {}
    p = Path(path)
    if p.is_file():
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    env.update(os.environ if environ is None else environ)
    return env


def mask(text: str) -> str:
    """Hide passwords in anything we print."""
    return re.sub(r"(://[^:/@\s]+:)[^@\s]+@", r"\1***@", text)


def database_url(env):
    if env.get("DATABASE_URL"):
        return env["DATABASE_URL"]
    if env.get("PGHOST"):  # psql reads the remaining PG* variables itself
        return "postgresql://"
    return None


def _run(cmd, env, capture=False):
    r = subprocess.run(cmd, env=env, text=True, capture_output=capture)
    if r.returncode != 0:
        err = mask((r.stderr or "").strip()) if capture else ""
        sys.exit(f"command failed ({r.returncode}): {mask(' '.join(cmd[:1] + [c for c in cmd[1:] if '://' not in c]))}\n{err}")
    return (r.stdout or "").strip()


def run(a):
    env = load_env(a.env_file)
    url = database_url(env)
    if not url:
        sys.exit("No database configured. Set DATABASE_URL (or PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE) "
                 "in the environment or a .env file. See .env.example.")
    sql_dir = Path(env.get("MF_SQL_DIR", "")).expanduser()
    for f in ("load.sh", "load_history.sh", "backup.sh", "0012_mf_data_pipeline.up.sql"):
        if not (sql_dir / f).is_file():
            sys.exit(f"MF_SQL_DIR must point at the internal loader folder; missing {sql_dir / f}")
    if not shutil.which("psql"):
        sys.exit("psql not found on PATH")
    penv = dict(os.environ)
    penv.update({k: v for k, v in env.items() if k.startswith(("PG", "DATABASE", "MF_"))})
    penv["DATABASE_URL"] = url

    version = _run(["psql", url, "-Atc", "select version()"], penv, capture=True)
    print("connected:", version.split(",")[0])

    have_tbl = _run(["psql", url, "-Atc", "select to_regclass('public.mf_nav_history') is not null"],
                    penv, capture=True) == "t"
    if not have_tbl:
        if not a.apply_migration:
            sys.exit("Migration 0012 has not been applied. Re-run with --apply-migration to apply it.")
        print("applying migration 0012 ...")
        _run(["psql", url, "-v", "ON_ERROR_STOP=1", "-q", "-f", str(sql_dir / "0012_mf_data_pipeline.up.sql")], penv)

    nav_rows = int(_run(["psql", url, "-Atc", "select count(*) from mf_nav_history"], penv, capture=True))
    bootstrap = a.bootstrap or nav_rows == 0

    # 1) fetch
    out = a.out
    cli.cmd_nav(Namespace(out=out, days=0 if a.mode == "ter" else a.days, delay=0.3, min_rows=5000))
    cli.cmd_ter(Namespace(out=out, min_rows=1000))
    if not os.path.exists(os.path.join(out, "attrs.csv")):
        cli.cmd_attrs(Namespace(out=out))
    cli.cmd_match(Namespace(out=out))

    # 2) safety backup + history on first run
    if bootstrap:
        if not a.skip_backup:
            dest = Path("backups") / time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            _run([str(sql_dir / "backup.sh"), str(dest)], penv)
        if not a.no_history:
            if not shutil.which("zstd"):
                sys.exit("zstd CLI is required for the one-time history backfill (or pass --no-history)")
            cli.cmd_history(Namespace(out=out, db=None, workdir=a.workdir, all_schemes=False))
            _run([str(sql_dir / "load_history.sh"), os.path.join(out, "history")], penv)
            _run(["psql", url, "-qc", "ANALYZE mf_nav_history"], penv)

    # 3) load
    if a.dry_run:
        print("dry run: fetched data into", out, "- not loading")
        return
    penv["MF_DATA_DIR"] = os.path.abspath(out)
    _run([str(sql_dir / "load.sh"), "ter" if a.mode == "ter" else "full"], penv)
    print("sync complete")
