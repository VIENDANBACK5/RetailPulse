"""Download the original UCI workbook with source URL and checksum."""
from pathlib import Path
import hashlib
import io
import json
import zipfile
import requests

URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"


def main():
    folder = Path(__file__).resolve().parents[1] / "data_lake/raw/uci"
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / "online_retail_II.xlsx"
    downloaded = False
    if not destination.exists():
        response = requests.get(URL, timeout=180)
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".xlsx")]
            if len(names) != 1:
                raise ValueError("Unexpected UCI archive contents")
            payload = archive.read(names[0])
        temporary = destination.with_suffix(".download")
        temporary.write_bytes(payload)
        temporary.replace(destination)
        downloaded = True
    sidecar = destination.with_suffix(".xlsx.metadata.json")
    if downloaded:
        metadata = {"data_mode": "historical", "source_url": URL,
                    "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}
        sidecar.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(destination)
    print(sidecar.read_text(encoding="utf-8") if sidecar.exists() else "Existing workbook: provenance unverified")


if __name__ == "__main__":
    main()
