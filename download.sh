#!/bin/bash

# Download files from Raspberry Pi to Mac

PI_HOST="bunny@radish"
PI_PATH="~/workhorse"
LOCAL_PATH="."

echo "📥 Downloading from Raspberry Pi..."

# Sync logs and generated files back to Mac
rsync -avz --progress \
    --include '*.log' \
    --include 'logs/' \
    --include 'config.yaml' \
    --exclude '*' \
    "$PI_HOST:$PI_PATH/" "$LOCAL_PATH/"

echo "✅ Download complete!"
