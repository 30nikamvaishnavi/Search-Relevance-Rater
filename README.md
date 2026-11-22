# Search-Relevance-Rater

A local, human-powered tool for judging how well search results satisfy a user's intent. It uses Streamlit for the interface, pandas for CSV handling, and scikit-learn for Cohen's kappa. Search results can be retrieved through DuckDuckGo using the `ddgs` package.

## Setup

1. Install Python 3.10 or newer.
2. From the project root, create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

## How to run

Start the app from the project root:

```powershell
.venv\Scripts\python.exe -m streamlit run src/app.py
```

Enter a rater name on the **Rate results** page. Rate each result for a query and save the ratings. Files are written to `ratings/rater_<name>.csv`. Every submission is appended with a timestamp. The agreement page uses the latest submission per query/result for each rater. Use **Agreement** to compare two saved files or upload two rating CSVs, and **Summary** to review rating-count charts and download a combined CSV.

The app loads `data/queries.csv` and `data/results.csv`. Their required columns are:

- Queries: `query_id, language, query, intent`
- Results: `query_id, rank, title, url, snippet`

The app loads the query and search-result records from `data/queries.csv` and `data/results.csv`.

Run the unit tests from the project root:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
```

## Data source

The queries were chosen by the author. The results were retrieved from DuckDuckGo using the `ddgs` package on 2026-11-22. This is an unofficial retrieval method and may differ from Google.

## Rating rubric

- **Highly Relevant:** Directly and fully satisfies the intent. Example: for “official passport renewal website,” an official government renewal page.
- **Relevant:** Clearly useful and on-topic, but not the most direct answer. Example: a reputable guide explaining passport renewal steps.
- **Slightly Relevant:** Related to the topic but only partially helps with the specific intent. Example: a general travel article that briefly mentions passports.
- **Not Relevant:** Does not meaningfully satisfy the intent, is about a different subject, or conflicts with the query. Example: a driver's-license renewal page for a passport query.
- **Cannot judge / needs more info:** There is not enough information in the result to assess it. Example: an ambiguous title with no useful snippet.

“Cannot judge / needs more info” ratings remain visible in disagreements but are excluded from percent-agreement and kappa calculations.

## Results

Fill in these placeholders after collecting and analyzing ratings; no evaluation results are reported with the sample data.

- Number of queries rated: [N queries]
- Percent agreement: [agreement %]
- Cohen's kappa: [kappa]
