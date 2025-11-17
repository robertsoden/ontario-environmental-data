# Ontario Environmental Data Library

A Python library for accessing Ontario-specific environmental and biodiversity data sources.

## Overview

The `ontario-environmental-data` library provides clean, Pythonic interfaces to Ontario environmental data APIs including:

- **Biodiversity Data**: iNaturalist, eBird, GBIF
- **Water Quality**: DataStream, PWQMN (planned)
- **Forest Data**: Ontario FRI (planned)
- **Conservation Areas**: Ontario parks, conservation authorities

This library was created to share data access components between the [Ontario Nature Watch](https://github.com/robertsoden/onw) LLM agent and the [Williams Treaties](https://github.com/robertsoden/williams-treaties) mapping project.

## Features

✅ **Async/Await**: Fully async API clients using `aiohttp`
✅ **Type Hints**: Complete type annotations for better IDE support
✅ **Pydantic Models**: Data validation with Pydantic v2
✅ **Rate Limiting**: Automatic rate limiting to respect API limits
✅ **Retry Logic**: Exponential backoff on failures
✅ **GeoJSON Support**: Export observations as GeoJSON Features
✅ **Cultural Sensitivity**: Guidelines for working with Indigenous data

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

### Phase 1 (Current - v0.1.0)
✅ iNaturalist client
✅ eBird client
✅ Data models
✅ Constants

### Phase 2 (Planned - v0.2.0)
⏳ GBIF client
⏳ DataStream water quality
⏳ Spatial filtering utilities
⏳ Caching layer

### Phase 3 (Planned - v0.3.0)
⏳ Ontario FRI forest data
⏳ Conservation area boundaries
⏳ Indigenous Services Canada data
⏳ PostGIS integration utilities
