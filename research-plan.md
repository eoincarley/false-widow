# Research Plan: Correlating Noble False Widow (*Steatoda nobilis*) Distribution with Satellite-Derived Urban Heat and Nighttime Light Data

## Project Summary

| Parameter | Decision |
|-----------|----------|
| **Geographic scope** | Ireland + Western Europe (Ireland as focal region) |
| **Temporal window** | 2017 – present |
| **Satellite layers** | VIIRS DNB (nighttime light / ALAN) + Land Surface Temperature (Landsat-8/9, MODIS) |
| **SDM method** | MaxEnt (presence-only) |
| **Compute environment** | Google Earth Engine (server-side extraction) + local Python (SDM, analysis, plotting) |
| **Occurrence data** | iNaturalist + GBIF |

---

## Phase 1: Occurrence Data Acquisition

### 1.1 iNaturalist — Primary Georeferenced Records

**Source**: iNaturalist API via the `pyinaturalist` Python client.

**Target taxon**: *Steatoda nobilis* (taxon ID 122168 on iNaturalist).

**Query parameters**:
- `taxon_id=122168`
- `quality_grade='research'` (community-verified, photo-confirmed)
- `geo=True` (must have coordinates)
- `geoprivacy='open'` (exclude obscured/private locations)
- `d1='2017-01-01'` (start of temporal window)
- Bounding box or place_id filters for Ireland + Western Europe

**Key fields to extract**: `id`, `observed_on`, `latitude`, `longitude`, `positional_accuracy`, `place_guess`, `user.login`, `taxon.name`, `quality_grade`.

**Package**:
```
pip install pyinaturalist pyinaturalist-convert
```

**Pipeline**:
1. Use `pyinaturalist.get_all_observations()` to paginate through all matching records.
2. Convert to GeoDataFrame via `pyinaturalist-convert` or manual construction with `geopandas`.
3. Export to GeoPackage (`.gpkg`) for interoperability.

**Rate limits**: iNaturalist API allows 100 requests/minute for unauthenticated calls; 1,000/minute with an app token. Use `pyinaturalist`'s built-in request throttling.

### 1.2 GBIF — Aggregated Multi-Source Records

**Source**: GBIF Occurrence API via `pygbif`.

**Target taxon**: *Steatoda nobilis* — GBIF taxon key `5170126`.

**Query parameters**:
- `taxonKey=5170126`
- `hasCoordinate=True`
- `hasGeospatialIssue=False`
- `year='2017,2025'`
- `geometry=<WKT polygon for Ireland + W. Europe>`

**Package**:
```
pip install pygbif
```

**Pipeline**:
1. Register for a GBIF account (required for downloads).
2. Use `pygbif.occurrences.download()` to submit an asynchronous download request.
3. Poll with `pygbif.occurrences.download_meta()` until status is `SUCCEEDED`.
4. Retrieve the Darwin Core Archive (`.zip`) with `pygbif.occurrences.download_get()`.
5. Parse the `occurrence.txt` TSV into a pandas DataFrame; filter to `coordinateUncertaintyInMeters < 1000`.
6. Merge with iNaturalist data, de-duplicating on coordinate proximity (< 100 m) and date.

**Citation**: GBIF requires a DOI citation per download — store the DOI returned by the download request.

### 1.3 Data Cleaning and Quality Control

| Step | Action | Tool |
|------|--------|------|
| Remove marine/offshore points | Spatial join against land polygon | `geopandas`, `naturalearth` |
| Filter coordinate precision | Drop records with `positional_accuracy > 1000 m` (iNat) or `coordinateUncertaintyInMeters > 1000 m` (GBIF) | `pandas` |
| Temporal filter | Retain only 2017-01-01 to present | `pandas` |
| Taxonomic verification | Confirm all records map to GBIF key `5170126` | `pygbif.species.name_backbone()` |
| Spatial thinning | Thin to one record per 1 km grid cell to reduce sampling bias | `elapid.sample_raster()` or `spThin` logic |
| Projection | Reproject all points to EPSG:4326 (WGS84) for GEE compatibility | `geopandas` |

**Output**: A single cleaned GeoPackage file (`sn_occurrences_cleaned.gpkg`) with unique, thinned occurrence points.

---

## Phase 2: Satellite Data Acquisition via Google Earth Engine

All satellite data extraction will be performed server-side in GEE using the `earthengine-api` and `geemap` Python packages, avoiding bulk downloads of raw raster imagery.

### 2.1 Environment Setup

```
pip install earthengine-api geemap
```

Authenticate via `ee.Authenticate()` (one-time browser flow). Initialise with `ee.Initialize(project='your-cloud-project')`.

