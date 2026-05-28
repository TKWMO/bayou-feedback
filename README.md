# Bayou Feedback

A citizen-facing, static dashboard for Hunting Bayou waterway observations and infrastructure context.

## What this project includes

- A static GitHub Pages site in `docs/` with a dashboard, methods page, and low-power display snapshot.
- A Python data pipeline in `scripts/` that fetches USGS near-live observations and historical event windows.
- Generated CSV/JSON data files in `docs/data/` plus downloadable CSV files in `docs/downloads/`.
- A scheduled GitHub Actions workflow that refreshes data hourly at minute 17 and deploys `docs/` to Pages.

## Setup

1. Open this repository in a Codespace or local environment.
2. Install Python 3.11.
3. Install dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Running the data build manually

```bash
python scripts/build_all.py
```

This command fetches USGS station data, processes observations, writes generated JSON/CSV outputs to `docs/data/`, and updates `docs/display.html`.

## Validating outputs

```bash
python scripts/validate_outputs.py
pytest -q
```

## Previewing locally

```bash
python -m http.server 8000 --directory docs
```

Then open `http://localhost:8000` in a browser.

## GitHub Pages deployment

1. Enable Pages for this repository and select the `docs/` folder as the publishing source.
2. The workflow in `.github/workflows/deploy-refresh.yml` runs on push, manually via workflow dispatch, and hourly at minute 17.
3. The workflow installs dependencies, runs `python scripts/build_all.py`, validates outputs, runs tests, and deploys `docs/`.

## Data files and downloads

- `docs/data/latest_observations.csv`
- `docs/data/interpretive_summary.csv`
- `docs/data/historical_event_summary.csv`
- `docs/downloads/hunting_bayou_observations_latest.csv`
- `docs/downloads/hunting_bayou_interpretive_summary.csv`
- `docs/downloads/hunting_bayou_historical_event_summary.csv`

## Low-power display concept

The generated `docs/display.html` is a standalone HTML snapshot intended as a conceptual low-power or offline display. It is self-contained, text-focused, and does not load external resources.

## Notes

- This dashboard uses near-live observations, not guaranteed real-time data.
- It is not a flood warning system and does not replace official Harris County flood alerts.
