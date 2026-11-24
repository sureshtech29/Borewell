#!/bin/bash
# Runs once, the first time the PostGIS container initialises an empty data volume.
# Mounted by docker-compose.yml into /docker-entrypoint-initdb.d/.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /seed/schema.sql

if [ "${SEED_DEMO:-true}" = "true" ]; then
  echo ">> Loading SYNTHETIC DEMONSTRATION data (SEED_DEMO=true)"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /seed/seed_demo.sql
else
  echo ">> SEED_DEMO is not 'true' - database left empty (load real data with scripts/etl/load.py)"
fi
