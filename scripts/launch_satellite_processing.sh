#!/bin/bash
#
# Quick-start script to launch EC2 instance and run satellite data processing
#
# Usage: ./scripts/launch_satellite_processing.sh
#

set -e

echo "=========================================="
echo "Satellite Data Processing - EC2 Launcher"
echo "=========================================="
echo ""

# Configuration
INSTANCE_TYPE="t3.micro"
INSTANCE_NAME="ontario-satellite-processing"
REGION="us-east-1"
VOLUME_SIZE=500

# Check AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured. Run 'aws configure' first."
    exit 1
fi

echo "✓ AWS CLI configured"
echo ""

# Get latest Ubuntu 22.04 AMI
echo "🔍 Finding latest Ubuntu 22.04 AMI..."
AMI_ID=$(aws ec2 describe-images \
    --region $REGION \
    --owners 099720109477 \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*" \
    --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
    --output text)

echo "   AMI: $AMI_ID"
echo ""

# Check for existing key pair
echo "🔑 Checking SSH key pair..."
KEY_NAME="ontario-satellite-key"
if ! aws ec2 describe-key-pairs --key-names $KEY_NAME --region $REGION > /dev/null 2>&1; then
    echo "   Creating new key pair..."
    aws ec2 create-key-pair \
        --key-name $KEY_NAME \
        --region $REGION \
        --query 'KeyMaterial' \
        --output text > ~/.ssh/${KEY_NAME}.pem
    chmod 400 ~/.ssh/${KEY_NAME}.pem
    echo "   ✓ Key saved to ~/.ssh/${KEY_NAME}.pem"
else
    echo "   ✓ Key pair exists"
fi
echo ""

# Check for security group
echo "🔒 Checking security group..."
SG_NAME="satellite-processing-sg"
SG_ID=$(aws ec2 describe-security-groups \
    --region $REGION \
    --filters "Name=group-name,Values=$SG_NAME" \
    --query 'SecurityGroups[0].GroupId' \
    --output text 2>/dev/null || echo "")

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
    echo "   Creating security group..."
    VPC_ID=$(aws ec2 describe-vpcs \
        --region $REGION \
        --filters "Name=isDefault,Values=true" \
        --query 'Vpcs[0].VpcId' \
        --output text)

    SG_ID=$(aws ec2 create-security-group \
        --group-name $SG_NAME \
        --description "Security group for satellite data processing" \
        --vpc-id $VPC_ID \
        --region $REGION \
        --query 'GroupId' \
        --output text)

    # Allow SSH from your IP
    MY_IP=$(curl -s https://checkip.amazonaws.com)
    aws ec2 authorize-security-group-ingress \
        --group-id $SG_ID \
        --protocol tcp \
        --port 22 \
        --cidr ${MY_IP}/32 \
        --region $REGION

    echo "   ✓ Security group created: $SG_ID"
else
    echo "   ✓ Security group exists: $SG_ID"
fi
echo ""

# Launch instance
echo "🚀 Launching EC2 instance..."
echo "   Type: $INSTANCE_TYPE"
echo "   Storage: ${VOLUME_SIZE} GB"
echo "   Region: $REGION"
echo ""

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --instance-type $INSTANCE_TYPE \
    --key-name $KEY_NAME \
    --security-group-ids $SG_ID \
    --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":$VOLUME_SIZE,\"VolumeType\":\"gp3\"}}]" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
    --region $REGION \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "✓ Instance launched: $INSTANCE_ID"
echo ""

# Wait for instance to be running
echo "⏳ Waiting for instance to be running..."
aws ec2 wait instance-running --instance-ids $INSTANCE_ID --region $REGION
echo "✓ Instance is running"
echo ""

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --region $REGION \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo "✓ Public IP: $PUBLIC_IP"
echo ""

# Wait a bit for SSH to be ready
echo "⏳ Waiting 30 seconds for SSH to be ready..."
sleep 30

# Save connection details
cat > /tmp/satellite_ec2_connection.txt <<EOF
Instance ID: $INSTANCE_ID
Public IP: $PUBLIC_IP
SSH Key: ~/.ssh/${KEY_NAME}.pem
Region: $REGION

Connect with:
  ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@$PUBLIC_IP

Terminate when done:
  aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $REGION
EOF

cat /tmp/satellite_ec2_connection.txt
echo ""

# Ask if user wants to SSH and setup
read -p "🤔 SSH into instance and run setup now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "=========================================="
    echo "Setting up EC2 instance..."
    echo "=========================================="
    echo ""

    # Create setup script
    cat > /tmp/setup_satellite_processing.sh <<'SETUP_EOF'
#!/bin/bash
set -e

echo "📦 Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y \
    python3-pip \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    unzip \
    wget \
    git \
    htop \
    awscli

echo "🐍 Installing Python packages..."
pip3 install -q \
    rasterio \
    geopandas \
    shapely \
    numpy \
    pandas

echo "📥 Cloning repository..."
git clone https://github.com/yourusername/ontario-environmental-data.git
cd ontario-environmental-data

echo "📦 Installing package..."
pip3 install -q -e .

echo "📁 Creating working directory..."
sudo mkdir -p /mnt/satellite_processing
sudo chown ubuntu:ubuntu /mnt/satellite_processing

echo ""
echo "✅ Setup complete!"
echo ""
echo "To run processing:"
echo "  cd ontario-environmental-data"
echo "  nohup python3 scripts/process_satellite_data_ec2.py > processing.log 2>&1 &"
echo "  tail -f processing.log"
echo ""
SETUP_EOF

    # Copy setup script to EC2
    scp -i ~/.ssh/${KEY_NAME}.pem -o StrictHostKeyChecking=no \
        /tmp/setup_satellite_processing.sh ubuntu@$PUBLIC_IP:/tmp/

    # Run setup script
    ssh -i ~/.ssh/${KEY_NAME}.pem -o StrictHostKeyChecking=no ubuntu@$PUBLIC_IP \
        'bash /tmp/setup_satellite_processing.sh'

    echo ""
    echo "=========================================="
    echo "✅ Setup complete!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "1. SSH into instance:"
    echo "   ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@$PUBLIC_IP"
    echo ""
    echo "2. Start processing:"
    echo "   cd ontario-environmental-data"
    echo "   nohup python3 scripts/process_satellite_data_ec2.py > processing.log 2>&1 &"
    echo ""
    echo "3. Monitor progress:"
    echo "   tail -f processing.log"
    echo ""
    echo "4. When done, terminate instance:"
    echo "   aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $REGION"
    echo ""
fi

echo ""
echo "=========================================="
echo "Connection details saved to:"
echo "/tmp/satellite_ec2_connection.txt"
echo "=========================================="
