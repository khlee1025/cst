from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.results import analyze_run_dir, read_s11_file


class ResultAnalysisTests(unittest.TestCase):
    def test_reads_common_csv_and_analyzes_s11_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "s11.csv").write_text(
                "freq_ghz,s11_db\n"
                "2.30,-4\n"
                "2.40,-12\n"
                "2.45,-18\n"
                "2.50,-11\n"
                "2.60,-5\n",
                encoding="utf-8",
            )

            metrics = analyze_run_dir(run_dir, target_frequency_ghz=2.45, s11_goal_db=-10.0)

        self.assertEqual(metrics["result_status"], "analyzed")
        self.assertEqual(metrics["s11_min_db"], -18.0)
        self.assertEqual(metrics["s11_min_freq_ghz"], 2.45)
        self.assertEqual(metrics["s11_at_target_db"], -18.0)
        self.assertAlmostEqual(metrics["bandwidth_10db_low_ghz"], 2.375)
        self.assertAlmostEqual(metrics["bandwidth_10db_high_ghz"], 2.516666667)
        self.assertTrue(metrics["meets_s11_goal"])

    def test_converts_hz_to_ghz(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result_s11.txt"
            path.write_text("2300000000 -4\n2450000000 -20\n", encoding="utf-8")

            points = read_s11_file(path)

        self.assertAlmostEqual(points[0].frequency_ghz, 2.3)
        self.assertAlmostEqual(points[1].frequency_ghz, 2.45)

    def test_analyzes_s21_shielding_effectiveness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "s21.csv").write_text(
                "freq_ghz,s21_db\n"
                "8,-20\n"
                "10,-35\n"
                "12,-30\n",
                encoding="utf-8",
            )

            metrics = analyze_run_dir(run_dir, target_frequency_ghz=10.0, s11_goal_db=-10.0)

        self.assertEqual(metrics["result_status"], "analyzed")
        self.assertEqual(metrics["s21_min_db"], -35.0)
        self.assertEqual(metrics["s21_at_target_db"], -35.0)
        self.assertEqual(metrics["shielding_effectiveness_at_target_db"], 35.0)
        self.assertEqual(metrics["score"], -35.0)


if __name__ == "__main__":
    unittest.main()
