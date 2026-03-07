#!/usr/bin/env python3
"""
fetch_gbif.py
=============
Download georeferenced occurrence records of Steatoda nobilis from GBIF
using the pygbif Python client.

GBIF supports two retrieval modes:
    1. occ.search()   — real-time paginated search (max 100,000 records)
    2. occ.download() — asynchronous bulk download (returns a DOI-citable
                        Darwin Core Archive)

For a species with < 100k records in the query window, occ.search() is
simpler and sufficient. We implement both approaches and default to search
with a fallback note for the async workflow.

Prerequisites:
    - pip install pygbif geopandas shapely
    - A free GBIF account (register at https://www.gbif.org)
    - For the async download route, set environment variables:
        export GBIF_USER="your_username"
        export GBIF_PWD="your_password"
        export GBIF_EMAIL="your_email"

Scope:
    - Taxon: Steatoda nobilis (GBIF taxon key = 5170126)
    - Geography: Ireland + Western Europe (WKT polygon)
    - Temporal: 2017 to present
    - Coordinates: must have georeference, no geospatial issues

Output:
    data/raw/gbif_steatoda_nobilis.csv
    data/raw/gbif_steatoda_nobilis.gpkg

Usage:
    python scripts/fetch_gbif.py
"""

import logging
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# GBIF accepted taxon key for Steatoda nobilis (verified via API search)
TAXON_KEY = 2157203

# Bounding box as a WKT polygon (Ireland + Western Europe)
# Order: lon lat (WKT convention)
STUDY_AREA_WKT = (
    "POLYGON(("
    "-12 35, 15 35, 15 60, -12 60, -12 35"
    "))"
)

# Year range
YEAR_START = 2017
YEAR_END = 2025

# Maximum records per search page and total
PAGE_LIMIT = 300
MAX_RECORDS = 100_000  # GBIF search API hard limit

# Output paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUT_CSV = RAW_DIR / "gbif_steatoda_nobilis.csv"
OUT_GPKG = RAW_DIR / "gbif_steatoda_nobilis.gpkg"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Columns of interest from the GBIF response
# ---------------------------------------------------------------------------

KEEP_COLUMNS = [
    "gbifID",
    "species",
    "decimalLatitude",
    "decimalLongitude",
    "coordinateUncertaintyInMeters",
    "eventDate",
    "year",
    "month",
    "day",
    "countryCode",
    "stateProvince",
    "basisOfRecord",
    "institutionCode",
    "datasetName",
    "issue",
]


# ---------------------------------------------------------------------------
# Download via paginated search
# ---------------------------------------------------------------------------

def fetch_via_search() -> pd.DataFrame:
    """
    Retrieve occurrences using the GBIF search API (occ.search).

    This is synchronous and works without GBIF credentials. It paginates
    through results in batches of PAGE_LIMIT until all records are fetched
    or the MAX_RECORDS ceiling is reached.

    Returns
    -------
    pd.DataFrame
        Occurrence records with KEEP_COLUMNS subset.
    """
    from pygbif import occurrences as occ

    logger.info("Querying GBIF search API for taxonKey=%d ...", TAXON_KEY)

    all_records = []
    offset = 0

    while offset < MAX_RECORDS:
        result = occ.search(
            taxonKey=TAXON_KEY,
            hasCoordinate=True,
            hasGeospatialIssue=False,
            geometry=STUDY_AREA_WKT,
            year=f"{YEAR_START},{YEAR_END}",
            limit=PAGE_LIMIT,
            offset=offset,
        )

        records = result.get("results", [])
        if not records:
            break

        all_records.extend(records)
        total_on_server = result.get("count", 0)

        logger.info(
            "  Fetched %d records (offset=%d, server total=%d)",
            len(records), offset, total_on_server,
        )

        offset += PAGE_LIMIT

        # Stop if we've retrieved everything available
        if offset >= total_on_server:
            break

    logger.info(
        "GBIF search complete: %d total records retrieved.", len(all_records)
    )

    if not all_records:
        return pd.DataFrame()

    # Flatten to DataFrame and keep relevant columns
    df = pd.json_normalize(all_records)

    # Only keep columns that actually exist in the response
    available = [c for c in KEEP_COLUMNS if c in df.columns]
    df = df[available].copy()

    return df


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------

