#!/usr/bin/env python3
"""
extract_points_local.py
=======================
Extract satellite raster values at occurrence point locations using
local GeoTIFF files (exported from GEE) and rasterio.

This replaces the GEE server-side point extraction which hits memory
limits. Local extraction is faster and more reliable.

Input:
    data/processed/sn_occurrences_cleaned.gpkg  (occurrence points)
    data/raw/gee/viirs_dnb_median_radiance.tif
    data/raw/gee/modis_lst_mean_day_night.tif
    data/raw/gee/landsat_lst_summer_median_500m.tif

Output:
    data/processed/sn_occurrences_with_satellite.csv
    data/processed/sn_occurrences_with_satellite.gpkg

Usage:
    python scripts/extract_points_local.py
"""

import logging
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROC_DIR = PROJECT_ROOT / "data" / "processed"
GEE_DIR = PROJECT_ROOT / "data" / "raw" / "gee"

# Input
OCCURRENCE_GPKG = PROC_DIR / "sn_occurrences_cleaned.gpkg"

# Raster files and the band names to extract from each
# Format: (filename, [(band_index, output_column_name), ...])
RASTER_LAYERS = [
    (
        "viirs_dnb_median_radiance.tif",
        [(1, "viirs_avg_rad")],  # single-band: avg radiance (nW/cm²/sr)
    ),
    (
        "modis_lst_mean_day_night.tif",
        [
            (1, "modis_lst_day_c"),    # band 1: mean daytime LST (°C)
            (2, "modis_lst_night_c"),   # band 2: mean nighttime LST (°C)
        ],
    ),
    (
        "landsat_lst_summer_median_500m.tif",
        [(1, "landsat_lst_summer_c")],  # single-band: summer median LST (°C)
    ),
]

# Output
OUT_CSV = PROC_DIR / "sn_occurrences_with_satellite.csv"
OUT_GPKG = PROC_DIR / "sn_occurrences_with_satellite.gpkg"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Raster sampling
# ---------------------------------------------------------------------------

def sample_raster_at_points(
    raster_path: Path,
    lons: np.ndarray,
    lats: np.ndarray,
    band_index: int = 1,
) -> np.ndarray:
    """
    Sample a single raster band at an array of lon/lat coordinates.

    Uses nearest-pixel sampling (no interpolation). Points falling
    outside the raster extent or on nodata pixels return NaN.

    Parameters
    ----------
    raster_path : Path
        Path to the GeoTIFF file.
    lons : np.ndarray
        Longitude values (EPSG:4326).
    lats : np.ndarray
        Latitude values (EPSG:4326).
    band_index : int
        1-based band index to read.

    Returns
    -------
    np.ndarray
        Sampled values, same length as lons/lats. NaN where no data.
    """
    values = np.full(len(lons), np.nan)

    with rasterio.open(raster_path) as src:
        band = src.read(band_index)
        nodata = src.nodata
        transform = src.transform

        # Convert lon/lat to pixel row/col
        for i, (lon, lat) in enumerate(zip(lons, lats)):
            try:
                row, col = rowcol(transform, lon, lat)
            except Exception:
                continue

            # Check bounds
            if 0 <= row < src.height and 0 <= col < src.width:
                val = band[row, col]
                # Check nodata
                if nodata is not None and val == nodata:
                    continue
                # Check for common GEE nodata sentinel values
                if val == 0.0 or val < -999:
                    continue
                values[i] = float(val)

    return values


def extract_all_layers(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Extract values from all configured raster layers at occurrence points.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Occurrence points with geometry in EPSG:4326.

    Returns
    -------
    gpd.GeoDataFrame
        Input GeoDataFrame with new columns for each extracted band.
    """
    lons = gdf.geometry.x.values
    lats = gdf.geometry.y.values

    for raster_file, bands in RASTER_LAYERS:
        raster_path = GEE_DIR / raster_file

        if not raster_path.exists():
            logger.warning("Raster not found, skipping: %s", raster_path)
            for _, col_name in bands:
                gdf[col_name] = np.nan
            continue

        # Log raster info
        with rasterio.open(raster_path) as src:
            logger.info(
                "Sampling %s: %d x %d px, %d band(s), CRS=%s",
                raster_file, src.width, src.height, src.count, src.crs,
            )

        for band_idx, col_name in bands:
            values = sample_raster_at_points(raster_path, lons, lats, band_idx)
            gdf[col_name] = values

            n_valid = np.isfinite(values).sum()
            n_total = len(values)
            logger.info(
                "  Band %d → '%s': %d/%d points have data (%.1f%%)",
                band_idx, col_name, n_valid, n_total,
                100 * n_valid / n_total if n_total > 0 else 0,
            )

    return gdf


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(gdf: gpd.GeoDataFrame) -> None:
    """Print summary statistics of extracted satellite values."""
    sat_cols = [
        "viirs_avg_rad",
        "modis_lst_day_c",
        "modis_lst_night_c",
        "landsat_lst_summer_c",
    ]

    print("\n" + "=" * 60)
    print("Point Extraction Summary")
    print("=" * 60)
    print(f"  Total occurrence points: {len(gdf)}\n")

    for col in sat_cols:
        if col not in gdf.columns:
            print(f"  {col:30s}  [not extracted]")
            continue

        valid = gdf[col].dropna()
        n_valid = len(valid)
        n_total = len(gdf)
        pct = 100 * n_valid / n_total if n_total > 0 else 0

        if n_valid > 0:
            print(f"  {col:30s}  n={n_valid:5d} ({pct:4.1f}%)  "
                  f"min={valid.min():8.2f}  median={valid.median():8.2f}  "
                  f"max={valid.max():8.2f}")
        else:
            print(f"  {col:30s}  n=0 (0.0%)")

    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run local point extraction pipeline."""
    # Check inputs
    if not OCCURRENCE_GPKG.exists():
        logger.error("Occurrence file not found: %s", OCCURRENCE_GPKG)
        logger.error("Run clean_occurrences.py first.")
        sys.exit(1)

    # Check that at least one raster exists
    any_raster = any(
        (GEE_DIR / rf).exists() for rf, _ in RASTER_LAYERS
    )
    if not any_raster:
        logger.error(
            "No raster files found in %s. Download GEE exports first.", GEE_DIR
        )
        logger.error("Run: python scripts/download_gee_exports.py")
        sys.exit(1)

    # Load occurrence points
    gdf = gpd.read_file(OCCURRENCE_GPKG)
    logger.info("Loaded %d occurrence points.", len(gdf))

    # Extract raster values
    gdf = extract_all_layers(gdf)

    # Save outputs
    PROC_DIR.mkdir(parents=True, exist_ok=True)

    df_out = pd.DataFrame(gdf.drop(columns=["geometry"]))
    df_out.to_csv(OUT_CSV, index=False)
    logger.info("Saved CSV: %s", OUT_CSV)

    gdf.to_file(OUT_GPKG, driver="GPKG", layer="sn_with_satellite")
    logger.info("Saved GeoPackage: %s", OUT_GPKG)

    print_summary(gdf)


if __name__ == "__main__":
    main()
