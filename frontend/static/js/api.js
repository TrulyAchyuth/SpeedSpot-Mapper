// Client for the SpeedSpot JSON API (/api/v1). Errors always carry a friendly message.

export class ApiError extends Error {
  constructor(message, { code = "error", status = 0, details = null } = {}) {
    super(message);
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

const OFFLINE_MESSAGE = "We couldn't reach SpeedSpot. Check your internet connection and try again.";

async function request(path, { params, method = "GET", body } = {}) {
  const url = new URL(`/api/v1${path}`, window.location.origin);
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, value);
  }
  let response;
  try {
    response = await fetch(url, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(OFFLINE_MESSAGE, { code: "network" });
  }
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    /* non-JSON response */
  }
  if (!response.ok) {
    const error = payload?.error || {};
    throw new ApiError(error.message || "Something went wrong. Please try again.", {
      code: error.code, status: response.status, details: error.details,
    });
  }
  return payload;
}

const get = async (path, params) => (await request(path, { params })).data;

/** filters = { period, provider } from filters.js; empty values are left out of the URL. */
const f = (filters = {}) => ({ period: filters.period, provider: filters.provider });

export const api = {
  regionStats: (code, filters) => get(`/regions/${encodeURIComponent(code)}/stats`, f(filters)),
  cellStats: (cell, filters) => get(`/cells/${encodeURIComponent(cell)}/stats`, f(filters)),
  cells: (bbox, precision, filters) => get("/cells", { bbox: bbox.join(","), precision, ...f(filters) }),
  search: (q) => get("/search", { q }),
  locate: (cell) => get("/locate", { cell }),
  providers: () => get("/providers"),
  mapStates: (filters) => get("/map/states", f(filters)),
  rankings: (area, filters) => get("/providers/rankings", { area, period: filters?.period }),
  insights: (area, filters) => get("/insights", { area, ...f(filters) }),
  nearby: (cell, radius, filters) => get("/navigation/nearby", { cell, radius, ...f(filters) }),
  myProvider: () => get("/me/provider"),
  statistics: (area, filters) => get("/statistics", { area, ...f(filters) }),
  submitMeasurement: async (measurement) =>
    (await request("/measurements", { method: "POST", body: measurement })).data,
};

export function exportUrl(area, type, filters = {}) {
  const url = new URL("/api/v1/export/areas.csv", window.location.origin);
  for (const [key, value] of Object.entries({ area, type, ...f(filters) })) {
    if (value) url.searchParams.set(key, value);
  }
  return url.pathname + url.search;
}

/** Region codes start with "IN"; anything else is a geohash cell. */
export const statsFor = (area, filters) =>
  area.toUpperCase().startsWith("IN") ? api.regionStats(area, filters) : api.cellStats(area, filters);
