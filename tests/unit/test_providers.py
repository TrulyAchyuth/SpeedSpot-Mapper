"""Provider identification: IP → ASN → provider, with honest VPN/unknown handling."""
import re
from pathlib import Path

import pytest
from sqlalchemy import func, select

from backend.extensions import db
from backend.models import Provider, ProviderASN
from backend.services import providers
from backend.services.regions import REFERENCE_DIR, load_reference, seed_providers
from tests.conftest import CLOUD_IP, JIO_IP, OTHER_ISP_IP, UNLISTED_IP

REAL_DB = Path(__file__).resolve().parents[2] / "data" / "asn" / "dbip-asn-lite.mmdb"


def test_known_provider_is_identified(seeded, asn_db):
    result = providers.identify(JIO_IP)
    assert result.status == "identified"
    assert result.provider.name == "Jio"
    assert result.asn == 55836
    assert result.counts_towards_scores


def test_cloud_and_vpn_networks_are_flagged(seeded, asn_db):
    result = providers.identify(CLOUD_IP)
    assert result.status == "vpn_or_hosting"
    assert result.provider is None
    assert not result.counts_towards_scores
    assert "VPN" in result.to_public()["message"]


def test_unlisted_isp_is_reported_by_name_not_guessed(seeded, asn_db):
    result = providers.identify(OTHER_ISP_IP)
    assert result.status == "other_isp"
    public = result.to_public()
    assert public["provider"] is None and public["network"] == "Example Broadband Pvt Ltd"


@pytest.mark.parametrize("ip", [UNLISTED_IP, "127.0.0.1", "192.168.1.20", "10.0.0.1", "::1", "not-an-ip", "", None])
def test_unknown_and_private_addresses(seeded, asn_db, ip):
    assert providers.identify(ip).status == "unknown"


def test_private_addresses_are_never_looked_up(seeded, asn_db):
    providers.identify("192.168.1.20")
    assert asn_db.lookups == []


def test_hosting_keywords():
    assert providers.HOSTING_PATTERN.search("Example Hosting Ltd")
    assert providers.HOSTING_PATTERN.search("Acme Data Center LLC")
    assert providers.HOSTING_PATTERN.search("FastVPN Inc")
    assert not providers.HOSTING_PATTERN.search("RailTel Corporation is an Internet Service Provider")
    assert not providers.HOSTING_PATTERN.search("Bharti Airtel Limited")


def test_missing_database_means_unknown_not_an_error(seeded):
    db_file = providers.AsnDatabase("/nonexistent.mmdb")
    assert not db_file.available
    assert db_file.lookup(JIO_IP) is None
    assert providers.identify(JIO_IP).status == "unknown"


def test_provider_seeding_includes_asns_and_is_idempotent(seeded):
    seed_providers()
    data = load_reference(REFERENCE_DIR / "providers.json")["providers"]
    assert db.session.scalar(select(func.count(Provider.id))) == len(data)
    assert db.session.scalar(select(func.count(ProviderASN.asn))) == sum(len(p["asns"]) for p in data)
    airtel = db.session.scalar(select(Provider).where(Provider.slug == "airtel"))
    assert sorted(a.asn for a in airtel.asns) == [9498, 9730, 24560, 45609]


def test_registry_has_no_duplicate_asns():
    asns = [a for p in load_reference(REFERENCE_DIR / "providers.json")["providers"] for a in p["asns"]]
    assert len(asns) == len(set(asns))
    assert not set(asns) & providers.HOSTING_ASNS


# ---------- Checks against the real DB-IP file (skipped if it isn't downloaded) ----------

@pytest.fixture(scope="module")
def real_asn_names():
    if not REAL_DB.exists():
        pytest.skip("Real ASN database not downloaded (python scripts/download_asn_db.py)")
    import maxminddb
    names = {}
    with maxminddb.open_database(str(REAL_DB)) as reader:
        for _network, record in reader:
            names[record["autonomous_system_number"]] = record.get("autonomous_system_organization", "")
    return names


EXPECTED_ORG = {
    "jio": r"reliance jio", "airtel": r"bharti airtel", "vi": r"vodafone idea", "bsnl": r"bharat sanchar",
    "mtnl": r"mahanagar telephone", "act": r"atria convergence", "hathway": r"hathway", "excitel": r"excitel",
    "tata-play": r"tata play", "tata-tele": r"tata teleservices", "you": r"you broadband",
    "alliance": r"alliance broadband", "spectra": r"spectra", "asianet": r"asianet", "gtpl": r"gtpl",
    "tikona": r"tikona", "railwire": r"railtel", "sify": r"^sify",
}


def test_every_registry_asn_belongs_to_that_company(real_asn_names):
    for provider in load_reference(REFERENCE_DIR / "providers.json")["providers"]:
        for asn in provider["asns"]:
            org = real_asn_names.get(asn, "")
            assert re.search(EXPECTED_ORG[provider["slug"]], org, re.I), f"{provider['slug']} AS{asn} is '{org}'"


def test_hosting_asns_are_really_hosting_companies(real_asn_names):
    for asn in providers.HOSTING_ASNS:
        assert real_asn_names.get(asn), f"AS{asn} not in database"


def test_real_lookups(seeded):
    if not REAL_DB.exists():
        pytest.skip("Real ASN database not downloaded")
    seeded.extensions["asn_database"] = providers.AsnDatabase(REAL_DB)
    assert providers.identify(JIO_IP).provider.slug == "jio"
    assert providers.identify(CLOUD_IP).status == "vpn_or_hosting"
