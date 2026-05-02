// US AQI bands (US EPA) — mirrors src/weahist/visualization/_helpers.py.

export const AQI_BANDS = [
  { lower: 0, upper: 50, label: "Good", short: "Good", color: "#00E400" },
  { lower: 51, upper: 100, label: "Moderate", short: "Moderate", color: "#FFFF00" },
  { lower: 101, upper: 150, label: "Unhealthy for Sensitive Groups", short: "Sensitive", color: "#FF7E00" },
  { lower: 151, upper: 200, label: "Unhealthy", short: "Unhealthy", color: "#FF0000" },
  { lower: 201, upper: 300, label: "Very Unhealthy", short: "Very Unh.", color: "#8F3F97" },
  { lower: 301, upper: 500, label: "Hazardous", short: "Hazardous", color: "#7E0023" },
];

export function aqiCategory(value) {
  for (const band of AQI_BANDS) {
    if (value <= band.upper) return band.label;
  }
  return AQI_BANDS[AQI_BANDS.length - 1].label;
}

/** Sensible upper bound for the AQI y-axis: ceiling of the worst observed band. */
export function aqiMax(values) {
  const cleaned = values.filter((v) => v != null && Number.isFinite(v));
  if (cleaned.length === 0) return 100;
  const observed = Math.max(...cleaned);
  for (const band of AQI_BANDS) {
    if (observed <= band.upper) return band.upper;
  }
  return 500;
}
