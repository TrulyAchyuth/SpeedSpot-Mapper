"""Identify a visitor's internet provider from their IP address (IP → ASN → provider).

Privacy: the IP address is used only inside `identify()`, in memory, and is never stored
or logged. What we keep is the ASN — a number identifying the network operator (a
company), not a person.

Data: DB-IP "IP to ASN Lite" (CC-BY 4.0, https://db-ip.com), a local file read with
`maxminddb`, so no third-party service ever sees our visitors' IP addresses.
Download it with `python scripts/download_asn_db.py`.

Honesty rules:
  - "identified"     ASN belongs to a provider in our curated list (reference/providers.json)
  - "other_isp"      a real ISP we don't list separately; shown as its operator name
  - "vpn_or_hosting" a VPN, proxy or cloud network: the test measured that network, not the
                     local connection, so the result is kept out of area scores
  - "unknown"        private/local address, address not in the database, or no database
"""
import ipaddress
import re
from dataclasses import dataclass
from pathlib import Path

from flask import current_app

from ..extensions import db
from ..models import Provider, ProviderASN

# Large cloud, CDN, hosting and VPN-infrastructure networks. Each organisation name was
# checked in the DB-IP data (2026-11).
HOSTING_ASNS = {
    13335,          # Cloudflare (incl. WARP)
    15169,          # Google
    16509, 14618,   # Amazon
    8075,           # Microsoft
    31898,          # Oracle
    45102,          # Alibaba
    132203,         # Tencent
    14061,          # DigitalOcean
    16276,          # OVH
    24940,          # Hetzner
    20473,          # The Constant Company (Vultr)
    63949, 20940,   # Akamai / Linode
    51167,          # Contabo
    62240,          # Clouvider
    53667,          # FranTech
    396356,         # Latitude.sh
    9009,           # M247 (widely used by VPN services)
    60068, 212238,  # Datacamp / CDN77 (widely used by VPN services)
    136787,         # PacketHub (widely used by VPN services)
}
HOSTING_PATTERN = re.compile(
    r"hosting|\bcloud\b|data ?cent(er|re)|vpn|\bvps\b|colocation|dedicated server|server hosting", re.I)

MESSAGES = {
    "identified": "You appear to be using {name}.",
    "other_isp": "You appear to be on {org}. We don't list this provider separately yet.",
    "vpn_or_hosting": ("Your connection seems to go through a VPN, proxy or cloud network. A test would "
                       "measure that network rather than your local one, so it won't count towards area scores."),
    "unknown": "We couldn't identify your provider. Your test still works.",
}


@dataclass(frozen=True)
class Identification:
    status: str
    provider: Provider | None = None
    asn: int | None = None
    asn_org: str | None = None

    @property
    def counts_towards_scores(self) -> bool:
        return self.status != "vpn_or_hosting"

    def to_public(self) -> dict:
        message = MESSAGES[self.status].format(
            name=self.provider.name if self.provider else "", org=self.asn_org or "an unlisted provider")
        return {
            "status": self.status,
            "provider": self.provider.to_summary() if self.provider else None,
            "network": self.asn_org if self.status == "other_isp" else None,
            "counts_towards_scores": self.counts_towards_scores,
            "message": message,
        }


class AsnDatabase:
    """Read-only wrapper around the local IP → ASN database file."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._reader = None
        if self.path.exists():
            import maxminddb
            self._reader = maxminddb.open_database(str(self.path))

    @property
    def available(self) -> bool:
        return self._reader is not None

    def lookup(self, ip: str) -> tuple[int, str] | None:
        if self._reader is None:
            return None
        try:
            record = self._reader.get(ip)
        except ValueError:
            return None
        if not record or "autonomous_system_number" not in record:
            return None
        return record["autonomous_system_number"], record.get("autonomous_system_organization") or ""


def get_asn_database():
    """One reader per app; tests can replace it via app.extensions["asn_database"]."""
    extensions = current_app.extensions
    if "asn_database" not in extensions:
        extensions["asn_database"] = AsnDatabase(current_app.config["ASN_DATABASE_PATH"])
    return extensions["asn_database"]


def identify(ip: str | None) -> Identification:
    try:
        address = ipaddress.ip_address(ip or "")
    except ValueError:
        return Identification("unknown")
    if not address.is_global:  # 127.0.0.1, 192.168.x.x, … (e.g. local development)
        return Identification("unknown")

    found = get_asn_database().lookup(str(address))
    if found is None:
        return Identification("unknown")
    asn, org = found

    link = db.session.get(ProviderASN, asn)
    if link is not None:
        return Identification("identified", link.provider, asn, org)
    if asn in HOSTING_ASNS or HOSTING_PATTERN.search(org):
        return Identification("vpn_or_hosting", None, asn, org)
    return Identification("other_isp", None, asn, org)
