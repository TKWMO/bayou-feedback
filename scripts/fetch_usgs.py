import json
from datetime import datetime
from typing import Any
import requests

from scripts.config import FALLBACK_STATION_IDS, HISTORICAL_WINDOWS, PARAMETERS, STATION_IDS, USGS_BASE, DEFAULT_PERIOD


def build_usgs_params(site_ids, parameter_codes, period=None, start_date=None, end_date=None):
    params = {
        "format": "json",
        "sites": ",".join(site_ids),
        "parameterCd": ",".join(parameter_codes),
        "siteStatus": "all",
    }
    if period:
        params["period"] = period
    if start_date and end_date:
        params["startDT"] = start_date
        params["endDT"] = end_date
    return params


def fetch_usgs(url: str, params: dict[str, Any]) -> dict[str, Any]:
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _attach_fallback_series(payload: dict, save_raw=False, prefix="recent") -> dict:
    if not payload.get("value", {}).get("timeSeries"):
        fallback_payload = fetch_usgs(USGS_BASE, build_usgs_params(site_ids=FALLBACK_STATION_IDS, parameter_codes=list(PARAMETERS.keys())))
        if fallback_payload.get("value", {}).get("timeSeries"):
            payload = payload.copy()
            payload_value = payload.setdefault("value", {})
            payload_value["timeSeries"] = fallback_payload["value"]["timeSeries"]
            if save_raw:
                _save_raw_snapshot(fallback_payload, f"{prefix}_fallback.json")
        return payload
    fallback_payload = fetch_usgs(USGS_BASE, build_usgs_params(site_ids=FALLBACK_STATION_IDS, parameter_codes=list(PARAMETERS.keys())))
    if fallback_payload.get("value", {}).get("timeSeries"):
        payload_value = payload.setdefault("value", {})
        payload_value["timeSeries"] = payload_value.get("timeSeries", []) + fallback_payload["value"]["timeSeries"]
        if save_raw:
            _save_raw_snapshot(fallback_payload, f"{prefix}_fallback.json")
    return payload


def fetch_recent(period: str = DEFAULT_PERIOD, save_raw=False) -> dict:
    params = build_usgs_params(site_ids=STATION_IDS, parameter_codes=list(PARAMETERS.keys()), period=period)
    payload = fetch_usgs(USGS_BASE, params)
    if save_raw:
        _save_raw_snapshot(payload, "recent.json")
    payload = _attach_fallback_series(payload, save_raw=save_raw, prefix="recent")
    return payload


def fetch_historical(save_raw=False) -> dict:
    result = {}
    for name, window in HISTORICAL_WINDOWS.items():
        params = build_usgs_params(site_ids=STATION_IDS, parameter_codes=list(PARAMETERS.keys()), start_date=window["start"], end_date=window["end"])
        try:
            payload = fetch_usgs(USGS_BASE, params)
            if save_raw:
                _save_raw_snapshot(payload, f"historical_{name.lower()}.json")
            payload = _attach_fallback_series(payload, save_raw=save_raw, prefix=f"historical_{name.lower()}")
            result[name] = payload
        except Exception as exc:
            result[name] = {"error": str(exc), "window": window}
    return result


def _save_raw_snapshot(payload: dict, name: str):
    filename = f"data_raw/{name}"
    with open(filename, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
