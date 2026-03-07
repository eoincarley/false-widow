#!/usr/bin/env python3
"""
clean_occurrences.py
====================
Merge, deduplicate, filter, and spatially thin the Steatoda nobilis
occurrence records from iNaturalist and GBIF into analysis-ready files.

Processes data **year-by-year** for speed, outputting per-year files,
then concatenates into a final combined dataset.

Pipeline (per year):
    1. Load raw iNaturalist and GBIF GeoPackages.
    2. Harmonise column names into a common schema.
    3. Remove records falling in the ocean (spatial join with land polygons).
    4. Filter out records with positional accuracy > 1000 m.
    5. Deduplicate: records within 100 m and on the same date are merged.
    6. Spatial thinning: retain at most one record per 1 km grid cell.
    7. Export per-year CSV and GeoPackage.

Final step:
    8. Concatenate all per-year outputs into combined files.

Output:
    data/processed/by_year/2017_sn_cleaned.csv   (+ .gpkg)
    data/processed/by_year/2018_sn_cleaned.csv   (+ .gpkg)
    ...
    data/processed/sn_occurrences_cleaned.csv     (combined)
    data/processed/sn_occurrences_cleaned.gpkg    (combined)

Usage:
    python scripts/clean_occurrences.py
"""

import logging
import sys
import urllib.request
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROC_DIR = PROJECT_ROOT / "data" / "processed"
YEAR_DIR = PROC_DIR / "by_year"

# Input files (produced by fetch_inaturalist.py and fetch_gbif.py)
INAT_GPKG = RAW_DIR / "inaturalist_steatoda_nobilis.gpkg"
GBIF_GPKG = RAW_DIR / "gbif_steatoda_nobilis.gpkg"

# Final combined output files
OUT_CSV = PROC_DIR / "sn_occurrences_cleaned.csv"
OUT_GPKG = PROC_DIR / "sn_occurrences_cleaned.gpkg"

# Cleaning parameters
MAX_POSITIONAL_ACCURACY_M = 1000   # drop records > 1 km uncertainty
DEDUP_DISTANCE_M = 100             # merge records within 100 m on same date
THINNING_CELL_SIZE_DEG = 0.01      # ~1 km at mid-latitudes

# Year range to process
YEAR_START = 2017
YEAR_END = 2026

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Cache for the land polygon (loaded once, reused across years)
_land_gdf = None


# ---------------------------------------------------------------------------
# Loading and harmonisation
# ---------------------------------------------------------------------------

def load_inaturalist(path: Path) -> gpd.GeoDataFrame:
    """Load iNaturalist GeoPackage and harmonise to a common schema."""
    if not path.exists():
        logger.warning("iNaturalist file not found: %s", path)
        return gpd.GeoDataFrame()

    gdf = gpd.read_file(path)
    logger.info("Loaded %d iNaturalist records from %s", len(gdf), path)

    harmonised = gpd.GeoDataFrame(
        {
            "source": "iNaturalist",
            "source_id": gdf["inat_id"].astype(str) if "inat_id" in gdf.columns else None,
            "observed_on": pd.to_datetime(gdf["observed_on"], errors="coerce", utc=True),
            "latitude": gdf.geometry.y,
            "longitude": gdf.geometry.x,
            "positional_accuracy_m": gdf.get("positional_accuracy"),
            "country": gdf.get("place_guess", pd.Series(dtype=str)),
        },
        geometry=gdf.geometry,
        crs=gdf.crs,
    )
    return harmonised


def load_gbif(path: Path) -> gpd.GeoDataFrame:
    """Load GBIF GeoPackage and harmonise to the common schema."""
    if not path.exists():
        logger.warning("GBIF file not found: %s", path)
        return gpd.GeoDataFrame()

    gdf = gpd.read_file(path)
    logger.info("Loaded %d GBIF records from %s", len(gdf), path)

    harmonised = gpd.GeoDataFrame(
        {
            "source": "GBIF",
            "source_id": gdf["gbifID"].astype(str) if "gbifID" in gdf.columns else None,
            "observed_on": pd.to_datetime(gdf["eventDate"], errors="coerce", utc=True),
            "latitude": gdf.geometry.y,
            "longitude": gdf.geometry.x,
            "positional_accuracy_m": gdf.get("coordinateUncertaintyInMeters"),
            "country": gdf.get("countryCode", pd.Series(dtype=str)),
        },
        geometry=gdf.geometry,
        crs=gdf.crs,
    )
    return harmonised


# ---------------------------------------------------------------------------
# Land polygon (cached)
# ---------------------------------------------------------------------------

