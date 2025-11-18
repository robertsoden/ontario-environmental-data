# Comprehensive Data Requirements Analysis
## ontario-environmental-data Library for ONW + williams-treaties

**Date**: 2025-11-17
**Purpose**: Ensure ontario-environmental-data library can 100% accommodate data and settings from both parent projects

---

## Executive Summary

The ontario-environmental-data library was created to share data access components between:
1. **ONW (Ontario Nature Watch)** - LLM agent for environmental queries
2. **williams-treaties** - Interactive mapping project for Williams Treaty territories

**Current Library Coverage**: ~20% of combined requirements
**Status**: ⚠️ NOT READY for full integration
**Critical Gaps**: 8 major data sources missing, geometry utilities incomplete, no tests for API clients

---

## Project Overview

### ONW (Ontario Nature Watch)
- **Type**: LangGraph-based LLM agent with ReAct architecture
- **Infrastructure**: PostgreSQL/PostGIS + eoAPI (STAC) + RAG vector DB
- **Data Strategy**: Pre-ingest large datasets into PostGIS, query on-demand for biodiversity
- **Current Library Usage**: ✅ Already using ontario_data for iNaturalist + eBird
- **Location**: https://github.com/robertsoden/onw

### williams-treaties
- **Type**: Interactive web map (Flask + Folium)
- **Infrastructure**: File-based, GeoJSON outputs
- **Data Strategy**: Download and process to static GeoJSON files
- **Current Library Usage**: ❌ Not using library yet
- **Location**: https://github.com/robertsoden/williams-treaties

---

## Complete Data Source Requirements

### ✅ IMPLEMENTED (2 sources)

| Source | ONW | williams-treaties | Library Status | Notes |
|--------|-----|-------------------|----------------|-------|
| **iNaturalist** | ✅ Used | ❌ Not used | ✅ `INaturalistClient` | Fully functional |
| **eBird** | ✅ Used | ❌ Not used | ✅ `EBirdClient` | Fully functional |

### 🔴 CRITICAL - Missing Sources (4 sources)

| Source | ONW | williams-treaties | Library Status | Priority |
|--------|-----|-------------------|----------------|----------|
| **ISC Water Advisories** | ✅ Required | ✅ Required | ❌ Missing | **HIGHEST** |
| **Stats Canada WFS (Reserves)** | ✅ Required | ✅ Required | ❌ Missing | **HIGHEST** |
| **CWFIS Fire Data** | ✅ Required | ✅ Required | ❌ Missing | **HIGH** |
| **Ontario GeoHub** | ✅ Required | ✅ Required | ❌ Missing | **HIGH** |

### 🟡 HIGH PRIORITY - Missing Sources (4 sources)

| Source | ONW | williams-treaties | Library Status | Priority |
|--------|-----|-------------------|----------------|----------|
| **DataStream (Water Quality)** | ✅ Required | ❌ Not used | ❌ Missing | **MEDIUM-HIGH** |
| **PWQMN (Water Quality)** | ✅ Required | ❌ Not used | ❌ Missing | **MEDIUM** |
| **Conservation Areas** | ✅ Required | ✅ Required | ❌ Missing | **MEDIUM** |
| **Ontario Parks** | ✅ Required | ❌ Not used | ❌ Missing | **MEDIUM** |

### 🟢 LOWER PRIORITY - Missing Sources (7 sources)

| Source | ONW | williams-treaties | Library Status | Priority |
|--------|-----|-------------------|----------------|----------|
| **Satellite Data (Landsat/Sentinel)** | ❌ Not used | ✅ Required | ❌ Missing | **MEDIUM** |
| **Land Cover** | ❌ Not used | ✅ Required | ❌ Missing | **MEDIUM** |
| **NDVI** | ❌ Not used | ✅ Required | ❌ Missing | **MEDIUM** |
| **DEM (Elevation)** | ❌ Not used | ✅ Required | ❌ Missing | **MEDIUM** |
| **GBIF** | ✅ Planned | ❌ Not used | ❌ Missing | **LOW** |
| **Community Well-Being** | ✅ Required | ✅ Required | ❌ Missing | **LOW** |
| **Infrastructure Projects** | ✅ Required | ✅ Required | ❌ Missing | **LOW** |

### 📊 SPECIAL - Analytics/Global Sources

