#!/usr/bin/env python3
"""
generate_background.py
======================
Generate bias-corrected background (pseudo-absence) points for MaxEnt
species distribution modelling.

MaxEnt requires background points sampled from the study area to contrast
against presence locations. Naive uniform random sampling creates a bias
because citizen-science records are concentrated near population centres.
To correct for this, we weight background sampling by VIIRS nighttime
radiance as a proxy for human population density — areas with more light
(= more people) get proportionally more background points, matching the
sampling effort pattern.

Pipeline:
    1. Define the accessible area ("M"): dissolve a 50 km buffer around
       all occurrence points, intersected with land.
    2. Generate a bias surface from the VIIRS DNB raster (log-transformed
       radiance as sampling weight).
    3. Draw 10,000 background points, weighted by the bias surface.
    4. Extract satellite raster values at background points.
    5. Export background points with extracted values.

Input:
    data/processed/sn_occurrences_cleaned.gpkg
    data/processed/rasters/study_area_stack_1km.tif

Output:
    data/processed/background_points.csv
    data/processed/background_points.gpkg

Usage:
    python scripts/generate_background.py
"""

import logging
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol, xy
from shapely.geometry import Point

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROC_DIR = PROJECT_ROOT / "data" / "processed"
RASTER_DIR = PROC_DIR / "rasters"

# Input
OCCURRENCE_GPKG = PROC_DIR / "sn_occurrences_cleaned.gpkg"
STACK_FILE = RASTER_DIR / "study_area_stack_1km.tif"

# Output
OUT_CSV = PROC_DIR / "background_points.csv"
OUT_GPKG = PROC_DIR / "background_points.gpkg"

# Parameters
N_BACKGROUND = 10_000        # number of background points to generate
BUFFER_KM = 50               # buffer around occurrences to define M
RANDOM_SEED = 42             # for reproducibility

# Band names in the stacked raster (must match prepare_rasters.py output)
BAND_NAMES = [
    "viirs_avg_rad",
    "modis_lst_day_c",
    "modis_lst_night_c",
    "landsat_lst_summer_c",
]

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step 1: Define the accessible area (M)
# ---------------------------------------------------------------------------

def build_accessible_area(gdf: gpd.GeoDataFrame, buffer_km: float) -> gpd.GeoDataFrame:
    """
    Create the accessible area by buffering occurrence points and dissolving.

    Projects to EPSG:3035 (ETRS89-LAEA Europe) for metric buffering,
    then reprojects back to EPSG:4326.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Occurrence points in EPSG:4326.
    buffer_km : float
        Buffer distance in kilometres.

    Returns
    -------
    gpd.GeoDataFrame
        Single-row GeoDataFrame with the dissolved accessible area polygon.
    """
    # Project to metric CRS
    gdf_metric = gdf.to_crs("EPSG:3035")

    # Buffer each point and dissolve into a single polygon
    buffered = gdf_metric.geometry.buffer(buffer_km * 1000)
    dissolved = buffered.unary_union

    # Back to WGS84
    m_area = gpd.GeoDataFrame(geometry=[dissolved], crs="EPSG:3035").to_crs("EPSG:4326")

    area_km2 = gdf_metric.geometry.buffer(buffer_km * 1000).unary_union.area / 1e6
    logger.info(
        "Accessible area (M): %.0f km² (%.0f km buffer around %d points)",
        area_km2, buffer_km, len(gdf),
    )
    return m_area


# ---------------------------------------------------------------------------
# Step 2: Build bias surface from VIIRS band
# ---------------------------------------------------------------------------

def build_bias_weights(stack_path: Path) -> tuple:
    """
    Build a bias surface from the VIIRS nighttime radiance band (band 1).

    Uses log(1 + radiance) as the weight — this compresses the dynamic
    range of radiance values so that extremely bright city centres don't
    dominate, while still giving urban areas substantially more weight
    than rural areas.

    Returns
    -------
    weights : np.ndarray (2D)
        Sampling probability weight for each pixel.
    transform : rasterio.Affine
        The raster's affine transform.
    crs : rasterio.crs.CRS
        The raster's CRS.
    shape : tuple
        (height, width) of the raster.
    """
    with rasterio.open(stack_path) as src:
        viirs = src.read(1)  # band 1 = viirs_avg_rad
        transform = src.transform
        crs = src.crs
        nodata = src.nodata

    # Mask nodata and negative values
    valid = np.isfinite(viirs) & (viirs > 0)
    if nodata is not None:
        valid &= (viirs != nodata)

    # Log-transform to compress dynamic range
    weights = np.where(valid, np.log1p(viirs), 0.0)

    # Normalise to sum to 1 (probability distribution)
    total = weights.sum()
    if total > 0:
        weights /= total

    n_valid = valid.sum()
    logger.info(
        "Bias surface: %d valid pixels (%.1f%% of raster), "
        "max weight ratio = %.0f:1",
        n_valid,
        100 * n_valid / viirs.size,
        weights.max() / (weights[weights > 0].min()) if (weights > 0).any() else 0,
    )
    return weights, transform, crs, viirs.shape


