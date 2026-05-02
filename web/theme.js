// Theme palettes — mirror of src/weahist/visualization/plotly_renderer.py.

export const LIGHT = {
  template: "plotly_white",
  paperBg: "#FFFFFF",
  plotBg: "#FFFFFF",
  text: "#1F2328",
  textMute: "rgba(0,0,0,0.65)",
  grid: "rgba(0,0,0,0.08)",
  border: "rgba(0,0,0,0.4)",
  tempLine: "#C0392B",
  humidityLine: "#2F80ED",
  aqiLine: "#1F2328",
  weekendFill: "rgba(0,0,0,0.06)",
  daySeparator: "rgba(0,0,0,0.12)",
  legendBg: "rgba(255,255,255,0.7)",
  annotationBg: "rgba(255,255,255,0.85)",
  bandOpacity: [0.28, 0.28, 0.28, 0.28, 0.32, 0.4],
};

export const DARK = {
  template: "plotly_dark",
  paperBg: "#161B22",
  plotBg: "#0D1117",
  text: "#E6EDF3",
  textMute: "rgba(230,237,243,0.75)",
  grid: "rgba(255,255,255,0.08)",
  border: "rgba(230,237,243,0.45)",
  tempLine: "#FF6B6B",
  humidityLine: "#79C0FF",
  aqiLine: "#E6EDF3",
  weekendFill: "rgba(255,255,255,0.05)",
  daySeparator: "rgba(255,255,255,0.12)",
  legendBg: "rgba(22,27,34,0.75)",
  annotationBg: "rgba(22,27,34,0.85)",
  bandOpacity: [0.22, 0.18, 0.25, 0.3, 0.38, 0.5],
};

export function paletteFor(theme) {
  return theme === "dark" ? DARK : LIGHT;
}
