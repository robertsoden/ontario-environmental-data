# Static Datasets Guide

## Overview

**Static datasets** are large datasets that are processed locally once and then uploaded to S3 for permanent storage. The registry knows their S3 URLs instead of re-collecting them each time a workflow runs.

## Why Static Datasets?

Some datasets require:
- Large shapefile downloads (100MB+)
- Expensive processing
- Infrequent updates
- Long collection times

For these datasets, it's more efficient to:
1. Process them locally once
2. Upload to S3
3. Reference the S3 URL in the registry
4. Skip collection in workflows

## Current Static Datasets

| Dataset | Size | Source | Last Updated |
|---------|------|--------|--------------|
| Ontario Provincial Boundary | 163 MB | Statistics Canada | 2024 |
| Ontario Municipalities | 45 MB | Statistics Canada Census | 2021 |
| Watersheds | 255 MB | Ontario GeoHub | 2024 |
| Provincial Parks | 77 MB | Ontario GeoHub | 2024 |

## Adding a New Static Dataset

### 1. Process the Dataset Locally

Run the collection function locally to generate the processed file:

```bash
# Set environment variable to collect the dataset
export COLLECT_YOUR_DATASET=true
python3 collect_data.py
```

This will create the processed file in `data/processed/`.

### 2. Upload to S3

Upload the file to the appropriate S3 bucket location:

```bash
aws s3 cp data/processed/your_dataset.geojson \
  s3://ontario-environmental-data/datasets/category/your_dataset.geojson \
  --cache-control "public, max-age=86400" \
  --content-type "application/geo+json" \
  --region us-east-1
```

Categories:
- `boundaries/` - Administrative boundaries
- `environmental/` - Environmental features
- `protected_areas/` - Parks and conservation areas
- `biodiversity/` - Species observations
- `community/` - Community data

### 3. Update the Registry

In `ontario_data/datasets.py`, update the dataset definition:

```python
"your_dataset": DatasetDefinition(
    id="your_dataset",
    name="Your Dataset Name",
    description="Description of the dataset",
    category="boundaries",  # or appropriate category

    # Mark as static
    is_static=True,
    s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/category/your_dataset.geojson",
    local_path=Path("data/processed/your_dataset.geojson"),

    # Keep collection function for local re-processing
    collect_fn=_collect_your_dataset,  # Optional

    output_path=Path("data/processed/your_dataset.geojson"),
    output_format="geojson",
    min_records=1,
    enabled=True,
),
```

### 4. Commit and Deploy

```bash
git add ontario_data/datasets.py
git commit -m "Add static dataset: your_dataset"
git push origin main
```

### 5. Regenerate Catalog

Trigger the workflow to regenerate the catalog with the new dataset:

```bash
gh workflow run "Collect Data and Upload to S3"
```

The catalog at `https://ontario-environmental-data.s3.us-east-1.amazonaws.com/catalog.json` will now include your static dataset.

## Re-processing Static Datasets

If a static dataset needs to be updated:

1. **Update the source data** (if applicable)
2. **Re-run collection locally**:
   ```bash
   export COLLECT_YOUR_DATASET=true
   export OVERWRITE=true  # Force re-collection
   python3 collect_data.py
   ```
3. **Re-upload to S3** (same command as initial upload)
4. **No code changes needed** - S3 URL stays the same

## Architecture Benefits

✅ **Faster workflows** - No re-processing of huge files
✅ **Lower bandwidth** - No repeated downloads
✅ **S3 as permanent storage** - Reliable, scalable hosting
✅ **Local updates possible** - Collection functions still available
✅ **Automatic catalog inclusion** - Registry integration works seamlessly

## Workflow Behavior

Static datasets:
- **Are NOT re-collected** by GitHub workflows
- **ARE included** in the catalog automatically
- **CAN be updated** by running collection locally and re-uploading
- **Reference S3 URLs** for downloads

Dynamic datasets:
- **ARE collected** every workflow run
- **Upload fresh data** to S3 each time
- **Use collection functions** defined in registry
