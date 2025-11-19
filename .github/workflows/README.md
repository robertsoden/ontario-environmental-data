# GitHub Actions Workflows

This directory contains CI/CD workflows for the Ontario Environmental Data Library.

## Workflows

### 🧪 CI (`ci.yml`)
**Trigger:** Automatic on push/PR to main and claude/* branches
**Purpose:** Run tests, linting, and code quality checks

**Jobs:**
- **Test**: Runs pytest across Python 3.9, 3.10, 3.11, 3.12
  - Uploads coverage to Codecov (requires `CODECOV_TOKEN` secret)
- **Lint**: Checks code formatting (Black), linting (Ruff), type hints (MyPy)

**Required for:** Every PR must pass CI before merge

---

### ✅ Data Scripts Validation (`data-validation.yml`)
**Trigger:** Automatic when data scripts or library code changes
**Purpose:** Validate data collection scripts work without collecting large datasets

**What it checks:**
- Scripts have valid Python syntax
- All imports work correctly
- Client integration tests run (with timeout)

**Does NOT:** Generate or upload large datasets

---

### 📊 Data Collection (`data-collection.yml`)
**Trigger:** Manual only (workflow_dispatch)
**Purpose:** Generate Ontario environmental datasets on demand

**Mode:**
- `status-only` (default) - Check which data exists without collecting
- `collect` - Actually collect selected data sources

**Data Sources:** (7 individual checkboxes)
- Williams Treaty Communities (community points)
- Williams Treaty Boundaries (territory polygon) - ✓ EXISTS
- Fire Perimeters (historical 1976-2024)
- Provincial Parks (Ontario parks)
- Conservation Authorities (CA boundaries)
- iNaturalist (biodiversity observations)
- Satellite Data (NDVI, land cover info)

**Options:**
- `upload_artifacts` - Upload generated data as GitHub artifacts (30 day retention)
- `force_refresh` - Re-download data even if it exists

**To trigger:**
1. Go to Actions tab in GitHub
2. Select "Data Collection" workflow
3. Click "Run workflow"
4. Choose collection type and artifact upload option

**Secrets needed:**
- `EBIRD_API_KEY` (optional) - For eBird data collection

**Output:**
- Data files saved to `data/processed/`
- Artifacts available for download (if enabled)
- Summary shown in workflow run

---

### 🛰️ Satellite Data Processing (`satellite-processing.yml`)
**Trigger:** Manual only (workflow_dispatch)
**Purpose:** Process large satellite datasets (NDVI, land cover, elevation) for all of Ontario

**Data Types:**
- `ndvi` - Vegetation index from Statistics Canada MODIS (250m resolution)
- `landcover` - Land cover classification from NRCan (30m resolution)
- `elevation` - Digital elevation model from NRCan CDEM (20m resolution)

**Options:**
- `year` - Year to process (required)
- `skip_download` - Use cached raw data instead of downloading
- `upload_to_storage` - Upload tiles to cloud storage (requires AWS/Azure credentials)

**Processing Pipeline:**
1. Download raw satellite data (~6-7 GB per dataset)
2. Clip to Ontario bounds
3. Classify/polygonize raster data
4. Generate vector tiles (PMTiles format)
5. Upload to cloud storage (optional)
6. Update satellite data registry

**Output:**
- Processed raster files (GeoTIFF)
- Vector data (GeoJSON)
- Vector tiles (PMTiles)
- Updated `satellite_data_registry.json`

**Requirements:**
- Large dataset storage (use GitHub Actions cache for raw data)
- Cloud storage credentials for tile hosting (AWS S3 or Azure Blob)
- Long timeout (up to 6 hours for download + processing)

**Storage:**
- Tiles should be hosted on cloud storage (S3, Azure, Cloudflare R2)
- NOT stored in git repository due to size (500MB - 1GB per dataset)
- See [docs/SATELLITE_DATA_GUIDE.md](../../docs/SATELLITE_DATA_GUIDE.md) for detailed setup

**To trigger:**
1. Go to Actions tab in GitHub
2. Select "Satellite Data Processing" workflow
3. Click "Run workflow"
4. Choose data type and year
5. Wait 2-6 hours for processing to complete
6. Download artifacts or verify upload to cloud storage

---

## Setup Required

### Secrets to Configure

1. **CODECOV_TOKEN** (optional)
   - For code coverage reporting
   - Get from https://codecov.io/

2. **EBIRD_API_KEY** (optional)
   - For eBird bird observation data
   - Get from https://ebird.org/api/keygen

3. **AWS_ACCESS_KEY_ID** and **AWS_SECRET_ACCESS_KEY** (optional)
   - For satellite tile upload to S3
   - Create IAM user with S3 write permissions
   - Alternative: Use OIDC for GitHub Actions (no secrets needed)

4. **AZURE_STORAGE_CONNECTION_STRING** (optional)
   - For satellite tile upload to Azure Blob Storage
   - Alternative to AWS S3

### Branch Protection Rules (Recommended)

For `main` branch:
- ✅ Require status checks to pass before merging
  - Required checks: `Test (3.11)`, `Code Quality Checks`
- ✅ Require branches to be up to date before merging
- ✅ Require linear history

---

## Local Testing

Before pushing, ensure your code passes all checks:

```bash
# Run tests
python -m pytest tests/ -v --cov=ontario_data

# Check formatting
black --check ontario_data/ tests/ examples/ *.py

# Run linter
ruff check ontario_data/ tests/ examples/ *.py

# Type check (informational)
mypy ontario_data/ --ignore-missing-imports
```

## Notes

- Data collection is **manual trigger only** to avoid unnecessary API calls
- Test data artifacts expire after 30 days
- For large datasets (>500MB), consider using GitHub Releases instead of artifacts
