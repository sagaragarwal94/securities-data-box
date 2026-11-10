# securities-data-box

Data fetchers for Indian securities masters (mutual funds first, stocks later).
Fetches Indian mutual fund data and publishes it as CSV artifacts on a rolling GitHub
release (`data-latest`). **Contains no SQL**: loading into Postgres is done by a separate,
internal loader that downloads these artifacts.

| Artifact | Source | Cadence |
|---|---|---|
| `scheme_snapshot.csv` | AMFI `NAVAll.txt` (live schemes, AMC, category, ISINs, latest NAV) | daily |
| `nav_delta.csv.gz` | AMFI per-day NAV reports, last 7 days (90 on Sundays) | daily |
| `ter.csv` | captn3m0/india-mutual-fund-ter-tracker | hourly |
| `nsdl_map_candidates.csv` | NSDL code -> AMFI code by name (`exact` / `fuzzy` / `none`) | with TER |
| `attrs.csv` | InertExpert2911/Mutual-Fund-Data (launch date, min amount, AUM seed) | daily, but stale upstream |

One-time NAV history backfill (not run in CI, needs ~1.5 GB disk and the `zstd` CLI):

    PYTHONPATH=src python -m mfpipe --out out nav --days 0      # creates scheme_snapshot.csv
    PYTHONPATH=src python -m mfpipe --out out history           # live schemes only
    # add --all-schemes to include ~28k closed schemes (large)

Local run / tests:

    PYTHONPATH=src python -m unittest discover -s tests
    PYTHONPATH=src python -m mfpipe --out out nav --days 3

Upstream licences: AMFI data is public; both GitHub sources are MIT.