### 2.2 VIIRS Day/Night Band — Nighttime Light (ALAN)

**GEE Collection**: `NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG` (stray-light corrected monthly composites).

**Band**: `avg_rad` — monthly average radiance in nanoWatts/cm²/sr.

**Temporal range in GEE**: 2014-01 to present (monthly updates).

**Spatial resolution**: ~463 m (15 arc-seconds).

**Extraction strategy — two approaches**:

**(A) Point extraction** (for MaxEnt training data):
1. Upload cleaned occurrence points as a `ee.FeatureCollection`.
2. For each point, compute the **median annual radiance** from the 12 monthly composites of each year (2017–present).
3. Use `ee.Image.reduceRegions()` with a 500 m buffer to extract radiance at each point.
4. Export the resulting table to Google Drive as CSV via `ee.batch.Export.table.toDrive()`.

**(B) Raster export** (for continuous prediction surfaces):
1. Compute a multi-year median composite (2017–present) for the study area.
2. Clip to a bounding box covering Ireland + Western Europe.
3. Export as GeoTIFF at native resolution via `ee.batch.Export.image.toDrive()`.

**Quality filtering**: Mask pixels where `cf_cvg < 3` (fewer than 3 cloud-free observations in a month) to avoid unreliable composites.

### 2.3 Land Surface Temperature (LST)

Two LST products will be used, trading off spatial vs. temporal resolution:

#### 2.3.1 MODIS LST (coarser, frequent)

**GEE Collection**: `MODIS/061/MOD11A2` (Terra 8-day composite, 1 km).

**Bands**: `LST_Day_1km`, `LST_Night_1km` (Kelvin × 0.02 scale factor).

**Strategy**:
1. Filter to 2017–present and the study area bounding box.
2. Compute long-term **mean nighttime LST** and **mean daytime LST** composites.
3. Derive a **UHI intensity proxy**: pixel LST minus the mean LST of a 25 km rural buffer ring around each urban centre.
4. Extract at occurrence points and export raster as per VIIRS workflow.

#### 2.3.2 Landsat LST (finer, less frequent)

**GEE Collection**: `LANDSAT/LC08/C02/T1_L2` and `LANDSAT/LC09/C02/T1_L2` (Collection 2, Level 2).

**Band**: `ST_B10` — Surface Temperature (Kelvin × 0.00341802 + 149.0).

**Strategy**:
1. Filter to 2017–present, study area, and `CLOUD_COVER < 30`.
2. Apply the scale/offset and mask clouds using the `QA_PIXEL` band.
3. Reduce to a **median summer nighttime LST** composite (June–August, where Landsat overpass captures the strongest UHI signal).
4. Export at 100 m resolution for urban-scale analysis.

**Note on Ireland cloud cover**: Landsat revisit is 16 days per satellite (8 days with L8+L9 combined), and Irish cloud cover is high. A multi-year summer median (2017–present) will be needed to accumulate sufficient clear-sky pixels. GEE's server-side compositing handles this efficiently.

### 2.4 Supplementary Layer — Urban Land Cover

**GEE Asset**: Copernicus Global Land Cover (`COPERNICUS/Landcover/100m/Proba-V-C3/Global/2019`) or upload Copernicus Urban Atlas 2018 polygons.

**Purpose**: Classify each occurrence as urban/peri-urban/rural; provide an urbanisation covariate for the SDM.

### 2.5 Summary of GEE Exports

| Layer | GEE Collection | Resolution | Export Format |
|-------|---------------|------------|---------------|
| VIIRS DNB median radiance | `NOAA/VIIRS/DNB/MONTHLY_V1/VCMSLCFG` | 463 m | GeoTIFF + CSV |
| MODIS nighttime LST | `MODIS/061/MOD11A2` | 1 km | GeoTIFF + CSV |
| MODIS daytime LST | `MODIS/061/MOD11A2` | 1 km | GeoTIFF + CSV |
| Landsat summer LST | `LANDSAT/LC08/C02/T1_L2` + LC09 | 100 m | GeoTIFF + CSV |
| Land cover / urbanisation | Copernicus | 100 m | GeoTIFF |

---

## Phase 3: Local Data Processing and Integration

### 3.1 Python Environment

```
pip install elapid geopandas rasterio xarray rioxarray shapely pyproj \
            matplotlib seaborn scikit-learn pandas numpy pyinaturalist pygbif \
            earthengine-api geemap contextily folium
```

**Key package roles**:

