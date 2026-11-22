import unittest

import pandas as pd

from src.metrics import (
    agreement_by_language,
    agreement_statistics,
    compare_raters,
    find_disagreements,
)


def _ratings(labels: list[str], language: str = "en") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "query_id": [f"q1-{language}"] * len(labels),
            "rank": list(range(1, len(labels) + 1)),
            "language": [language] * len(labels),
            "query": ["sample query"] * len(labels),
            "intent": ["informational"] * len(labels),
            "title": [f"Result {rank}" for rank in range(1, len(labels) + 1)],
            "label": labels,
        }
    )


class AgreementMetricsTests(unittest.TestCase):
    def test_perfect_agreement_has_full_percent_and_kappa(self) -> None:
        ratings = _ratings(["Highly Relevant", "Relevant", "Not Relevant"])

        paired = compare_raters(ratings, ratings)
        stats = agreement_statistics(paired)

        self.assertEqual(stats["n"], 3)
        self.assertEqual(stats["percent_agreement"], 100.0)
        self.assertEqual(stats["cohen_kappa"], 1.0)

    def test_partial_agreement_and_disagreement_rows(self) -> None:
        rater_a = _ratings(["Highly Relevant", "Highly Relevant", "Relevant", "Not Relevant"])
        rater_b = _ratings(["Highly Relevant", "Relevant", "Relevant", "Not Relevant"])

        paired = compare_raters(rater_a, rater_b)
        stats = agreement_statistics(paired)

        self.assertEqual(stats["percent_agreement"], 75.0)
        self.assertAlmostEqual(stats["cohen_kappa"], 7 / 11)
        self.assertEqual(len(find_disagreements(paired)), 1)

    def test_unjudgeable_pairs_are_excluded_from_scores_but_kept_as_disagreements(self) -> None:
        rater_a = _ratings(["Relevant", "Cannot judge / needs more info"])
        rater_b = _ratings(["Relevant", "Slightly Relevant"])

        paired = compare_raters(rater_a, rater_b)
        stats = agreement_statistics(paired)

        self.assertEqual(stats["n"], 1)
        self.assertEqual(stats["percent_agreement"], 100.0)
        self.assertEqual(stats["cohen_kappa"], None)
        self.assertEqual(len(find_disagreements(paired)), 1)

    def test_language_breakdown_uses_query_language(self) -> None:
        english_a = _ratings(["Relevant"], "en")
        hindi_a = _ratings(["Relevant"], "hi")
        english_b = _ratings(["Relevant"], "en")
        hindi_b = _ratings(["Not Relevant"], "hi")
        paired = compare_raters(
            pd.concat([english_a, hindi_a], ignore_index=True),
            pd.concat([english_b, hindi_b], ignore_index=True),
        )

        by_language = agreement_by_language(paired)

        self.assertEqual(by_language["en"]["percent_agreement"], 100.0)
        self.assertEqual(by_language["hi"]["percent_agreement"], 0.0)

    def test_latest_submission_is_used_for_each_rater_and_result(self) -> None:
        first = _ratings(["Not Relevant"])
        first["rated_at"] = ["2026-01-01T00:00:00+00:00"]
        second = _ratings(["Relevant"])
        second["rated_at"] = ["2026-01-02T00:00:00+00:00"]
        rater_a = pd.concat([first, second], ignore_index=True)
        rater_b = _ratings(["Relevant"])

        stats = agreement_statistics(compare_raters(rater_a, rater_b))

        self.assertEqual(stats["percent_agreement"], 100.0)


if __name__ == "__main__":
    unittest.main()
