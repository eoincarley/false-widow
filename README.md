# Predicting the distribution of *Steatoda nobilis* using satellite data

Species distribution modelling of the noble false widow spider across Western Europe, using satellite-derived artificial light at night and land surface temperature.

## Overview

The noble false widow spider (*Steatoda nobilis*) has rapidly colonised Britain, Ireland, and northern France over the past three decades. This project combines 10,226 citizen-science occurrence records (iNaturalist + GBIF) with four satellite-derived environmental predictors — VIIRS nighttime radiance, MODIS daytime and nighttime land surface temperature (LST), and Landsat summer LST — to build a MaxEnt species distribution model across Western Europe. High-suitability areas in Ireland not yet colonised are identified, and a control species (*Pholcus phalangioides*) is used to disentangle genuine range expansion from platform-driven recording effort.

## Repository structure

```
false-widow/
├── scripts/
│   ├── fetch_inaturalist.py        # Download iNaturalist occurrence records
│   ├── fetch_gbif.py               # Download GBIF occurrence records
│   ├── clean_occurrences.py        # Merge, deduplicate, and spatially thin records
│   ├── gee_extract.py              # Submit Google Earth Engine satellite export jobs
│   ├── download_gee_exports.py     # Verify GEE exports are downloaded
│   ├── prepare_rasters.py          # Reproject and align raster layers to common grids
│   ├── extract_points_local.py     # Sample satellite values at occurrence/background points
│   └── generate_background.py      # Generate bias-corrected pseudo-absence background points
├── notebooks/
│   └── analysis.ipynb              # MaxEnt model, cross-validation, figures, control analysis
├── research-paper/
│   ├── manuscript.tex              # LaTeX manuscript
│   ├── references.bib              # Bibliography
│   └── custom.bst                  # Custom BibTeX style (numbered, no titles, DOI hyperlinks)
├── data/                           # (gitignored — see Data section below)
│   ├── raw/                        # Raw downloads from APIs and GEE
│   ├── processed/                  # Cleaned, analysis-ready CSVs and raster stacks
│   └── cache/                      # Cached model and CV results (created by notebook)
├── outputs/                        # Figures (PNG) and suitability GeoTIFFs
├── requirements.txt                # Core Python dependencies (pinned)
├── requirements-fetch.txt          # Additional deps for data collection and control analysis
└── .gitignore
```

## Requirements

- **Python 3.9+** (tested with 3.9.1; should work through 3.12)
- **GDAL system library** — required by `rasterio` and `geopandas`. Install before `pip install`:
  - macOS: `brew install gdal`
  - Ubuntu/Debian: `sudo apt install gdal-bin libgdal-dev`
- **LaTeX** (optional) — only needed to compile the manuscript (`pdflatex` + `bibtex`)

## Quick start

```bash
git clone https://github.com/<username>/false-widow.git
cd false-widow

python3 -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-fetch.txt   # Needed for control group analysis (pyinaturalist)
```

Then obtain the data (see below) and run the notebook:

```bash
jupyter notebook notebooks/analysis.ipynb
```

## Data

The `data/` directory is **not included in the repository** (gitignored) because it contains large raster files (~560 MB). There are two ways to obtain it:

### Option A: Download the data archive (recommended)

Download the processed data from Zenodo and extract it into the project root:

```bash
# TODO: replace with actual Zenodo DOI URL once deposited
wget https://zenodo.org/records/XXXXXXX/files/false-widow-data.zip
unzip false-widow-data.zip -d .
```

This populates `data/raw/`, `data/processed/`, and `data/cache/`, including the raster stacks and cached model results needed by the notebook.

### Option B: Re-fetch from source (advanced)

This requires API credentials and a Google Earth Engine account. Install the additional dependencies first:

```bash
pip install -r requirements-fetch.txt
earthengine authenticate
```

Then run the data collection scripts in order (see pipeline below).

## Running the pipeline

