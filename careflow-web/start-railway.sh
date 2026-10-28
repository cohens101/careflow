#!/bin/sh
set -eu

if [ -z "${SNOWFLAKE_PRIVATE_KEY_B64:-}" ]; then
  echo "Snowflake private key not configured"
  exit 1
fi

umask 077
printf '%s' "$SNOWFLAKE_PRIVATE_KEY_B64" | base64 -d > /tmp/careflow-key.p8
export SNOWFLAKE_PRIVATE_KEY_PATH=/tmp/careflow-key.p8

exec ./node_modules/.bin/next start \
  --hostname 0.0.0.0 \
  --port "${PORT:-3000}"
