import json
from datetime import datetime
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def build_display(summary_path: str, metadata_path: str, output_path: str):
    latest = load_json(summary_path)
    metadata = load_json(metadata_path)
    now = metadata.get("build_time_utc", datetime.utcnow().isoformat())
    rows = latest.get("data", []) if isinstance(latest, dict) else []
    station_section = "".join(render_station_block(item) for item in rows)
    sparkline = render_sparkline(rows)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Hunting Bayou Waterway Snapshot</title>
<style>
body{{font-family:system-ui, sans-serif; margin:16px; color:#111; background:#fff;}}
main{{max-width:760px;}}
h1{{font-size:1.6rem; margin-bottom:0.4rem;}}
p{{margin:0.6rem 0;}}
.section{{border-top:1px solid #333; padding-top:12px; margin-top:16px;}}
.metric{{display:flex; justify-content:space-between; margin:8px 0;}}
.metric strong{{font-weight:700;}}
.sparkline{{width:100%; height:120px; margin-top:10px;}}
.footer{{margin-top:18px; font-size:0.9rem; color:#333;}}
</style>
</head>
<body>
<main>
<h1>Hunting Bayou Waterway Snapshot</h1>
<p>Latest build: {now.replace('T',' ').replace('Z',' UTC')}</p>
{station_section}
<div class="section">
<h2>Recent waterway response</h2>
{sparkline}
<p>This is a public information display concept. Not an official flood warning device.</p>
</div>
<div class="section footer">
<p>Full dashboard: visit the GitHub Pages site if available.</p>
<p>Not a substitute for official Harris County flood alerts.</p>
</div>
</main>
</body>
</html>"""
    Path(output_path).write_text(html, encoding="utf-8")


def render_station_block(item):
    if not item:
        return "<p>No station summary available.</p>"
    age = item.get("latest_observation_age_minutes")
    freshness = item.get("freshness")
    return f"<div class='section'><h2>{item.get('station_name')}</h2><div class='metric'><strong>Gage height</strong><span>{item.get('latest_gage_height_ft', 'N/A')} ft</span></div><div class='metric'><strong>Discharge</strong><span>{item.get('latest_discharge_cfs', 'N/A')} cfs</span></div><div class='metric'><strong>One-hour trend</strong><span>{item.get('trend_label', 'N/A')}</span></div><div class='metric'><strong>Freshness</strong><span>{freshness} ({age} min)</span></div></div>"


def render_sparkline(rows):
    if not rows:
        return "<p>No trend data available.</p>"
    values = [row.get("latest_gage_height_ft") or 0 for row in rows][:20]
    if len(values) < 2:
        return "<p>Insufficient recent stage data for sparkline.</p>"
    width = 720
    height = 110
    points = []
    minv = min(values)
    maxv = max(values)
    span = maxv - minv if maxv != minv else 1
    for i, value in enumerate(values):
        x = int(i * width / (len(values) - 1))
        y = int(height - ((value - minv) / span) * height)
        points.append(f"{x},{y}")
    return f"<svg class='sparkline' viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg'><polyline fill='none' stroke='#111' stroke-width='2' points='{' '.join(points)}' /></svg>"