| Package | Role |
|---------|------|
| `elapid` | MaxEnt implementation + geospatial SDM utilities (Anderson, 2023, *JOSS*). Provides `MaxentModel`, `sample_raster()`, `apply_model_to_rasters()`. |
| `geopandas` | Vector I/O, spatial joins, CRS transformations |
| `rasterio` / `rioxarray` | Raster I/O, clipping, reprojection, value extraction |
| `geemap` | GEE ↔ Python bridge, interactive mapping, batch export |
| `pyinaturalist` | iNaturalist API client |
| `pygbif` | GBIF API client |
| `scikit-learn` | Model evaluation, cross-validation, AUC/ROC |
| `contextily` / `folium` | Basemap tiles for static/interactive maps |

### 3.2 Raster Stack Preparation

1. **Download GeoTIFFs** from Google Drive (exported from GEE).
2. **Reproject** all rasters to a common CRS (EPSG:4326 or EPSG:3035 / ETRS89 LAEA for a European extent).
3. **Resample** to a common grid. Since MaxEnt requires aligned rasters, resample all layers to the coarsest common resolution (1 km, matching MODIS) using bilinear interpolation for continuous variables.
4. **Stack** into a multi-band raster or individual aligned GeoTIFFs for `elapid`.

### 3.3 Background Point Generation

MaxEnt requires background (pseudo-absence) points sampled from the study area:

1. Define the accessible area ("M" in BAM framework): buffer all occurrence points by 50 km and dissolve, or use country boundaries for Ireland + W. Europe.
2. Use `elapid.sample_raster()` to generate 10,000 background points within this area, with density weighted by a bias surface (e.g., human population density raster from WorldPop) to account for citizen-science sampling effort bias.

---

## Phase 4: Species Distribution Modelling with MaxEnt

### 4.1 Model Configuration

Using `elapid.MaxentModel`:

```python
from elapid import MaxentModel

model = MaxentModel(
    feature_types=["linear", "quadratic", "hinge"],  # LQH features
    tau=0.5,               # prevalence prior
    n_hinge_features=50,
    n_threshold_features=50,
    beta_multiplier=1.5,   # regularisation (tune via cross-validation)
)
```

**Predictor variables**:
1. VIIRS DNB median radiance (ALAN proxy)
2. MODIS mean nighttime LST
3. MODIS mean daytime LST
4. Landsat summer median LST (100 m, for Ireland-only fine-scale model)
5. Copernicus land cover class / impervious surface fraction

### 4.2 Model Training and Evaluation

1. **Spatial cross-validation**: Use spatially-blocked k-fold CV (e.g., `sklearn.model_selection.GroupKFold` with grid-cell group labels, or `ENMeval`-style spatial blocks) to avoid spatial autocorrelation inflating AUC.
2. **Metrics**: AUC (ROC), Boyce Index (continuous), threshold-dependent sensitivity/specificity.
3. **Variable importance**: Permutation importance and marginal response curves for each predictor.
4. **Prediction surface**: Apply the fitted model across the raster stack to produce a continuous habitat suitability map using `elapid.apply_model_to_rasters()`.

### 4.3 Key Hypotheses to Test

| Hypothesis | Test | Expected Outcome |
|------------|------|------------------|
| H1: *S. nobilis* occurrence is positively associated with ALAN intensity | VIIRS radiance contribution to MaxEnt; univariate response curve | Positive monotonic or plateau response |
| H2: *S. nobilis* occurrence is positively associated with UHI (nighttime warmth) | Nighttime LST contribution; partial dependence | Positive response, consistent with Macaronesian thermal niche |
| H3: ALAN and UHI independently predict occurrence (not just co-varying urban proxies) | Compare full model AUC vs. single-predictor models; examine correlation between ALAN and LST | If both contribute unique variance, this supports distinct photic and thermal drivers |
| H4: Model trained on W. Europe predicts Irish distribution | Transferability assessment — train on W. Europe, predict Ireland, compare with held-out Irish records | Supports a conserved climatic/urban niche across the invasion range |

---

## Phase 5: Analysis and Visualisation

### 5.1 Exploratory Spatial Analysis