def clean_gbif_records(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply basic quality filters to the raw GBIF records.

    Filters:
        1. Remove rows without valid coordinates.
        2. Remove rows with coordinate uncertainty > 1000 m (where reported).
        3. Parse event dates.

    Parameters
    ----------
    df : pd.DataFrame
        Raw GBIF occurrence records.

    Returns
    -------
    pd.DataFrame
        Filtered records.
    """
    n_start = len(df)

    # 1. Drop rows missing coordinates
    df = df.dropna(subset=["decimalLatitude", "decimalLongitude"])

    # 2. Filter on coordinate uncertainty (keep NaN — many GBIF records
    #    don't report uncertainty, and excluding them would lose too much data)
    if "coordinateUncertaintyInMeters" in df.columns:
        mask_high_uncertainty = (
            df["coordinateUncertaintyInMeters"].notna()
            & (df["coordinateUncertaintyInMeters"] > 1000)
        )
        df = df[~mask_high_uncertainty]

    # 3. Parse eventDate to datetime (best effort)
    if "eventDate" in df.columns:
        df["eventDate"] = pd.to_datetime(df["eventDate"], errors="coerce")

    n_end = len(df)
    logger.info(
        "Quality filter: %d → %d records (removed %d).",
        n_start, n_end, n_start - n_end,
    )
    return df.reset_index(drop=True)


def to_geodataframe(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Convert to a GeoDataFrame with Point geometry in WGS84."""
    geometry = [
        Point(lon, lat)
        for lon, lat in zip(df["decimalLongitude"], df["decimalLatitude"])
    ]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
    return gdf


def save_outputs(df: pd.DataFrame, gdf: gpd.GeoDataFrame) -> None:
    """Save CSV and GeoPackage."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    df.to_csv(OUT_CSV, index=False)
    logger.info("Saved CSV: %s (%d rows)", OUT_CSV, len(df))

    gdf.to_file(OUT_GPKG, driver="GPKG", layer="steatoda_nobilis")
    logger.info("Saved GeoPackage: %s (%d features)", OUT_GPKG, len(gdf))


def print_summary(gdf: gpd.GeoDataFrame) -> None:
    """Print a summary of the downloaded data."""
    print("\n" + "=" * 60)
    print("GBIF Download Summary — Steatoda nobilis")
    print("=" * 60)
    print(f"  Total records:          {len(gdf)}")

    if "year" in gdf.columns:
        print(f"  Year range:             {gdf['year'].min()} – {gdf['year'].max()}")

    print(f"  Bounding box (data):    "
          f"lat [{gdf.geometry.y.min():.2f}, {gdf.geometry.y.max():.2f}], "
          f"lon [{gdf.geometry.x.min():.2f}, {gdf.geometry.x.max():.2f}]")

    if "coordinateUncertaintyInMeters" in gdf.columns:
        acc = gdf["coordinateUncertaintyInMeters"].dropna()
        if len(acc) > 0:
            print(f"  Coord. uncertainty:     median={acc.median():.0f} m, "
                  f"mean={acc.mean():.0f} m")

    if "countryCode" in gdf.columns:
        print(f"\n  Records by country:")
        for code, count in gdf["countryCode"].value_counts().head(15).items():
            print(f"    {code:6s} {count:5d}")

    if "basisOfRecord" in gdf.columns:
        print(f"\n  Records by basis of record:")
        for basis, count in gdf["basisOfRecord"].value_counts().items():
            print(f"    {basis:30s} {count:5d}")

    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Async download workflow (alternative — requires credentials)
# ---------------------------------------------------------------------------

def fetch_via_download() -> None:
    """
    Submit an asynchronous GBIF download request (Darwin Core Archive).

    This requires GBIF credentials set as environment variables:
        GBIF_USER, GBIF_PWD, GBIF_EMAIL

    The download is queued server-side and may take minutes to hours.
    This function prints the download key for later retrieval.

    Not called by default — provided as documentation for bulk downloads.
    """
    import os
    from pygbif import occurrences as occ

    user = os.environ.get("GBIF_USER")
    pwd = os.environ.get("GBIF_PWD")
    email = os.environ.get("GBIF_EMAIL")

    if not all([user, pwd, email]):
        logger.error(
            "GBIF credentials not set. Export GBIF_USER, GBIF_PWD, GBIF_EMAIL."
        )
        return

    logger.info("Submitting async GBIF download request ...")
    download_key = occ.download(
        f"taxonKey = {TAXON_KEY}",
        "hasCoordinate = true",
        "hasGeospatialIssue = false",
        f"geometry within '{STUDY_AREA_WKT}'",
        f"year >= {YEAR_START}",
        user=user,
        pwd=pwd,
        email=email,
    )
    logger.info(
        "Download request submitted. Key: %s", download_key
    )
    logger.info(
        "Check status at: https://www.gbif.org/occurrence/download/%s",
        download_key[0] if isinstance(download_key, (list, tuple)) else download_key,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run the GBIF occurrence download pipeline."""
    try:
        df = fetch_via_search()
    except ImportError:
        logger.error("pygbif is not installed. Run: pip install pygbif")
        sys.exit(1)

    if df.empty:
        logger.warning("No data retrieved from GBIF. Exiting.")
        sys.exit(0)

    df = clean_gbif_records(df)
    gdf = to_geodataframe(df)
    save_outputs(df, gdf)
    print_summary(gdf)


if __name__ == "__main__":
    main()
