import csv
import json
from pathlib import Path
from datetime import datetime

import pytest


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_outputs_exist():
    expected = [
        "docs/index.html",
        "docs/display.html",
        "docs/data/metadata.json",
        "docs/data/latest_observations.csv",
        "docs/data/interpretive_summary.csv",
        "docs/data/historical_event_summary.csv",
    ]
    for path in expected:
        p = Path(path)
        assert p.exists(), f"Missing {path}"
        assert p.stat().st_size > 0, f"Empty file {path}"


def test_metadata_timestamp():
    data = load_json("docs/data/metadata.json")
    ts = data.get("build_time_utc")
    assert ts is not None, "metadata missing build_time_utc"
    datetime.fromisoformat(ts.replace("Z", "+00:00"))


def test_trend_labels_valid():
    with open("docs/data/interpretive_summary.csv", "r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        labels = {"Rising", "Falling", "Relatively Stable", "Insufficient Data"}
        for row in reader:
            trend = row.get("trend_label", "").strip()
            if trend:
                assert trend in labels


def test_display_html_standalone():
    content = Path("docs/display.html").read_text(encoding="utf-8")
    assert "<link" not in content
    assert "<script src=" not in content
    assert "Not an official flood warning device" in content


def test_index_includes_disclaimer_and_link():
    content = Path("docs/index.html").read_text(encoding="utf-8").lower()
    assert "not a flood warning" in content
    assert "harris county flood warning system" in content
