"""Link NSDL-keyed TER rows to AMFI scheme codes by scheme name.

TER is per scheme (Regular + Direct); AMFI codes are per plan/option. We derive a
scheme-level base name from each AMFI NAV name and match on a normalised key.
exact -> safe to auto-load; fuzzy -> needs human review; none -> unmatched.
"""
import difflib
import re
from collections import defaultdict

OPTION_WORDS = {
    "direct", "regular", "plan", "growth", "idcw", "dividend", "payout", "reinvestment",
    "reinvest", "of", "option", "bonus", "daily", "weekly", "fortnightly", "monthly",
    "quarterly", "half", "yearly", "annual", "cumulative", "reinv", "and", "div", "inst",
}
DROP = re.compile(r"\b(mutual fund|fund|scheme|plan|option)\b")


def base_name(name: str) -> str:
    segs = re.split(r"\s*-\s*", name.strip())
    while len(segs) > 1 and all(w.lower().strip("()") in OPTION_WORDS for w in segs[-1].split()):
        segs.pop()
    words = "-".join(segs).split()
    while words and words[-1].lower().strip("()-") in OPTION_WORDS:
        words.pop()
    return " ".join(words)


def key(name: str) -> str:
    s = name.lower().replace("&", "and")
    s = DROP.sub(" ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def candidates(ter_rows, snapshot_rows, fuzzy_cutoff=0.93):
    by_key = defaultdict(list)
    for r in snapshot_rows:
        by_key[key(base_name(r["scheme_name"]))].append(r)
    keys = list(by_key)
    out = []
    for t in ter_rows:
        k = key(t["scheme_name"])
        mtype, score, rows = "none", 0.0, []
        if k in by_key:
            mtype, score, rows = "exact", 1.0, by_key[k]
        else:
            best = difflib.get_close_matches(k, keys, 1, fuzzy_cutoff)
            if best:
                mtype = "fuzzy"
                score = round(difflib.SequenceMatcher(None, k, best[0]).ratio(), 4)
                rows = by_key[best[0]]
        if not rows:
            out.append({"nsdl_code": t["nsdl_code"], "ter_name": t["scheme_name"], "scheme_code": "",
                        "amfi_name": "", "plan": "", "match_type": "none", "score": 0})
        for r in rows:
            plan = "direct" if "direct" in (r["plan"] + " " + r["scheme_name"]).lower() else "regular"
            out.append({"nsdl_code": t["nsdl_code"], "ter_name": t["scheme_name"],
                        "scheme_code": r["scheme_code"], "amfi_name": r["scheme_name"],
                        "plan": plan, "match_type": mtype, "score": score})
    return out
