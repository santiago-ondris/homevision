#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
response=$(mktemp)
trap 'rm -f "$response"' EXIT HUP INT TERM
api_url=http://localhost:8080
expected_boxes=41
worker_url=http://localhost:8000/healthz

expect_status() {
  expected=$1
  shift
  actual=$(curl --silent --show-error --max-time 30 -o "$response" -w '%{http_code}' "$@")
  if [ "$actual" != "$expected" ]; then
    printf 'Expected HTTP %s, got %s\n' "$expected" "$actual" >&2
    cat "$response" >&2
    exit 1
  fi
}

expect_status 200 "$api_url/healthz"
expect_status 200 "$api_url/readyz"
expect_status 200 -F 'file=@samples/sample2.jpg' "$api_url/detect"
docker compose exec -T worker python -c '
import json, sys
body = json.load(sys.stdin)
count = len(body["boxes"])
if count != int(sys.argv[1]):
    sys.exit(f"Expected {sys.argv[1]} boxes, got {count}")
' "$expected_boxes" < "$response"

printf 'This is a text file.\n' | expect_status 415 -F 'file=@-;filename=upload.txt' "$api_url/detect"
docker compose exec -T worker python -c '
import json, sys
body = json.load(sys.stdin)
if body["error"]["code"] != "unsupported_media_type":
    sys.exit(f"Unexpected error: {body}")
' < "$response"

if curl --silent --show-error --connect-timeout 2 "$worker_url" > /dev/null 2>&1; then
  printf 'Worker port is reachable from the host\n' >&2
  exit 1
else
  status=$?
  if [ "$status" != 7 ] && [ "$status" != 28 ]; then
    printf 'Expected no TCP connection to the worker, got curl exit %s\n' "$status" >&2
    exit 1
  fi
fi

printf 'Smoke checks passed\n'
