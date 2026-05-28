from datetime import datetime, timedelta

STATIONS = [
    {
        "station_id": "08075763",
        "station_name": "Hunting Bayou at Hoffman St, Houston, TX",
        "latitude": 29.7847,
        "longitude": -95.2402,
        "display_name": "Hoffman St",
    },
    {
        "station_id": "08075770",
        "station_name": "Hunting Bayou at IH 610, Houston, TX",
        "latitude": 29.7522,
        "longitude": -95.1817,
        "display_name": "IH 610",
    },
    {
        "station_id": "08075760",
        "station_name": "Hunting Bayou at Falls St, Houston, TX",
        "latitude": 29.7607,
        "longitude": -95.2320,
        "display_name": "Falls St",
        "fallback": True,
    },
]

STATION_IDS = [s["station_id"] for s in STATIONS if not s.get("fallback")]
FALLBACK_STATION_IDS = [s["station_id"] for s in STATIONS if s.get("fallback")]
PARAMETERS = {
    "00060": {"parameter_name": "Discharge", "unit": "cfs"},
    "00065": {"parameter_name": "Gage height", "unit": "ft"},
}

HISTORICAL_WINDOWS = {
    "Harvey": {
        "start": "2017-08-25",
        "end": "2017-09-05",
        "label": "Hurricane Harvey screening window",
    },
    "Imelda": {
        "start": "2019-09-17",
        "end": "2019-09-22",
        "label": "Tropical Storm Imelda screening window",
    },
}

USGS_BASE = "https://waterservices.usgs.gov/nwis/iv/"

DEFAULT_PERIOD = "P7D"

METADATA_SOURCE_LINKS = {
    "hcfcd_project": "https://www.hcfcd.org/Activity/Projects/Hunting-Bayou",
    "hcfcd_c18": "https://www.hcfcd.org/Activity/Projects/Hunting-Bayou/C-18-Project-Hunting",
    "harris_fws": "https://www.harriscountyfws.org/",
}

SCHEDULE_NOTE = "Scheduled refresh is best-effort only and may not retrieve new observations every hour."

def recent_window_days():
    return 7

def get_time_bounds():
    end = datetime.utcnow()
    start = end - timedelta(days=recent_window_days())
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
