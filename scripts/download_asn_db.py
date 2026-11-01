"""Download the free DB-IP "IP to ASN Lite" database (CC-BY 4.0, https://db-ip.com).

Saves data/asn/dbip-asn-lite.mmdb (git-ignored). DB-IP publishes a new file each month;
re-run this monthly. The licence requires attribution to DB-IP.com (shown on the
Privacy page and in the README).

Run:  python scripts/download_asn_db.py
"""
import gzip
import shutil
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "data" / "asn" / "dbip-asn-lite.mmdb"
URL = "https://download.db-ip.com/free/dbip-asn-lite-{month}.mmdb.gz"


def candidate_months(today: date) -> list[str]:
    previous = date(today.year - (today.month == 1), (today.month - 2) % 12 + 1, 1)
    return [today.strftime("%Y-%m"), previous.strftime("%Y-%m")]


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    for month in candidate_months(date.today()):
        url = URL.format(month=month)
        print(f"Downloading {url} …")
        try:
            # DB-IP rejects Python's default User-Agent, so identify the project instead.
            request = urllib.request.Request(url, headers={"User-Agent": "speedspot-mapper/1.0 (asn-db-download)"})
            # Fixed https:// URL above, never user input.
            with urllib.request.urlopen(request, timeout=120) as response, gzip.GzipFile(fileobj=response) as gz:  # nosec B310
                tmp = TARGET.with_suffix(".tmp")
                with tmp.open("wb") as out:
                    shutil.copyfileobj(gz, out)
            tmp.replace(TARGET)
        except urllib.error.HTTPError as exc:
            print(f"  not available ({exc.code}), trying the previous month")
            continue
        import maxminddb  # verify the file opens and answers a lookup
        with maxminddb.open_database(str(TARGET)) as reader:
            sample = reader.get("1.1.1.1")
        print(f"Saved {TARGET} ({TARGET.stat().st_size / 1e6:.1f} MB). Check: 1.1.1.1 → {sample}")
        return
    sys.exit("Could not download the DB-IP ASN Lite database.")


if __name__ == "__main__":
    main()