def get_land_polygon() -> gpd.GeoDataFrame:
    """
    Load (and cache) the Natural Earth 110m countries shapefile.
    Downloads once on first call, then reuses the cached file.
    Returns a single dissolved land geometry (excluding Antarctica).
    """
    global _land_gdf
    if _land_gdf is not None:
        return _land_gdf

    ne_url = (
        "https://naciscdn.org/naturalearth/110m/cultural/"
        "ne_110m_admin_0_countries.zip"
    )
    cache_dir = RAW_DIR / "naturalearth"
    cache_shp = cache_dir / "ne_110m_admin_0_countries.shp"

    if not cache_shp.exists():
        logger.info("Downloading Natural Earth 110m countries shapefile ...")
        cache_dir.mkdir(parents=True, exist_ok=True)
        zip_path = cache_dir / "ne_110m_admin_0_countries.zip"
        urllib.request.urlretrieve(ne_url, zip_path)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(cache_dir)
        logger.info("Extracted to %s", cache_dir)

    world = gpd.read_file(cache_shp)
    _land_gdf = world[world["CONTINENT"] != "Antarctica"].dissolve()
    return _land_gdf


# ---------------------------------------------------------------------------
# Cleaning functions (operate on a single year's data)
# ---------------------------------------------------------------------------

