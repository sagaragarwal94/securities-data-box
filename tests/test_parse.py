import unittest

from mfpipe import amfi, match

SAMPLE = """Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date

Open Ended Schemes ( Equity Scheme - Multi Cap Fund )


Aditya Birla Sun Life Mutual Fund
148921;Aditya Birla Sun Life Multi-Cap Fund-Direct Growth;Direct Plan;GROWTH;INF209KB1Y49;;22.83;06-Nov-2026
148919;Aditya Birla Sun Life Multi-Cap Fund-Regular-IDCW Payout;Regular Plan;IDCW;IINF209KB1Y31;NOTAPP;N.A.;06-Nov-2026
148918;Aditya Birla Sun Life Multi-Cap Fund-Regular Growth;Regular Plan;GROWTH;inf209kb1y23;;1,021.5;06-Nov-2026
"""


class AmfiParse(unittest.TestCase):
    def test_parse(self):
        rows = list(amfi.parse(SAMPLE))
        self.assertEqual([r["scheme_code"] for r in rows], ["148921", "148918"])  # N.A. NAV dropped
        self.assertEqual(rows[0]["amc_name"], "Aditya Birla Sun Life Mutual Fund")
        self.assertEqual(rows[0]["scheme_type"], "Open Ended")
        self.assertEqual(rows[0]["category"], "Equity Scheme - Multi Cap Fund")
        self.assertEqual(rows[1]["isin_growth"], "INF209KB1Y23")  # lowercase fixed
        self.assertEqual(rows[1]["nav"], 1021.5)
        self.assertEqual(rows[0]["nav_date"], "2026-11-06")

    def test_isin_repair(self):
        self.assertEqual(amfi.normalize_isin("IINF209KB1Y31"), "INF209KB1Y31")
        self.assertEqual(amfi.normalize_isin("NOTAPP"), "")


class Match(unittest.TestCase):
    def test_base_name(self):
        self.assertEqual(match.base_name("Aditya Birla Sun Life Multi-Cap Fund-Direct Growth"),
                         "Aditya Birla Sun Life Multi-Cap Fund")
        self.assertEqual(match.base_name("X Fund - Regular Plan - Monthly IDCW Payout"), "X Fund")
        self.assertEqual(match.base_name("UTI Dividend Yield Fund - Growth"), "UTI Dividend Yield Fund")

    def test_candidates(self):
        snap = [{"scheme_code": "1", "scheme_name": "ABC Flexi Cap Fund - Direct Plan - Growth", "plan": "Direct Plan"},
                {"scheme_code": "2", "scheme_name": "ABC Flexi Cap Fund - Regular Plan - Growth", "plan": "Regular Plan"}]
        ter = [{"nsdl_code": "N1", "scheme_name": "ABC Flexi Cap Fund"}, {"nsdl_code": "N2", "scheme_name": "Zzz"}]
        out = match.candidates(ter, snap)
        self.assertEqual({(r["scheme_code"], r["plan"], r["match_type"]) for r in out if r["nsdl_code"] == "N1"},
                         {("1", "direct", "exact"), ("2", "regular", "exact")})
        self.assertEqual([r["match_type"] for r in out if r["nsdl_code"] == "N2"], ["none"])


if __name__ == "__main__":
    unittest.main()
