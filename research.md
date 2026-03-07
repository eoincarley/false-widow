# Literature Review: Noble False Widow Spider (*Steatoda nobilis*) in Ireland — Geospatial Distribution, Citizen Science, and Satellite-Derived Environmental Correlates

## 1. Introduction and Scope

The noble false widow spider (*Steatoda nobilis*) is one of the most notable invasive arachnid species globally, having expanded from its probable native range in the Canary Islands and Madeira to establish populations across Western Europe, the British Isles, California, Chile, and the Middle East (Bauer et al., 2019). In Ireland, where it was first recorded in 1999 from a single locality in Co. Wicklow (National Museum of Ireland records), it has become the subject of considerable public and scientific attention. This review examines the current literature on (i) the geospatial distribution and citizen-science mapping of *S. nobilis* in Ireland, (ii) studies correlating arthropod or insect distributions with satellite-derived urban heat island (UHI) and artificial light at night (ALAN) data, and (iii) the feasibility and gaps relevant to a proposed correlation of false widow geospatial records with satellite heat or light maps.

## 2. Distribution and Citizen Science Mapping of *S. nobilis* in Ireland

### 2.1 Key Irish Studies

The foundational study on the Irish distribution of *S. nobilis* is that of **Dugon et al. (2017)**, published in *Biology and Environment: Proceedings of the Royal Irish Academy*. This work combined citizen-science reports gathered via social media with systematic field surveys conducted between September 2014 and February 2017. The study yielded 36 positive reports across 13 counties from public submissions, and 14 confirmed locations across 6 counties from 32 surveyed sites. The species was characterised as having strong synanthropic affinities, predominantly colonising man-made structures (steel, concrete, timber) such as sheds, outhouses, and boundary railings.

Subsequent work from the **Venom Systems & Proteomics Laboratory** at NUI Galway (now University of Galway), led by Michel Dugon and John Dunbar, has continued to document the species' expanding range. The species is now recorded from at least 17 Irish counties and is found year-round in both indoor and outdoor habitats. A dedicated public-facing resource ([falsewidowspiderireland.ie](https://falsewidowspiderireland.ie/)) serves as both an information portal and a data-gathering tool, encouraging members of the public to report sightings to falsewidow@nuigalway.ie.

### 2.2 Wider European and Global Distribution Mapping

**Bauer et al. (2019)** provided the most comprehensive synthesis of *S. nobilis* distribution trends to date, published in *NeoBiota*. Drawing on data from museum collections, the Spider and Harvestman Recording Scheme of the British Arachnological Society, published literature, and original field observations from England, Germany, France, and Ecuador, they documented a significant northward expansion in Britain following decades of relative stasis in the far south of England. The study also noted that distribution maps likely under-record the species' true range, as the density of *S. nobilis* in the built environment is difficult to quantify due to access restrictions and high habitat heterogeneity.

**Dunbar et al. (2022)** further documented the ecological impact of *S. nobilis* in its invaded range, demonstrating that its venom potency is up to 230 times greater than that of native Irish spider species, allowing it to displace native synanthropic spiders from shared habitats (*Toxins*, 2022). Records of vertebrate predation — including a pipistrelle bat in Britain (Dunbar et al., 2022, *Ecosphere*) and a pygmy shrew (Dugon et al., 2023, *Ecosphere*) — underscore the species' ecological significance.

### 2.3 Methodological Observations

The Irish citizen-science approach relies heavily on photographic submissions via social media and email, with expert verification at NUI Galway. While effective for broad range documentation, these data are inherently presence-only and subject to spatial biases (e.g., higher reporting rates near population centres, media-driven reporting spikes). Bauer et al. (2019) noted that the northward expansion in Britain "highly correlates with a massive rise in press coverage," complicating interpretation of whether apparent range expansion reflects genuine spread or increased detection effort.

## 3. Urban Heat Islands, Light Pollution, and Arthropod Distributions

### 3.1 Spider Communities and the Urban Heat Island Effect

A growing body of literature links UHI intensity to spider community composition and individual fitness, though none of these studies has yet focused on *Steatoda nobilis*.

