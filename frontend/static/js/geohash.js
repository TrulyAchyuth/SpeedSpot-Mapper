// Geohash — mirrors backend/utils/geohash.py (same test vectors in both test suites).
// Used to turn a GPS position into a ~150 m area code ON THE DEVICE, so the exact
// location never has to be sent anywhere.

const BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz";

export function encode(lat, lng, precision = 7) {
  const latRange = [-90, 90];
  const lngRange = [-180, 180];
  let hash = "";
  let bits = 0;
  let bitCount = 0;
  let even = true;
  while (hash.length < precision) {
    const range = even ? lngRange : latRange;
    const value = even ? lng : lat;
    const mid = (range[0] + range[1]) / 2;
    if (value >= mid) {
      bits = (bits << 1) | 1;
      range[0] = mid;
    } else {
      bits <<= 1;
      range[1] = mid;
    }
    even = !even;
    if (++bitCount === 5) {
      hash += BASE32[bits];
      bits = 0;
      bitCount = 0;
    }
  }
  return hash;
}

/** [south, west, north, east] */
export function bounds(hash) {
  const latRange = [-90, 90];
  const lngRange = [-180, 180];
  let even = true;
  for (const char of hash) {
    const value = BASE32.indexOf(char);
    for (let shift = 4; shift >= 0; shift--) {
      const range = even ? lngRange : latRange;
      const mid = (range[0] + range[1]) / 2;
      if ((value >> shift) & 1) range[0] = mid;
      else range[1] = mid;
      even = !even;
    }
  }
  return [latRange[0], lngRange[0], latRange[1], lngRange[1]];
}
