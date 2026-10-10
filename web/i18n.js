// UI strings (Vietnamese + English) and locale-aware formatting.
// scripts/build_site.py repeats the Vietnamese meta/intro texts for the static
// pages; tests/e2e/test_i18n.py keeps the two in sync.
// The static HTML ships in Vietnamese (what crawlers index); elements with
// data-i18n* attributes are re-labelled when the visitor picks English.

export const LANG_KEY = "weahist.lang";
export const LANGS = ["vi", "en"];
const DEFAULT_LANG = "vi";

const STRINGS = {
  vi: {
    "meta.title": "Lịch sử thời tiết & chất lượng không khí | Weather History",
    "meta.titleCity": "Thời tiết {place}: lịch sử nhiệt độ, độ ẩm, AQI",
    "meta.description":
      "Xem miễn phí lịch sử thời tiết và chất lượng không khí của mọi thành phố: nhiệt độ, độ ẩm và chỉ số AQI theo giờ hoặc theo ngày, từ 24 giờ qua đến 1 năm.",
    "intro.root":
      "Xem lại thời tiết và không khí thực tế ở bất kỳ thành phố nào: nhiệt độ, độ ẩm và chỉ số chất lượng không khí (AQI) theo giờ hoặc theo ngày, từ 24 giờ qua đến 1 năm.",
    "intro.city":
      "Lịch sử thời tiết và chất lượng không khí tại {place}: nhiệt độ, độ ẩm và chỉ số AQI theo giờ hoặc theo ngày, từ 24 giờ qua đến 1 năm, cập nhật từ Open-Meteo.",
    dismiss: "Đóng",
    share: "Chia sẻ",
    "share.aria": "Chia sẻ trang này",
    language: "Ngôn ngữ",
    "language.switch": "Switch to English",
    theme: "Giao diện",
    "theme.system": "🖥 Hệ thống",
    "theme.light": "☀ Sáng",
    "theme.dark": "🌙 Tối",
    filters: "Bộ lọc",
    location: "Địa điểm",
    "location.placeholder": "Tìm thành phố",
    "location.locate": "Dùng vị trí của tôi",
    "location.recent": "Gần đây",
    "location.mine": "Vị trí của tôi",
    range: "Khoảng thời gian",
    "range.1d": "24 giờ qua",
    "range.3d": "3 ngày qua",
    "range.1w": "7 ngày qua",
    "range.2w": "2 tuần qua",
    "range.1m": "30 ngày qua",
    "range.3m": "3 tháng qua",
    "range.6m": "6 tháng qua",
    "range.1y": "1 năm qua",
    "chip.1d": "24 giờ",
    "chip.3d": "3 ngày",
    "chip.1w": "7 ngày",
    "chip.2w": "2 tuần",
    "chip.1m": "30 ngày",
    "chip.3m": "3 tháng",
    "chip.6m": "6 tháng",
    "chip.1y": "1 năm",
    "range.custom": "Tùy chọn",
    units: "Đơn vị",
    from: "Từ",
    to: "Đến",
    apply: "Áp dụng",
    loading: "Đang tải",
    noscript: "Ứng dụng cần JavaScript để tải và vẽ dữ liệu từ Open-Meteo. Vui lòng bật JavaScript.",
    "download.csv": "Tải CSV",
    summary: "Tóm tắt",
    charts: "Biểu đồ",
    "card.temperature": "Nhiệt độ",
    "card.humidity": "Độ ẩm tương đối",
    "card.aqi": "Chất lượng không khí",
    "card.png": "Tải biểu đồ dạng PNG",
    "card.table": "Bảng",
    "card.chart": "Biểu đồ",
    "card.aqiCategories": "Các mức AQI",
    "card.hourly": "{unit} · theo giờ",
    "card.dailyBand": "{unit} · khoảng thấp–cao và trung bình theo ngày",
    "card.aqiDaily": "US AQI · trung bình ngày",
    "empty.temperature": "Không có dữ liệu nhiệt độ cho khoảng này.",
    "empty.humidity": "Không có dữ liệu độ ẩm cho khoảng này.",
    "empty.aqi": "Không có dữ liệu chất lượng không khí cho khoảng này — thường chỉ có trong 2–3 năm gần nhất.",
    "kpi.temperature": "Nhiệt độ TB",
    "kpi.humidity": "Độ ẩm TB",
    "kpi.aqi": "AQI cao nhất (US)",
    "kpi.coverage": "Độ phủ AQI",
    "kpi.lowHigh": "Thấp {low} · Cao {high}",
    "kpi.noData": "Không có dữ liệu",
    "kpi.noAqi": "Không có dữ liệu chất lượng không khí cho khoảng này",
    "kpi.readings.hourly": "{n} số liệu theo giờ",
    "kpi.readings.daily": "{n} số liệu theo ngày",
    "granularity.hourly": "Theo giờ",
    "granularity.daily": "Theo ngày",
    "table.time": "Thời gian",
    "table.date": "Ngày",
    "table.temperature": "Nhiệt độ ({unit})",
    "table.humidity": "Độ ẩm (%)",
    "table.low": "Thấp ({unit})",
    "table.mean": "TB ({unit})",
    "table.high": "Cao ({unit})",
    "table.aria": "Dữ liệu {title}",
    "chart.max": "cao",
    "chart.min": "thấp",
    "chart.high": "Cao",
    "chart.low": "Thấp",
    "chart.mean": "TB",
    "status.enter": "Nhập địa điểm để bắt đầu.",
    "status.loading": "Đang tải {place} ({range})…",
    "error.timeout": "Quá {s} giây không có phản hồi. Hãy chọn khoảng ngắn hơn hoặc kiểm tra mạng.",
    "error.fetch": "Không tải được dữ liệu: {detail}",
    "error.noMatch": "Không tìm thấy \"{q}\"",
    "error.geoUnsupported": "Trình duyệt này không hỗ trợ định vị.",
    "error.geo": "Không lấy được vị trí của bạn: {reason}.",
    "error.geo.denied": "quyền truy cập bị từ chối",
    "error.geo.timeout": "quá thời gian chờ",
    "error.geo.unavailable": "không xác định được vị trí",
    "custom.missing": "Hãy chọn cả ngày bắt đầu và ngày kết thúc.",
    "custom.order": "Ngày bắt đầu phải trước hoặc bằng ngày kết thúc.",
    "custom.future": "Ngày kết thúc không được ở tương lai.",
    "custom.tooEarly": "Dữ liệu chỉ có từ năm 1940.",
    "custom.tooLong": "Chọn tối đa {max} ngày.",
    offline: "Bạn đang offline — đang hiển thị dữ liệu đã lưu (nếu có).",
    "toast.copied": "Đã sao chép liên kết",
    "toast.copyFailed": "Không sao chép được — hãy dùng địa chỉ trên thanh trình duyệt.",
    "toast.shareFailed": "Không mở được bảng chia sẻ.",
    "footer.source": "Nguồn:",
    "footer.reset": "Đặt lại tùy chọn",
    "footer.madeWith": "Làm với",
    "footer.by": "bởi",
    "footer.cities": "Các thành phố",
    "footer.vietnam": "Việt Nam",
    "footer.world": "Thế giới",
    "footer.about":
      "Weather History cho biết thời tiết và không khí thực tế ở mọi thành phố: nhiệt độ, độ ẩm tương đối và chỉ số chất lượng không khí (AQI) theo giờ hoặc theo ngày, từ 24 giờ qua đến cả năm, kèm khuyến nghị sức khỏe của EPA. Dữ liệu lấy từ API mã nguồn mở Open-Meteo (tái phân tích ECMWF và chất lượng không khí CAMS). Miễn phí — không cần đăng ký, không cần API key.",
    "aqi.good": "Tốt",
    "aqi.moderate": "Trung bình",
    "aqi.usg": "Kém (nhóm nhạy cảm)",
    "aqi.usg.short": "Kém",
    "aqi.unhealthy": "Xấu",
    "aqi.veryUnhealthy": "Rất xấu",
    "aqi.hazardous": "Nguy hại",
    "aqi.good.advice": "Chất lượng không khí tốt, ít hoặc không có rủi ro.",
    "aqi.moderate.advice": "Người rất nhạy cảm nên hạn chế vận động kéo dài ngoài trời.",
    "aqi.usg.advice": "Nhóm nhạy cảm nên giảm vận động mạnh hoặc kéo dài ngoài trời.",
    "aqi.unhealthy.advice": "Mọi người nên giảm vận động mạnh hoặc kéo dài ngoài trời.",
    "aqi.veryUnhealthy.advice": "Mọi người nên tránh vận động mạnh hoặc kéo dài ngoài trời.",
    "aqi.hazardous.advice": "Mọi người nên tránh mọi hoạt động ngoài trời.",
  },
  en: {
    "meta.title": "Weather & Air Quality History for Any City | Weather History",
    "meta.titleCity": "{place} weather history: temperature, humidity, AQI",
    "meta.description":
      "Free weather and air-quality history for any city: hourly or daily temperature, humidity and US AQI, from the last 24 hours up to a year. No sign-up.",
    "intro.root":
      "See what the weather and the air were really like in any city: hourly or daily temperature, humidity and Air Quality Index (AQI), from the last 24 hours up to a year.",
    "intro.city":
      "Weather and air-quality history for {place}: hourly or daily temperature, humidity and US AQI, from the last 24 hours up to a year, from Open-Meteo.",
    dismiss: "Dismiss",
    share: "Share",
    "share.aria": "Share this view",
    language: "Language",
    "language.switch": "Chuyển sang tiếng Việt",
    theme: "Theme",
    "theme.system": "🖥 System",
    "theme.light": "☀ Light",
    "theme.dark": "🌙 Dark",
    filters: "Filters",
    location: "Location",
    "location.placeholder": "Search a city",
    "location.locate": "Use my location",
    "location.recent": "Recent",
    "location.mine": "My location",
    range: "Time range",
    "range.1d": "Last 24 hours",
    "range.3d": "Last 3 days",
    "range.1w": "Last 7 days",
    "range.2w": "Last 2 weeks",
    "range.1m": "Last 30 days",
    "range.3m": "Last 3 months",
    "range.6m": "Last 6 months",
    "range.1y": "Last 1 year",
    "chip.1d": "24h",
    "chip.3d": "3d",
    "chip.1w": "7d",
    "chip.2w": "2w",
    "chip.1m": "30d",
    "chip.3m": "3m",
    "chip.6m": "6m",
    "chip.1y": "1y",
    "range.custom": "Custom",
    units: "Units",
    from: "From",
    to: "To",
    apply: "Apply",
    loading: "Loading",
    noscript: "Weather History needs JavaScript to fetch and chart data from Open-Meteo. Please enable it to continue.",
    "download.csv": "Download CSV",
    summary: "Summary",
    charts: "Charts",
    "card.temperature": "Temperature",
    "card.humidity": "Relative humidity",
    "card.aqi": "Air quality",
    "card.png": "Download chart as PNG",
    "card.table": "Table",
    "card.chart": "Chart",
    "card.aqiCategories": "AQI categories",
    "card.hourly": "{unit} · hourly",
    "card.dailyBand": "{unit} · daily low–high range and mean",
    "card.aqiDaily": "US AQI · daily mean",
    "empty.temperature": "No temperature data for this period.",
    "empty.humidity": "No humidity data for this period.",
    "empty.aqi": "No air-quality data for this period — it typically covers only the last 2–3 years.",
    "kpi.temperature": "Avg temperature",
    "kpi.humidity": "Avg humidity",
    "kpi.aqi": "Peak AQI (US)",
    "kpi.coverage": "AQI coverage",
    "kpi.lowHigh": "Low {low} · High {high}",
    "kpi.noData": "No data",
    "kpi.noAqi": "No air-quality data for this period",
    "kpi.readings.hourly": "{n} hourly readings",
    "kpi.readings.daily": "{n} daily readings",
    "granularity.hourly": "Hourly",
    "granularity.daily": "Daily",
    "table.time": "Time",
    "table.date": "Date",
    "table.temperature": "Temperature ({unit})",
    "table.humidity": "Humidity (%)",
    "table.low": "Low ({unit})",
    "table.mean": "Mean ({unit})",
    "table.high": "High ({unit})",
    "table.aria": "{title} data",
    "chart.max": "max",
    "chart.min": "min",
    "chart.high": "High",
    "chart.low": "Low",
    "chart.mean": "Mean",
    "status.enter": "Enter a location to begin.",
    "status.loading": "Loading {place} ({range})…",
    "error.timeout": "Request timed out after {s}s. Try a smaller range or check your network.",
    "error.fetch": "Failed to fetch data: {detail}",
    "error.noMatch": "No matches for \"{q}\"",
    "error.geoUnsupported": "Location isn't available in this browser.",
    "error.geo": "Couldn't use your location: {reason}.",
    "error.geo.denied": "permission was denied",
    "error.geo.timeout": "it took too long",
    "error.geo.unavailable": "your position is unavailable",
    "custom.missing": "Pick both a start and an end date.",
    "custom.order": "The start date must be on or before the end date.",
    "custom.future": "The end date can't be in the future.",
    "custom.tooEarly": "Data is only available from 1940 onwards.",
    "custom.tooLong": "Pick at most {max} days.",
    offline: "You're offline — showing saved data where available.",
    "toast.copied": "Link copied",
    "toast.copyFailed": "Couldn't copy — use the link in the address bar.",
    "toast.shareFailed": "Couldn't open the share sheet.",
    "footer.source": "Source:",
    "footer.reset": "Reset preferences",
    "footer.madeWith": "Made with",
    "footer.by": "by",
    "footer.cities": "Cities",
    "footer.vietnam": "Vietnam",
    "footer.world": "World",
    "footer.about":
      "Weather History shows what the weather and the air were really like in any city: hourly or daily temperature, relative humidity and US Air Quality Index (AQI) for the last 24 hours up to a full year, with the EPA's health guidance. Data comes from the free, open-source Open-Meteo API (ECMWF reanalysis and CAMS air quality). Free to use — no sign-up and no API key.",
    "aqi.good": "Good",
    "aqi.moderate": "Moderate",
    "aqi.usg": "Unhealthy for Sensitive Groups",
    "aqi.usg.short": "Sensitive",
    "aqi.unhealthy": "Unhealthy",
    "aqi.veryUnhealthy": "Very Unhealthy",
    "aqi.hazardous": "Hazardous",
    "aqi.good.advice": "Air quality is satisfactory; little or no risk.",
    "aqi.moderate.advice": "Unusually sensitive people should limit prolonged outdoor exertion.",
    "aqi.usg.advice": "Sensitive groups should reduce prolonged or heavy outdoor exertion.",
    "aqi.unhealthy.advice": "Everyone should reduce prolonged or heavy outdoor exertion.",
    "aqi.veryUnhealthy.advice": "Everyone should avoid prolonged or heavy outdoor exertion.",
    "aqi.hazardous.advice": "Everyone should avoid all outdoor physical activity.",
  },
};

