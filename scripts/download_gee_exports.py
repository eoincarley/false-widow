#!/usr/bin/env python3
"""
download_gee_exports.py
=======================
Verify that GEE export files have been downloaded from Google Drive
to the local project directory.

After gee_extract.py completes its export tasks, download all files
from the Google Drive folder 'false_widow_gee/' and place them in:
    data/raw/gee/

The point extraction may produce batched files:
    sn_point_extract_all_bands_batch1.csv
    sn_point_extract_all_bands_batch2.csv
    ...
These will be detected automatically via glob pattern matching.

Usage:
    python scripts/download_gee_exports.py
"""

import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GEE_DIR = PROJECT_ROOT / "data" / "raw" / "gee"

# Raster files (exact names)
RASTER_FILES = [
    "viirs_dnb_median_radiance.tif",
    "modis_lst_mean_day_night.tif",
    "landsat_lst_summer_median_500m.tif",
    "landsat_lst_summer_ireland_100m.tif",
]

# Point extraction files (may be batched or single)
POINT_PATTERN = "sn_point_extract_all_bands*.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def check_local_files():
    """Check which expected GEE files are already present locally."""
    GEE_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("GEE Export File Status")
    print("=" * 60)
    print(f"  Local directory: {GEE_DIR}\n")

    all_ok = True

    # Check raster files
    print("  Raster layers:")
    for fname in RASTER_FILES:
        fpath = GEE_DIR / fname
        if fpath.exists():
            size_mb = fpath.stat().st_size / (1024 * 1024)
            print(f"    [OK]      {fname:45s} ({size_mb:.1f} MB)")
        else:
            print(f"    [MISSING] {fname}")
            all_ok = False

    # Check point extraction files (glob for batched or single)
    print("\n  Point extraction:")
    point_files = sorted(GEE_DIR.glob(POINT_PATTERN))
    if point_files:
        total_rows = 0
        for pf in point_files:
            size_mb = pf.stat().st_size / (1024 * 1024)
            # Count lines (minus header)
            with open(pf) as f:
                n_lines = sum(1 for _ in f) - 1
            total_rows += n_lines
            print(f"    [OK]      {pf.name:45s} ({size_mb:.1f} MB, {n_lines} rows)")
        print(f"    Total point records: {total_rows}")
    else:
        print(f"    [MISSING] No files matching '{POINT_PATTERN}'")
        all_ok = False

    print()
    if all_ok:
        print("  All files present. Ready for Phase 3 (raster processing).")
    else:
        print("  Some files are missing. Download them from Google Drive:")
        print(f"    Folder: 'false_widow_gee/'")
        print(f"    Place them in: {GEE_DIR}/")

    print("=" * 60 + "\n")
    return all_ok


if __name__ == "__main__":
    check_local_files()
