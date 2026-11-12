from pathlib import Path
import sys
import unittest
from dataclasses import replace
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cost_model import Settings, COMPONENTS
from result_reporting import development_percent, deduction_report


def example():
    components = {key: np.array([0.]) for key in COMPONENTS}
    components["courtage"][:] = 1000
    return dict(initial_amount=100000., settings=Settings(account="AF", af_sale_view=False),
                components=components, af_sale_parts={key: np.array([0.]) for key in COMPONENTS},
                tax_af=np.array([5700.]), tax_isk=np.array([0.]),
                history={"gross": np.array([[120000.]]), "after_costs": np.array([[119000.]]),
                         "af": np.array([[113300.]]), "isk": np.array([[119000.]]),
                         "af_tax_if_sold": np.array([[5700.]])})


class PercentageReportingTests(unittest.TestCase):
    def test_return_uses_full_initial_amount_and_keeps_initial_buy_cost(self):
        np.testing.assert_allclose(development_percent([99000, 113300], 100000), [-1, 13.3])
        with self.assertRaises(ValueError):
            development_percent([100], 0)

    def test_start_capital_percentages_reconcile_with_percentage_point_drag(self):
        report = deduction_report(example(), "AF")
        rows = {row["label"]: row for row in report["rows"]}
        self.assertAlmostEqual(rows["Courtage"]["percent"], 1)
        self.assertAlmostEqual(rows["Skatt · AF"]["percent"], 5.7)
        self.assertAlmostEqual(report["rows"][-1]["percent"], 6.7)
        self.assertAlmostEqual(report["gross_return"], 20)
        self.assertAlmostEqual(report["net_return"], 13.3)
        self.assertAlmostEqual(report["return_impact_pp"], -6.7)
        self.assertAlmostEqual(sum(row["percent"] for row in report["rows"][:-1]), report["rows"][-1]["percent"])

    def test_final_wealth_and_profit_denominators_are_distinct(self):
        result = example()
        gross = deduction_report(result, "AF", base="Slutvärdet före avdrag")
        profit = deduction_report(result, "AF", base="Vinsten före avdrag")
        self.assertAlmostEqual(gross["rows"][-1]["percent"], 6700/120000*100)
        self.assertAlmostEqual(profit["rows"][-1]["percent"], 33.5)
        self.assertEqual(profit["denominator"], 20000)

    def test_no_positive_profit_does_not_create_a_percentage_or_infinity(self):
        for gross in [100000, 90000]:
            result = example()
            result["history"]["gross"][:] = gross
            report = deduction_report(result, "AF", base="Vinsten före avdrag")
            self.assertIsNone(report["denominator"])
            self.assertTrue(all(row["percent"] is None for row in report["rows"]))
            self.assertTrue(all(np.isfinite(row["amount"]) for row in report["rows"]))

    def test_deductions_can_exceed_the_gross_profit(self):
        result = example()
        result["history"]["gross"][:] = 101000
        result["history"]["af"][:] = 99000
        report = deduction_report(result, "AF", base="Vinsten före avdrag")
        self.assertEqual(report["rows"][-1]["percent"], 200)
        self.assertAlmostEqual(report["net_return"], -1)

    def test_hypothetical_af_exit_adds_only_remaining_fees_and_total_tax_once(self):
        result = example()
        result["settings"] = replace(result["settings"], liquidate=False, af_sale_view=True)
        result["af_sale_parts"]["courtage"][:] = 100
        result["tax_af"][:] = 1000
        result["history"]["af_tax_if_sold"][:] = 5000
        result["history"]["af"][:] = 113900
        report = deduction_report(result, "AF")
        rows = {row["label"]: row for row in report["rows"]}
        self.assertAlmostEqual(rows["Courtage"]["amount"], 1100)
        self.assertAlmostEqual(rows["Skatt · AF"]["amount"], 5000)
        self.assertAlmostEqual(sum(row["amount"] for row in report["rows"][:-1]), 6100)
        self.assertAlmostEqual(report["rows"][-1]["percent"], 6.1)

    def test_disabled_tax_is_not_deducted_in_the_percentage_report(self):
        result = example()
        result["settings"] = replace(result["settings"], include_tax=False)
        result["history"]["af"][:] = 119000
        report = deduction_report(result, "AF")
        self.assertEqual(next(row for row in report["rows"] if row["label"] == "Skatt · AF")["percent"], 0)
        self.assertAlmostEqual(report["rows"][-1]["percent"], 1)

    def test_compounding_effects_and_selected_path_reconcile_including_credits(self):
        result = example()
        result["history"]["gross"] = np.array([[120000., 140000., 160000.]])
        result["history"]["after_costs"] = np.array([[118000., 137000., 155000.]])
        result["history"]["af"] = np.array([[119000., 132000., 150000.]])
        result["tax_af"] = np.array([-1000., 5000., 5000.])
        result["components"] = {key: np.zeros(3) for key in COMPONENTS}
        result["components"]["courtage"] = np.array([1000., 2000., 4000.])
        for path in range(3):
            report = deduction_report(result, "AF", path)
            self.assertAlmostEqual(sum(row["amount"] for row in report["rows"][:-1]), report["rows"][-1]["amount"])
        first = deduction_report(result, "AF", 0)
        self.assertEqual(next(row for row in first["rows"] if row["label"] == "Courtage")["amount"], 1000)
        self.assertEqual(next(row for row in first["rows"] if row["label"] == "Skatt · AF")["percent"], -1)