| Source | ONW | williams-treaties | Library Status | Notes |
|--------|-----|-------------------|----------------|-------|
| **WRI Analytics API** | ✅ Required | ❌ Not used | ❌ Missing | ONW-specific, global scope |
| **GADM** | ✅ Required | ❌ Not used | ❌ Missing | Global admin boundaries |
| **KBA** | ✅ Required | ❌ Not used | ❌ Missing | Key biodiversity areas |
| **WDPA** | ✅ Required | ❌ Not used | ❌ Missing | Protected areas (10GB) |
| **LANDMARK** | ✅ Required | ❌ Not used | ❌ Missing | Indigenous territories |

---

## Detailed Source Analysis

### 1. 🔴 ISC Water Advisories (CRITICAL)

**Why Critical**: Core Indigenous health/safety data used by both projects

**ONW Implementation**: `src/ingest/ingest_water_advisories.py`
- Downloads CSV from ISC website manually
- Filters to Ontario
- Loads into PostGIS table: `water_advisories`
- Fields: community, first_nation, advisory_type, date_issued, date_lifted, lat/lng

**williams-treaties Implementation**: `scripts/10_process_water_advisories.py`
- Reads local CSV: `data/raw/water_advisory_map_data_2025_11_13.csv`
- Filters to Williams Treaty territories
- Outputs GeoJSON files

**Data Source**:
- URL: https://www.sac-isc.gc.ca/eng/1506514143353/1533317130660
- Format: CSV (manual download required)
- Coverage: All First Nations in Canada
- Update Frequency: Weekly/monthly

**Required Client**:
```python
class WaterAdvisoriesClient(BaseClient):
    """Client for Indigenous Services Canada drinking water advisories."""

    async def fetch_advisories(
        self,
        province: Optional[str] = "ON",
        active_only: bool = False
    ) -> List[Dict]:
        """Fetch drinking water advisories for First Nations."""
```

**Challenge**: No public API - requires web scraping or manual CSV download

---

### 2. 🔴 Statistics Canada WFS - Reserve Boundaries (CRITICAL)

**Why Critical**: Essential for spatial filtering to Indigenous territories

**ONW Implementation**: `src/ingest/ingest_williams_treaty.py`
- Uses WFS request to Stats Canada GeoServer
- Filters to 7 Williams Treaty First Nations
- Loads into PostGIS: `williams_treaty_boundaries`

**williams-treaties Implementation**: `scripts/07_download_williams_treaty_communities.py`
- Same WFS approach
- Hardcoded fallback with community coordinates
- Outputs GeoJSON boundaries

**Data Source**:
- WFS URL: `https://geo.statcan.gc.ca/geoserver/census-recensement/wfs`
- Layer: Indigenous reserve boundaries
- Also available: https://open.canada.ca/data/en/dataset/522b07b9-78e2-4819-b736-ad9208eb1067
- Format: WFS, GeoJSON, Shapefile, GeoPackage

**Required Client**:
```python
class StatisticsCanadaWFSClient(BaseClient):
    """Client for Statistics Canada geospatial WFS services."""

    async def get_reserve_boundaries(
        self,
        province: Optional[str] = None,
        first_nations: Optional[List[str]] = None
    ) -> gpd.GeoDataFrame:
        """Fetch First Nations reserve boundaries."""
```

**Implementation Notes**:
- Should return GeoDataFrame for spatial operations
- williams-treaties has working WFS code to port

---

### 3. 🔴 CWFIS - Fire Data (HIGH PRIORITY)

**Why Critical**: Environmental hazard monitoring for Indigenous territories

**ONW Implementation**: `src/ingest/ingest_williams_treaty.py` (includes fire data queries)
- Queries PostGIS table: `ontario_fire_incidents`
- Pre-loaded historical fire perimeter data

**williams-treaties Implementation**:
- `scripts/04_download_fire_data.py`
- `scripts/06_download_fire_fuel_dem.py`
- Fire perimeters 1976-2024 (37 fires documented)
- Wildland fuel type classifications

**Data Sources**:
1. **CWFIS (Primary)**
   - Base URL: `https://cwfis.cfs.nrcan.gc.ca/datamart`
   - WMS/WFS: `https://cwfis.cfs.nrcan.gc.ca/geoserver/public/ows`
   - Provides: Fire perimeters, fuel types, fire weather indices

2. **Ontario GeoHub (Alternative)**
   - Portal: `https://geohub.lio.gov.on.ca/`
   - Historical Ontario fire data
   - MNRF maintained

3. **NBAC (Alternative)**
   - National Burned Area Composite
   - URL: https://open.canada.ca/data/en/dataset/9d8f219c-4df0-4481-926f-8a2a532ca003
   - 30m Landsat-derived burned areas