const LOCALES = { vi: "vi-VN", en: "en-US" };

let current = detectLang();

function detectLang() {
  try {
    const saved = localStorage.getItem(LANG_KEY);
    if (LANGS.includes(saved)) return saved;
  } catch { /* storage unavailable */ }
  return DEFAULT_LANG;
}

export function getLang() {
  return current;
}

export function setLang(lang) {
  if (!LANGS.includes(lang)) return;
  current = lang;
  try {
    localStorage.setItem(LANG_KEY, lang);
  } catch { /* storage unavailable */ }
}

export function locale() {
  return LOCALES[current];
}

/** Translate `key`, filling `{name}` placeholders from `vars`. */
export function t(key, vars = {}) {
  const text = STRINGS[current][key] ?? STRINGS.en[key] ?? key;
  return text.replace(/\{(\w+)\}/g, (_, name) => (name in vars ? String(vars[name]) : `{${name}}`));
}

/** All strings for a language (used by tests and the site build). */
export function strings(lang) {
  return STRINGS[lang];
}

/** Fixed-decimal number in the current locale ("25.0" / "25,0"). */
export function formatNumber(value, digits) {
  return new Intl.NumberFormat(locale(), {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    useGrouping: false,
  }).format(value);
}

/** "2026-03-09" -> "Mar 9, 2026" / "9 thg 3, 2026" (noon, so no zone shifts the day). */
export function formatDate(ymd) {
  return new Intl.DateTimeFormat(locale(), {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(`${ymd}T12:00:00`));
}

/** Re-label every element carrying data-i18n* attributes. */
export function applyStaticStrings(root = document) {
  for (const el of root.querySelectorAll("[data-i18n]")) el.textContent = t(el.dataset.i18n);
  const attrs = { i18nAria: "aria-label", i18nTitle: "title", i18nPlaceholder: "placeholder" };
  for (const [dataKey, attr] of Object.entries(attrs)) {
    const selector = `[data-${dataKey.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)}]`;
    for (const el of root.querySelectorAll(selector)) el.setAttribute(attr, t(el.dataset[dataKey]));
  }
  document.documentElement.lang = current;
}

// Plotly month/day names for Vietnamese (English is Plotly's default).
export const PLOTLY_VI_LOCALE = {
  moduleType: "locale",
  name: "vi",
  dictionary: {},
  format: {
    days: ["Chủ nhật", "Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy"],
    shortDays: ["CN", "T2", "T3", "T4", "T5", "T6", "T7"],
    months: [
      "Tháng 1", "Tháng 2", "Tháng 3", "Tháng 4", "Tháng 5", "Tháng 6",
      "Tháng 7", "Tháng 8", "Tháng 9", "Tháng 10", "Tháng 11", "Tháng 12",
    ],
    shortMonths: ["Th1", "Th2", "Th3", "Th4", "Th5", "Th6", "Th7", "Th8", "Th9", "Th10", "Th11", "Th12"],
    date: "%d/%m/%Y",
  },
};