The most directly relevant programme of research concerns the **western black widow spider (*Latrodectus hesperus*)** in the Phoenix, Arizona metropolitan area, led by J.C. Johnson and collaborators. Key findings include:

- **Johnson et al. (2019)**, in *Animal Behaviour*, demonstrated that UHI conditions (urban refuges ~6 degrees C hotter than surrounding Sonoran Desert habitats in July) increase spider mortality, lengthen inter-moult intervals, and decrease growth rates across all life stages.
- **Clark & Johnson (2024)**, in *Journal of Thermal Biology*, measured the "functional microclimate" within black widow webs, finding a strong **nighttime** (but not daytime) UHI effect: urban webs were 2-5 degrees C warmer than desert webs at night, with the effect most prominent in spring. Web temperature correlated positively with spider boldness but showed no relationship with prey capture, web size, or body condition.

At the community level, a study of **20,499 spiders (137 species) across 36 grassland sites in Rennes, France** (published in *Land*, 2024, MDPI) found that intense UHI conditions were associated with species-poor communities dominated by small, thermophilic species. Large-bodied and heat-sensitive species declined as UHI intensity increased and local vegetation complexity was reduced.

**Critically, none of these studies used satellite-derived land surface temperature (LST) as a direct predictor of spider distribution.** The Clark & Johnson (2024) study explicitly noted the limitation that satellite LST sensors measure only the visible surface (e.g., rooftops, canopy tops) and cannot detect the understory microclimates where terrestrial arthropods actually experience temperature.

### 3.2 Artificial Light at Night (ALAN) and Insect/Arthropod Distributions

A substantial and growing literature documents the effects of ALAN on insect communities, with several studies explicitly using satellite-derived light data (DMSP-OLS and VIIRS Day/Night Band) as environmental predictors:

- **Wilson et al. (2018)**, in *Journal of Insect Conservation*, analysed the abundance of 100 widespread macro-moth species in the UK and Ireland using light-trap records from the **Garden Moth Scheme** (2005-2015) — a citizen-science initiative. Sites were classified into low, medium, and high nighttime illumination categories using satellite imagery. The medium-to-low lighting abundance ratio explained a significant 20% of variance in long-term moth population trends (P < 0.001). This is one of the clearest examples of directly correlating satellite-measured ALAN with citizen-science arthropod occurrence data.
- **Boyes et al. (2021)**, in *Science Advances*, used a matched-pairs experimental design to show that street lighting reduced moth caterpillar abundance by 47% in hedgerows and 33% in grass margins compared with unlit sites.
- **Owens et al. (2020)**, in *Biological Conservation*, reviewed the multiple pathways through which light pollution drives insect declines, including attraction, disruption of development, movement, foraging, and reproduction.
- A study in *iScience* (2023) documented immediate trophic-level shifts upon introduction of ALAN, with increased abundance of predators, scavengers, and parasites in arthropod communities.

**The VIIRS DNB instrument**, aboard the Suomi NPP satellite (operational since 2012), provides ~750 m resolution global nighttime radiance data and is the current standard for mapping ALAN in ecological studies. However, it has known limitations: it is insensitive to the blue wavelengths emitted by LED street lighting, potentially underestimating actual light exposure in cities that have switched to LED fixtures.

### 3.3 Satellite Remote Sensing and Species Distribution Modelling (SDM)

The most mature application of satellite-derived environmental data in arthropod SDMs is in **mosquito ecology**. Satellite land surface temperature (from MODIS and Landsat TIRS), NDVI, and microwave-derived soil moisture have been used extensively to model the distribution of disease vectors such as *Aedes aegypti* (e.g., Nature Scientific Reports, 2020) and malaria-transmitting *Anopheles* species. Models using AMSR-E satellite-derived data have been shown to outperform weather-station-based models in forecasting accuracy despite coarser spatial resolution (Chuang et al., 2012, *Remote Sensing of Environment*). NASA's Applied Remote Sensing Training (ARSET) programme now offers dedicated courses on species distribution modelling with satellite data, reflecting the maturity of this approach for certain taxa.

