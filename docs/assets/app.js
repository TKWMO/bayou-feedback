const stationSelect = document.getElementById("station-select");
const eventSelect = document.getElementById("event-select");
const refreshNote = document.getElementById("refresh-note");
const stationCards = document.getElementById("station-cards");
const trendSummary = document.getElementById("trend-summary");
const trendChart = document.getElementById("trend-chart");
const historicalPanel = document.getElementById("historical-panel");

let appState = {
  stations: [],
  latest: [],
  timeseries: [],
  history: [],
  metadata: {},
  geojson: null,
  activeStation: null,
  showDischarge: false,
};

async function loadJson(path) {
  try {
    const resp = await fetch(path);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
  } catch (error) {
    console.warn(`Failed to load ${path}:`, error);
    return null;
  }
}

function formatNumber(value, digits = 1) {
  return value === null || value === undefined || Number.isNaN(value) ? "N/A" : Number(value).toFixed(digits);
}

function renderStationCards() {
  if (!appState.latest.length) {
    stationCards.innerHTML = "<p>No current station observations available yet.</p>";
    return;
  }
  stationCards.innerHTML = appState.latest.map((item) => `
    <div class="station-card">
      <h3>${item.station_name}</h3>
      <p><strong>Gage height:</strong> ${formatNumber(item.latest_gage_height_ft)} ft</p>
      <p><strong>Discharge:</strong> ${formatNumber(item.latest_discharge_cfs, 0)} cfs</p>
      <p><strong>Trend:</strong> ${item.trend_label || "N/A"}</p>
      <p><strong>Freshness:</strong> ${item.freshness || "N/A"}</p>
    </div>
  `).join("");
}

function renderTrendSummary() {
  if (!appState.latest.length) {
    trendSummary.innerHTML = "<p>Trend summary unavailable until data are retrieved.</p>";
    return;
  }
  const summary = appState.latest.map((item) => `
    <p><strong>${item.station_name}</strong><br />${item.trend_label}, ${formatNumber(item.one_hour_change_ft)} ft change in one hour.</p>
  `).join("");
  trendSummary.innerHTML = summary;
}

function renderHistoricalPanel() {
  if (!appState.history.length) {
    historicalPanel.innerHTML = "<p>Historical screening data are unavailable.</p>";
    return;
  }
  const activeEvent = eventSelect.value || appState.history[0]?.event;
  const rows = appState.history.filter((row) => row.event === activeEvent);
  if (!rows.length) {
    historicalPanel.innerHTML = "<p>No historical event data for this selection.</p>";
    return;
  }
  historicalPanel.innerHTML = rows.map((row) => `
    <div class="station-card">
      <h3>${row.station_name || "Station unavailable"}</h3>
      <p><strong>Peak gage height:</strong> ${formatNumber(row.peak_gage_height_ft)} ft</p>
      <p><strong>Peak discharge:</strong> ${formatNumber(row.peak_discharge_cfs, 0)} cfs</p>
      <p><strong>Peak one-hour rise:</strong> ${formatNumber(row.max_one_hour_stage_rise_ft)} ft</p>
    </div>
  `).join("");
}

function setRefreshNote() {
  if (!appState.metadata.build_time_utc) {
    refreshNote.textContent = "No refresh timestamp available.";
    return;
  }
  const t = new Date(appState.metadata.build_time_utc);
  refreshNote.textContent = `Last successful refresh: ${t.toLocaleString("en-US", { timeZone: "America/Chicago" })}`;
}

function populateStationSelect() {
  stationSelect.innerHTML = appState.latest.map((item) => `
    <option value="${item.station_id}">${item.station_name}</option>
  `).join("");
  if (appState.latest.length) {
    appState.activeStation = appState.latest[0].station_id;
    stationSelect.value = appState.activeStation;
  }
}

function populateEventSelect() {
  const events = [...new Set(appState.history.map((item) => item.event))];
  eventSelect.innerHTML = events.map((event) => `
    <option value="${event}">${event}</option>
  `).join("");
}

