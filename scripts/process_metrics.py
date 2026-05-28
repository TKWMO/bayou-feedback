import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from scripts.config import HISTORICAL_WINDOWS, METADATA_SOURCE_LINKS, PARAMETERS, STATIONS

PARAMETER_MAPPING = {
    "00060": "discharge_cfs",
    "00065": "gage_height_ft",
}

FRESHNESS_THRESHOLDS = {
    "Recent": 60,
    "Delayed": 180,
}

TREND_WINDOW_MINUTES = 60


def utc_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_usgs_time(time_str: str) -> datetime:
    return utc_timestamp(time_str)


def normalize_recent_payload(payload: dict[str, Any]) -> pd.DataFrame:
    records = []
    retrieval = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    time_series = payload.get("value", {}).get("timeSeries", [])

    for series in time_series:
        source_info = series.get("sourceInfo", {})
        variable = series.get("variable", {})
        station_id = source_info.get("siteCode", [{}])[0].get("value")
        station_name = source_info.get("siteName")
        parameter_code = variable.get("variableCode", [{}])[0].get("value")
        parameter_name = PARAMETERS.get(parameter_code, {}).get("parameter_name", variable.get("variableName"))
        unit = variable.get("unit", {}).get("unitCode")
        values = series.get("values", [])
        if not values:
            continue
        for value_block in values:
            for item in value_block.get("value", []):
                if item.get("value") is None:
                    continue
                timestamp_utc = parse_usgs_time(item.get("dateTime"))
                records.append({
                    "station_id": station_id,
                    "station_name": station_name,
                    "timestamp_utc": timestamp_utc.isoformat(),
                    "timestamp_local": timestamp_utc.astimezone().isoformat(),
                    "parameter_code": parameter_code,
                    "parameter_name": parameter_name,
                    "value": float(item.get("value")),
                    "unit": unit,
                    "provisional_or_qualifier": item.get("qualifiers", []),
                    "retrieval_timestamp_utc": retrieval,
                    "source": "USGS Water Services",
                })
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def wide_format(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=[
            "timestamp_local",
            "station_id",
            "station_name",
            "gage_height_ft",
            "discharge_cfs",
            "data_quality_note",
            "source",
        ])
    pivot = df.pivot_table(
        index=["timestamp_local", "timestamp_utc", "station_id", "station_name", "source"],
        columns="parameter_code",
        values="value",
        aggfunc="last",
    ).reset_index()
    rename_map = {code: PARAMETER_MAPPING.get(code, code) for code in PARAMETERS}
    pivot = pivot.rename(columns=rename_map)
    pivot["data_quality_note"] = pivot.apply(lambda row: "" if pd.notna(row.get("gage_height_ft")) or pd.notna(row.get("discharge_cfs")) else "No valid observation", axis=1)
    return pivot


def calculate_trend_label(latest_df: pd.DataFrame, recent_df: pd.DataFrame) -> str:
    if latest_df.empty or recent_df.empty:
        return "Insufficient Data"
    raw_time = latest_df["timestamp_utc"].iloc[0]
    base_time = pd.to_datetime(raw_time)
    cutoff = base_time - timedelta(minutes=TREND_WINDOW_MINUTES)
    window = recent_df[pd.to_datetime(recent_df["timestamp_utc"]) >= cutoff]
    if window.empty or "gage_height_ft" not in window.columns:
        return "Insufficient Data"
    stage = window.sort_values("timestamp_utc")["gage_height_ft"].dropna()
    if len(stage) < 2:
        return "Insufficient Data"
    delta = stage.iloc[-1] - stage.iloc[0]
    rate = delta / (len(stage) - 1)
    if abs(delta) < 0.1:
        return "Relatively Stable"
    if delta > 0:
        return "Rising"
    return "Falling"