def filter_land_only(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Remove points that fall in the ocean (outside land polygons)."""
    n_before = len(gdf)
    land = get_land_polygon()

    gdf = gpd.sjoin(gdf, land[["geometry"]], how="inner", predicate="within")
    if "index_right" in gdf.columns:
        gdf = gdf.drop(columns=["index_right"])

    logger.info(
        "  Land filter: %d → %d (-%d offshore)",
        n_before, len(gdf), n_before - len(gdf),
    )
    return gdf.reset_index(drop=True)


def filter_accuracy(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Remove records with positional accuracy > threshold. Keep NaN."""
    n_before = len(gdf)
    mask = (
        gdf["positional_accuracy_m"].isna()
        | (gdf["positional_accuracy_m"] <= MAX_POSITIONAL_ACCURACY_M)
    )
    gdf = gdf[mask].copy()
    logger.info(
        "  Accuracy filter (≤%dm): %d → %d",
        MAX_POSITIONAL_ACCURACY_M, n_before, len(gdf),
    )
    return gdf.reset_index(drop=True)


def deduplicate(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Remove duplicates: records within DEDUP_DISTANCE_M on the same date.

    Prefers iNaturalist over GBIF. Groups by date string, then does
    pairwise distance checks within each date-group (typically small).
    """
    n_before = len(gdf)
    if n_before < 2:
        return gdf

    # Sort: iNaturalist first (preferred source to keep)
    source_order = {"iNaturalist": 0, "GBIF": 1}
    gdf["_sort"] = gdf["source"].map(source_order).fillna(2)
    gdf = gdf.sort_values("_sort").reset_index(drop=True)

    # Project to metric CRS for distance checks
    gdf_metric = gdf.to_crs("EPSG:3035")

    # Date string for grouping
    gdf["_date_str"] = gdf["observed_on"].dt.strftime("%Y-%m-%d").fillna("unknown")

    keep = np.ones(len(gdf), dtype=bool)

    for _, group in gdf.groupby("_date_str"):
        if len(group) < 2:
            continue

        idx = group.index.tolist()
        geoms = gdf_metric.geometry.loc[idx]

        for i_pos, i in enumerate(idx):
            if not keep[i]:
                continue
            for j in idx[i_pos + 1:]:
                if not keep[j]:
                    continue
                if geoms.loc[i].distance(geoms.loc[j]) < DEDUP_DISTANCE_M:
                    keep[j] = False

    gdf = gdf[keep].drop(columns=["_sort", "_date_str"]).reset_index(drop=True)
    logger.info(
        "  Dedup (<%dm, same date): %d → %d (-%d)",
        DEDUP_DISTANCE_M, n_before, len(gdf), n_before - len(gdf),
    )
    return gdf


def spatial_thin(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Thin to one record per ~1km grid cell (best accuracy wins).
    Reduces spatial autocorrelation and citizen-science reporting bias.
    """
    n_before = len(gdf)
    cs = THINNING_CELL_SIZE_DEG

    gdf["_cx"] = (gdf.geometry.x / cs).astype(int)
    gdf["_cy"] = (gdf.geometry.y / cs).astype(int)

    # Keep the record with the smallest positional accuracy per cell
    gdf["_acc"] = gdf["positional_accuracy_m"].fillna(1e9)
    gdf = gdf.sort_values("_acc")
    gdf = gdf.drop_duplicates(subset=["_cx", "_cy"], keep="first")
    gdf = gdf.drop(columns=["_cx", "_cy", "_acc"]).reset_index(drop=True)

    logger.info(
        "  Spatial thin (~%dkm): %d → %d",
        int(cs * 111), n_before, len(gdf),
    )
    return gdf


# ---------------------------------------------------------------------------
# Per-year processing
# ---------------------------------------------------------------------------

def process_year(gdf_all: gpd.GeoDataFrame, year: int) -> gpd.GeoDataFrame:
    """
    Extract, clean, and save records for a single year.

    Parameters
    ----------
    gdf_all : gpd.GeoDataFrame
        Full combined dataset with an 'observed_on' datetime column.
    year : int
        The year to process.

    Returns
    -------
    gpd.GeoDataFrame
        Cleaned records for this year (also saved to disk).
    """
    # Filter to this year
    mask = gdf_all["observed_on"].dt.year == year
    gdf_year = gdf_all[mask].copy().reset_index(drop=True)

    if gdf_year.empty:
        logger.info("Year %d: 0 records — skipping.", year)
        return gpd.GeoDataFrame()

    logger.info("Year %d: %d raw records", year, len(gdf_year))

    # Run cleaning pipeline
    gdf_year = filter_land_only(gdf_year)
    gdf_year = filter_accuracy(gdf_year)
    gdf_year = deduplicate(gdf_year)
    gdf_year = spatial_thin(gdf_year)

    if gdf_year.empty:
        logger.info("Year %d: 0 records after cleaning.", year)
        return gpd.GeoDataFrame()

    # Save per-year outputs
    YEAR_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = YEAR_DIR / f"{year}_sn_cleaned.csv"
    gpkg_path = YEAR_DIR / f"{year}_sn_cleaned.gpkg"

    pd.DataFrame(gdf_year.drop(columns=["geometry"])).to_csv(csv_path, index=False)
    gdf_year.to_file(gpkg_path, driver="GPKG", layer=f"sn_{year}")

    logger.info(
        "Year %d: %d cleaned records → %s", year, len(gdf_year), csv_path.name
    )
    return gdf_year


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(gdf: gpd.GeoDataFrame) -> None:
    """Print summary statistics of the combined cleaned dataset."""
    print("\n" + "=" * 60)
    print("Cleaned Occurrence Data — Steatoda nobilis")
    print("=" * 60)
    print(f"  Total records:          {len(gdf)}")

    dates = gdf["observed_on"].dropna()
    if len(dates) > 0:
        print(f"  Date range:             "
              f"{dates.min().strftime('%Y-%m-%d')} to "
              f"{dates.max().strftime('%Y-%m-%d')}")

    print(f"  Bounding box:           "
          f"lat [{gdf.geometry.y.min():.2f}, {gdf.geometry.y.max():.2f}], "
          f"lon [{gdf.geometry.x.min():.2f}, {gdf.geometry.x.max():.2f}]")

    # Per-year counts
    if "observed_on" in gdf.columns:
        print(f"\n  Records per year:")
        year_counts = gdf["observed_on"].dt.year.value_counts().sort_index()
        for yr, cnt in year_counts.items():
            print(f"    {int(yr):6d}   {cnt:5d}")

    # Source breakdown
    if "source" in gdf.columns:
        print(f"\n  By source:")
        for src, count in gdf["source"].value_counts().items():
            print(f"    {src:20s} {count:5d}")

    # Country breakdown
    if "country" in gdf.columns:
        print(f"\n  By country (top 15):")
        for country, count in gdf["country"].value_counts().head(15).items():
            label = str(country)[:30] if country else "Unknown"
            print(f"    {label:30s} {count:5d}")

    # Accuracy stats
    acc = gdf["positional_accuracy_m"].dropna()
    if len(acc) > 0:
        print(f"\n  Positional accuracy (n={len(acc)}):")
        print(f"    Median: {acc.median():.0f} m")
        print(f"    Mean:   {acc.mean():.0f} m")
        print(f"    Max:    {acc.max():.0f} m")

    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run the full year-by-year cleaning pipeline."""
    # Load both sources
    gdf_inat = load_inaturalist(INAT_GPKG)
    gdf_gbif = load_gbif(GBIF_GPKG)

    if gdf_inat.empty and gdf_gbif.empty:
        logger.error(
            "No input data found. Run fetch_inaturalist.py and "
            "fetch_gbif.py first."
        )
        sys.exit(1)

    # Concatenate all sources
    parts = [g for g in [gdf_inat, gdf_gbif] if not g.empty]
    gdf_all = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs="EPSG:4326")
    logger.info("Combined raw dataset: %d records.", len(gdf_all))

    # Drop records with no parseable date (can't assign to a year)
    n_nodate = gdf_all["observed_on"].isna().sum()
    if n_nodate > 0:
        logger.info("Dropping %d records with unparseable dates.", n_nodate)
        gdf_all = gdf_all.dropna(subset=["observed_on"]).reset_index(drop=True)

    # Process year by year
    yearly_results = []
    for year in range(YEAR_START, YEAR_END + 1):
        result = process_year(gdf_all, year)
        if not result.empty:
            yearly_results.append(result)

    if not yearly_results:
        logger.error("No records survived cleaning. Check parameters.")
        sys.exit(1)

    # Concatenate all years into final output
    gdf_combined = gpd.GeoDataFrame(
        pd.concat(yearly_results, ignore_index=True), crs="EPSG:4326"
    )
    logger.info("Combined cleaned dataset: %d records.", len(gdf_combined))

    # Save combined files
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(gdf_combined.drop(columns=["geometry"])).to_csv(OUT_CSV, index=False)
    gdf_combined.to_file(OUT_GPKG, driver="GPKG", layer="steatoda_nobilis_cleaned")
    logger.info("Saved combined CSV:  %s", OUT_CSV)
    logger.info("Saved combined GPKG: %s", OUT_GPKG)

    print_summary(gdf_combined)


if __name__ == "__main__":
    main()
