"""Streamlit interface for rating search result relevance."""

import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from data_loader import (
    RATING_COLUMNS,
    append_ratings,
    load_all_ratings,
    load_queries,
    load_results,
    validate_ratings,
)
from metrics import (
    RATING_LABELS,
    UNJUDGEABLE_LABEL,
    agreement_by_language,
    agreement_statistics,
    compare_raters,
    find_disagreements,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIRECTORY = PROJECT_ROOT / "data"
RATINGS_DIRECTORY = PROJECT_ROOT / "ratings"
LABEL_OPTIONS = ("— Select a rating —", *RATING_LABELS, UNJUDGEABLE_LABEL)

st.set_page_config(page_title="Search-Relevance-Rater", page_icon="🔎", layout="wide")


def _load_sample_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        return (
            load_queries(DATA_DIRECTORY / "queries.csv"),
            load_results(DATA_DIRECTORY / "results.csv"),
        )
    except (FileNotFoundError, ValueError, pd.errors.ParserError) as error:
        st.error(f"Could not load the project data: {error}")
        st.stop()


def _rater_filename(name: str) -> str:
    safe_name = re.sub(r"[^\w.-]+", "_", name.strip(), flags=re.UNICODE).strip("._")
    if not safe_name:
        raise ValueError("Enter a name containing at least one letter or number.")
    return f"rater_{safe_name}.csv"


def _render_rater_setup() -> str | None:
    if st.session_state.get("rater_name"):
        return st.session_state["rater_name"]

    st.subheader("Start rating")
    with st.form("rater_setup"):
        name = st.text_input("Your rater name")
        started = st.form_submit_button("Continue")
    if started:
        if not name.strip():
            st.error("Enter your name to continue.")
        else:
            st.session_state["rater_name"] = name.strip()
            st.rerun()
    return None


def _rating_page(queries: pd.DataFrame, results: pd.DataFrame) -> None:
    st.title("Rate search results")
    rater_name = _render_rater_setup()
    if not rater_name:
        return

    st.caption(f"Rater: {rater_name}")
    query_ids = queries["query_id"].tolist()
    query_by_id = queries.set_index("query_id").to_dict("index")
    selected_id = st.selectbox(
        "Choose a query",
        query_ids,
        format_func=lambda query_id: (
            f"{query_by_id[query_id]['query']} ({query_by_id[query_id]['language']})"
        ),
    )
    query = query_by_id[selected_id]
    st.subheader(query["query"])
    st.write(f"**Intent:** {query['intent']}  ·  **Language:** {query['language']}")

    query_results = results[results["query_id"] == selected_id].sort_values("rank")
    if query_results.empty:
        st.warning("No results are available for this query.")
        return

    selections: list[tuple[pd.Series, str, str]] = []
    for _, result in query_results.iterrows():
        st.markdown(f"**Rank {result['rank']}: [{result['title']}]({result['url']})**")
        st.write(result["snippet"])
        key_base = f"{selected_id}_{result['rank']}"
        label = st.selectbox(
            "Relevance rating",
            LABEL_OPTIONS,
            key=f"label_{key_base}",
            label_visibility="collapsed",
        )
        notes = st.text_input("Optional notes", key=f"notes_{key_base}")
        selections.append((result, label, notes))
        st.divider()

    if st.button("Save ratings for this query", type="primary"):
        incomplete = [str(result["rank"]) for result, label, _ in selections if label == LABEL_OPTIONS[0]]
        if incomplete:
            st.error(f"Choose a rating for every result. Missing ranks: {', '.join(incomplete)}.")
            return

        rated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        rows = [
            {
                "rater_name": rater_name,
                "query_id": selected_id,
                "language": query["language"],
                "query": query["query"],
                "intent": query["intent"],
                "rank": result["rank"],
                "title": result["title"],
                "url": result["url"],
                "label": label,
                "notes": notes,
                "rated_at": rated_at,
            }
            for result, label, notes in selections
        ]
        try:
            filename = _rater_filename(rater_name)
            append_ratings(rows, RATINGS_DIRECTORY / filename)
        except (OSError, ValueError, pd.errors.ParserError) as error:
            st.error(f"Could not save ratings: {error}")
            return
        st.success(f"Saved {len(rows)} ratings to ratings/{filename}.")


def _read_rating_upload(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    return validate_ratings(pd.read_csv(uploaded_file), uploaded_file.name)


def _agreement_page() -> None:
    st.title("Inter-rater agreement")
    source = st.radio("Load raters from", ("Ratings folder", "Upload two CSV files"), horizontal=True)
    rating_files = sorted(RATINGS_DIRECTORY.glob("rater_*.csv"))

    if source == "Ratings folder":
        if len(rating_files) < 2:
            st.info("Save ratings from at least two raters, or upload two rating CSV files.")
            return
        names = [path.name for path in rating_files]
        col_a, col_b = st.columns(2)
        name_a = col_a.selectbox("Rater A", names, index=0)
        options_b = [name for name in names if name != name_a]
        name_b = col_b.selectbox("Rater B", options_b)
        try:
            ratings_a = validate_ratings(pd.read_csv(RATINGS_DIRECTORY / name_a), name_a)
            ratings_b = validate_ratings(pd.read_csv(RATINGS_DIRECTORY / name_b), name_b)
        except (OSError, ValueError, pd.errors.ParserError) as error:
            st.error(f"Could not load the selected ratings: {error}")
            return
    else:
        col_a, col_b = st.columns(2)
        file_a = col_a.file_uploader("Rater A CSV", type="csv", key="agreement_file_a")
        file_b = col_b.file_uploader("Rater B CSV", type="csv", key="agreement_file_b")
        if file_a is None or file_b is None:
            st.info("Upload both raters' CSV files to calculate agreement.")
            return
        try:
            ratings_a = _read_rating_upload(file_a)
            ratings_b = _read_rating_upload(file_b)
        except (ValueError, pd.errors.ParserError) as error:
            st.error(f"Could not read the uploaded ratings: {error}")
            return
        if ratings_a is None or ratings_b is None:
            return

    paired = compare_raters(ratings_a, ratings_b)
    if paired.empty:
        st.warning("The selected files have no matching query and result ranks.")
        return

    overall = agreement_statistics(paired)
    metric_a, metric_b, metric_c = st.columns(3)
    metric_a.metric("Percent agreement", "N/A" if overall["percent_agreement"] is None else f"{overall['percent_agreement']:.1f}%")
    metric_b.metric("Cohen's kappa", "N/A" if overall["cohen_kappa"] is None else f"{overall['cohen_kappa']:.3f}")
    metric_c.metric("Judgeable result pairs", overall["n"])
    st.caption("“Cannot judge / needs more info” pairs are excluded from agreement scores.")

    by_language = agreement_by_language(paired)
    language_rows = [
        {
            "Language": language,
            "Judgeable pairs": stats["n"],
            "Percent agreement": (
                "N/A" if stats["percent_agreement"] is None else f"{stats['percent_agreement']:.1f}%"
            ),
            "Cohen's kappa": "N/A" if stats["cohen_kappa"] is None else f"{stats['cohen_kappa']:.3f}",
        }
        for language, stats in by_language.items()
    ]
    st.subheader("Agreement by language")
    st.dataframe(pd.DataFrame(language_rows), hide_index=True, use_container_width=True)

    disagreements = find_disagreements(paired)
    st.subheader(f"Disagreements ({len(disagreements)})")
    if disagreements.empty:
        st.success("The raters agree on all matched results.")
    else:
        columns = [
            "query_id",
            "language_a",
            "query_a",
            "intent_a",
            "rank",
            "title_a",
            "label_a",
            "label_b",
        ]
        st.dataframe(disagreements[columns], hide_index=True, use_container_width=True)


def _summary_page() -> None:
    st.title("Ratings summary")
    try:
        ratings = load_all_ratings(RATINGS_DIRECTORY)
    except (OSError, ValueError, pd.errors.ParserError) as error:
        st.error(f"Could not load saved ratings: {error}")
        return
    if ratings.empty:
        st.info("No ratings have been saved yet.")
        return

    if "rated_at" in ratings.columns:
        ratings = ratings.sort_values("rated_at", kind="stable").drop_duplicates(
            ["rater_name", "query_id", "rank"], keep="last"
        )

    st.subheader("Rating counts by language")
    by_language = ratings.groupby(["language", "label"]).size().unstack(fill_value=0)
    st.bar_chart(by_language)
    st.subheader("Rating counts by intent")
    by_intent = ratings.groupby(["intent", "label"]).size().unstack(fill_value=0)
    st.bar_chart(by_intent)
    st.download_button(
        "Download all ratings as CSV",
        data=ratings.to_csv(index=False).encode("utf-8"),
        file_name="all_ratings.csv",
        mime="text/csv",
    )


def _rubric_page() -> None:
    st.title("Rating rubric")
    st.write(
        "Judge how well the result satisfies the likely intent behind the query. "
        "Consider the result title, destination, and snippet together."
    )
    rubric = [
        ("Highly Relevant", "Directly and fully satisfies the intent. Example: for “official passport renewal website,” the official government renewal page."),
        ("Relevant", "Clearly useful and on-topic, but not the best or most direct answer. Example: a reputable guide explaining passport renewal steps."),
        ("Slightly Relevant", "Touches the topic but only partially helps with the specific intent. Example: a general travel article that briefly mentions passports."),
        ("Not Relevant", "Does not meaningfully satisfy the intent, is about a different subject, or conflicts with the query. Example: a page about renewing a driver's license for a passport query."),
        ("Cannot judge / needs more info", "The available title, URL, and snippet are not enough to determine relevance, or the result cannot be assessed. Example: a broken-looking result with an empty snippet and ambiguous title."),
    ]
    for label, definition in rubric:
        st.markdown(f"**{label}.** {definition}")


def main() -> None:
    queries, results = _load_sample_data()
    page = st.sidebar.radio("Page", ("Rate results", "Agreement", "Summary", "Rubric"))
    if page == "Rate results":
        _rating_page(queries, results)
    elif page == "Agreement":
        _agreement_page()
    elif page == "Summary":
        _summary_page()
    else:
        _rubric_page()


if __name__ == "__main__":
    main()
