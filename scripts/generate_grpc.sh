#!/bin/bash
# Generate gRPC stubs from proto file

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PROTO_DIR="$PROJECT_DIR/proto"
OUTPUT_DIR="$PROJECT_DIR/src/spooled/grpc/stubs"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Generate Python gRPC stubs
python -m grpc_tools.protoc \
    -I"$PROTO_DIR" \
    --python_out="$OUTPUT_DIR" \
    --grpc_python_out="$OUTPUT_DIR" \
    --pyi_out="$OUTPUT_DIR" \
    "$PROTO_DIR/spooled.proto"

# Create __init__.py
cat > "$OUTPUT_DIR/__init__.py" << 'EOF'
"""Generated gRPC stubs."""
from spooled.grpc.stubs.spooled_pb2 import *
from spooled.grpc.stubs.spooled_pb2_grpc import *
EOF

echo "gRPC stubs generated successfully in $OUTPUT_DIR"