**Required Client**:
```python
class CWFISClient(BaseClient):
    """Client for Canadian Wildland Fire Information System."""

    async def get_fire_perimeters(
        self,
        bounds: tuple,
        start_year: int,
        end_year: int
    ) -> gpd.GeoDataFrame:
        """Fetch historical fire perimeter polygons."""

    async def get_fuel_types(
        self,
        bounds: tuple
    ) -> gpd.GeoDataFrame:
        """Fetch wildland fuel type classifications."""

    async def get_current_fire_danger(
        self,
        bounds: tuple
    ) -> Dict:
        """Fetch current fire weather indices."""
```

**Implementation Notes**:
- williams-treaties scripts note "requires manual download"
- Provides WMS/WFS endpoints - can be automated
- Should return GeoDataFrame for vector data

---

### 4. 🔴 Ontario GeoHub - Multiple Datasets (HIGH PRIORITY)

**Why Critical**: Primary source for Ontario government environmental data

**ONW Implementations**:
- `src/ingest/ingest_ontario_parks.py` - Provincial parks
- `src/ingest/ingest_conservation_areas.py` - Conservation authority boundaries

**Data Sources via Ontario GeoHub**:

1. **Provincial Parks**
   - URL: `https://ws.lioservices.lrc.gov.on.ca/arcgis1071a/rest/services/LIO_Cartographic/LIO_Topographic/MapServer/9/query`
   - Format: ArcGIS REST API, GeoJSON
   - Contains: Park boundaries, names, classifications, area

2. **Conservation Authority Boundaries**
   - URL: `https://ws.lioservices.lrc.gov.on.ca/arcgis1071a/rest/services/MOE/Conservation_Authorities/MapServer/0/query`
   - Format: ArcGIS REST API, GeoJSON

3. **Fire Data** (see CWFIS section)

**Required Client**:
```python
class OntarioGeoHubClient(BaseClient):
    """Client for Ontario GeoHub / Land Information Ontario (LIO)."""

    async def get_provincial_parks(
        self,
        bounds: Optional[tuple] = None
    ) -> gpd.GeoDataFrame:
        """Fetch Ontario provincial parks and conservation reserves."""

    async def get_conservation_authorities(
        self,
        bounds: Optional[tuple] = None
    ) -> gpd.GeoDataFrame:
        """Fetch conservation authority boundaries."""
```

**Implementation Notes**:
- ArcGIS REST API - can use `arcgis` or custom HTTP client
- Should return GeoDataFrame
- ONW has working code to port

---

### 5. 🟡 DataStream - Water Quality (MEDIUM-HIGH)

**Why Important**: Ontario-specific water quality monitoring

**ONW Implementation**: Planned but not yet implemented
- Listed in ontario_handler.py as planned source
- Configuration exists in OntarioConfig

**Data Source**:
- Organization: DataStream
- Coverage: Community-led water quality monitoring
- API: Requires API key

**Required Client**:
```python
class DataStreamClient(BaseClient):
    """Client for DataStream water quality data."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def get_water_quality(
        self,
        bounds: tuple,
        start_date: str,
        end_date: str
    ) -> List[Dict]:
        """Fetch water quality observations."""
```

---

### 6. 🟡 PWQMN - Provincial Water Quality (MEDIUM)

**Why Important**: Official Ontario government water monitoring

**ONW Implementation**: Planned but not yet implemented
- Listed in ontario_handler.py as planned source

**Data Source**:
- Full Name: Provincial Water Quality Monitoring Network
- Organization: Ontario Ministry of Environment
- Access: Requires investigation of API availability

**Required Client**:
```python
class PWQMNClient(BaseClient):
    """Client for Provincial Water Quality Monitoring Network."""

    async def get_water_quality(
        self,
        bounds: tuple,
        start_date: str,
        end_date: str,
        parameters: Optional[List[str]] = None
    ) -> List[Dict]:
        """Fetch water quality measurements."""
```

---

### 7. 🟢 Satellite Data - Land Cover, NDVI, DEM (MEDIUM)

**Why Important**: Ecosystem monitoring for williams-treaties

**williams-treaties Implementation**:
- `scripts/02_download_landcover.py` - Land cover classification
- `scripts/03_process_ndvi.py` - Vegetation health indices
- `scripts/download_cdem_2m.py` - Digital elevation models
- Uses: Planetary Computer, Google Earth Engine, STAC catalogs

