#!/bin/bash

# Wait for MinIO to be ready
echo "Waiting for MinIO to be ready..."
sleep 10

# Download MinIO client if not exists
if [ ! -f "./mc" ]; then
    echo "Downloading MinIO client..."
    curl -s https://dl.min.io/client/mc/release/linux-amd64/mc -o mc
    chmod +x mc
fi

# Configure MinIO client
echo "Configuring MinIO client..."
./mc alias set myminio http://localhost:9000 ${MINIO_ACCESS_KEY} ${MINIO_SECRET_KEY}

# Set CORS configuration
echo "Setting CORS configuration..."
./mc admin config set myminio api \
    cors_allow_origin="*" \
    cors_allow_headers="*" \
    cors_allow_methods="GET,PUT,POST,DELETE,HEAD,OPTIONS" \
    cors_expose_headers="ETag,Content-Length,Content-Range,Accept-Ranges"

# Restart MinIO to apply changes
echo "Restarting MinIO service..."
./mc admin service restart myminio

echo "MinIO CORS configuration completed!"
