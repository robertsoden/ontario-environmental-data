# Satellite Data Processing Guide

This guide covers the complete workflow for processing satellite data (NDVI, land cover, elevation) for all of Ontario.

## Overview

Satellite data is handled differently from other data sources due to:
- **Large file sizes** (6-7 GB raw, 2-10 GB processed, 0.5-1 GB tiles per dataset)
- **Infrequent updates** (annual for NDVI/land cover, rarely for elevation)
- **Specialized serving** (vector tiles via PMTiles or tile server)
- **Cloud storage required** (GitHub repository not suitable for large binary files)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. RAW DATA (FTP Servers)                                       │
│    • Statistics Canada: MODIS NDVI (6-7 GB/year)                │
│    • NRCan: Land Cover (4-5 GB), Elevation (10-15 GB)           │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. PROCESSING PIPELINE (GitHub Actions)                         │
│    • Download and cache raw data (90 days)                      │
│    • Clip to Ontario bounds                                     │
│    • Classify/polygonize raster data                            │
│    • Generate vector tiles (PMTiles)                            │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. STORAGE (Cloud)                                              │
│    • AWS S3 or Azure Blob Storage                               │
│    • Organized by: /tiles/{dataset}/{year}/{z}/{x}/{y}.pbf     │
│    • PMTiles format: single file per dataset/year               │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. SERVING (CDN / Tile Server)                                  │
│    • Static hosting with CDN (Cloudflare, CloudFront)           │
│    • Or: Dynamic tile server (martin, pg_tileserv)              │
│    • PMTiles: Efficient range requests, no extraction needed    │
└─────────────────────────────────────────────────────────────────┘
```

## Data Sources

### 1. NDVI (Vegetation Index)

**Source:** Statistics Canada MODIS 250m
**URL:** https://ftp.maps.canada.ca/pub/statcan_statcan/modis/
**Update Frequency:** Weekly composites, process annually
**File Size:** 6-7 GB raw → ~2 GB processed → ~450 MB tiles
**Coverage:** All of Canada (clip to Ontario)

**Classifications:**
- Water/Snow: NDVI < 0
- Barren: NDVI 0-0.2
- Sparse Vegetation: NDVI 0.2-0.4
- Moderate Vegetation: NDVI 0.4-0.6
- Dense Vegetation: NDVI 0.6-1.0

**Tile Zoom Levels:** 4-12

### 2. Land Cover

**Source:** Natural Resources Canada NALCMS
**URL:** https://ftp.maps.canada.ca/pub/nrcan_rncan/Land-cover_Couverture-du-sol/
**Update Frequency:** Every 5 years (2010, 2015, 2020, 2025?)
**File Size:** 4-5 GB raw → ~1.2 GB processed → ~650 MB tiles
**Resolution:** 30m

**19 Land Cover Classes:**
- Forests (needleleaf, deciduous, mixed)
- Shrublands (temperate, sub-polar)
- Grasslands
- Wetlands
- Cropland
- Barren
- Urban
- Water
- Snow/Ice

**Tile Zoom Levels:** 4-14

### 3. Digital Elevation Model (DEM)

**Source:** Natural Resources Canada CDEM
**URL:** https://ftp.maps.canada.ca/pub/elevation/dem_mne/highresolution_hauteresolution/
**Update Frequency:** Rarely
**File Size:** 10-15 GB raw → ~3.5 GB processed → ~800 MB tiles
**Resolution:** 20m

**Classifications:**
- Lowland: < 200m
- Upland: 200-400m
- Highland: 400-600m
- Mountain: > 600m

**Tile Zoom Levels:** 4-14

## Processing Workflow

### Prerequisites

1. **System Dependencies:**
```bash
sudo apt-get install gdal-bin libgdal-dev tippecanoe
```

2. **Python Dependencies:**
```bash
pip install rasterio geopandas shapely numpy
```

3. **Cloud Storage Credentials** (for upload):
   - AWS: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
   - Azure: `AZURE_STORAGE_CONNECTION_STRING`

### Step 1: Manual Download (if needed)

For first-time processing or when cache expires:

```bash
# NDVI
cd data/raw/satellite
wget https://ftp.maps.canada.ca/pub/statcan_statcan/modis/MODISCOMP7d_2023.zip
unzip MODISCOMP7d_2023.zip
# Rename main TIF to MODISCOMP7d_2023.tif