**Data Sources**:
1. **Microsoft Planetary Computer**
   - Landsat, Sentinel-2, MODIS imagery
   - Land cover products
   - NDVI time series

2. **Google Earth Engine**
   - Alternative satellite data access
   - Requires Earth Engine API key

3. **Natural Resources Canada**
   - Canadian DEM (2m, 30m resolution)

**Required Client**:
```python
class SatelliteDataClient(BaseClient):
    """Client for satellite imagery and derived products."""

    async def get_land_cover(
        self,
        bounds: tuple,
        date: str
    ) -> xarray.Dataset:
        """Fetch land cover classification raster."""

    async def get_ndvi_timeseries(
        self,
        bounds: tuple,
        start_date: str,
        end_date: str
    ) -> xarray.Dataset:
        """Fetch NDVI vegetation indices."""

    async def get_elevation(
        self,
        bounds: tuple,
        resolution: str = "30m"
    ) -> xarray.Dataset:
        """Fetch digital elevation model."""
```

**Implementation Notes**:
- Different paradigm: returns raster data (xarray), not observations
- Requires heavy dependencies: planetary-computer, earthengine-api, pystac-client
- May be better as separate optional module

---

### 8. 🟢 Community Well-Being & Infrastructure (LOW)

**Why Important**: Indigenous community socioeconomic data

**ONW Implementation**:
- `src/ingest/ingest_community_wellbeing.py`
- `src/ingest/ingest_indigenous_infrastructure.py`

**Data Sources**:
1. **Community Well-Being Scores**
   - Source: Statistics Canada
   - 122 communities scored
   - Metrics: education, employment, income, housing

2. **Indigenous Infrastructure Projects**
   - Source: Indigenous Services Canada ICIM dataset
   - Requires manual access request
   - 445 federal projects documented

**Required Client**: Lower priority - mostly static data, can be CSV-based

---

### 9. 📊 Global/Analytics Sources (ONW-SPECIFIC)

**ONW-Only Requirements** (not needed by williams-treaties):

- **WRI Analytics API** - Global forest/land use statistics
- **GADM** - Global administrative boundaries
- **KBA** - Key biodiversity areas worldwide
- **WDPA** - World database on protected areas (10GB)
- **LANDMARK** - Indigenous territories globally

**Decision**: These should NOT be in ontario-environmental-data library
- Global scope, not Ontario-specific
- Massive data downloads (WDPA ~10GB)
- ONW-specific agent functionality
- Keep in ONW codebase

---

## Architecture Compatibility Analysis

### Data Return Types Needed

| Type | ONW Needs | williams-treaties Needs | Current Library |
|------|-----------|-------------------------|-----------------|
| **List[Dict]** (observations) | ✅ Yes | ✅ Yes | ✅ Supported |
| **GeoDataFrame** (vector GIS) | ✅ Yes | ✅ Yes | ❌ Not supported |
| **xarray.Dataset** (rasters) | ❌ No | ✅ Yes | ❌ Not supported |
| **GeoJSON** (file export) | ✅ Yes | ✅ Yes | ✅ Partial (via models) |

### Processing Paradigm Differences

**ONW Approach**:
- Download → Load to PostGIS → Query via handlers
- Async API clients for real-time data (iNat, eBird)
- Pre-ingested static data (parks, boundaries, fire history)
- Returns data to LLM agent as JSON

**williams-treaties Approach**:
- Download → Process → Export to GeoJSON files
- Script-based, file-oriented
- All data pre-generated for web map
- No database, no real-time queries

**Library Must Support BOTH**:
- ✅ Async API clients (ONW real-time needs)
- ✅ GeoDataFrame returns (both need GIS operations)
- ✅ GeoJSON export (williams-treaties needs)
- ✅ Dictionary returns (ONW needs for database loading)

---

## Utility Functions - Critical Gaps

### ❌ MISSING: Geometry Utilities

**Current Status**: Constants reference exists but no implementation!

**ONW Requirements** (from ontario_handler.py):
```python
from ontario_data.utils import (
    get_bounds_from_aoi,
    filter_by_bounds,
    point_in_bounds  # Also needed
)
```

**Existing in ONW** (must be ported to library):
- `get_bounds_from_aoi(aoi_geometry)` - Extract (swlat, swlng, nelat, nelng)
- `filter_by_bounds(observations, bounds)` - Filter list by bounding box
- `point_in_bounds(lat, lng, bounds)` - Check if point in bounds

**Status**: ✅ **GOOD NEWS** - Found in ontario-environmental-data!
- `/home/user/ontario-environmental-data/ontario_data/utils/geometry.py`
- All three functions exist with tests
- Just need to verify export in `__init__.py`

