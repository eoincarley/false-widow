#!/usr/bin/env python3
"""
gee_extract.py
==============
Extract satellite environmental layers from Google Earth Engine for the
Steatoda nobilis species distribution modelling study.

Layers extracted:
    1. VIIRS DNB — median annual nighttime radiance (ALAN proxy), ~463 m
    2. MODIS LST — mean nighttime and daytime land surface temperature, 1 km
    3. Landsat 8/9 — median summer (Jun–Aug) surface temperature, 100 m

Two modes of extraction:
    A. Point extraction: sample raster values at each occurrence point
       → exports CSV to Google Drive
    B. Raster export: clip composites to the study area bounding box
       → exports GeoTIFF to Google Drive

Prerequisites:
    1. pip install earthengine-api geemap geopandas
    2. Authenticate once:  earthengine authenticate
       (or: python -c "import ee; ee.Authenticate()")
    3. Register a GEE cloud project at https://code.earthengine.google.com/
       and set GEE_PROJECT env var, or the script will try default init.

Usage:
    # Authenticate first (one-time, opens browser):
    earthengine authenticate

    # Then run extraction:
    python scripts/gee_extract.py

    # To only do point extraction (faster, no large raster exports):
    python scripts/gee_extract.py --points-only

    # To only export rasters:
    python scripts/gee_extract.py --rasters-only

Output:
    Exports are sent to your Google Drive under the folder 'false_widow_gee/'.
    After export tasks complete, download files from Drive to data/raw/gee/.
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import ee
import geopandas as gpd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OCCURRENCE_GPKG = PROJECT_ROOT / "data" / "processed" / "sn_occurrences_cleaned.gpkg"

# Google Drive export folder
DRIVE_FOLDER = "false_widow_gee"

# Study area bounding box: Ireland + Western Europe
# [west, south, east, north]
BBOX = [-12.0, 35.0, 15.0, 60.0]

# Temporal window
YEAR_START = 2017
YEAR_END = 2025

# Buffer radius (metres) for point extraction — averages the raster
# value within this radius around each occurrence point
POINT_BUFFER_M = 500

# CRS for exports
EXPORT_CRS = "EPSG:4326"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GEE initialisation
# ---------------------------------------------------------------------------

def init_gee():
    """
    Initialise the Earth Engine API.

    Tries the default credentials first. If a GEE_PROJECT environment
    variable is set, uses that as the cloud project.
    """
    project = os.environ.get("GEE_PROJECT")

    try:
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
        logger.info("Google Earth Engine initialised successfully.")
    except ee.EEException:
        logger.error(
            "GEE authentication required. Run one of:\n"
            "  earthengine authenticate\n"
            "  python -c \"import ee; ee.Authenticate()\"\n"
            "Then re-run this script."
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Study area geometry
# ---------------------------------------------------------------------------

def get_study_area() -> ee.Geometry:
    """Return the study area as a GEE geometry (bounding box)."""
    return ee.Geometry.Rectangle(BBOX)


# ---------------------------------------------------------------------------
# Occurrence points as GEE FeatureCollection
# ---------------------------------------------------------------------------

def load_occurrence_points() -> ee.FeatureCollection:
    """
    Load cleaned occurrence points from the local GeoPackage and upload
    them as a GEE FeatureCollection for server-side point extraction.

    Each feature has properties: source_id, year, source.
    """
    if not OCCURRENCE_GPKG.exists():
        logger.error("Occurrence file not found: %s", OCCURRENCE_GPKG)
        logger.error("Run clean_occurrences.py first.")
        sys.exit(1)

    gdf = gpd.read_file(OCCURRENCE_GPKG)
    logger.info("Loaded %d occurrence points for GEE upload.", len(gdf))

    # Convert to GEE features
    features = []
    for _, row in gdf.iterrows():
        lon = float(row.geometry.x)
        lat = float(row.geometry.y)
        point = ee.Geometry.Point([lon, lat])
        props = {
            "source_id": str(row.get("source_id", "")),
            "source": str(row.get("source", "")),
        }
        features.append(ee.Feature(point, props))

    fc = ee.FeatureCollection(features)
    logger.info("Created GEE FeatureCollection with %d points.", len(features))
    return fc


# ---------------------------------------------------------------------------
# Layer 1: VIIRS DNB nighttime radiance
# ---------------------------------------------------------------------------

def build_viirs_composite(study_area: ee.Geometry) -> ee.Image:
    """
    Build a multi-year median VIIRS DNB nighttime radiance composite.

    Uses the stray-light-corrected monthly composites
    (NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG).

    Filters:
        - Temporal: YEAR_START to YEAR_END
        - Cloud-free coverage: cf_cvg >= 3 per month
        - Band: avg_rad (nanoWatts/cm²/sr)

    Returns a single-band image: 'viirs_avg_rad' (median across all months).
    """
    collection = (
        ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG")
        .filterDate(f"{YEAR_START}-01-01", f"{YEAR_END}-12-31")
        .filterBounds(study_area)
    )

    def mask_low_coverage(img):
        """Mask pixels with fewer than 3 cloud-free observations."""
        mask = img.select("cf_cvg").gte(3)
        return img.select("avg_rad").updateMask(mask)

    masked = collection.map(mask_low_coverage)

    # Take the temporal median across all monthly composites
    composite = masked.median().rename("viirs_avg_rad")

    logger.info(
        "VIIRS composite: %d monthly images, %d-%d",
        collection.size().getInfo(), YEAR_START, YEAR_END,
    )
    return composite.clip(study_area)


# ---------------------------------------------------------------------------
# Layer 2: MODIS Land Surface Temperature
# ---------------------------------------------------------------------------

def build_modis_lst_composites(study_area: ee.Geometry) -> ee.Image:
    """
    Build mean daytime and nighttime LST composites from MODIS Terra
    8-day product (MOD11A2, Collection 6.1, 1 km resolution).

    Applies the scale factor (0.02) to convert from raw DN to Kelvin,
    then converts to Celsius.

    Returns a two-band image:
        - 'modis_lst_day_c'   (mean daytime LST in °C)
        - 'modis_lst_night_c' (mean nighttime LST in °C)
    """
    collection = (
        ee.ImageCollection("MODIS/061/MOD11A2")
        .filterDate(f"{YEAR_START}-01-01", f"{YEAR_END}-12-31")
        .filterBounds(study_area)
    )

    def apply_scale_and_mask(img):
        """Apply QC mask and scale factor to LST bands."""
        # QC bands use bitwise flags; bits 0-1 = LST error flag
        # 00 = good, 01 = average, rest = poor/not produced
        qc_day = img.select("QC_Day")
        qc_night = img.select("QC_Night")

        # Keep pixels where bits 0-1 are 00 or 01 (values 0 or 1)
        mask_day = qc_day.bitwiseAnd(3).lte(1)
        mask_night = qc_night.bitwiseAnd(3).lte(1)

        lst_day = (
            img.select("LST_Day_1km")
            .multiply(0.02)          # scale to Kelvin
            .subtract(273.15)        # convert to Celsius
            .updateMask(mask_day)
            .rename("modis_lst_day_c")
        )
        lst_night = (
            img.select("LST_Night_1km")
            .multiply(0.02)
            .subtract(273.15)
            .updateMask(mask_night)
            .rename("modis_lst_night_c")
        )
        return lst_day.addBands(lst_night)

    processed = collection.map(apply_scale_and_mask)

    # Take the temporal mean
    composite = processed.mean()

    logger.info(
        "MODIS LST composite: %d 8-day images, %d-%d",
        collection.size().getInfo(), YEAR_START, YEAR_END,
    )
    return composite.clip(study_area)


# ---------------------------------------------------------------------------
# Layer 3: Landsat 8/9 Surface Temperature
# ---------------------------------------------------------------------------

def build_landsat_lst_composite(study_area: ee.Geometry) -> ee.Image:
    """
    Build a median summer (June–August) surface temperature composite
    from Landsat 8 and 9 Collection 2 Level 2, at 100 m resolution.

    Uses the ST_B10 band with the official scale/offset:
        T(K) = DN * 0.00341802 + 149.0
    Then converts to Celsius.

    Cloud masking uses the QA_PIXEL band (bit 3 = cloud, bit 4 = cloud shadow).

    The multi-year summer median (YEAR_START–YEAR_END) accumulates enough
    clear-sky pixels despite Ireland/W.Europe's frequent cloud cover.

    Returns a single-band image: 'landsat_lst_summer_c'.
    """
    def process_landsat(img):
        """Mask clouds and compute surface temperature in Celsius."""
        # Cloud mask from QA_PIXEL: bit 3 (cloud) and bit 4 (cloud shadow)
        qa = img.select("QA_PIXEL")
        cloud_mask = (
            qa.bitwiseAnd(1 << 3).eq(0)     # no cloud
            .And(qa.bitwiseAnd(1 << 4).eq(0))  # no cloud shadow
        )

        # Surface temperature: apply scale/offset, convert K → C
        lst = (
            img.select("ST_B10")
            .multiply(0.00341802)
            .add(149.0)
            .subtract(273.15)
            .updateMask(cloud_mask)
            .rename("landsat_lst_summer_c")
        )
        return lst

    # Combine Landsat 8 and 9
    l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
    l9 = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")

    # Build a merged summer collection across all years
    summer_images = ee.ImageCollection([])
    for year in range(YEAR_START, YEAR_END + 1):
        start = f"{year}-06-01"
        end = f"{year}-08-31"

        l8_summer = (
            l8.filterDate(start, end)
            .filterBounds(study_area)
            .filter(ee.Filter.lt("CLOUD_COVER", 30))
        )
        l9_summer = (
            l9.filterDate(start, end)
            .filterBounds(study_area)
            .filter(ee.Filter.lt("CLOUD_COVER", 30))
        )

        summer_images = summer_images.merge(l8_summer).merge(l9_summer)

    processed = summer_images.map(process_landsat)

    # Multi-year summer median
    composite = processed.median()

    logger.info(
        "Landsat summer LST: %d images (L8+L9, Jun-Aug, <%d%% cloud), %d-%d",
        summer_images.size().getInfo(), 30, YEAR_START, YEAR_END,
    )
    return composite.clip(study_area)


# ---------------------------------------------------------------------------
# Point extraction
# ---------------------------------------------------------------------------

# Maximum features per sampleRegions call — GEE can choke on very large
# FeatureCollections, so we batch in chunks of this size.
BATCH_SIZE = 5000


def extract_at_points(
    image: ee.Image,
    points: ee.FeatureCollection,
    band_names: list,
    export_name: str,
) -> list:
    """
    Sample raster values at occurrence points and export as CSV to Drive.

    Uses ee.Image.sampleRegions() which is GEE's optimised bulk sampling
    function — orders of magnitude faster than mapping reduceRegion()
    over individual features. Points are processed in batches of
    BATCH_SIZE to stay within GEE compute limits.

    Parameters
    ----------
    image : ee.Image
        The composite image to sample.
    points : ee.FeatureCollection
        Occurrence point features.
    band_names : list of str
        Band names to include in the export.
    export_name : str
        Base name for the export task(s) and output file(s).

    Returns
    -------
    list of ee.batch.Task
        The started export tasks (one per batch).
    """
    tasks = []

    # Get the total count to determine batching
    total = points.size().getInfo()
    n_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    logger.info(
        "Point extraction: %d points in %d batch(es) of %d",
        total, n_batches, BATCH_SIZE,
    )

    # Convert to a list for slicing into batches
    points_list = points.toList(total)

    for i in range(n_batches):
        start = i * BATCH_SIZE
        end = min(start + BATCH_SIZE, total)
        batch_fc = ee.FeatureCollection(points_list.slice(start, end))

        # sampleRegions: efficiently samples the image at all points at once
        sampled = image.select(band_names).sampleRegions(
            collection=batch_fc,
            scale=500,           # sample at 500m (matches VIIRS resolution)
            geometries=True,     # preserve point coordinates in output
        )

        # Export batch to Drive
        batch_name = export_name if n_batches == 1 else f"{export_name}_batch{i+1}"
        task = ee.batch.Export.table.toDrive(
            collection=sampled,
            description=batch_name,
            folder=DRIVE_FOLDER,
            fileNamePrefix=batch_name,
            fileFormat="CSV",
        )
        task.start()
        logger.info("  Started batch %d/%d: %s (%d points)", i+1, n_batches, batch_name, end - start)
        tasks.append(task)

    return tasks


# ---------------------------------------------------------------------------
# Raster export
# ---------------------------------------------------------------------------

def export_raster(
    image: ee.Image,
    export_name: str,
    scale: int,
    study_area: ee.Geometry,
) -> ee.batch.Task:
    """
    Export a GEE image as a GeoTIFF to Google Drive.

    Parameters
    ----------
    image : ee.Image
        Image to export.
    export_name : str
        Task description and filename prefix.
    scale : int
        Output resolution in metres.
    study_area : ee.Geometry
        Region to export.

    Returns
    -------
    ee.batch.Task
        The started export task.
    """
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=export_name,
        folder=DRIVE_FOLDER,
        fileNamePrefix=export_name,
        region=study_area,
        scale=scale,
        crs=EXPORT_CRS,
        maxPixels=1e10,
        fileFormat="GeoTIFF",
    )
    task.start()
    logger.info("Started raster export task: %s (scale=%dm)", export_name, scale)
    return task


# ---------------------------------------------------------------------------
# Task monitoring
# ---------------------------------------------------------------------------

def monitor_tasks(tasks: list, poll_interval: int = 30):
    """
    Poll GEE export tasks until all complete or fail.

    Parameters
    ----------
    tasks : list of ee.batch.Task
        Export tasks to monitor.
    poll_interval : int
        Seconds between status checks.
    """
    logger.info("Monitoring %d export tasks ...", len(tasks))
    pending = {t.id: t for t in tasks}

    while pending:
        time.sleep(poll_interval)
        still_pending = {}
        for tid, task in pending.items():
            status = task.status()
            state = status.get("state", "UNKNOWN")
            desc = status.get("description", tid)

            if state in ("COMPLETED",):
                logger.info("  COMPLETED: %s", desc)
            elif state in ("FAILED", "CANCEL_REQUESTED", "CANCELLED"):
                err = status.get("error_message", "no error message")
                logger.error("  FAILED: %s — %s", desc, err)
            else:
                still_pending[tid] = task

        n_done = len(pending) - len(still_pending)
        if n_done > 0:
            logger.info(
                "  %d/%d tasks finished, %d remaining.",
                len(tasks) - len(still_pending), len(tasks), len(still_pending),
            )
        pending = still_pending

    logger.info("All export tasks finished.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract satellite layers from GEE for S. nobilis SDM."
    )
    parser.add_argument(
        "--points-only", action="store_true",
        help="Only extract values at occurrence points (skip raster export).",
    )
    parser.add_argument(
        "--rasters-only", action="store_true",
        help="Only export rasters (skip point extraction).",
    )
    parser.add_argument(
        "--no-wait", action="store_true",
        help="Submit tasks without waiting for completion.",
    )
    args = parser.parse_args()

    # --- Initialise GEE ---
    init_gee()
    study_area = get_study_area()

    # --- Build composites ---
    logger.info("Building satellite composites ...")

    logger.info("  [1/3] VIIRS DNB nighttime radiance ...")
    viirs = build_viirs_composite(study_area)

    logger.info("  [2/3] MODIS daytime + nighttime LST ...")
    modis_lst = build_modis_lst_composites(study_area)

    logger.info("  [3/3] Landsat 8/9 summer surface temperature ...")
    landsat_lst = build_landsat_lst_composite(study_area)

    # --- Stack all bands into one image (for combined point extraction) ---
    stacked = viirs.addBands(modis_lst).addBands(landsat_lst)
    all_bands = [
        "viirs_avg_rad",
        "modis_lst_day_c",
        "modis_lst_night_c",
        "landsat_lst_summer_c",
    ]

    tasks = []

    # --- Point extraction ---
    if not args.rasters_only:
        logger.info("Loading occurrence points ...")
        points = load_occurrence_points()

        logger.info("Submitting point extraction tasks ...")

        # extract_at_points now returns a list of tasks (one per batch)
        point_tasks = extract_at_points(
            stacked, points, all_bands,
            export_name="sn_point_extract_all_bands",
        )
        tasks.extend(point_tasks)

    # --- Raster exports ---
    if not args.points_only:
        logger.info("Submitting raster export tasks ...")

        # VIIRS at native resolution (~463m)
        tasks.append(export_raster(
            viirs, "viirs_dnb_median_radiance", scale=463, study_area=study_area,
        ))

        # MODIS LST at native resolution (~1000m)
        tasks.append(export_raster(
            modis_lst, "modis_lst_mean_day_night", scale=1000, study_area=study_area,
        ))

        # Landsat LST at native resolution (~100m)
        # NOTE: at 100m over the full study area this is a LARGE export
        # (~2.7 billion pixels). Exporting at 500m as a compromise.
        # For Ireland-only fine-scale analysis, re-export at 100m with
        # a smaller bounding box.
        tasks.append(export_raster(
            landsat_lst, "landsat_lst_summer_median_500m",
            scale=500, study_area=study_area,
        ))

        # Also export an Ireland-only Landsat LST at native 100m
        ireland_bbox = ee.Geometry.Rectangle([-10.5, 51.3, -5.5, 55.5])
        landsat_ireland = landsat_lst.clip(ireland_bbox)
        tasks.append(export_raster(
            landsat_ireland, "landsat_lst_summer_ireland_100m",
            scale=100, study_area=ireland_bbox,
        ))

    # --- Summary ---
    print("\n" + "=" * 60)
    print("GEE Export Tasks Submitted")
    print("=" * 60)
    for t in tasks:
        status = t.status()
        print(f"  {status['description']:45s}  {status['state']}")
    print(f"\nFiles will appear in Google Drive folder: '{DRIVE_FOLDER}/'")
    print("=" * 60 + "\n")

    # --- Wait for completion ---
    if not args.no_wait:
        monitor_tasks(tasks, poll_interval=30)
        print("\nAll exports complete. Download files from Google Drive to:")
        print(f"  {PROJECT_ROOT / 'data' / 'raw' / 'gee'}/")
    else:
        print("Tasks submitted (--no-wait). Monitor at:")
        print("  https://code.earthengine.google.com/tasks")


if __name__ == "__main__":
    main()
