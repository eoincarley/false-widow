#!/usr/bin/env python3
"""
fetch_inaturalist.py
====================
Download research-grade, georeferenced observations of Steatoda nobilis
(noble false widow spider) from iNaturalist using the pyinaturalist API client.

Scope:
    - Taxon: Steatoda nobilis (iNaturalist taxon_id = 366894)
    - Quality: research grade only (community-verified, photo-confirmed)
    - Geography: Ireland + Western Europe (bounding box: ~35N-60N, 12W-15E)
    - Temporal: 2017-01-01 to present
    - Coordinates: georeferenced only

Output:
    data/raw/inaturalist_steatoda_nobilis.csv
    data/raw/inaturalist_steatoda_nobilis.gpkg  (GeoPackage)

Usage:
    python scripts/fetch_inaturalist.py
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

# iNaturalist taxon ID for Steatoda nobilis (verified via taxa autocomplete)
TAXON_ID = 366894

# Bounding box: Ireland + Western Europe
# SW corner (lat, lon) to NE corner (lat, lon)
SWLAT, SWLNG = 35.0, -12.0   # southern Iberia, west of Ireland
NELAT, NELNG = 60.0, 15.0     # Scandinavia, central Europe

# Temporal window
DATE_START = "2017-01-01"

# iNaturalist API returns max 200 results per page; we paginate through all
PER_PAGE = 200

# Output paths (relative to project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUT_CSV = RAW_DIR / "inaturalist_steatoda_nobilis.csv"
OUT_GPKG = RAW_DIR / "inaturalist_steatoda_nobilis.gpkg"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core fetch function
# ---------------------------------------------------------------------------

def fetch_observations() -> pd.DataFrame:
    """
    Query the iNaturalist v1 API for all matching observations.

    Uses pyinaturalist.get_observations() with manual pagination via
    the id_above parameter (cursor-based paging), which is the
    recommended approach for large result sets in pyinaturalist >= 0.19.

    Returns
    -------
    pd.DataFrame
        One row per observation with columns for ID, date, coordinates,
        accuracy, place, observer, and taxon name.
    """
    from pyinaturalist import get_observations

    logger.info(
        "Querying iNaturalist for Steatoda nobilis (taxon_id=%d) ...", TAXON_ID
    )
    logger.info(
        "Bounding box: lat [%.1f, %.1f], lon [%.1f, %.1f]",
        SWLAT, NELAT, SWLNG, NELNG,
    )
    logger.info("Date range: %s to present", DATE_START)

    all_results = []
    id_above = 0   # cursor: fetch observations with ID > this value
    page_num = 0

    while True:
        page_num += 1
        response = get_observations(
            taxon_id=TAXON_ID,
            quality_grade="research",
            geo=True,
            d1=DATE_START,
            swlat=SWLAT,
            swlng=SWLNG,
            nelat=NELAT,
            nelng=NELNG,
            order_by="id",
            order="asc",
            per_page=PER_PAGE,
            id_above=id_above,
        )

        results = response.get("results", [])
        total = response.get("total_results", 0)

        if not results:
            break

        all_results.extend(results)
        id_above = results[-1]["id"]  # move cursor past last fetched ID

        logger.info(
            "  Page %d: fetched %d (cumulative %d / %d)",
            page_num, len(results), len(all_results), total,
        )

        # Stop if we've fetched fewer than a full page (no more results)
        if len(results) < PER_PAGE:
            break

    logger.info(
        "Download complete: %d total observations retrieved.", len(all_results)
    )

    if not all_results:
        logger.warning("No observations returned. Check API parameters.")
        return pd.DataFrame()

    # Parse each observation into a flat dict
    records = []
    for obs in all_results:
        location = obs.get("location")
        if location is None:
            continue

        # pyinaturalist v0.21 returns location as a [lat, lng] list
        if isinstance(location, (list, tuple)):
            lat, lon = float(location[0]), float(location[1])
        elif isinstance(location, str):
            parts = location.split(",")
            lat, lon = float(parts[0]), float(parts[1])
        else:
            continue

        taxon = obs.get("taxon") or {}
        user = obs.get("user") or {}

        records.append({
            "inat_id": obs.get("id"),
            "observed_on": obs.get("observed_on"),
            "latitude": lat,
            "longitude": lon,
            "positional_accuracy": obs.get("positional_accuracy"),
            "place_guess": obs.get("place_guess"),
            "user_login": user.get("login"),
            "taxon_name": taxon.get("name"),
            "quality_grade": obs.get("quality_grade"),
            "uri": obs.get("uri"),
        })

    df = pd.DataFrame(records)
    logger.info(
        "Parsed %d records with valid coordinates (of %d total).",
        len(df), len(all_results),
    )
    return df


# ---------------------------------------------------------------------------
# Conversion and I/O
# ---------------------------------------------------------------------------

def to_geodataframe(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Convert a DataFrame with latitude/longitude columns to a GeoDataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain 'latitude' and 'longitude' columns.

    Returns
    -------
    gpd.GeoDataFrame
        With Point geometry in EPSG:4326 (WGS84).
    """
    geometry = [Point(lon, lat) for lon, lat in zip(df["longitude"], df["latitude"])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
    return gdf


def save_outputs(df: pd.DataFrame, gdf: gpd.GeoDataFrame) -> None:
    """Save CSV and GeoPackage outputs."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    df.to_csv(OUT_CSV, index=False)
    logger.info("Saved CSV: %s (%d rows)", OUT_CSV, len(df))

    gdf.to_file(OUT_GPKG, driver="GPKG", layer="steatoda_nobilis")
    logger.info("Saved GeoPackage: %s (%d features)", OUT_GPKG, len(gdf))


def print_summary(gdf: gpd.GeoDataFrame) -> None:
    """Print a summary of the downloaded data."""
    print("\n" + "=" * 60)
    print("iNaturalist Download Summary — Steatoda nobilis")
    print("=" * 60)
    print(f"  Total records:          {len(gdf)}")
    dates = pd.to_datetime(gdf["observed_on"], errors="coerce").dropna()
    if len(dates) > 0:
        print(f"  Date range:             {dates.min().strftime('%Y-%m-%d')} to "
              f"{dates.max().strftime('%Y-%m-%d')}")
    print(f"  Bounding box (data):    "
          f"lat [{gdf.geometry.y.min():.2f}, {gdf.geometry.y.max():.2f}], "
          f"lon [{gdf.geometry.x.min():.2f}, {gdf.geometry.x.max():.2f}]")

    # Positional accuracy statistics (where available)
    acc = gdf["positional_accuracy"].dropna()
    if len(acc) > 0:
        print(f"  Positional accuracy:    median={acc.median():.0f} m, "
              f"mean={acc.mean():.0f} m, max={acc.max():.0f} m")
        print(f"  Records with accuracy:  {len(acc)} / {len(gdf)}")

    # Country-level breakdown (rough, from place_guess)
    if "place_guess" in gdf.columns:
        print(f"\n  Top 10 place guesses:")
        places = gdf["place_guess"].dropna()
        if len(places) > 0:
            # Take the last comma-separated segment as a rough country proxy
            countries = places.str.split(",").str[-1].str.strip()
            for place, count in countries.value_counts().head(10).items():
                print(f"    {place:30s} {count:5d}")

    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run the full iNaturalist download pipeline."""
    try:
        df = fetch_observations()
    except ImportError:
        logger.error(
            "pyinaturalist is not installed. Run: pip install pyinaturalist"
        )
        sys.exit(1)

    if df.empty:
        logger.warning("No data retrieved. Exiting.")
        sys.exit(0)

    gdf = to_geodataframe(df)
    save_outputs(df, gdf)
    print_summary(gdf)


if __name__ == "__main__":
    main()