### ❌ MISSING: Configuration Management

**ONW Requirements**:
```python
from ontario_data.config import OntarioConfig
```

**Current Status**: ✅ Exists in library at `ontario_data/config.py`

---

## Dependencies Compatibility

### ONW Requirements
- Python 3.12
- aiohttp (async HTTP)
- pydantic v2
- geopandas
- sqlalchemy (PostGIS)

### williams-treaties Requirements
- Python 3.x
- requests (HTTP)
- geopandas
- rasterio (raster data)
- xarray (satellite data)
- planetary-computer, earthengine-api (optional)

### Library Current Dependencies
- aiohttp ✅
- pydantic v2 ✅
- geopandas (optional) ⚠️

**Compatibility**: ✅ GOOD
- No conflicts
- Should make geopandas a required dependency (not optional)

---

## Implementation Roadmap

### Phase 1: CRITICAL Fixes (Week 1)
**Goal**: Support ONW integration 100%

1. ✅ Verify geometry utilities exported correctly
2. ✅ Verify OntarioConfig exported
3. ❌ **Add WaterAdvisoriesClient**
4. ❌ **Add StatisticsCanadaWFSClient**
5. ❌ **Add comprehensive tests** for all clients
6. ❌ Make geopandas required dependency

**Deliverables**:
- ONW can fully migrate ontario_handler.py to use library
- All ONW biodiversity + Indigenous data needs met
- Test coverage >80%

### Phase 2: williams-treaties Support (Week 2-3)
**Goal**: Support williams-treaties data downloads

1. ❌ **Add CWFISClient** (fire data)
2. ❌ **Add OntarioGeoHubClient** (parks, conservation areas)
3. ❌ Add DataStreamClient (water quality)
4. ❌ Add PWQMNClient (provincial water quality)
5. ❌ Port williams-treaties download scripts to use library

**Deliverables**:
- williams-treaties can replace manual downloads with library calls
- All fire, water, parks data available
- GeoJSON export utilities

### Phase 3: Advanced Features (Week 4+)
**Goal**: Complete coverage

1. ❌ Add SatelliteDataClient (optional module)
2. ❌ Add remaining data sources
3. ❌ Performance optimization
4. ❌ Caching layer implementation
5. ❌ Documentation & examples

---

## Testing Requirements

### Current State: ⚠️ INCOMPLETE
- ✅ 15 tests for geometry utilities
- ✅ 6 tests for config
- ❌ **ZERO tests for INaturalistClient**
- ❌ **ZERO tests for EBirdClient**
- ❌ **ZERO tests for data models**
- ❌ No integration tests
- ❌ No mock API tests

### Required Tests

**Unit Tests**:
- [ ] INaturalistClient (with mocked responses)
- [ ] EBirdClient (with mocked responses)
- [ ] BiodiversityObservation model validation
- [ ] Each new client (WaterAdvisories, StatsCan, CWFIS, etc.)
- [ ] Error handling and retries
- [ ] Rate limiting

**Integration Tests**:
- [ ] ONW ontario_handler.py using library
- [ ] williams-treaties scripts using library
- [ ] Real API calls (limited, in CI only)
- [ ] Database loading workflows

**Target**: >90% code coverage (claimed but not verified)

---

## Configuration & Settings Requirements

### Environment Variables Needed

**Current**:
```bash
EBIRD_API_KEY=xxx          # ✅ Supported
```

**Additional Required**:
```bash
# Water Quality
DATASTREAM_API_KEY=xxx     # ⏳ Config exists, client missing

# Satellite Data (optional)
PLANETARY_COMPUTER_KEY=xxx # ❌ Not supported
EARTHENGINE_KEY=xxx        # ❌ Not supported

# No keys needed for:
# - iNaturalist (public API)
# - ISC Water Advisories (public web scraping)
# - Stats Canada WFS (public)
# - CWFIS (public)
# - Ontario GeoHub (public)
```

### Williams Treaty Constants

**Current**: ✅ Already in library
- `ontario_data/constants/regions.py`
- `WILLIAMS_TREATY_FIRST_NATIONS` list
- First Nations names, communities, regions

**Usage**:
- Both ONW and williams-treaties filter to these territories
- Should be central source of truth

---

## Data Model Requirements

### Current Models (✅ Implemented)
- `BiodiversityObservation` - For iNat/eBird
- `GeoJSONPoint` - Point geometry
- `Taxonomy` - Taxonomic information

