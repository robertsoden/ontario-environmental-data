# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`ontario-environmental-data` is a Python library providing clean, async interfaces to Ontario environmental data APIs. It's designed to be shared between the Ontario Nature Watch LLM agent and the Williams Treaties mapping project.

Key features:
- Fully async API clients using `aiohttp`
- Pydantic v2 models for data validation
- Built-in rate limiting and retry logic with exponential backoff
- GeoJSON/GeoDataFrame support for spatial data
- Cultural sensitivity guidelines for working with Indigenous data

## Development Commands

### Installation
```bash
# Development installation with all dependencies
pip install -e ".[dev]"

# Include optional raster/satellite data dependencies
pip install -e ".[dev,raster]"
```

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_models.py -v

# Run with coverage
pytest tests/ --cov=ontario_data --cov-report=html

# Run only integration tests (requires API keys)
pytest tests/test_integration_real_apis.py -v
```

### Code Quality
```bash
# Format code (Black is configured for line-length 88)
black ontario_data/ tests/

# Lint with Ruff (auto-fix issues)
ruff check ontario_data/ tests/ --fix

# Type check with mypy
mypy ontario_data/

# Run all pre-commit hooks manually
pre-commit run --all-files
```

### Pre-commit Hooks
The project uses pre-commit hooks (Black, Ruff, trailing whitespace, etc.). They run automatically on commit. Install with:
```bash
pre-commit install
```

Note: GitHub workflow YAML files are excluded from YAML validation due to specific syntax requirements.

## Architecture

### Core Components

**`ontario_data/sources/`** - API client implementations
- `base.py`: `BaseClient` abstract class with rate limiting, retry logic, and error handling
- `biodiversity.py`: `INaturalistClient`, `EBirdClient` for species observations
- `indigenous.py`: `WaterAdvisoriesClient`, `StatisticsCanadaWFSClient` for First Nations data
- `protected_areas.py`: `OntarioGeoHubClient` for parks and conservation areas
- `fire.py`: `CWFISClient` for wildfire perimeters and fuel types
- `community.py`: `CommunityWellBeingClient`, `InfrastructureClient` for community data
- `satellite.py`: `SatelliteDataClient` for satellite imagery and raster data
- `boundaries.py`: `OntarioBoundariesClient` for administrative boundaries

**`ontario_data/models/`** - Pydantic v2 data models
- `biodiversity.py`: `BiodiversityObservation` with GeoJSON export
- `indigenous.py`: `WaterAdvisory`, `ReserveBoundary`
- `protected_areas.py`: `ProtectedArea`
- `fire.py`: `FirePerimeter`
- `community.py`: `CommunityWellBeing`, `InfrastructureProject`

**`ontario_data/constants/`** - Shared constants
- `regions.py`: Ontario place IDs, Williams Treaty First Nations list
- `data_sources.py`: API endpoint URLs and metadata

**`ontario_data/utils/`** - Utility functions
- `geometry.py`: `get_bounds_from_aoi()`, `filter_by_bounds()`, `point_in_bounds()`

**`ontario_data/validation.py`** - Data validation utilities
- Validates downloaded data files (GeoJSON, JSON, CSV)
- Checks geometry validity, required fields, minimum record counts
- Used by data collection scripts

### Client Implementation Pattern

All API clients inherit from `BaseClient` which provides:
1. **Rate limiting**: Automatic throttling to respect API limits (default 60 req/min)
2. **Retry logic**: Exponential backoff for failed requests (max 3 retries by default)
3. **Error handling**: Catches `aiohttp.ClientError` and raises `DataSourceError`

Example client structure:
```python
class MyClient(BaseClient):
    def __init__(self, api_key: str = None, rate_limit: int = 60):
        super().__init__(rate_limit=rate_limit)
        self.api_key = api_key

    async def fetch(self, **kwargs) -> List[Dict]:
        async with aiohttp.ClientSession() as session:
            # Use self._rate_limit_wait() before requests
            # Use self._retry_request() for automatic retries
            # Return standardized list of dicts
```

### Data Flow

1. **Client fetches data** → Returns `List[Dict]` with standardized fields
2. **Validate with Pydantic** → Optional validation using models from `ontario_data.models`
3. **Export options**:
   - JSON (native Python dicts)
   - GeoJSON (using model's `.to_geojson_feature()` method)
   - GeoDataFrame (using `gpd.GeoDataFrame.from_features()`)

### Root-Level Scripts

The repository includes several utility scripts in the root directory:

- **`collect_all_data.py`**: Main data collection script that fetches from all sources and saves to `data/` directory
- **`check_data_status.py`**: Validates collected data using validation utilities
- **`diagnose_data_sources.py`**: Tests connectivity to all data sources, useful for debugging API issues
- **`generate_williams_treaty_data.py`**: Specialized script for Williams Treaty First Nations data collection
- **`test_all_clients.py`**: Manual testing script for all API clients

These scripts are meant to be run directly (not imported) and demonstrate how to use the library.

## API Keys and Environment Variables

Some data sources require API keys:

```bash
# Required for eBird client
EBIRD_API_KEY=your_key_here  # Get from https://ebird.org/api/keygen

