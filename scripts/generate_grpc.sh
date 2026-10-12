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

# grpcio-tools generates a top-level sibling import; rewrite it for this package.
python - "$OUTPUT_DIR/spooled_pb2_grpc.py" << 'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
# Bytes in and out: text mode would write CRLF line endings on Windows.
content = path.read_bytes()
content = content.replace(
    b"import spooled_pb2 as spooled__pb2",
    b"from spooled.grpc.stubs import spooled_pb2 as spooled__pb2",
)
path.write_bytes(content)
PY


echo "gRPC stubs generated successfully in $OUTPUT_DIR"