For terrestrial arthropods in urban contexts, however, the integration of satellite-derived LST or ALAN into formal SDMs remains rare. Most urban spider ecology studies use in-situ temperature loggers or weather station data rather than satellite products.

## 4. Gap Analysis: Has This Study Been Done?

**No study has been published that correlates the geospatial distribution of *Steatoda nobilis* (or any closely related theridiid spider) with satellite-derived urban heat island or nighttime light data.** This represents a clear gap in the literature.

The closest analogues are:

| Study | Taxon | Satellite Data | Citizen Science |
|-------|-------|----------------|-----------------|
| Wilson et al. (2018) | UK/Ireland macro-moths | VIIRS/DMSP nighttime light | Yes (Garden Moth Scheme) |
| Clark & Johnson (2024) | *Latrodectus hesperus* | None (in-situ loggers) | No |
| Rennes spider community (2024) | Multi-species (137 spp.) | None (weather stations) | No |
| Chuang et al. (2012) | Mosquitoes (*Aedes*) | AMSR-E, MODIS | No |
| Nature Sci. Rep. (2020) | *Aedes aegypti* | Landsat-8 TIRS | No |

The proposed study — correlating citizen-science records of *S. nobilis* in Ireland with Landsat/MODIS LST and VIIRS ALAN data — would therefore be **novel** in combining: (a) an invasive synanthropic spider, (b) citizen-science occurrence data, and (c) satellite-derived environmental layers within a formal geospatial or SDM framework.

## 5. Feasibility Considerations

### 5.1 Strengths of the Proposed Approach

- *S. nobilis* is strongly synanthropic, with its distribution tied to the built environment — precisely where UHI and ALAN effects are most pronounced. Its thermal ecology as a species of Macaronesian origin suggests it may preferentially colonise warmer urban microclimates.
- Citizen-science data from the NUI Galway programme and from iNaturalist/GBIF provide a growing spatial dataset of georeferenced occurrence records.
- Freely available satellite products (Landsat-8/9 LST at 100 m, MODIS LST at 1 km, VIIRS DNB at 750 m, and Sentinel-3 SLSTR) offer adequate temporal and spatial resolution for urban-scale analysis in Irish cities.

### 5.2 Challenges and Limitations

- **Spatial resolution mismatch**: Satellite LST (100 m-1 km) captures roof-level temperature, not the ground-level or wall-crevice microclimates inhabited by *S. nobilis*. Clark & Johnson (2024) emphasise this disconnect.
- **Presence-only data**: Citizen-science records lack structured absences, requiring pseudo-absence generation or use of presence-only SDM methods (MaxEnt, ensemble models).
- **Reporting bias**: Records cluster near population centres and media-awareness events, confounding any correlation with urban environmental variables.
- **Cloud cover**: Ireland's persistent cloud cover limits the temporal availability of clear-sky Landsat and MODIS thermal scenes, particularly in winter.

### 5.3 Recommended Data Sources

| Data Layer | Source | Resolution | Access |
|------------|--------|------------|--------|
| Land surface temperature | Landsat-8/9 TIRS | 100 m | USGS EarthExplorer (free) |
| Land surface temperature | MODIS (Terra/Aqua) | 1 km | NASA Earthdata (free) |
| Nighttime light / ALAN | VIIRS DNB (Suomi NPP) | 750 m | NOAA EOG (free) |
| Spider occurrence records | NUI Galway, iNaturalist, GBIF | Point data | Open access |
| Urban land cover | Copernicus Urban Atlas | 2.5 m | Copernicus (free) |

## 6. Conclusions

The noble false widow spider is well studied in Ireland from a distributional, venomics, and public-health perspective, with an active citizen-science reporting infrastructure centred at the University of Galway. The broader ecological literature demonstrates clear relationships between urban heat islands, artificial light at night, and arthropod community structure — with the moth-ALAN and black widow-UHI systems being the most developed examples. However, **no published study has yet correlated the geospatial distribution of any spider species with satellite-derived heat or light maps**, and no such study exists for *S. nobilis* specifically. The proposed correlation of Irish false widow records with Landsat/MODIS thermal data and VIIRS nighttime light imagery would therefore represent a genuinely novel contribution at the intersection of invasion ecology, urban ecology, remote sensing, and citizen science.

