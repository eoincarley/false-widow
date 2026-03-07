#!/usr/bin/env python3
"""
prepare_rasters.py
==================
Reproject, resample, and align all satellite raster layers to a common
grid for use in MaxEnt species distribution modelling.

All layers are aligned to the MODIS 1 km grid (the coarsest resolution),
using bilinear interpolation for continuous variables. This ensures that
all predictor rasters have identical extent, resolution, and CRS — a
requirement for MaxEnt and most SDM frameworks.

An additional Ireland-only stack at 500 m is also produced for fine-scale
analysis using the Landsat data.

Input (data/raw/gee/):
    viirs_dnb_median_radiance.tif      (~463 m)
    modis_lst_mean_day_night.tif       (~1 km, 2 bands)
    landsat_lst_summer_median_500m.tif (~500 m)

Output (data/processed/rasters/):
    study_area_stack_1km.tif    — 4-band aligned stack (full study area)
    ireland_stack_500m.tif      — 4-band aligned stack (Ireland only)
    Individual aligned layers:
        viirs_avg_rad_1km.tif
        modis_lst_day_1km.tif
        modis_lst_night_1km.tif
        landsat_lst_summer_1km.tif

Usage:
    python scripts/prepare_rasters.py
"""

import logging
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject, calculate_default_transform

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GEE_DIR = PROJECT_ROOT / "data" / "raw" / "gee"
RASTER_DIR = PROJECT_ROOT / "data" / "processed" / "rasters"

# Target CRS
TARGET_CRS = "EPSG:4326"

# Full study area bounding box [west, south, east, north]
STUDY_BBOX = (-12.0, 35.0, 15.0, 60.0)

# Ireland bounding box
IRELAND_BBOX = (-10.5, 51.3, -5.5, 55.5)

# Target resolutions (degrees)
# At ~50°N: 0.009° ≈ 1 km latitude, ~0.6 km longitude
RES_1KM = 0.009     # ~1 km
RES_500M = 0.0045   # ~500 m

# Input rasters
VIIRS_FILE = GEE_DIR / "viirs_dnb_median_radiance.tif"
MODIS_FILE = GEE_DIR / "modis_lst_mean_day_night.tif"
LANDSAT_FILE = GEE_DIR / "landsat_lst_summer_median_500m.tif"
LANDSAT_IRELAND_FILE = GEE_DIR / "landsat_lst_summer_ireland_100m.tif"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core resampling function
# ---------------------------------------------------------------------------

def resample_to_grid(
    src_path: Path,
    dst_path: Path,
    src_band: int,
    bbox: tuple,
    res: float,
    dst_nodata: float = np.nan,
) -> None:
    """
    Reproject and resample a single raster band to a target grid.

    Parameters
    ----------
    src_path : Path
        Input GeoTIFF.
    dst_path : Path
        Output GeoTIFF (single-band).
    src_band : int
        1-based band index to read from the source.
    bbox : tuple
        Target extent as (west, south, east, north).
    res : float
        Target pixel size in degrees.
    dst_nodata : float
        Nodata value for the output.
    """
    west, south, east, north = bbox

    # Compute target dimensions
    width = int(round((east - west) / res))
    height = int(round((north - south) / res))
    dst_transform = from_bounds(west, south, east, north, width, height)

    with rasterio.open(src_path) as src:
        src_data = src.read(src_band)
        src_nodata = src.nodata

        # Prepare output array
        dst_data = np.full((height, width), dst_nodata, dtype=np.float32)

        # Reproject
        reproject(
            source=src_data,
            destination=dst_data,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src_nodata,
            dst_transform=dst_transform,
            dst_crs=TARGET_CRS,
            dst_nodata=dst_nodata,
            resampling=Resampling.bilinear,
        )

    # Write output
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": width,
        "height": height,
        "count": 1,
        "crs": TARGET_CRS,
        "transform": dst_transform,
        "nodata": dst_nodata,
        "compress": "deflate",
    }

    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(dst_data, 1)

    n_valid = np.isfinite(dst_data).sum()
    n_total = dst_data.size
    logger.info(
        "  %s: %d x %d px, %.1f%% valid data",
        dst_path.name, width, height, 100 * n_valid / n_total,
    )


# ---------------------------------------------------------------------------
# Stack builder
# ---------------------------------------------------------------------------