def freshness_label(obs_time: datetime, now: datetime) -> str:
    age = (now - obs_time).total_seconds() / 60
    if age <= FRESHNESS_THRESHOLDS["Recent"]:
        return "Recent"
    if age <= FRESHNESS_THRESHOLDS["Delayed"]:
        return "Delayed"
    return "Stale"


def derive_summary(wide: pd.DataFrame, metadata: list[dict[str, Any]]) -> pd.DataFrame:
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    rows = []
    if wide.empty:
        return pd.DataFrame(columns=[
            "station_id",
            "station_name",
            "latest_gage_height_ft",
            "latest_discharge_cfs",
            "one_hour_change_ft",
            "six_hour_change_ft",
            "max_gage_height_24h_ft",
            "max_discharge_24h_cfs",
            "trend_label",
            "latest_observation_age_minutes",
            "freshness",
            "source",
        ])
    wide = wide.copy()
    wide["timestamp_utc"] = pd.to_datetime(wide["timestamp_utc"])
    for station in metadata:
        station_id = station["station_id"]
        station_rows = wide[wide["station_id"] == station_id].sort_values("timestamp_utc")
        if station_rows.empty:
            continue
        latest = station_rows.iloc[-1]
        latest_time = latest["timestamp_utc"]
        window = station_rows[station_rows["timestamp_utc"] >= latest_time - timedelta(hours=24)]
        change_1h = compute_change(station_rows, latest_time, hours=1)
        change_6h = compute_change(station_rows, latest_time, hours=6)
        rows.append({
            "station_id": station_id,
            "station_name": station["station_name"],
            "latest_gage_height_ft": latest.get("gage_height_ft"),
            "latest_discharge_cfs": latest.get("discharge_cfs"),
            "one_hour_change_ft": change_1h,
            "six_hour_change_ft": change_6h,
            "max_gage_height_24h_ft": window["gage_height_ft"].max() if not window.empty else None,
            "max_discharge_24h_cfs": window["discharge_cfs"].max() if not window.empty else None,
            "trend_label": calculate_trend_label(latest.to_frame().T, station_rows),
            "latest_observation_age_minutes": round((now - latest_time).total_seconds() / 60, 1),
            "freshness": freshness_label(latest_time, now),
            "source": latest.get("source"),
        })
    return pd.DataFrame(rows)


def compute_change(rows: pd.DataFrame, latest_time: datetime, hours: int) -> Any:
    target = latest_time - timedelta(hours=hours)
    candidates = rows[rows["timestamp_utc"] <= target]
    if candidates.empty:
        return None
    nearest = candidates.iloc[-1]
    latest = rows[rows["timestamp_utc"] == latest_time].iloc[0]
    if pd.isna(nearest.get("gage_height_ft")) or pd.isna(latest.get("gage_height_ft")):
        return None
    return round(latest.get("gage_height_ft") - nearest.get("gage_height_ft"), 2)


