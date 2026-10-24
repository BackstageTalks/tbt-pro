import unittest
from unittest.mock import patch
from .test_research import match
from ..pre_match import build_features
from .. import quarterly


class SurfaceShrinkageTests(unittest.TestCase):
    def test_surface_rating_only_after_embargo(self):
        rows=[match("2024-01-01",1,"A","B","Hard"),
              match("2024-01-15",1,"A","B","Clay"),
              match("2024-01-23",1,"A","B","Hard"),
              match("2024-02-15",1,"A","B","Hard")]
        generated,excluded=build_features(rows,"ATP")
        self.assertFalse(excluded)
        # Prior match on 2024-01-01 is still unreleased on 2024-01-15.
        self.assertIsNone(generated[1]["surface_elo_shrunk_diff"])
        self.assertIsNotNone(generated[2]["surface_elo_shrunk_diff"])
        self.assertIsNotNone(generated[3]["shrunk_surface_serve_diff"])

    def test_point_weighted_opponent_posteriors_are_history_only(self):
        rows=[match("2024-01-01",1,"A","B","Hard"),
              match("2024-02-05",1,"B","A","Hard"),
              match("2024-03-10",1,"A","B","Hard")]
        out,_=build_features(rows,"ATP")
        # The first completed match has no previous opponent quality context.
        self.assertIsNone(out[1]["adj_serve_points20_diff"])
        # By the third tournament, February has matured and opponent's
        # January pre-match serve/return context can safely be used.
        self.assertIsNotNone(out[2]["bayes_serve20_diff"])
        self.assertIsNotNone(out[2]["bayes_return20_diff"])
        self.assertIsNotNone(out[2]["adj_serve_points20_diff"])
        self.assertIsNotNone(out[2]["adj_return_points20_diff"])

    def test_new_surface_shrinks_to_global_rating(self):
        rows=[match("2024-01-01",1,"A","B","Hard"),
              match("2024-02-05",1,"A","B","Clay")]
        generated,_=build_features(rows,"ATP")
        self.assertAlmostEqual(generated[1]["elo_diff"],generated[1]["surface_elo_shrunk_diff"],places=6)
        self.assertAlmostEqual(generated[1]["serve20_diff"],generated[1]["shrunk_surface_serve_diff"],places=6)

    def test_older_than_2024_training_refused(self):
        with self.assertRaisesRegex(ValueError,"2024"):
            quarterly.study([{"date":"2023-12-31","match_id":"invalid"}])

    def test_separate_calibration_and_equal_cohort(self):
        # One representative quarter; deliberately nonpredictive synthetic rows.
        all_rows=[]
        for year in (2024,2025):
            for month in range(1,13 if year==2024 else 4):
                for day in range(1,26):
                    for j in range(4):
                        row={"date":f"{year}-{month:02d}-{day:02d}",
                            "match_id":f"{year}/{month}/{day}/{j}",
                            "y":int((day+j)%2==0),"surface":"hard"}
                        for keyset in quarterly.ARMS.values():
                            for key in keyset:
                                row[key]=((day*7+j)%11-5)/11.0
                        all_rows.append(row)
        with patch.object(quarterly,"QUARTERS",("2025-01-01",)):
            r=quarterly.study(all_rows)
        self.assertEqual(r["evaluated_folds"],1)
        fold=r["folds"][0]
        self.assertEqual(fold["test_start"],"2025-01-01")
        self.assertEqual(fold["calibration_start"],"2024-11-02")
        self.assertEqual(fold["common_cohort_n"],fold["n_test_available"])
        self.assertFalse(r["production_mutated"])
        self.assertEqual(r["provider_requests"],0)


if __name__=="__main__":
    unittest.main()
