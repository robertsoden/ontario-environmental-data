# Ontario Environmental Data Library

A Python library for accessing Ontario-specific environmental and biodiversity data sources.

## Overview

The `ontario-environmental-data` library provides clean, Pythonic interfaces to Ontario environmental data APIs including:

- **Biodiversity Data**: iNaturalist, eBird observations
- **Indigenous Data**: Water advisories, First Nations reserve boundaries, Community Well-Being Index
- **Protected Areas**: Ontario provincial parks, conservation authorities, watersheds
- **Fire Data**: CWFIS fire perimeters and fuel types
- **Boundary Data**: Municipal boundaries, conservation authority boundaries, watershed boundaries
- **Satellite/Raster Data**: NDVI vegetation indices, land cover classification, digital elevation models (see [Satellite Data Guide](docs/SATELLITE_DATA_GUIDE.md))

This library was created to share data access components between the [Ontario Nature Watch](https://github.com/robertsoden/onw) LLM agent and the [Williams Treaties](https://github.com/robertsoden/williams-treaties) mapping project.

## Data Architecture

This library manages two distinct types of environmental data with different workflows:

### Vector/Tabular Data (< 100 MB)

**What:** GeoJSON, JSON, CSV files with geographic features and observations

**Examples:**
- Protected area boundaries
- Fire perimeters
- Biodiversity observations
- Community points
- Municipal boundaries

**Collection:**
- Via Python library clients: `INaturalistClient`, `OntarioGeoHubClient`, etc.
- Via GitHub Actions: [Data Collection workflow](.github/workflows/data-collection.yml)
- Stored in repository: `data/processed/*.geojson`

**Usage:**
```python
from ontario_data import OntarioGeoHubClient
client = OntarioGeoHubClient()
parks = await client.get_provincial_parks()
```

### Raster/Tile Data (500 MB - 2 GB)

**What:** Satellite imagery derivatives as vector tiles for web mapping

**Examples:**
- NDVI vegetation indices (250m resolution, Ontario-wide)
- Land cover classification (30m, 19 classes)
- Digital elevation model (20m)

**Processing:**
- Via dedicated pipeline: `scripts/process_satellite_data.py`
- Via GitHub Actions: [Satellite Processing workflow](.github/workflows/satellite-processing.yml)
- Stored externally: AWS S3, Azure Blob Storage, or Cloudflare R2
- Takes 2-6 hours to process (multi-GB downloads + tile generation)

**Documentation:** See [Satellite Data Guide](docs/SATELLITE_DATA_GUIDE.md) for complete setup

**Why separate?** Raster data is:
- Too large for git repository (6-7 GB raw files)
- Requires specialized processing (rasterio, tippecanoe, GDAL)
- Needs cloud storage for tile serving
- Updated infrequently (annually or every 5 years)

## Features

✅ **Async/Await**: Fully async API clients using `aiohttp`
✅ **Type Hints**: Complete type annotations for better IDE support
✅ **Pydantic Models**: Data validation with Pydantic v2
✅ **Geometry Utilities**: Extract bounds, filter by bounding box, spatial processing
✅ **Configuration Management**: Centralized config for API keys and rate limits
✅ **Rate Limiting**: Automatic rate limiting to respect API limits
✅ **Retry Logic**: Exponential backoff on failures
✅ **GeoJSON Support**: Export observations as GeoJSON Features
✅ **Cultural Sensitivity**: Guidelines for working with Indigenous data
✅ **Comprehensive Tests**: 21 unit tests with >90% coverage

## Installation

### From PyPI (when published)

```bash
pip install ontario-environmental-data
```

### From GitHub

```bash
pip install git+https://github.com/robertsoden/ontario-environmental-data.git
```

### For development

```bash
git clone https://github.com/robertsoden/ontario-environmental-data.git
cd ontario-environmental-data
pip install -e ".[dev]"
```

## Quick Start

### iNaturalist - Biodiversity Observations

```python
import asyncio
from ontario_data.sources import INaturalistClient

async def get_observations():
    client = INaturalistClient()

    # Peterborough area bounding box
    bounds = (44.0, -79.5, 45.0, -78.5)  # (swlat, swlng, nelat, nelng)

    observations = await client.fetch(
        bounds=bounds,
        start_date="2024-01-01",
        end_date="2024-12-31",
        quality_grade="research"
    )

    print(f"Found {len(observations)} observations")
    for obs in observations[:5]:
        print(f"  - {obs['common_name']} ({obs['scientific_name']})")
        print(f"    Location: {obs['location']['coordinates']}")
        print(f"    URL: {obs['url']}")

asyncio.run(get_observations())
```

### eBird - Bird Observations

```python
import asyncio
import os
from ontario_data.sources import EBirdClient

async def get_bird_observations():
    # Get API key from https://ebird.org/api/keygen
    api_key = os.getenv("EBIRD_API_KEY")
    client = EBirdClient(api_key=api_key)

    # Get recent observations for Ontario
    observations = await client.fetch(
        region_code="CA-ON",
        back_days=7
    )

    print(f"Found {len(observations)} bird observations")
    for obs in observations[:5]:
        print(f"  - {obs['common_name']} ({obs['scientific_name']})")
        print(f"    Count: {obs['count']}")
        print(f"    Location: {obs['location_name']}")

asyncio.run(get_bird_observations())
```

### Using Data Models

```python
from ontario_data.models import BiodiversityObservation

# Create and validate observation
obs = BiodiversityObservation(
    source="iNaturalist",
    observation_id="123456",
    scientific_name="Dryocopus pileatus",
    common_name="Pileated Woodpecker",
    observation_date="2024-11-01",
    location={
        "type": "Point",
        "coordinates": [-78.3, 44.3]
    },
    observer="naturalist123",
    quality_grade="research"
)

# Export as GeoJSON
geojson_feature = obs.to_geojson_feature()
```

### Using Constants

```python
from ontario_data.constants import (
    WILLIAMS_TREATY_FIRST_NATIONS,
    ONTARIO_PLACE_ID,
    DATA_SOURCE_URLS
)

print(f"Williams Treaty First Nations: {WILLIAMS_TREATY_FIRST_NATIONS}")
print(f"iNaturalist Ontario Place ID: {ONTARIO_PLACE_ID}")
print(f"Data sources: {DATA_SOURCE_URLS}")
```

### Using Geometry Utilities

```python
from ontario_data.utils import get_bounds_from_aoi, filter_by_bounds

# Extract bounding box from AOI geometry
aoi = {
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [-79.0, 44.0],
            [-78.0, 44.0],
            [-78.0, 45.0],
            [-79.0, 45.0],
            [-79.0, 44.0]
        ]]
    }
}
bounds = get_bounds_from_aoi(aoi)
# Returns: (44.0, -79.0, 45.0, -78.0) as (swlat, swlng, nelat, nelng)

# Filter observations by bounds
observations = [
    {"id": 1, "lat": 44.5, "lng": -78.5, "species": "Deer"},
    {"id": 2, "lat": 43.0, "lng": -78.5, "species": "Bear"},
]
filtered = filter_by_bounds(observations, bounds)
# Returns only observations within the bounding box
```

### Using Configuration

```python
from ontario_data.config import OntarioConfig

# Create configuration
config = OntarioConfig(
    ebird_api_key="your-api-key",
    inat_rate_limit=100,  # Custom rate limit
    cache_ttl_hours=12    # Custom cache TTL
)

# Use with clients
from ontario_data.sources import EBirdClient
client = EBirdClient(api_key=config.ebird_api_key, rate_limit=config.inat_rate_limit)
```

## API Clients

### INaturalistClient

Community science biodiversity observations.

- **API Docs**: https://api.inaturalist.org/v1/docs/
- **No API key required**
- **Rate limit**: 60 requests/minute
- **Coverage**: 100K+ Ontario observations

### EBirdClient

Real-time bird observation data.

- **API Docs**: https://documenter.getpostman.com/view/664302/S1ENwy59
- **Requires free API key**: https://ebird.org/api/keygen
- **Rate limit**: 60 requests/minute
- **Coverage**: Comprehensive Ontario bird data

## Data Models

All models use Pydantic v2 for validation:

- `BiodiversityObservation`: Standardized observation format
- `GeoJSONPoint`: GeoJSON Point geometry with validation
- `Taxonomy`: Taxonomic information

## Environment Variables

```bash
# Optional - Get from https://ebird.org/api/keygen
EBIRD_API_KEY=your_ebird_key

# Future
DATASTREAM_API_KEY=your_datastream_key
```

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=ontario_data --cov-report=html
```

### Code Quality

```bash
# Format code
black ontario_data/ tests/

# Lint
ruff check ontario_data/ tests/

# Type check
mypy ontario_data/
```

## Cultural Sensitivity

When working with Indigenous data:

✅ Follow OCAP® principles (Ownership, Control, Access, Possession)
✅ Respect data sovereignty
✅ Include proper attribution
✅ Obtain permission for sensitive data
✅ Use respectful terminology

The Williams Treaty First Nations are:
- Alderville First Nation
- Curve Lake First Nation
- Hiawatha First Nation
- Mississaugas of Scugog Island First Nation
- Chippewas of Beausoleil First Nation
- Chippewas of Georgina Island First Nation
- Chippewas of Rama First Nation

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Attribution

### Data Sources

- **iNaturalist**: www.inaturalist.org (CC0, CC-BY, CC-BY-NC licenses)
- **eBird**: www.ebird.org (eBird Basic Dataset)
- **GBIF**: www.gbif.org (various licenses)

### Acknowledgments

- Williams Treaty First Nations
- Ontario conservation authorities
- Ontario Ministry of Natural Resources and Forestry
- Environment and Climate Change Canada

## Related Projects

- **Ontario Nature Watch**: https://github.com/robertsoden/onw - LLM agent for environmental queries
- **Williams Treaties**: https://github.com/robertsoden/williams-treaties - Interactive mapping project

## Contact

For questions or issues:
- Open an issue: https://github.com/robertsoden/ontario-environmental-data/issues
- Email: robertsoden@users.noreply.github.com

## Roadmap

### Phase 1 (v0.1.0) - COMPLETE
✅ iNaturalist client
✅ eBird client
✅ Data models (biodiversity)
✅ Constants
✅ Geometry utilities

### Phase 2 (v0.2.0) - COMPLETE
✅ **WaterAdvisoriesClient** - Indigenous Services Canada drinking water advisories
✅ **StatisticsCanadaWFSClient** - First Nations reserve boundaries via WFS
✅ **CWFISClient** - Fire perimeters from Canadian Wildland Fire Information System
✅ **OntarioGeoHubClient** - Provincial parks and conservation authorities
✅ New data models: WaterAdvisory, ReserveBoundary, FirePerimeter, ProtectedArea
✅ GeoDataFrame support
✅ Williams Treaty First Nations support

### Phase 3 (Planned - v0.3.0)
⏳ GBIF client for biodiversity
⏳ DataStream water quality client
⏳ PWQMN water quality client
⏳ Comprehensive test suite for all clients
⏳ Caching layer
⏳ Satellite data support (NDVI, land cover, DEM)
