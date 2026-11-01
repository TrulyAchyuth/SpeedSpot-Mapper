// Plain-language formatting. Public pages never show raw technical terms.

export const BAND_LABEL = { good: "Good", fair: "Fair", weak: "Weak" };

export const BAND_VERDICT = {
  good: "Great for video calls, HD streaming and working from home.",
  fair: "Fine for browsing and video. Calls may sometimes stutter.",
  weak: "Expect slow loading and unreliable video calls.",
};

export const METRICS = [
  { key: "download_mbps", label: "Download", hint: "How fast things load", unit: "Mbps", icon: "download" },
  { key: "upload_mbps", label: "Upload", hint: "Sending photos and video", unit: "Mbps", icon: "upload" },
  { key: "latency_ms", label: "Response time", hint: "How quickly it reacts", unit: "ms", icon: "pulse" },
  { key: "jitter_ms", label: "Stability", hint: "Lower is steadier", unit: "ms", icon: "wave" },
];

const numberFormat = new Intl.NumberFormat("en-IN");

export function number(value) {
  return numberFormat.format(value);
}

export function speed(value) {
  if (value === null || value === undefined) return "–";
  return value >= 100 ? String(Math.round(value)) : value.toFixed(1).replace(/\.0$/, "");
}

export function metricValue(key, value) {
  if (value === null || value === undefined) return "–";
  return key.endsWith("_mbps") ? speed(value) : String(Math.round(value));
}

export function plural(count, singular, pluralWord = `${singular}s`) {
  return `${number(count)} ${count === 1 ? singular : pluralWord}`;
}

export function timeAgo(iso) {
  if (!iso) return null;
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  if (seconds < 3600) return "within the last hour";
  const hours = Math.floor(seconds / 3600);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  const months = Math.floor(days / 30);
  return `${months} month${months === 1 ? "" : "s"} ago`;
}

export const LEVEL_NOUN = {
  country: "India", state: "state", district: "district", city: "city",
  neighbourhood: "neighbourhood", block: "block",
};

export const PROVIDER_KIND = { mobile: "Mobile", broadband: "Broadband", both: "Mobile & broadband" };

// Mirrors backend/services/nqi.py, for showing the user's own result instantly.
// The server always recalculates the score itself.
export function connectionScore({ download_mbps, upload_mbps, latency_ms, jitter_ms }) {
  const d = Math.min(download_mbps / 50, 1);
  const u = Math.min(upload_mbps / 20, 1);
  const l = Math.max(0, 1 - latency_ms / 200);
  const j = Math.max(0, 1 - jitter_ms / 50);
  return Math.round(100 * (0.4 * d + 0.2 * u + 0.25 * l + 0.15 * j));
}

export function bandFor(score) {
  if (score === null || score === undefined) return null;
  return score >= 70 ? "good" : score >= 40 ? "fair" : "weak";
}
