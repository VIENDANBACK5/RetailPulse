"""Compatibility launcher for the canonical official UCI downloader."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.utils.data_downloader import prepare_uci_data


def main():
    path = prepare_uci_data()
    print(path)
    return path


if __name__ == '__main__':
    main()
