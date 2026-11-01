// Guided navigation helpers: walking routes and distances.
//
// Walking routes come from the FOSSGIS OpenStreetMap routing service (OSRM, foot profile).
// It receives the start and end points and keeps them in its server logs, so a route is
// only requested when the person explicitly asks, after being told. Usage policy: at most
// one request per second, no heavy use, attribution + "fix the map" link required.

const ROUTER = "https://routing.openstreetmap.de/routed-foot/route/v1/foot";
const MIN_INTERVAL_MS = 1100; // FOSSGIS: max 1 request per second
let lastRequest = 0;

export const ROUTING_ATTRIBUTION =
  'Walking routes: <a href="https://routing.openstreetmap.de/about.html">FOSSGIS</a> / OSRM · ' +
  '<a href="https://www.openstreetmap.org/fixthemap">Fix the map</a>';

export function haversineM([lat1, lng1], [lat2, lng2]) {
  const r = Math.PI / 180;
  const h = Math.sin(((lat2 - lat1) * r) / 2) ** 2 +
    Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(((lng2 - lng1) * r) / 2) ** 2;
  return 2 * 6371000 * Math.asin(Math.sqrt(h));
}

export function formatDistance(metres) {
  if (metres < 1000) return `${Math.round(metres / 10) * 10} m`;
  return `${(metres / 1000).toFixed(1)} km`;
}

export function formatMinutes(minutes) {
  const m = Math.max(1, Math.round(minutes));
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

/** Straight-line walking estimate: streets are ~30% longer, walking ~4.8 km/h. */
export function estimateWalkMinutes(metres) {
  return (metres * 1.3) / 80;
}

/**
 * @returns {Promise<{distance_m:number, duration_min:number, latlngs:[number,number][]}>}
 */
export async function walkingRoute([fromLat, fromLng], [toLat, toLng]) {
  const wait = lastRequest + MIN_INTERVAL_MS - Date.now();
  if (wait > 0) await new Promise((r) => setTimeout(r, wait));
  lastRequest = Date.now();

  const coords = `${fromLng.toFixed(6)},${fromLat.toFixed(6)};${toLng.toFixed(6)},${toLat.toFixed(6)}`;
  const response = await fetch(`${ROUTER}/${coords}?overview=full&geometries=geojson&steps=false`);
  if (!response.ok) throw new Error("The walking-route service didn't respond.");
  const data = await response.json();
  const route = data.routes?.[0];
  if (data.code !== "Ok" || !route) throw new Error("No walking route was found to this place.");
  return {
    distance_m: route.distance,
    duration_min: route.duration / 60,
    latlngs: route.geometry.coordinates.map(([lng, lat]) => [lat, lng]),
  };
}

/** Google Maps walking directions to a destination. Google uses the phone's own location. */
export function googleMapsUrl([lat, lng]) {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat.toFixed(6)},${lng.toFixed(6)}&travelmode=walking`;
}
