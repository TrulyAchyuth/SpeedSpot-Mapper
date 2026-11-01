"""Geohash encoding/decoding (the ~150 m grid). Mirrors frontend/static/js/geohash.js.

A geohash interleaves longitude and latitude bits and writes them in base-32.
Each extra character makes the cell 32× smaller; precision 7 ≈ 153 m × 150 m in India.
"""
BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
_DECODE = {c: i for i, c in enumerate(BASE32)}

BLOCK_PRECISION = 7          # ~150 m — what a measurement is stored at
NEIGHBOURHOOD_PRECISION = 6  # ~1.2 km × 0.6 km


def encode(lat: float, lng: float, precision: int = BLOCK_PRECISION) -> str:
    lat_range, lng_range = [-90.0, 90.0], [-180.0, 180.0]
    chars, bits, bit_count, even = [], 0, 0, True
    while len(chars) < precision:
        rng, value = (lng_range, lng) if even else (lat_range, lat)
        mid = (rng[0] + rng[1]) / 2
        if value >= mid:
            bits = (bits << 1) | 1
            rng[0] = mid
        else:
            bits <<= 1
            rng[1] = mid
        even = not even
        bit_count += 1
        if bit_count == 5:
            chars.append(BASE32[bits])
            bits, bit_count = 0, 0
    return "".join(chars)


def is_valid(cell: str, precision: int | None = None) -> bool:
    if not isinstance(cell, str) or not cell or not all(c in _DECODE for c in cell):
        return False
    return precision is None or len(cell) == precision


def bounds(cell: str) -> tuple[float, float, float, float]:
    """(south, west, north, east) of a geohash cell."""
    lat_range, lng_range = [-90.0, 90.0], [-180.0, 180.0]
    even = True
    for char in cell:
        value = _DECODE[char]
        for shift in range(4, -1, -1):
            rng = lng_range if even else lat_range
            mid = (rng[0] + rng[1]) / 2
            if (value >> shift) & 1:
                rng[0] = mid
            else:
                rng[1] = mid
            even = not even
    return lat_range[0], lng_range[0], lat_range[1], lng_range[1]


def center(cell: str) -> tuple[float, float]:
    south, west, north, east = bounds(cell)
    return (south + north) / 2, (west + east) / 2
