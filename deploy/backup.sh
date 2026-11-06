#!/bin/sh
set -eu
mkdir -p /backups
while :; do
  name="/backups/phase1-$(date -u +%Y%m%dT%H%M%SZ).dump"
  pg_dump --format=custom --no-owner --file="$name.partial"
  mv "$name.partial" "$name"
  echo "backup_complete"
  sleep 86400
done