# ---------------------------------------------------------------------------
# Step 3: Sample background points
# ---------------------------------------------------------------------------

def sample_background_points(
    weights: np.ndarray,
    transform: rasterio.Affine,
    m_area: gpd.GeoDataFrame,
    n_points: int,
    seed: int,
) -> gpd.GeoDataFrame:
    """
    Draw background points weighted by the bias surface.

    Samples pixel indices proportional to their weight, converts to
    geographic coordinates, and filters to the accessible area polygon.
    Oversamples by 50% to account for points that fall outside M.

    Parameters
    ----------
    weights : np.ndarray
        2D probability weights (sum to 1).
    transform : rasterio.Affine
        Affine transform of the raster.
    m_area : gpd.GeoDataFrame
        Accessible area polygon (EPSG:4326).
    n_points : int
        Target number of background points.
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    gpd.GeoDataFrame
        Background points with lat/lon in EPSG:4326.
    """
    rng = np.random.default_rng(seed)
    height, width = weights.shape

    # Flatten weights for multinomial sampling
    flat_weights = weights.ravel()
    if flat_weights.sum() == 0:
        logger.error("All weights are zero — cannot sample.")
        sys.exit(1)

    # Oversample to account for M-boundary clipping (study area is ~50%
    # of the raster bounding box, so 3x oversampling is needed)
    n_sample = int(n_points * 3.0)

    # Draw pixel indices
    flat_indices = rng.choice(len(flat_weights), size=n_sample, p=flat_weights)
    rows, cols = np.unravel_index(flat_indices, (height, width))

    # Add sub-pixel jitter (uniform within pixel) to avoid grid artefacts
    row_jitter = rng.uniform(-0.5, 0.5, size=n_sample)
    col_jitter = rng.uniform(-0.5, 0.5, size=n_sample)

    # Convert pixel coordinates to geographic coordinates
    lons, lats = [], []
    for r, c, rj, cj in zip(rows, cols, row_jitter, col_jitter):
        x, y = xy(transform, int(r) + rj, int(c) + cj)
        lons.append(x)
        lats.append(y)

    # Build GeoDataFrame
    geometry = [Point(lon, lat) for lon, lat in zip(lons, lats)]
    gdf = gpd.GeoDataFrame(
        {"longitude": lons, "latitude": lats},
        geometry=geometry,
        crs="EPSG:4326",
    )

    # Clip to accessible area
    n_before = len(gdf)
    m_polygon = m_area.geometry.iloc[0]
    gdf = gdf[gdf.geometry.within(m_polygon)].reset_index(drop=True)
    logger.info(
        "Sampled %d points, %d within M (clipped %d outside).",
        n_before, len(gdf), n_before - len(gdf),
    )

    # Take exactly n_points
    if len(gdf) > n_points:
        gdf = gdf.iloc[:n_points].reset_index(drop=True)
    elif len(gdf) < n_points:
        logger.warning(
            "Only %d points within M (target: %d). Consider increasing oversample ratio.",
            len(gdf), n_points,
        )

    logger.info("Final background set: %d points.", len(gdf))
    return gdf


# ---------------------------------------------------------------------------
# Step 4: Extract raster values at background points
# ---------------------------------------------------------------------------