# Land Cover (requires manual selection of Ontario tiles)
# Download from NRCan FTP and place as landcover_2020.tif

# Elevation (requires NTS tile identification)
# Download required NTS tiles and mosaic to ontario_cdem.tif
```

### Step 2: Process Data

**Using GitHub Actions (Recommended):**

1. Go to Actions → "Satellite Data Processing"
2. Click "Run workflow"
3. Select:
   - Data type (ndvi / landcover / elevation)
   - Year (e.g., 2023)
   - Skip download if using cached data
   - Upload to cloud storage (if configured)
4. Monitor progress (may take 2-6 hours)

**Using Local Script:**

```bash
# Process NDVI for 2023
python scripts/process_satellite_data.py --data-type ndvi --year 2023

# Process Land Cover for 2020
python scripts/process_satellite_data.py --data-type landcover --year 2020

# Process Elevation
python scripts/process_satellite_data.py --data-type elevation --year 2023
```

### Step 3: Verify Output

```bash
# Check processing status
python check_data_status.py

# Verify files
ls -lh data/processed/satellite/
ls -lh data/tiles/

# Inspect registry
cat satellite_data_registry.json | jq '.datasets.ndvi'
```

## Cloud Storage Setup

### Option A: AWS S3 (Recommended)

**Setup:**

1. Create S3 bucket:
```bash
aws s3 mb s3://ontario-satellite-data --region us-east-1
```

2. Configure CORS (for web access):
```json
[
  {
    "AllowedOrigins": ["*"],
    "AllowedMethods": ["GET", "HEAD"],
    "AllowedHeaders": ["*"],
    "MaxAgeSeconds": 3600
  }
]
```

3. Set bucket policy for public read:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::ontario-satellite-data/*"
    }
  ]
}
```

4. Add GitHub secrets:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

5. Upload tiles:
```bash
aws s3 sync data/tiles/ s3://ontario-satellite-data/tiles/ \
  --acl public-read \
  --cache-control "max-age=31536000"
```

**Costs:**
- Storage: $0.023/GB/month (~$0.05/month for ~2GB tiles)
- Bandwidth: First 100 GB/month free, then $0.09/GB
- **Total: ~$1-2/month for moderate usage**

### Option B: Azure Blob Storage

**Setup:**

1. Create storage account and container
2. Configure public access level: "Blob"
3. Add GitHub secret: `AZURE_STORAGE_CONNECTION_STRING`
4. Upload via workflow or Azure CLI

**Costs:** Similar to AWS (~$0.02/GB/month storage)

### Option C: Cloudflare R2 (Alternative)

**Benefits:**
- Zero egress fees (free bandwidth)
- S3-compatible API
- Better for high-traffic applications

**Costs:** $0.015/GB/month storage only

## Serving Tiles

### Option 1: Static Hosting + CDN (Simplest)

**PMTiles Format** (single file per dataset):

```bash
# Tiles are already in PMTiles format from processing
# Upload to any static host with range request support

# Examples:
# - Cloudflare Pages
# - Netlify
# - AWS S3 + CloudFront
# - Azure Blob + CDN
```

**Usage in web map:**
```javascript
import { Protocol } from 'pmtiles';

const protocol = new Protocol();
maplibregl.addProtocol('pmtiles', protocol.tile);

map.addSource('ndvi-2023', {
  type: 'vector',
  url: 'pmtiles://https://ontario-satellite-data.s3.amazonaws.com/tiles/ndvi_2023.pmtiles'
});
```

### Option 2: Tile Server (martin)

**Setup:**

```bash
# Install martin
cargo install martin

# Serve PMTiles
martin --listen 0.0.0.0:3000 /path/to/tiles/
```

