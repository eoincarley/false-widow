# Satellite-derived artificial light and land surface temperature predict the expanding distribution of *Steatoda nobilis* in Western Europe

## Background

The noble false widow spider (*Steatoda nobilis*) is one of Europe's most prominent synanthropic invasive arachnids. Native to Macaronesia and the western Mediterranean, it has spread rapidly through Britain and Ireland since the late 20th century, with established populations now recorded across urban and suburban environments in Western Europe. In Ireland, where it was first confirmed in 1999, the species has become a subject of public health concern due to its medically significant bite.

Despite growing occurrence data from citizen-science platforms, the environmental drivers of *S. nobilis* distribution remain poorly quantified. The species' apparent association with heated buildings and artificially lit environments suggests that remotely sensed proxies for urbanisation — particularly artificial light at night (ALAN) and land surface temperature (LST) — may be strong predictors of habitat suitability. No previous study has combined satellite-derived ALAN and multi-sensor LST data in a species distribution model for this species.

## Data

**Occurrence records.** 10,226 research-grade *S. nobilis* records were compiled from iNaturalist (via pyinaturalist) and GBIF (via pygbif), spanning 2017--2025. Records were merged, deduplicated by a 1 km spatial buffer, and filtered to the study area (35--60N, 12W--15E). Ireland contributed 232 records, predominantly clustered around Dublin and the east coast.

**Background points.** 10,000 pseudo-absence points were generated using a bias-corrected sampling grid that mirrors the spatial distribution of recording effort, preventing observer bias from being confounded with habitat preference.

**Satellite predictors.** Four environmental layers were derived from Google Earth Engine:

- **VIIRS DNB nighttime radiance** (2017--2024 median; nW/cm^2/sr) — proxy for ALAN / urbanisation.
- **MODIS daytime LST** (2017--2024 annual mean; C) — broadscale thermal environment.
- **MODIS nighttime LST** (2017--2024 annual mean; C) — nocturnal thermal buffering, relevant to a nocturnally active species.
- **Landsat 8/9 summer LST** (2017--2024 June--August median; C) — higher spatial resolution (30 m native, composited to 500 m for Ireland, 1 km for study area).

All layers were reprojected, resampled, and aligned to a common 1 km grid (EPSG:4326) for the full study area, with a separate 500 m Ireland-only stack for fine-scale analysis. Point values were extracted from both occurrence and background locations.

## Methods

**MaxEnt SDM.** A MaxEnt model was fitted using the `elapid` Python package with linear, hinge, and product feature types (beta multiplier = 1.5). The model was trained on 9,967 presence and 8,343 background samples (after dropping rows with missing satellite values, primarily over water).

**Spatial cross-validation.** Model performance was evaluated using 4-fold geographic k-fold cross-validation (`elapid.GeographicKFold`), which partitions the study area into spatially contiguous blocks to account for spatial autocorrelation.

**Variable importance.** Permutation importance was calculated by shuffling each predictor 10 times and measuring the resulting AUC drop.

**Prediction surfaces.** The trained model was applied to the full raster stacks to produce continuous habitat suitability maps for both the study area (1 km) and Ireland (500 m).

**Temporal expansion analysis.** For Ireland, cumulative geographic spread was tracked using ~10 km grid cells (0.1 degrees). A logistic growth model was fitted to the colonisation curve (2017--2025) and projected forward to estimate carrying capacity and saturation timelines. High-suitability grid cells with no records were identified as candidate locations for future colonisation.

## Results

### Exploratory analysis

Presence sites had significantly higher VIIRS nighttime radiance (median 8.7 vs 1.2 nW/cm^2/sr for background), confirming the species' association with artificially lit environments. Landsat summer LST was approximately 3C warmer at presence sites (median 35.1C vs 32.3C). The three LST variables were intercorrelated (r = 0.65--0.85) but VIIRS radiance was only weakly correlated with LST (r = 0.25--0.34), confirming it captures an independent environmental axis.

### Model performance

- **Training AUC:** 0.80
- **Spatial CV AUC:** 0.69 +/- 0.03 (4-fold geographic)

The gap between training and CV AUC reflects spatial autocorrelation inflation. A spatial CV AUC of 0.69 is moderate but reasonable given only four satellite-derived predictors covering a large geographic extent.

### Variable importance (permutation)

| Variable | Mean AUC drop |
|----------|:---:|
| MODIS daytime LST | 0.200 |
| Landsat summer LST | 0.152 |
| MODIS nighttime LST | 0.085 |
| VIIRS nighttime radiance | 0.059 |

Temperature variables dominate, with MODIS daytime LST as the single strongest predictor. VIIRS radiance (ALAN) contributes a smaller but distinct signal. Response curves show suitability increases monotonically with VIIRS radiance (saturating at approximately 60 nW/cm^2/sr), peaks at cooler temperate daytime LST (10--14C, consistent with a British/Atlantic climate), is unimodal for nighttime LST (peak at 8--10C), and increases above approximately 30C for Landsat summer LST.

### Prediction surfaces

The study-area suitability map identifies highest predicted suitability in southeastern England, the greater London area, northern France, and urban centres across the study area. Ireland shows elevated suitability around Dublin, Cork, Limerick, Galway, and Belfast — all urban areas with higher ALAN and LST.

### Temporal expansion in Ireland

Annual sightings in Ireland grew from 2 (2017) to 44 (2025). Cumulative geographic spread reached 85 unique ~10 km grid cells by 2025 (from 2 in 2017). A fitted logistic growth model estimates:

- **Carrying capacity (K):** 103 grid cells (+/- 23)
- **Growth rate (r):** 0.47/yr
- **Inflection year (t0):** 2022
- **75% of K reached by:** ~2025
- **90% of K reached by:** ~2027

34 high-suitability (>= 0.4) grid cells in Ireland have no records to date. The top candidates for future colonisation include areas around Tullamore/Athlone (midlands), Waterford, Naas/Kildare, Ennis/Shannon, Navan, and Dundalk/Newry — all locations with moderate urban development but lower citizen-science recorder effort.

## Conclusions

This study demonstrates that satellite-derived ALAN and LST are effective predictors of *S. nobilis* distribution at a continental scale. The species' niche is characterised by warmer temperate climates with moderate-to-high artificial lighting — consistent with its synanthropic ecology and dependence on heated built structures. In Ireland, the species has colonised approximately 75% of its predicted suitable range as of 2025, with the logistic model projecting near-saturation (~90%) by 2027. The remaining uncolonised high-suitability areas are concentrated in the Irish midlands and smaller regional towns, representing the most likely sites for new establishment in the coming years. These findings have direct relevance for public health surveillance and invasive species management prioritisation.