### Data collection (optional — skip if using the data archive)

```bash
python scripts/fetch_inaturalist.py        # 1. Download iNaturalist records
python scripts/fetch_gbif.py               # 2. Download GBIF records
python scripts/clean_occurrences.py        # 3. Merge, deduplicate, thin to 1 km
python scripts/gee_extract.py              # 4. Submit GEE satellite export jobs
# 5. Download exported GeoTIFFs from Google Drive to data/raw/gee/
python scripts/download_gee_exports.py     # 6. Verify all GEE files are present
```

### Data processing

```bash
python scripts/prepare_rasters.py          # 7. Align rasters to common 1 km / 500 m grids
python scripts/extract_points_local.py     # 8. Sample satellite values at each point
python scripts/generate_background.py      # 9. Generate 10,000 bias-corrected background points
```

### Analysis

Open and run all cells in order:

```bash
jupyter notebook notebooks/analysis.ipynb
```

The notebook fits the MaxEnt model, runs spatial cross-validation, computes permutation importance, generates suitability maps, identifies high-suitability uncolonised areas, and performs the control species comparison. All manuscript and appendix figures are produced.

**Caching:** Expensive computations (model fitting, CV, permutation importance, raster prediction) are cached in `data/cache/`. On subsequent runs, only the plots are regenerated. To force a full recompute, set `FORCE_RECOMPUTE = True` in the first code cell.

Alternatively, to execute the notebook non-interactively:

```bash
jupyter nbconvert --to notebook --execute notebooks/analysis.ipynb --ExecutePreprocessor.timeout=600
```

### Compiling the manuscript

```bash
cd research-paper
pdflatex manuscript.tex
bibtex manuscript
pdflatex manuscript.tex
pdflatex manuscript.tex
```

The full LaTeX + BibTeX cycle is required to resolve citations and cross-references.

## Outputs

After running the notebook, the `outputs/` directory will contain:

### Manuscript figures

| File | Figure | Description |
|------|--------|-------------|
| `study_area_map.png` | Fig. 1 | Study area map with occurrence and background points |
| `violin_plots.png` | Fig. 2 | Satellite variable distributions: presence vs background |
| `suitability_map_combined.png` | Fig. 3 | Two-panel suitability map (Europe + Ireland) |
| `roc_curves.png` | Fig. 4 | ROC curves (training + spatial CV folds) |
| `variable_importance.png` | Fig. 5 | Permutation importance bar chart |
| `response_curves.png` | Fig. 6 | Marginal response curves |
| `ireland_uncolonised_suitable.png` | Fig. 7 | Colonised vs uncolonised high-suitability cells |

### Appendix figures (control species analysis)

| File | Description |
|------|-------------|
| `control_kde_all_variables.png` | KDE distributions of all four satellite variables for *S. nobilis*, *P. phalangioides*, and background |
| `control_ireland_map.png` | Ireland occurrence map: both species |
| `control_temporal.png` | Temporal comparison of annual iNaturalist records |
| `control_viirs_comparison.png` | VIIRS radiance violin + cumulative distribution comparison |
| `control_viirs_kde.png` | VIIRS radiance KDE comparison |

### Suitability rasters (gitignored)

| File | Description |
|------|-------------|
| `suitability_study_area_1km.tif` | Habitat suitability GeoTIFF, Western Europe (1 km) |
| `suitability_ireland_500m.tif` | Habitat suitability GeoTIFF, Ireland (500 m) |

### Other outputs

| File | Description |
|------|-------------|
| `correlation_heatmap.png` | Predictor correlation matrix |
| `kde_distributions.png` | KDE distributions of satellite variables (presence vs background) |

## Citation

> Carley, E. P. and Power, R. A. (2026). Predicting the distribution of *Steatoda nobilis* in Western Europe using satellite observations of artificial light and land surface temperature. *Biology and Environment: Proceedings of the Royal Irish Academy*.

## License

TBD
