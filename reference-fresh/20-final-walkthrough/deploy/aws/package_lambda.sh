#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <s3-bucket> <s3-prefix>" >&2
  exit 1
fi

S3_BUCKET="$1"
S3_PREFIX="$2"
BUILD_DIR="deploy/aws/build/lambda"
ZIP_FILE="deploy/aws/build/lambda_inventory.zip"

rm -rf "deploy/aws/build"
mkdir -p "$BUILD_DIR"
python3 -m pip install -r requirements.txt -t "$BUILD_DIR"
cp src/lambda_inventory.py "$BUILD_DIR/"
cp src/db_adapter.py "$BUILD_DIR/"
(
  cd "$BUILD_DIR"
  zip -r "../lambda_inventory.zip" .
)
aws s3 cp "$ZIP_FILE" "s3://${S3_BUCKET}/${S3_PREFIX}/lambda_inventory.zip"
echo "Uploaded s3://${S3_BUCKET}/${S3_PREFIX}/lambda_inventory.zip"