def extract_at_background(
    gdf: gpd.GeoDataFrame, stack_path: Path
) -> gpd.GeoDataFrame:
    """
    Extract all band values from the raster stack at background point locations.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Background points in EPSG:4326.
    stack_path : Path
        Path to the multi-band aligned raster stack.

    Returns
    -------
    gpd.GeoDataFrame
        Input with additional columns for each band.
    """
    with rasterio.open(stack_path) as src:
        n_bands = src.count
        data = src.read()  # shape: (bands, height, width)
        transform = src.transform
        nodata = src.nodata

    lons = gdf.geometry.x.values
    lats = gdf.geometry.y.values

    # Initialise output columns
    for bname in BAND_NAMES[:n_bands]:
        gdf[bname] = np.nan

    for i, (lon, lat) in enumerate(zip(lons, lats)):
        try:
            row, col = rowcol(transform, lon, lat)
        except Exception:
            continue

        if 0 <= row < data.shape[1] and 0 <= col < data.shape[2]:
            for b in range(n_bands):
                val = data[b, row, col]
                if np.isfinite(val) and (nodata is None or val != nodata):
                    gdf.iloc[i, gdf.columns.get_loc(BAND_NAMES[b])] = float(val)

    for bname in BAND_NAMES[:n_bands]:
        n_valid = gdf[bname].notna().sum()
        logger.info(
            "  %s: %d/%d background points have data (%.1f%%)",
            bname, n_valid, len(gdf), 100 * n_valid / len(gdf),
        )

    return gdf


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(
    gdf_bg: gpd.GeoDataFrame, gdf_occ: gpd.GeoDataFrame
) -> None:
    """Compare summary statistics between occurrence and background points."""
    print("\n" + "=" * 60)
    print("Background Points Summary")
    print("=" * 60)
    print(f"  Background points: {len(gdf_bg)}")
    print(f"  Occurrence points: {len(gdf_occ)}")

    print(f"\n  {'Variable':30s} {'':5s} {'Occurrences':>20s}  {'Background':>20s}")
    print(f"  {'-'*30} {'-'*5} {'-'*20}  {'-'*20}")

    for bname in BAND_NAMES:
        if bname not in gdf_bg.columns:
            continue

        occ_vals = gdf_occ[bname].dropna() if bname in gdf_occ.columns else pd.Series()
        bg_vals = gdf_bg[bname].dropna()

        if len(occ_vals) > 0 and len(bg_vals) > 0:
            print(
                f"  {bname:30s} {'med':5s} "
                f"{occ_vals.median():20.2f}  {bg_vals.median():20.2f}"
            )
            print(
                f"  {'':30s} {'mean':5s} "
                f"{occ_vals.mean():20.2f}  {bg_vals.mean():20.2f}"
            )

    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run the background point generation pipeline."""
    # Check inputs
    if not OCCURRENCE_GPKG.exists():
        logger.error("Occurrence file not found: %s", OCCURRENCE_GPKG)
        sys.exit(1)

    if not STACK_FILE.exists():
        logger.error("Raster stack not found: %s", STACK_FILE)
        logger.error("Run prepare_rasters.py first.")
        sys.exit(1)

    # Load occurrences
    gdf_occ = gpd.read_file(OCCURRENCE_GPKG)
    logger.info("Loaded %d occurrence points.", len(gdf_occ))

    # Step 1: Build accessible area
    m_area = build_accessible_area(gdf_occ, BUFFER_KM)

    # Step 2: Build bias surface
    weights, transform, crs, shape = build_bias_weights(STACK_FILE)

    # Step 3: Sample background points
    gdf_bg = sample_background_points(
        weights, transform, m_area, N_BACKGROUND, RANDOM_SEED
    )

    # Step 4: Extract raster values
    logger.info("Extracting raster values at background points ...")
    gdf_bg = extract_at_background(gdf_bg, STACK_FILE)

    # Save outputs
    PROC_DIR.mkdir(parents=True, exist_ok=True)

    df_out = pd.DataFrame(gdf_bg.drop(columns=["geometry"]))
    df_out.to_csv(OUT_CSV, index=False)
    logger.info("Saved CSV: %s", OUT_CSV)

    gdf_bg.to_file(OUT_GPKG, driver="GPKG", layer="background_points")
    logger.info("Saved GeoPackage: %s", OUT_GPKG)

    # Load occurrence satellite data for comparison
    occ_sat_path = PROC_DIR / "sn_occurrences_with_satellite.gpkg"
    if occ_sat_path.exists():
        gdf_occ_sat = gpd.read_file(occ_sat_path)
    else:
        gdf_occ_sat = gdf_occ

    print_summary(gdf_bg, gdf_occ_sat)


if __name__ == "__main__":
    main()
