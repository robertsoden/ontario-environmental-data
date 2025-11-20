# S3 Storage Guide

This document explains the S3-based storage architecture for Ontario Environmental Data and how to set it up.

## Overview

The Ontario Environmental Data project has migrated from GitHub Artifacts to AWS S3 for data storage. This provides:

- **Unlimited storage**: No 2GB artifact size limits
- **Persistent storage**: Data doesn't expire after 30-90 days
- **Direct HTTPS access**: Public URLs for all datasets
- **Scalability**: Support for ingesting all open data portals (TBs of data)
- **Cost-effective**: Pay only for storage and bandwidth used

## Architecture

### Storage Structure

```
s3://ontario-environmental-data/
├── datasets/                       # All processed datasets
│   ├── boundaries/                 # Administrative boundaries
│   │   ├── ontario_boundary.geojson
│   │   ├── ontario_municipalities.geojson
│   │   └── williams_treaty_reserves.geojson
│   ├── communities/                # Indigenous communities
│   │   └── williams_treaty_communities.geojson
│   ├── community/                  # Community well-being
│   │   └── community_wellbeing_ontario.geojson
│   ├── protected_areas/            # Parks and conservation
│   │   ├── ontario_reserves.geojson
│   │   └── conservation_authorities.geojson
│   ├── biodiversity/               # Species observations
│   │   ├── ebird_observations.geojson
│   │   └── inaturalist_observations.geojson
│   └── environmental/              # Environmental features
│       ├── watersheds.geojson
│       └── fire_perimeters.geojson
├── catalog.json                    # Dataset catalog (API endpoint)
└── metadata/
    └── collection_report.json      # Collection metadata
```

### Public Access URLs

All files are publicly accessible via HTTPS:

- **Base URL**: `https://ontario-environmental-data.s3.us-east-1.amazonaws.com`
- **Catalog**: `https://ontario-environmental-data.s3.us-east-1.amazonaws.com/catalog.json`
- **Dataset example**: `https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/boundaries/watersheds.geojson`

## Setup Instructions

### 1. Create S3 Bucket

```bash
# Using AWS CLI
aws s3 mb s3://ontario-environmental-data --region us-east-1

# Configure public access (optional, for public data)
aws s3api put-public-access-block \
  --bucket ontario-environmental-data \
  --public-access-block-configuration \
  "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

# Set bucket policy for public read access
aws s3api put-bucket-policy \
  --bucket ontario-environmental-data \
  --policy '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "PublicReadGetObject",
        "Effect": "Allow",
        "Principal": "*",
        "Action": "s3:GetObject",
        "Resource": "arn:aws:s3:::ontario-environmental-data/*"
      }
    ]
  }'
```

### 2. Configure GitHub Secrets

Add these secrets to your GitHub repository:

1. Go to Settings → Secrets and variables → Actions
2. Add the following secrets:

   - `AWS_ACCESS_KEY_ID`: Your AWS access key ID
   - `AWS_SECRET_ACCESS_KEY`: Your AWS secret access key
   - `EBIRD_API_KEY`: eBird API key (if using eBird data)

### 3. IAM User Setup

Create an IAM user with S3 access:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::ontario-environmental-data",
        "arn:aws:s3:::ontario-environmental-data/*"
      ]
    }
  ]
}
```

## Workflows

### Collect and Upload to S3

The `collect-and-upload-to-s3.yml` workflow:

1. Collects all enabled datasets
2. Processes them to GeoJSON format
3. Uploads to S3 organized by category
4. Generates and uploads catalog.json
5. Creates backup artifact

**Trigger manually:**
```bash
gh workflow run "Collect Data and Upload to S3"
```

**Trigger with specific datasets:**
```bash
gh workflow run "Collect Data and Upload to S3" \
  -f datasets="watersheds,ontario_municipalities,fire_perimeters"
```

**Scheduled**: Runs weekly on Sundays at 2 AM UTC

### Publish to GitHub Pages

The `publish-from-s3.yml` workflow:

1. Downloads catalog.json from S3
2. Generates landing page (index.html)
3. Publishes to GitHub Pages

**Note**: Data is served directly from S3, not from GitHub Pages

## Using the S3 Client

### Python Library

```python
from ontario_data.sources.storage import S3StorageClient

# Initialize client
storage = S3StorageClient(
    bucket="ontario-environmental-data",
    region="us-east-1",
    base_path="datasets"
)

# Upload a dataset
result = await storage.upload_dataset(
    local_path=Path("data/processed/watersheds.geojson"),
    category="environmental",
    dataset_id="watersheds"
)

print(f"Uploaded to: {result['url']}")

# Get catalog
catalog = await storage.get_catalog()
print(f"Available datasets: {list(catalog['datasets'].keys())}")