function renderChart() {
  const stationId = stationSelect.value || appState.activeStation;
  const stationRows = appState.timeseries.filter((item) => item.station_id === stationId);
  if (!stationRows.length) {
    trendChart.innerHTML = "<p style='padding:20px;'>Unable to render chart without station time series.</p>";
    return;
  }
  const stage = stationRows.filter((r) => r.gage_height_ft !== null && r.gage_height_ft !== undefined);
  const discharge = stationRows.filter((r) => r.discharge_cfs !== null && r.discharge_cfs !== undefined);
  const trace1 = {
    x: stage.map((r) => new Date(r.timestamp_local)),
    y: stage.map((r) => r.gage_height_ft),
    name: "Gage height (ft)",
    mode: "lines+markers",
    line: { color: "#0b2340" },
    visible: appState.showDischarge ? "legendonly" : true,
  };
  const trace2 = {
    x: discharge.map((r) => new Date(r.timestamp_local)),
    y: discharge.map((r) => r.discharge_cfs),
    name: "Discharge (cfs)",
    mode: "lines+markers",
    line: { color: "#2563eb" },
    visible: appState.showDischarge ? true : "legendonly",
    yaxis: "y2",
  };
  const layout = {
    margin: { t: 30, r: 40, l: 40, b: 50 },
    legend: { orientation: "h" },
    xaxis: { title: "Local time (America/Chicago)" },
    yaxis: { title: "Gage height (ft)" },
    yaxis2: { title: "Discharge (cfs)", overlaying: "y", side: "right" },
  };
  Plotly.newPlot(trendChart, [trace1, trace2], layout, { responsive: true, displayModeBar: false });
}

function renderMap() {
  if (!appState.geojson) {
    document.getElementById("map").textContent = "Map data unavailable.";
    return;
  }
  const map = L.map("map").setView([29.77, -95.21], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
  L.geoJSON(appState.geojson, {
    pointToLayer(feature, latlng) {
      return L.circleMarker(latlng, { radius: 8, fillColor: "#2563eb", color: "#0b2340", weight: 1.5, fillOpacity: 0.9 });
    },
    onEachFeature(feature, layer) {
      const station = appState.latest.find((item) => item.station_id === feature.properties.station_id);
      const latestText = station ? `${station.trend_label}, ${formatNumber(station.latest_gage_height_ft)} ft` : "No recent data";
      layer.bindPopup(`<strong>${feature.properties.station_name}</strong><br />${latestText}`);
    },
  }).addTo(map);
}

async function initialize() {
  const [summaryData, metadataData, geoData] = await Promise.all([
    loadJson("data/interpretive_summary.json"),
    loadJson("data/metadata.json"),
    loadJson("data/station_locations.geojson"),
  ]);

  appState.latest = summaryData?.data || [];
  appState.metadata = metadataData || {};
  appState.geojson = geoData || null;

  setRefreshNote();
  renderStationCards();
  renderTrendSummary();
  populateStationSelect();
  renderMap();

  // Load larger chart and historical data after the main page is visible.
  loadAdditionalData();
}

async function loadAdditionalData() {
  const [timeseriesData, historicalData] = await Promise.all([
    loadJson("data/timeseries_7d.json"),
    loadJson("data/historical_event_summary.json"),
  ]);

  appState.timeseries = timeseriesData?.data || [];
  appState.history = historicalData?.data || [];

  populateEventSelect();
  renderHistoricalPanel();
  renderChart();
}

stationSelect.addEventListener("change", () => {
  appState.activeStation = stationSelect.value;
  renderChart();
});

eventSelect.addEventListener("change", () => {
  renderHistoricalPanel();
});

document.getElementById("toggle-series").addEventListener("click", () => {
  appState.showDischarge = !appState.showDischarge;
  renderChart();
});

initialize();