def build_stack(layer_paths: list, stack_path: Path, band_names: list) -> None:
    """
    Combine multiple single-band aligned GeoTIFFs into a multi-band stack.

    All input files must have identical CRS, extent, and resolution.

    Parameters
    ----------
    layer_paths : list of Path
        Paths to aligned single-band GeoTIFFs (in band order).
    stack_path : Path
        Output multi-band GeoTIFF path.
    band_names : list of str
        Descriptive names for each band.
    """
    # Read the first to get the profile
    with rasterio.open(layer_paths[0]) as ref:
        profile = ref.profile.copy()
        height = ref.height
        width = ref.width

    profile.update(count=len(layer_paths), compress="deflate")

    with rasterio.open(stack_path, "w", **profile) as dst:
        for i, (lpath, bname) in enumerate(zip(layer_paths, band_names), 1):
            with rasterio.open(lpath) as src:
                data = src.read(1)
            dst.write(data, i)
            dst.set_band_description(i, bname)

    logger.info(
        "Stack: %s (%d bands, %d x %d px)",
        stack_path.name, len(layer_paths), width, height,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    """Build aligned raster stacks for the full study area and Ireland."""
    RASTER_DIR.mkdir(parents=True, exist_ok=True)

    # Check inputs
    for f in [VIIRS_FILE, MODIS_FILE, LANDSAT_FILE]:
        if not f.exists():
            logger.error("Missing input: %s", f)
            sys.exit(1)

    # ---------------------------------------------------------------
    # 1. Full study area at 1 km resolution
    # ---------------------------------------------------------------
    logger.info("=== Full study area — 1 km resolution ===")

    layers_1km = []
    names_1km = []

    # VIIRS nighttime radiance
    out = RASTER_DIR / "viirs_avg_rad_1km.tif"
    logger.info("Resampling VIIRS DNB → 1 km ...")
    resample_to_grid(VIIRS_FILE, out, src_band=1, bbox=STUDY_BBOX, res=RES_1KM)
    layers_1km.append(out)
    names_1km.append("viirs_avg_rad")

    # MODIS daytime LST
    out = RASTER_DIR / "modis_lst_day_1km.tif"
    logger.info("Resampling MODIS daytime LST → 1 km ...")
    resample_to_grid(MODIS_FILE, out, src_band=1, bbox=STUDY_BBOX, res=RES_1KM)
    layers_1km.append(out)
    names_1km.append("modis_lst_day_c")

    # MODIS nighttime LST
    out = RASTER_DIR / "modis_lst_night_1km.tif"
    logger.info("Resampling MODIS nighttime LST → 1 km ...")
    resample_to_grid(MODIS_FILE, out, src_band=2, bbox=STUDY_BBOX, res=RES_1KM)
    layers_1km.append(out)
    names_1km.append("modis_lst_night_c")

    # Landsat summer LST
    out = RASTER_DIR / "landsat_lst_summer_1km.tif"
    logger.info("Resampling Landsat summer LST → 1 km ...")
    resample_to_grid(LANDSAT_FILE, out, src_band=1, bbox=STUDY_BBOX, res=RES_1KM)
    layers_1km.append(out)
    names_1km.append("landsat_lst_summer_c")

    # Build 4-band stack
    stack_1km = RASTER_DIR / "study_area_stack_1km.tif"
    logger.info("Building 1 km stack ...")
    build_stack(layers_1km, stack_1km, names_1km)

    # ---------------------------------------------------------------
    # 2. Ireland at 500 m resolution
    # ---------------------------------------------------------------
    logger.info("\n=== Ireland — 500 m resolution ===")

    layers_500m = []
    names_500m = []

    # VIIRS
    out = RASTER_DIR / "viirs_avg_rad_ireland_500m.tif"
    logger.info("Resampling VIIRS DNB → 500 m (Ireland) ...")
    resample_to_grid(VIIRS_FILE, out, src_band=1, bbox=IRELAND_BBOX, res=RES_500M)
    layers_500m.append(out)
    names_500m.append("viirs_avg_rad")

    # MODIS day
    out = RASTER_DIR / "modis_lst_day_ireland_500m.tif"
    logger.info("Resampling MODIS daytime LST → 500 m (Ireland) ...")
    resample_to_grid(MODIS_FILE, out, src_band=1, bbox=IRELAND_BBOX, res=RES_500M)
    layers_500m.append(out)
    names_500m.append("modis_lst_day_c")

    # MODIS night
    out = RASTER_DIR / "modis_lst_night_ireland_500m.tif"
    logger.info("Resampling MODIS nighttime LST → 500 m (Ireland) ...")
    resample_to_grid(MODIS_FILE, out, src_band=2, bbox=IRELAND_BBOX, res=RES_500M)
    layers_500m.append(out)
    names_500m.append("modis_lst_night_c")

    # Landsat — use the Ireland 100m file if available, else the 500m
    landsat_src = LANDSAT_IRELAND_FILE if LANDSAT_IRELAND_FILE.exists() else LANDSAT_FILE
    out = RASTER_DIR / "landsat_lst_summer_ireland_500m.tif"
    logger.info("Resampling Landsat summer LST → 500 m (Ireland) from %s ...", landsat_src.name)
    resample_to_grid(landsat_src, out, src_band=1, bbox=IRELAND_BBOX, res=RES_500M)
    layers_500m.append(out)
    names_500m.append("landsat_lst_summer_c")

    # Build 4-band stack
    stack_500m = RASTER_DIR / "ireland_stack_500m.tif"
    logger.info("Building 500 m Ireland stack ...")
    build_stack(layers_500m, stack_500m, names_500m)

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    print("\n" + "=" * 60)
    print("Raster Stack Summary")
    print("=" * 60)

    for label, spath in [("Study area (1 km)", stack_1km), ("Ireland (500 m)", stack_500m)]:
        with rasterio.open(spath) as src:
            size_mb = spath.stat().st_size / (1024 * 1024)
            print(f"\n  {label}: {spath.name}")
            print(f"    Dimensions: {src.width} x {src.height} px")
            print(f"    Bands:      {src.count}")
            print(f"    CRS:        {src.crs}")
            print(f"    Resolution: {src.res[0]:.4f}° x {src.res[1]:.4f}°")
            print(f"    File size:  {size_mb:.1f} MB")
            for i in range(1, src.count + 1):
                print(f"    Band {i}: {src.descriptions[i-1]}")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
