#!/bin/bash

# Initialize variables
WORKERS_VALUE=1
CONCURRENCY_VALUE=1

# Parse command line options
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --workers) WORKERS_VALUE="$2"; shift ;;
        --concurrency) CONCURRENCY_VALUE="$2"; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done


# Validate A_VALUE is a positive integer
if ! [[ "$WORKERS_VALUE" =~ ^[0-9]+$ ]] || [ "$WORKERS_VALUE" -lt 1 ]; then
    echo "Error: --workers must be a positive integer"
    exit 1
fi

# Run loop A_VALUE times
for ((i=1; i<=WORKERS_VALUE; i++)); do
    echo "Starting worker $i with concurrency $CONCURRENCY_VALUE"
    if [ "$CONCURRENCY_VALUE" -gt 1 ]; then
        celery -A config worker --loglevel=info -n worker$i --concurrency=$CONCURRENCY_VALUE &
    else
        celery -A config worker --loglevel=info -n worker$i &
    fi
done
celery -A config beat --loglevel=info &
celery -A config flower --loglevel=info &