# Future data sources
DATASTREAM_API_KEY=your_key_here
```

API keys can be passed directly to clients or loaded from environment variables in the client implementations.

## Cultural Sensitivity - Indigenous Data

When working with Indigenous data (water advisories, reserve boundaries, Williams Treaty data):

- Follow OCAP® principles (Ownership, Control, Access, Possession)
- Include proper attribution in outputs
- Use respectful terminology
- The Williams Treaty First Nations are defined in `ontario_data.constants.regions.WILLIAMS_TREATY_FIRST_NATIONS`
- Consult documentation in the README for specific guidelines

## Testing Philosophy

- Unit tests mock external API calls (see `tests/conftest.py` for fixtures)
- Integration tests in `test_integration_real_apis.py` make real API calls (run separately)
- Tests use `pytest-asyncio` with `asyncio_mode = "auto"` configured in `pyproject.toml`
- Coverage target: >90%

## Type Hints and Validation

- All code uses Python 3.9+ type hints
- Pydantic v2 models validate data at runtime
- mypy is configured but `disallow_untyped_defs = false` to allow gradual typing
- Use `Optional[T]` for nullable fields, not `T | None` (for Python 3.9 compatibility)

## Common Patterns

### Fetching biodiversity data with bounds
```python
from ontario_data.sources import INaturalistClient

client = INaturalistClient()
bounds = (44.0, -79.5, 45.0, -78.5)  # (swlat, swlng, nelat, nelng)
observations = await client.fetch(bounds=bounds, start_date="2024-01-01")
```

### Working with GeoDataFrames
```python
import geopandas as gpd
from ontario_data.sources import OntarioGeoHubClient

client = OntarioGeoHubClient()
parks_gdf = await client.fetch_provincial_parks()
# Returns GeoDataFrame directly, ready for spatial operations
```

### Using validation utilities
```python
from ontario_data.validation import validate_geojson_file

gdf, warnings = validate_geojson_file(
    Path("data/parks.geojson"),
    min_features=10,
    required_properties=["name", "type"]
)
```

## Repository Relationship: ontario-environmental-data and williams-treaties

### Overview

**ontario-environmental-data** (this repo) is the **single source of truth** for all datasets:
- Python dataset registry (`ontario_data/datasets.py`) defining all datasets with metadata, S3 URLs, and styling
- Data collection scripts that fetch from APIs and process raw data
- S3 bucket (`ontario-environmental-data`) where all processed data is stored
- GitHub Pages catalog (`https://robertsoden.io/ontario-environmental-data/`) listing available datasets

**williams-treaties** is a **consuming application** that displays data from this repo:
- Map application UI (Mapbox-based)
- Layer configuration (`web/config/layers.yaml`) that references S3 URLs from ontario-environmental-data
- Custom styling and popups for the Williams Treaty context
- Local customizations (layer groupings, UI features)

### Key Principle

**No data should exist in williams-treaties that isn't in ontario-environmental-data S3.** The williams-treaties app should only reference URLs from the ontario-environmental-data S3 bucket. Local customizations are limited to display configuration (styling, popups, layer grouping).

### S3 URL Structure

All datasets follow a **category-based** structure:

```
s3://ontario-environmental-data/datasets/{category}/{filename}.geojson
```

**Categories:**
- `boundaries` - Administrative boundaries (municipalities, reserves, treaty areas)
- `biodiversity` - Species observations (eBird, iNaturalist)
- `community` - Community data (well-being, water advisories, infrastructure)
- `environmental` - Environmental features (ecoregions, fire perimeters, contours)
- `hydrology` - Water features (watersheds, wetlands, waterbodies, dams)
- `infrastructure` - Built features (trails, trail access points)
- `organizations` - Organizations (environmental charities)
- `protected_areas` - Protected lands (parks, conservation authorities)
- `satellite` - Raster data (NDVI, land cover)

**Naming convention:**
- Ontario-wide datasets: `{name}.geojson` (e.g., `ontario_reserves.geojson`)
- Williams Treaty subsets: `williams_treaty_{name}.geojson` (e.g., `williams_treaty_watersheds.geojson`)

The `scope` field in the dataset registry (`ontario` vs `williams_treaty`) is metadata only - it does not affect the S3 path structure.

### Workflow for Adding New Data

1. **Add to ontario-environmental-data first:**
   - Create/update collection function in `ontario_data/sources/`
   - Add `DatasetDefinition` to `ontario_data/datasets.py` with `s3_url`
   - Run collection script to generate data
   - Upload to S3 bucket
   - Run "Publish Data to GitHub Pages" workflow to update catalog

2. **Then add to williams-treaties:**
   - Add layer entry to `web/config/layers.yaml`
   - Set `data_url` to the S3 URL from ontario-environmental-data
   - Configure styling, popups, and legend
   - Push to deploy on Render

## Common Development Workflows

### Adding a new data source

1. Create new client in `ontario_data/sources/[category].py` extending `BaseClient`
2. Add Pydantic model in `ontario_data/models/[category].py` if needed
3. Add constants to `ontario_data/constants/data_sources.py`
4. Export from `ontario_data/sources/__init__.py` and `ontario_data/__init__.py`
5. Write tests in `tests/test_[category].py` with mocked responses
6. Update README.md with usage examples

### Working with satellite/raster data

The `[raster]` optional dependencies include `rasterio`, `xarray`, `pystac-client`, and `planetary-computer`. These are required for the `SatelliteDataClient` but not for core functionality.

## Version and Dependencies

- Current version: 0.2.0 (defined in `pyproject.toml` and `ontario_data/__init__.py`)
- Python support: 3.9, 3.10, 3.11, 3.12
- Build system: setuptools (not poetry/uv)
- Key dependencies: aiohttp, pydantic>=2.0, geopandas, shapely, pandas
