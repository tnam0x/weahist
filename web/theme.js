// Chart palettes. Surface/ink/series values mirror the design tokens in
// styles.css (an e2e test keeps the two in sync); light and dark are chosen
// separately, not inverted.

export const FONT_FAMILY =
  'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';

export const LIGHT = {
  template: "plotly_white",
  paperBg: "#fcfcfb",
  plotBg: "#fcfcfb",
  text: "#0b0b0b",
  textMute: "#6b6a65",
  grid: "#e1e0d9",
  border: "#c3c2b7",
  tempLine: "#eb6834",
  humidityLine: "#2a78d6",
  aqiLine: "#3d3c39",
  weekendFill: "rgba(11,11,11,0.035)",
  daySeparator: "#e1e0d9",
  legendBg: "rgba(252,252,251,0.85)",
  annotationBg: "rgba(252,252,251,0.92)",
  bandOpacity: [0.2, 0.24, 0.22, 0.2, 0.2, 0.22],
};

export const DARK = {
  template: "plotly_dark",
  paperBg: "#1a1a19",
  plotBg: "#1a1a19",
  text: "#ffffff",
  textMute: "#9a9890",
  grid: "#2c2c2a",
  border: "#383835",
  tempLine: "#d95926",
  humidityLine: "#3987e5",
  aqiLine: "#e6e5df",
  weekendFill: "rgba(255,255,255,0.03)",
  daySeparator: "#2c2c2a",
  legendBg: "rgba(26,26,25,0.85)",
  annotationBg: "rgba(26,26,25,0.92)",
  // EPA hues are neon; keep them as a quiet wash on the dark surface.
  bandOpacity: [0.14, 0.12, 0.16, 0.18, 0.2, 0.24],
};

export function paletteFor(theme) {
  return theme === "dark" ? DARK : LIGHT;
}
