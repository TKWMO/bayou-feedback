import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from scripts.config import STATIONS, METADATA_SOURCE_LINKS, SCHEDULE_NOTE
from scripts.fetch_usgs import fetch_historical, fetch_recent
from scripts.generate_static_display import build_display
from scripts.process_metrics import (
    build_metadata,
    derive_summary,
    historical_summary,
    make_station_geojson,
    normalize_recent_payload,
    save_csv,
    save_json,
    wide_format,
)

OUTPUT_ROOT = Path("docs")
DATA_ROOT = OUTPUT_ROOT / "data"
DOWNLOADS_ROOT = OUTPUT_ROOT / "downloads"
DEFAULT_OUTPUTS = {
    "latest_observations": "latest_observations",
    "timeseries_7d": "timeseries_7d",
    "interpretive_summary": "interpretive_summary",
    "historical_events": "historical_events",
    "historical_event_summary": "historical_event_summary",
}


def ensure_directories():
    for path in [OUTPUT_ROOT, DATA_ROOT, DOWNLOADS_ROOT]:
        path.mkdir(parents=True, exist_ok=True)


def build():
    ensure_directories()
    build_time = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    status = "ok"
    message = "Latest build completed."
    recent_payload = None
    historical_payload = {}
    try:
        recent_payload = fetch_recent()
    except Exception as exc:
        status = "partial_failure"
        message = f"Recent USGS data fetch failed: {exc}"
        print(message)
    try:
        historical_payload = fetch_historical()
    except Exception as exc:
        status = "partial_failure"
        if status == "ok":
            message = f"Historical USGS fetch failed: {exc}"
        else:
            message += f"; Historical data fetch failed: {exc}"
        print(message)

    if recent_payload:
        normalized = normalize_recent_payload(recent_payload)
    else:
        normalized = None

    wide = wide_format(normalized) if normalized is not None else None
    summary = derive_summary(wide, STATIONS) if wide is not None else None
    hist_summary = historical_summary(historical_payload)

    metadata = build_metadata(status=status, message=message)
    metadata["build_time_utc"] = build_time
    metadata["notes"] = {
        "scheduling": SCHEDULE_NOTE,
        "data_observations": "This site uses near-live observation retrieval from USGS Water Services.",
    }

    save_outputs(normalized, wide, summary, hist_summary, historical_payload, metadata)
    if status == "ok" or not (OUTPUT_ROOT / "display.html").exists():
        build_display(str(DATA_ROOT / "interpretive_summary.json"), str(DATA_ROOT / "metadata.json"), str(OUTPUT_ROOT / "display.html"))


def save_outputs(normalized, wide, summary, hist_summary, historical_payload, metadata):
    save_json(DATA_ROOT / "metadata.json", metadata)
    save_json(DATA_ROOT / "station_locations.geojson", make_station_geojson(STATIONS))
    save_json(DATA_ROOT / "historical_events.json", historical_payload)

    if normalized is not None:
        save_json(DATA_ROOT / "timeseries_7d.json", {"data": normalized.to_dict(orient="records")})
        save_csv(DATA_ROOT / "timeseries_7d.csv", normalized)
    else:
        preserve_file(DATA_ROOT / "timeseries_7d.json", {"data": []})
        preserve_file(DATA_ROOT / "timeseries_7d.csv", pd.DataFrame())

    if wide is not None and not wide.empty:
        public_wide = wide.drop(columns=[col for col in ["timestamp_utc"] if col in wide.columns])
        save_json(DATA_ROOT / "latest_observations.json", {"data": public_wide.to_dict(orient="records")})
        save_csv(DATA_ROOT / "latest_observations.csv", public_wide)
    else:
        preserve_file(DATA_ROOT / "latest_observations.json", {"data": []})
        preserve_file(DATA_ROOT / "latest_observations.csv", pd.DataFrame())

    if summary is not None and not summary.empty:
        save_json(DATA_ROOT / "interpretive_summary.json", {"data": summary.to_dict(orient="records")})
        save_csv(DATA_ROOT / "interpretive_summary.csv", summary)
    else:
        preserve_file(DATA_ROOT / "interpretive_summary.json", {"data": []})
        preserve_file(DATA_ROOT / "interpretive_summary.csv", pd.DataFrame())

    if hist_summary is not None and not hist_summary.empty:
        save_json(DATA_ROOT / "historical_event_summary.json", {"data": hist_summary.to_dict(orient="records")})
        save_csv(DATA_ROOT / "historical_event_summary.csv", hist_summary)
    else:
        preserve_file(DATA_ROOT / "historical_event_summary.json", {"data": []})
        preserve_file(DATA_ROOT / "historical_event_summary.csv", pd.DataFrame())

    for src_name, filename in [
        ("latest_observations", "hunting_bayou_observations_latest.csv"),
        ("interpretive_summary", "hunting_bayou_interpretive_summary.csv"),
        ("historical_event_summary", "hunting_bayou_historical_event_summary.csv"),
    ]:
        source_file = DATA_ROOT / f"{src_name}.csv"
        dest_file = DOWNLOADS_ROOT / filename
        if source_file.exists() and source_file.stat().st_size > 0:
            dest_file.write_text(source_file.read_text(encoding="utf-8"), encoding="utf-8")


def preserve_file(path, payload):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if Path(path).exists() and Path(path).stat().st_size > 0:
        return
    save_json(path, payload) if isinstance(payload, (dict, list)) else save_csv(path, payload)


def save_json(path, payload):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)


def save_csv(path, df):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if hasattr(df, "to_csv"):
        df.to_csv(path, index=False)
    else:
        Path(path).write_text("", encoding="utf-8")


if __name__ == "__main__":
    build()
