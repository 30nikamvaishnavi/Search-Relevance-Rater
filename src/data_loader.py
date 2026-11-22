"""CSV loading and persistence helpers for Search-Relevance-Rater."""

from pathlib import Path

import pandas as pd


QUERY_COLUMNS = ("query_id", "language", "query", "intent")
RESULT_COLUMNS = ("query_id", "rank", "title", "url", "snippet")
RATING_COLUMNS = (
    "rater_name",
    "query_id",
    "language",
    "query",
    "intent",
    "rank",
    "title",
    "url",
    "label",
    "notes",
    "rated_at",
)


def _validate_columns(frame: pd.DataFrame, required: tuple[str, ...], source: str) -> pd.DataFrame:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{source} is missing required columns: {', '.join(missing)}")
    return frame


def load_queries(path: str | Path) -> pd.DataFrame:
    """Load and validate query records."""
    return _validate_columns(pd.read_csv(path), QUERY_COLUMNS, str(path))


def load_results(path: str | Path) -> pd.DataFrame:
    """Load and validate search result records."""
    return _validate_columns(pd.read_csv(path), RESULT_COLUMNS, str(path))


def validate_ratings(frame: pd.DataFrame, source: str = "Ratings file") -> pd.DataFrame:
    """Validate a ratings table while allowing additional future columns."""
    return _validate_columns(frame, RATING_COLUMNS, source)


def append_ratings(rows: list[dict], path: str | Path) -> None:
    """Append submitted ratings without discarding earlier submissions."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    new_rows = validate_ratings(pd.DataFrame(rows), "New ratings")
    if destination.exists():
        existing = validate_ratings(pd.read_csv(destination), str(destination))
        new_rows = pd.concat([existing, new_rows], ignore_index=True)
    new_rows.to_csv(destination, index=False)


def load_all_ratings(directory: str | Path) -> pd.DataFrame:
    """Load all rater CSVs in a directory, returning an empty schema if none exist."""
    paths = sorted(Path(directory).glob("rater_*.csv"))
    if not paths:
        return pd.DataFrame(columns=RATING_COLUMNS)
    frames = [validate_ratings(pd.read_csv(path), str(path)) for path in paths]
    return pd.concat(frames, ignore_index=True)