## Key References

- Bauer, T. et al. (2019). *Steatoda nobilis*, a false widow on the rise: a synthesis of past and current distribution trends. *NeoBiota*, 42, 19-43. [Link](https://neobiota.pensoft.net/article/31582/)
- Boyes, D.H. et al. (2021). Street lighting has detrimental impacts on local insect populations. *Science Advances*, 7(35). [Link](https://www.science.org/doi/10.1126/sciadv.abi8322)
- Boyes, D.H. et al. (2021). Is light pollution driving moth population declines? A review of causal mechanisms across the life cycle. *Insect Conservation and Diversity*. [Link](https://resjournals.onlinelibrary.wiley.com/doi/10.1111/icad.12447)
- Chuang, T.W. et al. (2012). Satellite microwave remote sensing for environmental modeling of mosquito population dynamics. *Remote Sensing of Environment*, 125, 147-156. [Link](https://www.sciencedirect.com/science/article/abs/pii/S0034425712002921)
- Clark, R.C. & Johnson, J.C. (2024). The functional microclimate of an urban arthropod pest: Urban heat island temperatures in webs of the western black widow spider. *Journal of Thermal Biology*, 119, 103769. [Link](https://www.sciencedirect.com/science/article/abs/pii/S0306456524000329)
- Dugon, M.M. et al. (2017). Occurrence, reproductive rate and identification of the non-native Noble false widow spider *Steatoda nobilis* (Thorell, 1875) in Ireland. *Biology and Environment: Proceedings of the Royal Irish Academy*, 117B(2), 77-89. [Link](https://www.researchgate.net/publication/319881734)
- Dugon, M.M. et al. (2023). Predation on a pygmy shrew, *Sorex minutus*, by the noble false widow spider, *Steatoda nobilis*. *Ecosphere*, 14(2), e4422. [Link](https://esajournals.onlinelibrary.wiley.com/doi/full/10.1002/ecs2.4422)
- Dunbar, J.P. et al. (2022). Webslinger vs. Dark Knight: First record of a false widow spider *Steatoda nobilis* preying on a pipistrelle bat in Britain. *Ecosphere*, 13(1), e3959. [Link](https://esajournals.onlinelibrary.wiley.com/doi/full/10.1002/ecs2.3959)
- Dunbar, J.P. et al. (2022). Worldwide Web: High venom potency and ability to optimize venom usage make the globally invasive Noble False Widow Spider highly competitive. *Toxins*, 14(9), 587. [Link](https://www.mdpi.com/2072-6651/14/9/587)
- Johnson, J.C. et al. (2019). Urban heat island conditions experienced by the Western black widow spider (*Latrodectus hesperus*): Extreme heat slows development but results in behavioral accommodations. *PLOS ONE*. [Link](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0220153)
- Owens, A.C.S. et al. (2020). Light pollution is a driver of insect declines. *Biological Conservation*, 241, 108259. [Link](https://www.sciencedirect.com/science/article/abs/pii/S0006320719307797)
- Prieto-Benitez, S. & Mendez, M. (2020). Predicting *Aedes aegypti* infestation using landscape and thermal features. *Scientific Reports*, 10, 21688. [Link](https://www.nature.com/articles/s41598-020-78755-8)
- Rennes spider community study (2024). Urban Heat Island and Reduced Habitat Complexity Explain Spider Community Composition by Excluding Large and Heat-Sensitive Species. *Land*, 13(1), 83. [Link](https://www.mdpi.com/2073-445X/13/1/83)
- Wilson, J.F. et al. (2018). A role for artificial night-time lighting in long-term changes in populations of 100 widespread macro-moths in UK and Ireland: a citizen-science study. *Journal of Insect Conservation*, 22, 189-196. [Link](https://link.springer.com/article/10.1007/s10841-018-0052-1)