**Docker:**
```yaml
version: '3'
services:
  martin:
    image: ghcr.io/maplibre/martin
    ports:
      - "3000:3000"
    volumes:
      - ./data/tiles:/tiles:ro
    command: ["martin", "--listen", "0.0.0.0:3000", "/tiles"]
```

### Option 3: pg_tileserv (PostgreSQL/PostGIS)

If you need dynamic data or want to combine with other layers:

```bash
# Import tiles to PostGIS
ogr2ogr -f PostgreSQL PG:"dbname=ontario" data/processed/satellite/ndvi_2023.geojson

# Serve with pg_tileserv
pg_tileserv --database postgresql://user:pass@localhost/ontario
```

## Updating Data

### Annual Updates (NDVI, Land Cover)

1. **Check for new data:**
   - NDVI: Check Statistics Canada FTP for latest year
   - Land Cover: NRCan releases every 5 years

2. **Run processing workflow:**
   ```bash
   # Via GitHub Actions or locally
   python scripts/process_satellite_data.py --data-type ndvi --year 2024
   ```

3. **Upload to storage:**
   ```bash
   aws s3 sync data/tiles/ndvi_2024.pmtiles s3://ontario-satellite-data/tiles/
   ```

4. **Update registry:**
   - Automatically updated by processing script
   - Commit `satellite_data_registry.json` to git

5. **Update map applications:**
   - Point to new tile URLs
   - Update year selectors in UI

## Troubleshooting

### Download Fails

```bash
# Retry with wget resume
wget -c https://ftp.maps.canada.ca/pub/statcan_statcan/modis/MODISCOMP7d_2023.zip

# Or use curl
curl -C - -O https://ftp.maps.canada.ca/pub/statcan_statcan/modis/MODISCOMP7d_2023.zip
```

### Processing Runs Out of Memory

```bash
# Process in chunks or use smaller resolution
# For NDVI, process by week instead of annual composite

# Or: Use instance with more RAM
# GitHub Actions: runners with 14 GB RAM
# Local: Recommend 16+ GB RAM for Ontario-wide processing
```

### Tiles Too Large

```bash
# Reduce max zoom level
tippecanoe -Z 4 -z 10 ... # Instead of -z 12

# Increase simplification
tippecanoe --simplification=4 ...

# Drop dense features
tippecanoe --drop-densest-as-needed ...
```

### Cloud Upload Fails

```bash
# Check credentials
aws sts get-caller-identity

# Test with small file first
aws s3 cp test.txt s3://ontario-satellite-data/test.txt

# Use multipart upload for large files (automatic for >5GB)
aws s3 cp large_file.pmtiles s3://bucket/ --storage-class STANDARD_IA
```

## Cost Optimization

### Storage

1. **Use PMTiles** - Single file, no directory structure overhead
2. **Compress tiles** - tippecanoe creates gzip-compressed PBF tiles
3. **Lifecycle policies** - Move old versions to cheaper storage tiers
4. **Cache raw data** - GitHub Actions cache (90 days free) vs re-downloading

### Bandwidth

1. **CDN** - Use CloudFront, Cloudflare, or Azure CDN
2. **Cloudflare R2** - Zero egress fees
3. **Aggressive caching** - Set `Cache-Control: max-age=31536000` (1 year)

### Processing

1. **Skip unnecessary steps** - Use `--skip-download` if data cached
2. **Process only changed datasets** - Don't re-process old years
3. **Use spot instances** - For local cloud processing (60-90% cheaper)

## Maintenance Schedule

- **Weekly:** Monitor FTP sources for new NDVI data
- **Monthly:** Check data status and verify tile availability
- **Annually:** Process latest NDVI year
- **Every 5 years:** Process new land cover release
- **As needed:** Update elevation when CDEM refreshed

## Support

For issues or questions:
- Check workflow logs in GitHub Actions
- Review `satellite_data_registry.json` for processing status
- See main [README.md](../README.md) for general library usage
