// Run with: node --test "tests/js/*.test.mjs"
// Same vectors as tests/unit/test_nqi_geohash.py, so the browser and server agree exactly.
import assert from "node:assert/strict";
import { test } from "node:test";

import { bounds, encode } from "../../frontend/static/js/geohash.js";
import { bandFor, connectionScore } from "../../frontend/static/js/format.js";
import { fraction } from "../../frontend/static/js/gauge.js";

const VECTORS = [
  [57.64911, 10.40744, 11, "u4pruydqqvj"],
  [42.6, -5.6, 5, "ezs42"],
  [12.8406, 80.1534, 7, "tf2cpct"],
];

test("geohash encode matches the Python implementation", () => {
  for (const [lat, lng, precision, expected] of VECTORS) assert.equal(encode(lat, lng, precision), expected);
});

test("geohash bounds contain the encoded point", () => {
  for (const [lat, lng, , code] of VECTORS) {
    const [s, w, n, e] = bounds(code);
    assert.ok(s <= lat && lat <= n && w <= lng && lng <= e);
  }
});

test("connection score mirrors the server formula (slide 7 example)", () => {
  assert.equal(connectionScore({ download_mbps: 38, upload_mbps: 12, latency_ms: 45, jitter_ms: 8 }), 74);
  assert.equal(connectionScore({ download_mbps: 500, upload_mbps: 200, latency_ms: 0, jitter_ms: 0 }), 100);
  assert.equal(bandFor(70), "good");
  assert.equal(bandFor(69), "fair");
  assert.equal(bandFor(39), "weak");
});

test("gauge scale is monotonic and bounded", () => {
  assert.equal(fraction(0), 0);
  assert.equal(fraction(1000), 1);
  assert.equal(fraction(5000), 1);
  let previous = -1;
  for (const v of [0, 1, 5, 9, 10, 25, 49, 50, 100, 300, 999]) {
    assert.ok(fraction(v) > previous);
    previous = fraction(v);
  }
});