### Required Models (❌ Missing)

```python
# Water Quality
class WaterAdvisory(BaseModel):
    """Drinking water advisory data."""
    community: str
    first_nation: str
    advisory_type: str
    date_issued: date
    date_lifted: Optional[date]
    location: GeoJSONPoint
    # ... etc

# Fire Data
class FirePerimeter(BaseModel):
    """Historical fire perimeter."""
    fire_id: str
    fire_year: int
    area_hectares: float
    geometry: Dict  # GeoJSON Polygon
    # ... etc

# Parks
class ProtectedArea(BaseModel):
    """Park or conservation area."""
    name: str
    area_type: str  # provincial_park, conservation_area, etc.
    area_hectares: float
    managing_authority: str
    geometry: Dict  # GeoJSON Polygon
    # ... etc

# Indigenous Boundaries
class ReserveBoundary(BaseModel):
    """First Nations reserve boundary."""
    reserve_name: str
    first_nation: str
    province: str
    area_hectares: float
    geometry: Dict  # GeoJSON Polygon
    # ... etc
```

---

## Success Criteria

### ✅ Library is Ready When:

**For ONW**:
- [ ] ontario_handler.py can import all needed clients
- [ ] All geometry utilities work
- [ ] All Ontario-specific data sources accessible
- [ ] Can replace ONW's embedded API client code
- [ ] Tests pass in ONW integration
- [ ] No performance regression

**For williams-treaties**:
- [ ] All download scripts can use library clients
- [ ] Can export to GeoJSON files
- [ ] Fire, water, parks, boundaries all available
- [ ] No dependency conflicts
- [ ] Scripts simpler/shorter than current versions

**For Library**:
- [ ] >90% test coverage (real, not claimed)
- [ ] All clients have unit tests with mocks
- [ ] Documentation complete
- [ ] Type hints 100%
- [ ] CI/CD passing
- [ ] Published to PyPI

---

## Risk Assessment

### 🔴 HIGH RISK
1. **No API for ISC Water Advisories** - May require web scraping
2. **Satellite data complexity** - Heavy dependencies, different paradigm
3. **Zero API client tests** - Unknown bugs in production code
4. **Manual downloads** - Some sources require manual data access requests

### 🟡 MEDIUM RISK
1. **GeoDataFrame vs Dict returns** - Need to support both patterns
2. **Async vs sync** - williams-treaties uses sync requests
3. **Large data volumes** - Some datasets are multi-GB
4. **Rate limiting** - Need to respect API limits

### 🟢 LOW RISK
1. **Dependency conflicts** - Minimal overlap, compatible versions
2. **Python version** - Both support 3.9+
3. **Geometry utilities** - Already implemented and tested

---

## Recommended Immediate Actions

### 1. Fix Critical Gaps (This Week)
- ✅ Verify geometry utils exported
- ❌ Add tests for INaturalist & eBird clients
- ❌ Implement WaterAdvisoriesClient
- ❌ Implement StatisticsCanadaWFSClient
- ❌ Add GeoDataFrame support to base clients

### 2. Validate with ONW (Next Week)
- ❌ Test ontario_handler.py migration
- ❌ Run ONW integration tests
- ❌ Performance benchmark
- ❌ Fix any compatibility issues

### 3. Add williams-treaties Support (Week 3-4)
- ❌ Implement CWFISClient
- ❌ Implement OntarioGeoHubClient
- ❌ Port download scripts
- ❌ Test GeoJSON export workflows

### 4. Comprehensive Testing (Week 4+)
- ❌ Unit tests for all clients
- ❌ Integration tests for both projects
- ❌ Mock API response fixtures
- ❌ CI/CD pipeline

---

## Conclusion

**Current Status**: The library has a solid foundation with 2 working biodiversity clients and good architecture, but is **NOT READY** for full production use in either project.

**Estimated Effort**:
- **Phase 1 (Critical)**: 40-50 hours
- **Phase 2 (williams-treaties)**: 30-40 hours
- **Phase 3 (Complete)**: 20-30 hours
- **Total**: ~100-120 hours of development

**Recommendation**:
1. Prioritize Phase 1 to unblock ONW integration (1-2 weeks)
2. Implement Phase 2 for williams-treaties support (2-3 weeks)
3. Phase 3 can be iterative based on real usage

**Bottom Line**: The vision is right, the architecture is sound, but execution is ~20% complete. With focused effort over 4-6 weeks, the library can fully support both projects and become a valuable shared resource for Ontario environmental data access.
