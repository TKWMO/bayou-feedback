import json
from pathlib import Path
from datetime import datetime

REQUIRED_FILES = [
    "docs/index.html",
    "docs/display.html",
    "docs/data/metadata.json",
    "docs/data/latest_observations.csv",
    "docs/data/interpretive_summary.csv",
    "docs/data/historical_event_summary.csv",
    "docs/data/station_locations.geojson",
]

TREND_LABELS = {"Rising", "Falling", "Relatively Stable", "Insufficient Data"}


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def validate():
    for path in REQUIRED_FILES:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Missing expected output file: {path}")
        if p.stat().st_size == 0:
            raise ValueError(f"Output file is empty: {path}")

    metadata = load_json("docs/data/metadata.json")
    datetime.fromisoformat(metadata.get("build_time_utc").replace("Z", "+00:00"))

    csv_text = Path("docs/data/interpretive_summary.csv").read_text(encoding="utf-8")
    if "trend_label" not in csv_text:
        raise ValueError("interpretive_summary.csv missing trend_label header")
    for line in csv_text.splitlines()[1:]:
        if not line.strip():
            continue
        parts = line.split(",")
        if len(parts) < 10:
            continue
    display_html = Path("docs/display.html").read_text(encoding="utf-8")
    if "<link" in display_html or "<script src=" in display_html:
        raise ValueError("display.html should be standalone and not include external linked resources")

    index_html = Path("docs/index.html").read_text(encoding="utf-8")
    if "official Harris County flood alerts" not in index_html and "Harris County Flood Warning System" not in index_html:
        raise ValueError("index.html must include the HCFCD alert source message")
    if "not a flood warning" not in index_html.lower():
        raise ValueError("index.html must include a disclaimer that it is not a flood warning tool")

    hist_json = load_json("docs/data/historical_events.json")
    if not isinstance(hist_json, dict):
        raise ValueError("historical_events.json must be JSON object")

    print("Validation passed")


if __name__ == "__main__":
    validate()
