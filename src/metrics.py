"""Agreement metrics for relevance ratings."""

import math

import pandas as pd
from sklearn.metrics import cohen_kappa_score


RATING_LABELS = (
    "Highly Relevant",
    "Relevant",
    "Slightly Relevant",
    "Not Relevant",
)
UNJUDGEABLE_LABEL = "Cannot judge / needs more info"
COMPARISON_KEYS = ("query_id", "rank")


def _latest_per_result(ratings: pd.DataFrame) -> pd.DataFrame:
    if "rated_at" in ratings.columns:
        ratings = ratings.sort_values("rated_at", kind="stable")
    return ratings.drop_duplicates(list(COMPARISON_KEYS), keep="last")


def compare_raters(rater_a: pd.DataFrame, rater_b: pd.DataFrame) -> pd.DataFrame:
    """Join two ratings by query and result rank, keeping each rater's latest submission."""
    left = _latest_per_result(rater_a).copy()
    right = _latest_per_result(rater_b).copy()
    left["rank"] = left["rank"].astype(str)
    right["rank"] = right["rank"].astype(str)
    return left.merge(
        right,
        on=list(COMPARISON_KEYS),
        how="inner",
        suffixes=("_a", "_b"),
        validate="one_to_one",
    )


def agreement_statistics(paired: pd.DataFrame) -> dict[str, float | int | None]:
    """Calculate exact agreement and unweighted Cohen's kappa on judgeable pairs."""
    judgeable = paired[
        paired["label_a"].isin(RATING_LABELS) & paired["label_b"].isin(RATING_LABELS)
    ]
    count = len(judgeable)
    if not count:
        return {"n": 0, "percent_agreement": None, "cohen_kappa": None}

    labels_a = judgeable["label_a"]
    labels_b = judgeable["label_b"]
    percent = float((labels_a == labels_b).mean() * 100)
    if labels_a.nunique() == labels_b.nunique() == 1 and labels_a.iloc[0] == labels_b.iloc[0]:
        kappa = None
    else:
        kappa = float(cohen_kappa_score(labels_a, labels_b, labels=list(RATING_LABELS)))
        if math.isnan(kappa):
            kappa = None
    return {"n": count, "percent_agreement": percent, "cohen_kappa": kappa}


def agreement_by_language(paired: pd.DataFrame) -> dict[str, dict[str, float | int | None]]:
    """Calculate agreement statistics separately for each language."""
    if "language_a" not in paired.columns:
        return {}
    return {
        str(language): agreement_statistics(group)
        for language, group in paired.groupby("language_a", dropna=False)
    }


def find_disagreements(paired: pd.DataFrame) -> pd.DataFrame:
    """Return all paired results whose labels differ, including unjudgeable ratings."""
    return paired[paired["label_a"] != paired["label_b"]].copy()
