#!/bin/bash

# Mac to Raspberry Pi sync scripts for development

PI_HOST="bunny@radish"
PI_PATH="~/workhorse"
LOCAL_PATH="."

echo "📤 Uploading to Raspberry Pi..."

# Sync files to Pi, excluding unnecessary files
rsync -avz --progress \
    --exclude 'venv/' \
    --exclude '__pycache__/' \
    --exclude '.git/' \
    --exclude '*.pyc' \
    --exclude '.DS_Store' \
    --exclude 'logs/' \
    --exclude '*.log' \
    "$LOCAL_PATH/" "$PI_HOST:$PI_PATH/"

echo "✅ Upload complete!"
echo ""
echo "To run on Pi:"
echo "  ssh $PI_HOST"
echo "  cd $PI_PATH"
echo "  ./start-pi.sh"
