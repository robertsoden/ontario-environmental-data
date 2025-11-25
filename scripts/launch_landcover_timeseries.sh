#!/bin/bash
# Launch EC2 instance to download and process land cover time series (2010, 2015)

set -e

INSTANCE_TYPE="${1:-t3.xlarge}"
REGION="us-east-1"

echo "=========================================="
echo "Land Cover Time Series - EC2 Launcher"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Instance Type: $INSTANCE_TYPE"
echo "  Storage: 150 GB"
echo "  Region: $REGION"
echo "  Processing: 2010, 2015 land cover + COG conversion"
echo ""

# Get latest Ubuntu 22.04 AMI
echo "🔍 Finding latest Ubuntu 22.04 AMI..."
AMI_ID=$(aws ec2 describe-images \
    --region $REGION \
    --owners 099720109477 \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
    --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
    --output text)
echo "   AMI: $AMI_ID"

# Check SSH key
echo ""
echo "🔑 Checking SSH key pair..."
if aws ec2 describe-key-pairs --region $REGION --key-names ontario-satellite-key &>/dev/null; then
    echo "   ✓ Key pair exists"
else
    echo "   ✗ Key pair not found"
    exit 1
fi

# Check security group
echo ""
echo "🔒 Checking security group..."
SG_ID=$(aws ec2 describe-security-groups --region $REGION \
    --filters "Name=group-name,Values=satellite-processing-sg" \
    --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "")

if [ "$SG_ID" != "" ] && [ "$SG_ID" != "None" ]; then
    echo "   ✓ Security group exists: $SG_ID"
else
    echo "   ✗ Security group not found"
    exit 1
fi

# Check IAM role
echo ""
echo "🔐 Checking IAM instance profile..."
if aws iam get-instance-profile --instance-profile-name ontario-satellite-processing-profile &>/dev/null; then
    echo "   ✓ IAM role exists"
    echo "   ✓ Instance profile exists"
else
    echo "   ✗ IAM instance profile not found"
    exit 1
fi

# Create user data script
USER_DATA=$(cat <<'EOF'
#!/bin/bash
set -e

# Log all output
exec > >(tee -a /var/log/landcover-processing-setup.log)
exec 2>&1

echo "Starting land cover time series processing setup..."
date

# Update and install dependencies
apt-get update
apt-get install -y python3 python3-pip gdal-bin awscli unzip curl

# Download processing script
mkdir -p /home/ubuntu
aws s3 cp s3://ontario-environmental-data/scripts/process_landcover_timeseries.py /home/ubuntu/ 2>/dev/null || \
    curl -o /home/ubuntu/process_landcover_timeseries.py https://raw.githubusercontent.com/robertsoden/ontario-environmental-data/main/scripts/process_landcover_timeseries.py

chmod +x /home/ubuntu/process_landcover_timeseries.py
chown ubuntu:ubuntu /home/ubuntu/process_landcover_timeseries.py

# Download COG conversion script
aws s3 cp s3://ontario-environmental-data/scripts/convert_to_cog.py /home/ubuntu/ 2>/dev/null || \
    curl -o /home/ubuntu/convert_to_cog.py https://raw.githubusercontent.com/robertsoden/ontario-environmental-data/main/scripts/convert_to_cog.py

chmod +x /home/ubuntu/convert_to_cog.py
chown ubuntu:ubuntu /home/ubuntu/convert_to_cog.py

# Create status indicator
echo "setup_complete" > /home/ubuntu/status.txt

# Run processing pipeline
echo "Starting land cover download and processing..."
sudo -u ubuntu python3 /home/ubuntu/process_landcover_timeseries.py > /home/ubuntu/processing.log 2>&1

# Update status after processing
if [ $? -eq 0 ]; then
    echo "processing_complete" > /home/ubuntu/status.txt

    # Run COG conversion on new files only (2010, 2015)
    echo "Starting COG conversion for 2010 and 2015..."
    sudo -u ubuntu python3 /home/ubuntu/convert_to_cog.py >> /home/ubuntu/processing.log 2>&1

    if [ $? -eq 0 ]; then
        echo "conversion_complete" > /home/ubuntu/status.txt
    else
        echo "conversion_failed" > /home/ubuntu/status.txt
    fi
else
    echo "processing_failed" > /home/ubuntu/status.txt
fi

echo "Setup and processing complete"
date
EOF
)

# Launch instance
echo ""
echo "🚀 Launching EC2 instance..."
echo "   Type: $INSTANCE_TYPE"
echo "   Storage: 150 GB"
echo "   Region: $REGION"
echo ""

INSTANCE_ID=$(aws ec2 run-instances \
    --region $REGION \
    --image-id $AMI_ID \
    --instance-type $INSTANCE_TYPE \
    --key-name ontario-satellite-key \
    --security-group-ids $SG_ID \
    --iam-instance-profile Name=ontario-satellite-processing-profile \
    --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":150,"VolumeType":"gp3","DeleteOnTermination":true}}]' \
    --user-data "$USER_DATA" \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=ontario-landcover-timeseries}]' \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "✓ Instance launched: $INSTANCE_ID"
echo ""
echo "⏳ Waiting for instance to be running..."

aws ec2 wait instance-running --region $REGION --instance-ids $INSTANCE_ID

PUBLIC_IP=$(aws ec2 describe-instances \
    --region $REGION \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo "✓ Instance is running"
echo ""
echo "✓ Public IP: $PUBLIC_IP"
echo ""

# Save connection details
cat > /tmp/landcover_ec2_connection.txt <<EOL
========================================
Ontario Land Cover Time Series Instance
========================================

Instance ID: $INSTANCE_ID
Instance Type: $INSTANCE_TYPE
Public IP: $PUBLIC_IP
Region: $REGION
SSH Key: ~/.ssh/ontario-satellite-key.pem

Status: Processing started automatically via user-data

========================================
Monitoring
========================================

Connect to instance:
  ssh -i ~/.ssh/ontario-satellite-key.pem ubuntu@$PUBLIC_IP

View setup log:
  ssh -i ~/.ssh/ontario-satellite-key.pem ubuntu@$PUBLIC_IP "tail -f /var/log/landcover-processing-setup.log"

View processing log:
  ssh -i ~/.ssh/ontario-satellite-key.pem ubuntu@$PUBLIC_IP "tail -f /home/ubuntu/processing.log"

Check status:
  ssh -i ~/.ssh/ontario-satellite-key.pem ubuntu@$PUBLIC_IP "cat /home/ubuntu/status.txt"

========================================
Termination
========================================

Terminate when done:
  aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $REGION

Check instance status:
  aws ec2 describe-instances --instance-ids $INSTANCE_ID --region $REGION --query 'Reservations[0].Instances[0].State.Name' --output text

EOL

cat /tmp/landcover_ec2_connection.txt

echo ""
echo "=========================================="
echo "✅ Instance launched successfully!"
echo "=========================================="
echo ""
echo "Processing will start automatically in ~2-3 minutes."
echo "Connection details saved to: /tmp/landcover_ec2_connection.txt"
echo ""
echo "Monitor progress:"
echo "  ssh -i ~/.ssh/ontario-satellite-key.pem ubuntu@$PUBLIC_IP \"tail -f /home/ubuntu/processing.log\""
echo ""