def historical_summary(historical_payloads: dict[str, Any]) -> pd.DataFrame:
    records = []
    for event_name, payload in historical_payloads.items():
        if payload.get("error"):
            records.append({
                "event": event_name,
                "station_id": None,
                "station_name": None,
                "peak_gage_height_ft": None,
                "peak_gage_height_time_utc": None,
                "peak_discharge_cfs": None,
                "peak_discharge_time_utc": None,
                "max_one_hour_stage_rise_ft": None,
                "observations_retrieved": 0,
                "data_completeness_note": "Historical data unavailable for this event",
            })
            continue
        event_df = normalize_recent_payload(payload)
        if event_df.empty:
            for station in STATIONS:
                records.append({
                    "event": event_name,
                    "station_id": station["station_id"],
                    "station_name": station["station_name"],
                    "peak_gage_height_ft": None,
                    "peak_gage_height_time_utc": None,
                    "peak_discharge_cfs": None,
                    "peak_discharge_time_utc": None,
                    "max_one_hour_stage_rise_ft": None,
                    "observations_retrieved": 0,
                    "data_completeness_note": "Data unavailable for this station/event",
                })
            continue
        event_df["timestamp_utc"] = pd.to_datetime(event_df["timestamp_utc"])
        for station in STATIONS:
            site_id = station["station_id"]
            station_df = event_df[event_df["station_id"] == site_id]
            if station_df.empty:
                records.append({
                    "event": event_name,
                    "station_id": site_id,
                    "station_name": station["station_name"],
                    "peak_gage_height_ft": None,
                    "peak_gage_height_time_utc": None,
                    "peak_discharge_cfs": None,
                    "peak_discharge_time_utc": None,
                    "max_one_hour_stage_rise_ft": None,
                    "observations_retrieved": 0,
                    "data_completeness_note": "Data unavailable for this station/event",
                })
                continue
            stage_df = station_df[station_df["parameter_code"] == "00065"].sort_values("timestamp_utc")
            discharge_df = station_df[station_df["parameter_code"] == "00060"].sort_values("timestamp_utc")
            peak_stage_row = stage_df.loc[stage_df["value"].idxmax()] if not stage_df.empty else None
            peak_disc_row = discharge_df.loc[discharge_df["value"].idxmax()] if not discharge_df.empty else None
            max_one_hour = compute_max_one_hour_rise(stage_df)
            records.append({
                "event": event_name,
                "station_id": site_id,
                "station_name": station["station_name"],
                "peak_gage_height_ft": float(peak_stage_row["value"]) if peak_stage_row is not None else None,
                "peak_gage_height_time_utc": peak_stage_row["timestamp_utc"].isoformat() if peak_stage_row is not None else None,
                "peak_discharge_cfs": float(peak_disc_row["value"]) if peak_disc_row is not None else None,
                "peak_discharge_time_utc": peak_disc_row["timestamp_utc"].isoformat() if peak_disc_row is not None else None,
                "max_one_hour_stage_rise_ft": max_one_hour,
                "observations_retrieved": int(station_df.shape[0]),
                "data_completeness_note": "Data retrieved from USGS for the event window",
            })
    return pd.DataFrame(records)


def compute_max_one_hour_rise(stage_df: pd.DataFrame) -> Any:
    if stage_df.empty:
        return None
    stage_df = stage_df.sort_values("timestamp_utc")
    max_rise = 0.0
    for idx, row in stage_df.iterrows():
        start_time = row["timestamp_utc"]
        later = stage_df[stage_df["timestamp_utc"] >= start_time + timedelta(hours=1)]
        if later.empty:
            continue
        rise = later["value"].max() - row["value"]
        if rise > max_rise:
            max_rise = rise
    return round(max_rise, 2) if max_rise > 0 else 0.0


def save_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)


def save_csv(path: str, df: pd.DataFrame) -> None:
    df.to_csv(path, index=False)


def make_station_geojson(stations: list[dict[str, Any]]) -> dict[str, Any]:
    features = []
    for station in stations:
        features.append({
            "type": "Feature",
            "properties": {
                "station_id": station["station_id"],
                "station_name": station["station_name"],
                "display_name": station["display_name"],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [station["longitude"], station["latitude"]],
            },
        })
    return {"type": "FeatureCollection", "features": features}


def build_metadata(status: str = "ok", message: str = "Latest build completed.") -> dict[str, Any]:
    return {
        "build_time_utc": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        "status": status,
        "message": message,
        "sources": {
            "usgs": "USGS Water Services",
            "hcfcd_project": METADATA_SOURCE_LINKS["hcfcd_project"],
            "hcfcd_c18": METADATA_SOURCE_LINKS["hcfcd_c18"],
            "harris_fws": METADATA_SOURCE_LINKS["harris_fws"],
        },
        "refresh_policy": {
            "description": "Data refresh is near-live observations only, not guaranteed, and uses scheduled hourly retrieval where available.",
        },
    }
