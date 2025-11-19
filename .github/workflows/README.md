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

**Options:**
- `full-ontario` - Run complete Ontario data collection
- `williams-treaty` - Generate Williams Treaty specific data
- `test-clients` - Run integration tests for all API clients
- `upload_artifacts` - Upload generated data as GitHub artifacts (30 day retention)

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

## Setup Required

### Secrets to Configure

1. **CODECOV_TOKEN** (optional)
   - For code coverage reporting
   - Get from https://codecov.io/

2. **EBIRD_API_KEY** (optional)
   - For eBird bird observation data
   - Get from https://ebird.org/api/keygen

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
