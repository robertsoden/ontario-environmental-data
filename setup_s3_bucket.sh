#!/bin/bash

# S3 Bucket Setup Script for Ontario Environmental Data
# This script creates and configures the S3 bucket for data hosting

set -e  # Exit on error

BUCKET_NAME="ontario-environmental-data"
REGION="us-east-1"

echo "🪣  Setting up S3 bucket: $BUCKET_NAME"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Installing..."

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install awscli
        else
            echo "Please install AWS CLI:"
            echo "  curl 'https://awscli.amazonaws.com/AWSCLIV2.pkg' -o 'AWSCLIV2.pkg'"
            echo "  sudo installer -pkg AWSCLIV2.pkg -target /"
            exit 1
        fi
    else
        # Linux
        pip install awscli
    fi
fi

# Check AWS credentials
echo "Checking AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured"
    echo ""
    echo "Please configure AWS credentials:"
    echo "  aws configure"
    echo ""
    echo "Or set environment variables:"
    echo "  export AWS_ACCESS_KEY_ID=your_key"
    echo "  export AWS_SECRET_ACCESS_KEY=your_secret"
    exit 1
fi

echo "✅ AWS credentials found"
IDENTITY=$(aws sts get-caller-identity)
echo "   Account: $(echo $IDENTITY | python3 -c 'import sys, json; print(json.load(sys.stdin)["Account"])')"
echo ""

# Create bucket
echo "Creating S3 bucket..."
if aws s3 ls "s3://${BUCKET_NAME}" 2>&1 | grep -q 'NoSuchBucket'; then
    aws s3 mb "s3://${BUCKET_NAME}" --region "${REGION}"
    echo "✅ Bucket created: s3://${BUCKET_NAME}"
else
    echo "✅ Bucket already exists: s3://${BUCKET_NAME}"
fi

# Disable Block Public Access
echo ""
echo "Configuring public access..."
aws s3api put-public-access-block \
  --bucket "${BUCKET_NAME}" \
  --public-access-block-configuration \
  "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

echo "✅ Public access configured"

# Set bucket policy for public read
echo ""
echo "Setting bucket policy for public read access..."
cat > /tmp/bucket-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::${BUCKET_NAME}/*"
    }
  ]
}
EOF

aws s3api put-bucket-policy \
  --bucket "${BUCKET_NAME}" \
  --policy file:///tmp/bucket-policy.json

rm /tmp/bucket-policy.json

echo "✅ Bucket policy set"

# Set CORS for web access
echo ""
echo "Configuring CORS for web applications..."
cat > /tmp/cors-config.json <<EOF
{
  "CORSRules": [
    {
      "AllowedOrigins": ["*"],
      "AllowedMethods": ["GET", "HEAD"],
      "AllowedHeaders": ["*"],
      "MaxAgeSeconds": 3600
    }
  ]
}
EOF

aws s3api put-bucket-cors \
  --bucket "${BUCKET_NAME}" \
  --cors-configuration file:///tmp/cors-config.json

rm /tmp/cors-config.json

echo "✅ CORS configured"

# Create directory structure
echo ""
echo "Creating directory structure..."
for dir in datasets/boundaries datasets/communities datasets/community datasets/protected_areas datasets/biodiversity datasets/environmental metadata; do
    echo "Creating ${dir}/"
    aws s3api put-object \
      --bucket "${BUCKET_NAME}" \
      --key "${dir}/" \
      --content-length 0 \
      || true
done

echo "✅ Directory structure created"

# Test upload
echo ""
echo "Testing upload with a placeholder file..."
echo '{"message": "Ontario Environmental Data - S3 bucket initialized"}' > /tmp/test.json
aws s3 cp /tmp/test.json "s3://${BUCKET_NAME}/test.json" \
  --acl public-read \
  --content-type "application/json"
rm /tmp/test.json

echo "✅ Test upload successful"

# Verify public access
echo ""
echo "Verifying public access..."
TEST_URL="https://${BUCKET_NAME}.s3.${REGION}.amazonaws.com/test.json"
if curl -s -f "$TEST_URL" > /dev/null; then
    echo "✅ Public access verified"
    echo "   URL: $TEST_URL"
else
    echo "⚠️  Public access verification failed"
    echo "   You may need to wait a few seconds for DNS propagation"
fi

# Summary
echo ""
echo "=========================================="
echo "✅ S3 Bucket Setup Complete!"
echo "=========================================="
echo ""
echo "Bucket Name: ${BUCKET_NAME}"
echo "Region: ${REGION}"
echo "Base URL: https://${BUCKET_NAME}.s3.${REGION}.amazonaws.com"
echo ""
echo "Next steps:"
echo "1. Add GitHub secrets (if not already done):"
echo "   - AWS_ACCESS_KEY_ID"
echo "   - AWS_SECRET_ACCESS_KEY"
echo ""
echo "2. Run the data collection workflow:"
echo "   gh workflow run 'Collect Data and Upload to S3'"
echo ""
echo "3. View the setup guide for more details:"
echo "   docs/S3_STORAGE_GUIDE.md"
echo ""
