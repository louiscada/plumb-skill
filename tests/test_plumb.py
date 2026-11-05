"""Tests for plumb/scripts/plumb.py — standard library only.

Run from the repository root:
    python -m unittest discover -s tests -v

The expected grades below are deliberate: if a change moves them, the change
alters everyone's grade, so update the numbers on purpose and note it in
CHANGELOG.md.
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "plumb", "scripts", "plumb.py")

spec = importlib.util.spec_from_file_location("plumb", SCRIPT)
plumb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plumb)


def run(data, *args):
    """Run a CLI command; return (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            plumb.main(["--data", data] + list(args))
        except SystemExit as e:
            code = e.code or 0
    return code, out.getvalue(), err.getvalue()


def checkin(data, payload, *extra):
    return run(data, "checkin", "--json", json.dumps(payload), *extra)


class LedgerCase(unittest.TestCase):
    """Each test gets an empty ledger in a temporary folder."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.data = os.path.join(self.tmp, "plumb-data")
        code, _, err = run(self.data, "init")
        self.assertEqual(code, 0, err)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def ledger(self):
        with open(os.path.join(self.data, "ledger.json"), encoding="utf-8") as f:
            return json.load(f)

    def write(self, **parts):
        led = self.ledger()
        for k, v in parts.items():
            if k == "profile":
                led["profile"].update(v)
            else:
                led[k] = v
        with open(os.path.join(self.data, "ledger.json"), "w",
                  encoding="utf-8") as f:
            json.dump(led, f)

    def score(self):
        return plumb.score(plumb.load(self.data))


def saver_profile(case):
    """A careful saver: big cushion, half of income kept, small 0% debt."""
    case.write(
        profile={"name": "Ana", "currency": "PHP", "monthly_income": 50000,
                 "monthly_spending": 25000, "checkin_frequency": "biweekly"},
        assets=[{"name": "Savings", "type": "savings", "liquid": True},
                {"name": "Index fund", "type": "funds", "liquid": False,
                 "currency": "USD"}],
        debts=[{"name": "Family loan", "type": "family_friend", "rate": 0,
                "monthly_payment": 3000},
               {"name": "Card", "type": "credit_card", "monthly_payment": 0}],
        receivables=[{"name": "Friend", "likelihood": "unsure"}],
        goals=[{"name": "Millionaire", "target": 1000000,
                "bucket": "net_worth"},
               {"name": "Trip", "by": "2027"}],
    )
    code, _, err = checkin(case.data, {
        "date": "2026-11-05",
        "balances": {"assets": {"Savings": 160000, "Index fund": 1600},
                     "debts": {"Family loan": 60000, "Card": 8000},
                     "receivables": {"Friend": 8000}},
        "fx": {"USD": 60.0}, "income": 50000, "spending": 25000})
    case.assertEqual(code, 0, err)


class TestGrading(LedgerCase):

    def test_strong_saver_scores_an_a(self):
        saver_profile(self)
        s = self.score()
        self.assertEqual((s["grade"], s["score"]), ("A", 98))
        # 160k savings + $1,600 × 60 = 256k assets; 4k of an "unsure" 8k loan
        self.assertAlmostEqual(s["assets_total"], 256000)
        self.assertAlmostEqual(s["net_worth"], 256000 + 4000 - 68000)
        self.assertAlmostEqual(s["metrics"]["emergency_months"], 6.4)

    def test_struggling_case_scores_an_f(self):
        self.write(
            profile={"currency": "USD", "monthly_income": 2000,
                     "monthly_spending": 2300},
            assets=[{"name": "Checking", "type": "checking", "liquid": True}],
            debts=[{"name": "Card", "type": "credit_card", "rate": 24,
                    "monthly_payment": 900}])
        checkin(self.data, {"date": "2026-11-05",
                            "balances": {"assets": {"Checking": 400},
                                         "debts": {"Card": 9000}},
                            "income": 2000, "spending": 2300})
        s = self.score()
        self.assertEqual(s["grade"], "F")
        codes = {f["code"] for f in s["flags"]}
        self.assertTrue({"high_interest_debt", "overspending",
                         "low_emergency"} <= codes)

    def test_ownership_share_and_equity(self):
        self.write(
            profile={"currency": "PHP", "monthly_income": 80000,
                     "monthly_spending": 40000},
            assets=[{"name": "Lot", "type": "land", "share": 25,
                     "valuation": "estimate", "valued_on": "2026-10"},
                    {"name": "Condo", "type": "condo",
                     "valuation": "appraisal", "valued_on": "2026-10"}],
            debts=[{"name": "Home loan", "type": "mortgage", "rate": 7,
                    "monthly_payment": 20000, "secured_by": "Condo"}])
        checkin(self.data, {"date": "2026-11-05",
                            "balances": {"assets": {"Lot": 4000000,
                                                    "Condo": 3000000},
                                         "debts": {"Home loan": 3500000}},
                            "income": 80000, "spending": 40000})
        s = self.score()
        self.assertAlmostEqual(s["assets_total"], 1000000 + 3000000)
        self.assertIn("underwater", {f["code"] for f in s["flags"]})


class TestMomentum(LedgerCase):

    def setUp(self):
        super().setUp()
        saver_profile(self)

    def test_revaluation_and_fx_are_excluded(self):
        # Savings +10k (real progress); fund price +$100 (real progress);
        # the peso weakens 60 → 62 (FX, excluded).
        code, out, err = checkin(self.data, {
            "date": "2026-11-19",
            "balances": {"assets": {"Savings": 170000, "Index fund": 1700}},
            "fx": {"USD": 62.0}, "income": 25000, "spending": 12000})
        self.assertEqual(code, 0, err)
        h = self.score()["history"][-1]
        fx_effect = 1600 * (62 - 60)
        self.assertAlmostEqual(h["revaluation"], fx_effect)
        self.assertAlmostEqual(h["underlying"], 10000 + 100 * 62)
        self.assertAlmostEqual(h["change"], h["underlying"] + fx_effect)

    def test_foreign_holding_needs_a_rate(self):
        self.write(assets=self.ledger()["assets"] + [
            {"name": "Euro account", "type": "savings", "currency": "EUR"}])
        code, _, err = checkin(self.data, {
            "date": "2026-11-19",
            "balances": {"assets": {"Euro account": 500}}})
        self.assertEqual(code, 1)
        self.assertIn("No exchange rate for EUR", err)


class TestTypoGuard(LedgerCase):

    def setUp(self):
        super().setUp()
        saver_profile(self)

    def test_big_drop_needs_confirmation(self):
        payload = {"date": "2026-11-19",
                   "balances": {"assets": {"Savings": 16000}}}
        code, _, err = checkin(self.data, payload)
        self.assertEqual(code, 3)
        self.assertIn("Savings", err)
        self.assertEqual(len(self.ledger()["checkins"]), 1)  # not saved
        code, _, err = checkin(self.data, payload, "--confirm")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(self.ledger()["checkins"]), 2)

    def test_normal_moves_and_card_swings_pass(self):
        code, _, err = checkin(self.data, {
            "date": "2026-11-19",
            "balances": {"assets": {"Savings": 150000},
                         "debts": {"Card": 0}}})
        self.assertEqual(code, 0, err)

    def test_account_numbers_are_refused(self):
        code, _, err = checkin(self.data, {
            "date": "2026-11-19", "note": "card 4111 1111 1111 1111"})
        self.assertEqual(code, 1)
        self.assertIn("account/card/ID number", err)


class TestBackups(LedgerCase):

    def test_backup_before_each_change_and_restore(self):
        saver_profile(self)
        checkin(self.data, {"date": "2026-11-19",
                            "balances": {"assets": {"Savings": 165000}}})
        bdir = os.path.join(self.data, "backups")
        files = sorted(os.listdir(bdir))
        self.assertGreaterEqual(len(files), 2)
        self.assertEqual(len(self.ledger()["checkins"]), 2)
        code, _, err = run(self.data, "restore", "--file", files[-1])
        self.assertEqual(code, 0, err)
        self.assertEqual(len(self.ledger()["checkins"]), 1)

    def test_only_the_newest_backups_are_kept(self):
        saver_profile(self)
        for day in range(6, 6 + plumb.BACKUPS_KEPT + 3):
            checkin(self.data, {"date": f"2026-11-{day:02d}", "note": "x"})
        kept = os.listdir(os.path.join(self.data, "backups"))
        self.assertEqual(len(kept), plumb.BACKUPS_KEPT)


class TestGoalsAndWhatIf(LedgerCase):

    def setUp(self):
        super().setUp()
        saver_profile(self)

    def test_net_worth_goal_uses_savings_before_second_checkin(self):
        g = {x["name"]: x for x in self.score()["goals"]}
        mil = g["Millionaire"]
        self.assertEqual(mil["pace_basis"], "monthly savings")
        self.assertAlmostEqual(mil["pace"], 25000)
        months = -(-(1000000 - 192000) // 25000)
        self.assertEqual(mil["eta"], plumb.add_months("2026-11-05",
                                                      int(months)))
        self.assertEqual(g["Trip"]["status"], "no_target")

    def test_whatif_rent_lowers_cushion_and_saves_nothing(self):
        before = json.dumps(self.ledger(), sort_keys=True)
        code, out, err = run(self.data, "whatif", "--as-json", "--json",
                             json.dumps({"spending_change": 18000,
                                         "cash_change": -60000}))
        self.assertEqual(code, 0, err)
        result = json.loads(out[out.index("{"):])
        self.assertLess(result["whatif"]["metrics"]["emergency_months"],
                        result["now"]["metrics"]["emergency_months"])
        self.assertLess(result["whatif"]["score"], result["now"]["score"])
        self.assertEqual(before, json.dumps(self.ledger(), sort_keys=True))


    def test_liquid_savings_goal(self):
        led = self.ledger()
        led["goals"].append({"name": "Move-out fund", "target": 200000,
                             "bucket": "liquid"})
        self.write(goals=led["goals"])
        g = {x["name"]: x for x in self.score()["goals"]}["Move-out fund"]
        self.assertAlmostEqual(g["current"], 160000)
        self.assertEqual(g["pct"], 80)
        self.assertEqual(g["eta"], plumb.add_months("2026-11-05", 2))

    def test_whatif_purchase_adds_the_asset_with_the_loan(self):
        code, out, err = run(self.data, "whatif", "--as-json", "--json",
                             json.dumps({
                                 "cash_change": -100000,
                                 "new_assets": [{"name": "Condo", "type": "condo",
                                                 "balance": 1000000}],
                                 "new_debts": [{"name": "Loan", "balance": 900000,
                                                "monthly_payment": 8000,
                                                "rate": 7}]}))
        self.assertEqual(code, 0, err)
        now = self.score()["net_worth"]
        s = plumb.score(plumb.load(self.data))  # ledger unchanged
        self.assertEqual(s["net_worth"], now)
        self.assertIn("Net worth", out)
        # 1,000,000 asset − 900,000 loan − 100,000 cash = no net change
        line = [l for l in out.splitlines() if l.startswith("Net worth")][0]
        before, after = [x.strip() for x in line[len("Net worth"):].split("→")]
        self.assertEqual(before, after)


class TestReport(LedgerCase):

    def test_report_renders_and_escapes_user_text(self):
        saver_profile(self)
        self.write(profile={"name": "<script>alert(1)</script>"})
        out_file = os.path.join(self.tmp, "r.html")
        code, _, err = run(self.data, "report", "--out", out_file,
                           "--message", "Fine & dandy", "--step", "<b>x</b>")
        self.assertEqual(code, 0, err)
        with open(out_file, encoding="utf-8") as f:
            page = f.read()
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", page)
        self.assertIn("Income and spending", page)
        self.assertIn(f"v{plumb.VERSION}", page)


if __name__ == "__main__":
    unittest.main()
