"""Network Quality Index (slide 7) — shown to the public as the "Connection Score".

NQI = 100 × (0.40·D + 0.20·U + 0.25·L + 0.15·J)
  D = min(download / 50 Mbps, 1)      U = min(upload / 20 Mbps, 1)
  L = max(0, 1 − latency / 200 ms)    J = max(0, 1 − jitter / 50 ms)
"""
WEIGHTS = {"download": 0.40, "upload": 0.20, "latency": 0.25, "jitter": 0.15}
DOWNLOAD_CAP_MBPS = 50.0
UPLOAD_CAP_MBPS = 20.0
LATENCY_LIMIT_MS = 200.0
JITTER_LIMIT_MS = 50.0

GOOD_MIN = 70
FAIR_MIN = 40


def components(download_mbps: float, upload_mbps: float, latency_ms: float, jitter_ms: float) -> dict:
    return {
        "download": min(download_mbps / DOWNLOAD_CAP_MBPS, 1.0),
        "upload": min(upload_mbps / UPLOAD_CAP_MBPS, 1.0),
        "latency": max(0.0, 1.0 - latency_ms / LATENCY_LIMIT_MS),
        "jitter": max(0.0, 1.0 - jitter_ms / JITTER_LIMIT_MS),
    }


def calculate(download_mbps: float, upload_mbps: float, latency_ms: float, jitter_ms: float) -> float:
    parts = components(download_mbps, upload_mbps, latency_ms, jitter_ms)
    return round(100 * sum(WEIGHTS[k] * v for k, v in parts.items()), 1)


def band(score: float | None) -> str | None:
    """'good' (70–100), 'fair' (40–69), 'weak' (0–39), or None when there is no score."""
    if score is None:
        return None
    if score >= GOOD_MIN:
        return "good"
    if score >= FAIR_MIN:
        return "fair"
    return "weak"