# Download a dataset
await storage.download_file(
    s3_key="datasets/boundaries/watersheds.geojson",
    local_path=Path("watersheds.geojson")
)
```

### AWS CLI

```bash
# List all datasets
aws s3 ls s3://ontario-environmental-data/datasets/ --recursive

# Download a dataset
aws s3 cp \
  s3://ontario-environmental-data/datasets/environmental/watersheds.geojson \
  ./watersheds.geojson

# Upload a dataset
aws s3 cp \
  ./my-dataset.geojson \
  s3://ontario-environmental-data/datasets/environmental/my-dataset.geojson \
  --acl public-read \
  --content-type "application/geo+json"

# Sync entire directory
aws s3 sync \
  data/processed/boundaries/ \
  s3://ontario-environmental-data/datasets/boundaries/ \
  --acl public-read \
  --exclude "*" --include "*.geojson"
```

## Configuration

The `storage_config.json` file contains all S3 settings:

```json
{
  "storage": {
    "provider": "aws_s3",
    "bucket": "ontario-environmental-data",
    "region": "us-east-1"
  },
  "endpoints": {
    "catalog": "https://ontario-environmental-data.s3.us-east-1.amazonaws.com/catalog.json"
  }
}
```

## Migration from GitHub Artifacts

### Step 1: Upload Existing Data

If you have existing data in GitHub artifacts:

```bash
# Download artifact
gh run download <run-id> --name ontario-data-<number>

# Upload to S3
aws s3 sync \
  data/processed/ \
  s3://ontario-environmental-data/datasets/ \
  --acl public-read \
  --exclude "*" --include "*.geojson"
```

### Step 2: Update Workflows

1. Disable old artifact-based workflows
2. Enable new S3-based workflows
3. Run initial collection

### Step 3: Update Applications

Update any applications or scripts that consume data:

**Old URL** (GitHub Pages):
```
https://robertsoden.github.io/ontario-environmental-data/data/processed/watersheds.geojson
```

**New URL** (S3):
```
https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/environmental/watersheds.geojson
```

## Cost Estimation

### Storage Costs (S3 Standard)

- **Price**: $0.023 per GB/month
- **Estimated data**: ~5 GB (current), up to 100 GB (with portal aggregation)
- **Monthly cost**: $0.12 - $2.30/month

### Data Transfer Costs

- **Price**: $0.09 per GB (first 10 TB/month)
- **Free tier**: 100 GB/month
- **Estimated cost**: $0 - $10/month (depending on usage)

### Total Estimated Cost

- **Current scale**: < $1/month
- **With portal aggregation**: $5-15/month

**Much cheaper than GitHub Enterprise for large-scale data hosting!**

## Monitoring

### Check S3 Usage

```bash
# Get total bucket size
aws s3 ls s3://ontario-environmental-data/ --recursive --human-readable --summarize

# Check specific category
aws s3 ls s3://ontario-environmental-data/datasets/environmental/ --recursive --human-readable
```

### CloudWatch Metrics

Monitor in AWS Console:
- Total bucket size
- Number of objects
- Download requests
- Data transfer

## Troubleshooting

### Upload Fails

**Issue**: `An error occurred (AccessDenied) when calling the PutObject operation`

**Solution**: Check IAM permissions and GitHub secrets

```bash
# Test AWS credentials
aws sts get-caller-identity

# Verify bucket access
aws s3 ls s3://ontario-environmental-data/
```

### Public Access Denied

**Issue**: Files not accessible via public URL

**Solution**: Ensure public read ACL and bucket policy are set

```bash
# Check bucket policy
aws s3api get-bucket-policy --bucket ontario-environmental-data

# Re-upload with public ACL
aws s3 cp file.geojson s3://ontario-environmental-data/file.geojson --acl public-read
```

### CORS Issues

If accessing from web applications:

```bash
# Set CORS policy
aws s3api put-bucket-cors \
  --bucket ontario-environmental-data \
  --cors-configuration '{
    "CORSRules": [
      {
        "AllowedOrigins": ["*"],
        "AllowedMethods": ["GET", "HEAD"],
        "AllowedHeaders": ["*"],
        "MaxAgeSeconds": 3600
      }
    ]
  }'
```

## Future Enhancements

1. **CloudFront CDN**: Add CloudFront for faster global access
2. **S3 Versioning**: Enable versioning for dataset history
3. **Lifecycle Policies**: Auto-archive old versions to Glacier
4. **Lambda Triggers**: Auto-process uploads with Lambda functions
5. **Multi-region**: Replicate to multiple regions for redundancy

## Support

For issues or questions:
- GitHub Issues: https://github.com/robertsoden/ontario-environmental-data/issues
- Documentation: https://github.com/robertsoden/ontario-environmental-data/tree/main/docs
