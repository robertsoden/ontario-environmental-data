# Satellite Data Processing on EC2

This guide explains how to process large satellite datasets (land cover, NDVI, DEM) on an EC2 instance, clip them to Ontario boundaries, and upload to S3.

## Overview

Satellite datasets are too large to process in GitHub Actions (6-7 GB each). Instead:
1. Launch an EC2 instance with sufficient storage and compute
2. Run the processing script to download, clip, and upload datasets
3. Add datasets to registry as static datasets with S3 URLs

## Datasets Processed

| Dataset | Years | Resolution | Source | Size (raw) |
|---------|-------|------------|--------|------------|
| Land Cover | 2010, 2015, 2020 | 30m | Natural Resources Canada | ~2 GB each |
| NDVI | 2023 | 250m | Statistics Canada MODIS | ~6-7 GB |
| DEM | Latest | Variable | Natural Resources Canada CDEM | ~500 MB tiles |

## EC2 Instance Requirements

### Recommended Instance Type
- **Type**: `t3.xlarge` (4 vCPU, 16 GB RAM) or `m5.xlarge`
- **Storage**: 500 GB EBS volume (gp3)
- **OS**: Ubuntu 22.04 LTS
- **Estimated cost**: ~$2-5 for processing (a few hours)

### Launch Instance

```bash
# Using AWS CLI
aws ec2 run-instances \
  --image-id ami-0c7217cdde317cfec \
  --instance-type t3.xlarge \
  --key-name your-key-name \
  --security-group-ids sg-xxxxxxxx \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":500,"VolumeType":"gp3"}}]' \
  --iam-instance-profile Name=EC2-S3-Access \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=satellite-processing}]'
```

Or use the AWS Console:
1. Launch EC2 instance
2. Ubuntu 22.04 LTS
3. t3.xlarge
4. 500 GB gp3 storage
5. Attach IAM role with S3 write permissions

## Setup EC2 Instance

SSH into the instance and run:

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install system dependencies
sudo apt-get install -y \
  python3-pip \
  gdal-bin \
  libgdal-dev \
  python3-gdal \
  unzip \
  wget \
  awscli \
  git

# Install Python packages
pip3 install \
  rasterio \
  geopandas \
  shapely \
  numpy \
  pandas

# Clone repository
git clone https://github.com/yourusername/ontario-environmental-data.git
cd ontario-environmental-data

# Install package
pip3 install -e .

# Create working directory
sudo mkdir -p /mnt/satellite_processing
sudo chown ubuntu:ubuntu /mnt/satellite_processing
```

## Configure AWS Credentials

Ensure the EC2 instance has an IAM role with S3 write permissions, or configure credentials:

```bash
aws configure
# Enter your AWS credentials
```

Required S3 permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::ontario-environmental-data/*",
        "arn:aws:s3:::ontario-environmental-data"
      ]
    }
  ]
}
```

## Run Processing Script

```bash
# Make script executable
chmod +x scripts/process_satellite_data_ec2.py

# Run processing (will take several hours)
python3 scripts/process_satellite_data_ec2.py

# Or run in background with nohup
nohup python3 scripts/process_satellite_data_ec2.py > processing.log 2>&1 &

# Monitor progress
tail -f processing.log
```

## Processing Workflow

The script performs these steps for each dataset:

1. **Download** raw data from source FTP/HTTP servers
2. **Extract** compressed archives
3. **Clip** to Ontario boundaries using rasterio
4. **Compress** with LZW compression
5. **Upload** to S3 with INTELLIGENT_TIERING storage class
6. **Clean up** raw data to save disk space

### Expected Processing Times

| Dataset | Download | Processing | Upload | Total |
|---------|----------|------------|--------|-------|
| Land Cover 2010 | ~20 min | ~30 min | ~10 min | ~1 hour |
| Land Cover 2015 | ~20 min | ~30 min | ~10 min | ~1 hour |
| Land Cover 2020 | ~20 min | ~30 min | ~10 min | ~1 hour |
| NDVI 2023 | ~45 min | ~1 hour | ~20 min | ~2 hours |

**Total: ~5-6 hours**

## Monitoring Progress

```bash
# Watch disk usage
watch -n 5 df -h /mnt/satellite_processing

# Check processing log
tail -f processing.log

# List processed files
ls -lh /mnt/satellite_processing/processed/*/
```

## Verify Uploads

After processing completes, verify files are on S3:

```bash
# List uploaded files
aws s3 ls s3://ontario-environmental-data/datasets/satellite/ --recursive --human-readable

# Expected output:
# datasets/satellite/landcover/ontario_landcover_2010.tif
# datasets/satellite/landcover/ontario_landcover_2015.tif
# datasets/satellite/landcover/ontario_landcover_2020.tif
# datasets/satellite/ndvi/ontario_ndvi_2023_250m.tif
```

## Add to Registry

After successful processing and upload, add datasets to the registry in `ontario_data/datasets.py`:

```python
"landcover_2020": DatasetDefinition(
    id="landcover_2020",
    name="Ontario Land Cover 2020",
    description="30m land cover classification for Ontario",
    category="satellite",
    is_static=True,
    s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/satellite/landcover/ontario_landcover_2020.tif",
    output_format="geotiff",
    min_records=1,
    enabled=True,
),

"ndvi_2023": DatasetDefinition(
    id="ndvi_2023",
    name="Ontario NDVI 2023 (250m)",
    description="MODIS-derived NDVI vegetation indices for Ontario",
    category="satellite",
    is_static=True,
    s3_url="https://ontario-environmental-data.s3.us-east-1.amazonaws.com/datasets/satellite/ndvi/ontario_ndvi_2023_250m.tif",
    output_format="geotiff",
    min_records=1,
    enabled=True,
),
```

## Cleanup

After successful processing and verification:

```bash
# Clean up working directory on EC2
sudo rm -rf /mnt/satellite_processing

# Terminate EC2 instance
aws ec2 terminate-instances --instance-ids i-xxxxxxxxxxxxxxxxx
```

## Troubleshooting

### Out of Disk Space

```bash
# Check disk usage
df -h

# Clean up raw data manually
rm -rf /mnt/satellite_processing/raw/*
```

### Download Failures

The script includes retry logic, but if downloads fail:

```bash
# Retry manually with wget
wget --continue --progress=bar:force <URL>
```

### Clipping Errors

Ensure Ontario boundary is valid:

```bash
# Validate boundary
python3 -c "import geopandas as gpd; gdf = gpd.read_file('/mnt/satellite_processing/ontario_boundary.geojson'); print(gdf.is_valid.all())"
```

### Memory Errors

If processing fails due to memory:
- Use a larger instance type (m5.2xlarge with 32 GB RAM)
- Process tiles separately instead of full datasets

## Cost Estimation

**EC2 Compute:**
- t3.xlarge: $0.1664/hour × 6 hours = ~$1.00

**EBS Storage:**
- 500 GB gp3: $0.08/GB/month × (6 hours / 720 hours) = ~$0.33

**Data Transfer:**
- Outbound to S3 (same region): Free
- Downloads from NRCan/StatCan: Free

**Total Estimated Cost: ~$1.50 per run**

## Next Steps

1. Launch EC2 instance
2. Run processing script
3. Verify uploads to S3
4. Add datasets to registry
5. Update catalog with new satellite datasets
6. Terminate EC2 instance
