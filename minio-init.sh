#!/bin/bash

# Start MinIO server in background
minio server /data --console-address ":9001" --address ":9000" &

# Wait for MinIO to start
sleep 10

# Download and setup mc client
curl -s https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc
chmod +x /usr/local/bin/mc

# Configure mc
mc alias set local http://localhost:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD}

# Set CORS policy
mc admin config set local api \
    cors_allow_origin="*" \
    cors_allow_headers="*" \
    cors_allow_methods="GET,PUT,POST,DELETE,HEAD,OPTIONS" \
    cors_expose_headers="ETag,Content-Length,Content-Range,Accept-Ranges"

# Restart MinIO to apply changes
mc admin service restart local

# Keep MinIO running in foreground
wait