- Point density maps of *S. nobilis* occurrences overlaid on VIIRS and LST rasters.
- Violin plots of VIIRS radiance and nighttime LST at occurrence vs. background points.
- Spatial autocorrelation analysis (Moran's I) of occurrence residuals.

### 5.2 Figures for Publication

| Figure | Content | Tools |
|--------|---------|-------|
| Fig. 1 | Study area map with occurrence points, coloured by year | `geopandas`, `contextily` |
| Fig. 2 | VIIRS DNB composite for Ireland + W. Europe | `rasterio`, `matplotlib` |
| Fig. 3 | MODIS nighttime LST composite | `rasterio`, `matplotlib` |
| Fig. 4 | MaxEnt response curves for each predictor | `elapid`, `matplotlib` |
| Fig. 5 | Predicted habitat suitability map (continuous) | `rasterio`, `matplotlib` |
| Fig. 6 | Urban zoom panels (Dublin, Cork, London, Paris) | `folium` or `contextily` |

### 5.3 Statistical Reporting

- AUC ± SD from spatial cross-validation.
- Permutation importance table for all predictors.
- Comparison of AUC: full model vs. ALAN-only vs. LST-only vs. null model.

---

## Phase 6: Timeline and Milestones

| Week | Phase | Deliverable |
|------|-------|-------------|
| 1 | Occurrence data download and cleaning | `sn_occurrences_cleaned.gpkg` |
| 2 | GEE satellite data extraction and export | GeoTIFFs + CSVs on Google Drive |
| 3 | Raster alignment, stacking, background sampling | Aligned raster stack + background points |
| 4 | MaxEnt model training, tuning, cross-validation | Fitted model, AUC metrics |
| 5 | Prediction surfaces, figures, sensitivity analysis | Suitability maps, all figures |
| 6 | Write-up and manuscript preparation | Draft methods + results sections |

---

## Phase 7: Python Package Summary

| Package | Version (as of 2025) | Purpose | Install |
|---------|---------------------|---------|---------|
| `pyinaturalist` | 0.21.x | iNaturalist API client | `pip install pyinaturalist` |
| `pyinaturalist-convert` | latest | Format conversion for iNat data | `pip install pyinaturalist-convert` |
| `pygbif` | 0.6.x | GBIF API client | `pip install pygbif` |
| `earthengine-api` | 1.x | Google Earth Engine Python API | `pip install earthengine-api` |
| `geemap` | 0.35.x | GEE interactive mapping + export helpers | `pip install geemap` |
| `elapid` | 1.1.x | MaxEnt SDM for Python (JOSS-published) | `pip install elapid` |
| `geopandas` | 1.0.x | Vector geospatial operations | `pip install geopandas` |
| `rasterio` | 1.4.x | Raster I/O and operations | `pip install rasterio` |
| `rioxarray` | 0.17.x | xarray + rasterio bridge | `pip install rioxarray` |
| `xarray` | 2024.x | N-dimensional labelled arrays | `pip install xarray` |
| `scikit-learn` | 1.5.x | Model evaluation, cross-validation | `pip install scikit-learn` |
| `matplotlib` | 3.9.x | Static plotting | `pip install matplotlib` |
| `seaborn` | 0.13.x | Statistical visualisation | `pip install seaborn` |
| `folium` | 0.18.x | Interactive Leaflet maps | `pip install folium` |
| `contextily` | 1.6.x | Basemap tiles for matplotlib | `pip install contextily` |
| `shapely` | 2.0.x | Geometric operations | `pip install shapely` |

---

## Data Access and Accounts Required

| Service | URL | Account Needed | Notes |
|---------|-----|----------------|-------|
| Google Earth Engine | [earthengine.google.com](https://earthengine.google.com) | Google account + GEE project registration | Free for research use |
| GBIF | [gbif.org](https://www.gbif.org) | Free registration | Required for occurrence downloads; provides DOI for citation |
| iNaturalist | [inaturalist.org](https://www.inaturalist.org) | Optional (API works unauthenticated) | App token recommended for higher rate limits |
| NOAA EOG (direct VIIRS downloads, backup) | [eogdata.mines.edu](https://eogdata.mines.edu/products/vnl/) | Free registration | VNL v2.2 annual composites; use GEE as primary |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Insufficient occurrence records in Ireland alone | Weak MaxEnt model | Western Europe scope provides 1000s of additional records; Ireland-only sub-model as secondary analysis |
| Irish cloud cover limits Landsat LST availability | Gaps in thermal layer | Use multi-year (2017–present) median composite; fall back to MODIS 1 km if Landsat still patchy |
| Citizen-science spatial bias towards cities | Spurious correlation with urban variables | Bias-corrected background sampling using human population density surface; report sensitivity analysis with/without bias correction |
| VIIRS insensitivity to blue LED lighting | Underestimates true ALAN in LED-converted cities | Document as limitation; supplement with local council lighting data if available for Irish cities |
| Spatial resolution mismatch (satellite vs. microhabitat) | Model predicts macro-habitat, not micro-site | Frame results as landscape-scale suitability; discuss Clark & Johnson (2024) microclimate caveat |
