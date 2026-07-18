#!/bin/bash
# Database extraction template: dump every Postgres/Mongo/volume from a host
# Dumps each Postgres DB, Mongo, and Maillayer file volume to /tmp/dbdumps/
# Sanity-checks each dump and reports final sizes.
# Intended to be uploaded to remote and executed there once.

set +e
TS=$(date +%Y%m%d-%H%M%S)
OUT=/tmp/dbdumps-$TS
mkdir -p "$OUT"
cd "$OUT"

# Container IDs from migration plan
PG_APP1="<RESOURCE_UUID>"
PG_APP2="<RESOURCE_UUID>"
PG_APP3="<RESOURCE_UUID>"
MONGO_MAILLAYER="<RESOURCE_UUID>"
MAILLAYER_VOLUME_PREFIX="<UUID_PREFIX>"

echo "===================================================="
echo "DB DUMP - <SERVER_NAME> - $TS"
echo "===================================================="
echo ""

dump_pg() {
  local container="$1"
  local label="$2"
  local outfile="$OUT/${label}.dump"

  echo "[*] Postgres: $label ($container)"

  # Discover database name (assume app_db for example HQ, 'postgres' for Coolify-managed)
  local dbname
  dbname=$(sudo docker exec "$container" psql -U postgres -At -c "SELECT datname FROM pg_database WHERE datname NOT IN ('template0','template1','postgres') LIMIT 1;" 2>/dev/null)
  if [ -z "$dbname" ]; then
    dbname="postgres"
    echo "    no user DB found, falling back to 'postgres'"
  fi
  echo "    db: $dbname"

  # Schema-only dump first (fast, lets us spot tampering even if data dump fails)
  sudo docker exec "$container" pg_dump -U postgres -s "$dbname" > "$OUT/${label}.schema.sql" 2>"$OUT/${label}.schema.err"
  echo "    schema: $(wc -l < $OUT/${label}.schema.sql) lines"

  # Custom-format full dump
  sudo docker exec "$container" pg_dump -U postgres -Fc "$dbname" > "$outfile" 2>"$OUT/${label}.err"
  local size
  size=$(stat -c %s "$outfile" 2>/dev/null || echo 0)
  echo "    dump: $size bytes -> $outfile"

  # Sanity-check: pg_restore --list should succeed and show object count
  if [ "$size" -gt 1000 ]; then
    local objcount
    objcount=$(sudo docker exec -i "$container" pg_restore --list < "$outfile" 2>/dev/null | grep -v '^;' | wc -l)
    echo "    pg_restore --list: $objcount objects"
  else
    echo "    WARNING: dump suspiciously small or empty"
  fi

  # Capture role and user list (separate file — easier to scan for added accounts)
  sudo docker exec "$container" psql -U postgres -c "\\du" > "$OUT/${label}.roles.txt" 2>&1
  echo ""
}

dump_pg "$PG_APP1"    "example-app"
dump_pg "$PG_APP2"  "exampleapp2"
dump_pg "$PG_APP3" "example"

echo "[*] MongoDB: Maillayer ($MONGO_MAILLAYER)"
# Mongo credentials must come from Maillayer container env. Discover them.
MAILLAYER_APP=$(sudo docker ps --format '{{.ID}} {{.Names}}' | grep -i maillayer | head -1 | awk '{print $1}')
echo "    Maillayer app container: $MAILLAYER_APP"

MONGO_USER=$(sudo docker exec "$MAILLAYER_APP" env 2>/dev/null | grep -iE 'MONGO_(USER|USERNAME|INITDB_ROOT_USERNAME)' | head -1 | cut -d= -f2)
MONGO_PASS=$(sudo docker exec "$MAILLAYER_APP" env 2>/dev/null | grep -iE 'MONGO_(PASS|PASSWORD|INITDB_ROOT_PASSWORD)' | head -1 | cut -d= -f2)

if [ -z "$MONGO_USER" ]; then
  # Try the mongo container's own env (where Coolify puts the root creds)
  MONGO_USER=$(sudo docker exec "$MONGO_MAILLAYER" env 2>/dev/null | grep MONGO_INITDB_ROOT_USERNAME | cut -d= -f2)
  MONGO_PASS=$(sudo docker exec "$MONGO_MAILLAYER" env 2>/dev/null | grep MONGO_INITDB_ROOT_PASSWORD | cut -d= -f2)
fi

if [ -n "$MONGO_USER" ] && [ -n "$MONGO_PASS" ]; then
  echo "    mongo user discovered: $MONGO_USER"
  sudo docker exec "$MONGO_MAILLAYER" mongodump --username "$MONGO_USER" --password "$MONGO_PASS" --authenticationDatabase admin --archive 2>"$OUT/maillayer-mongo.err" > "$OUT/maillayer-mongo.archive"
  size=$(stat -c %s "$OUT/maillayer-mongo.archive" 2>/dev/null || echo 0)
  echo "    archive: $size bytes -> $OUT/maillayer-mongo.archive"
  # List dbs and collections for visibility
  sudo docker exec "$MONGO_MAILLAYER" mongosh --quiet --username "$MONGO_USER" --password "$MONGO_PASS" --authenticationDatabase admin --eval 'db.adminCommand({listDatabases:1}).databases.forEach(d => print(d.name + " - " + d.sizeOnDisk + " bytes"))' > "$OUT/maillayer-mongo.dblist.txt" 2>&1
else
  echo "    WARNING: could not discover Mongo credentials - dump skipped"
fi

echo ""
echo "[*] Maillayer file volume"
MAILLAYER_VOLUME=$(sudo docker volume ls --format '{{.Name}}' | grep "${MAILLAYER_VOLUME_PREFIX}.*maillayer-data" | head -1)
if [ -n "$MAILLAYER_VOLUME" ]; then
  echo "    volume: $MAILLAYER_VOLUME"
  sudo tar -C "/var/lib/docker/volumes/$MAILLAYER_VOLUME/_data" -czf "$OUT/maillayer-files.tgz" . 2>"$OUT/maillayer-files.err"
  size=$(stat -c %s "$OUT/maillayer-files.tgz" 2>/dev/null || echo 0)
  echo "    tar: $size bytes -> $OUT/maillayer-files.tgz"
  echo "    contents (top level):"
  sudo tar -tzf "$OUT/maillayer-files.tgz" | head -20 | sed 's/^/      /'
else
  echo "    WARNING: maillayer-data volume not found"
fi

echo ""
echo "[*] Coolify state (for inventory comparison)"
# The migration plan reads inventory from coolify-db. Capture that DB too.
COOLIFY_DB=$(sudo docker ps --format '{{.ID}} {{.Names}}' | grep -i coolify-db | head -1 | awk '{print $1}')
if [ -n "$COOLIFY_DB" ]; then
  echo "    coolify-db container: $COOLIFY_DB"
  sudo docker exec "$COOLIFY_DB" pg_dump -U coolify -Fc coolify > "$OUT/coolify-internal.dump" 2>"$OUT/coolify-internal.err"
  size=$(stat -c %s "$OUT/coolify-internal.dump" 2>/dev/null || echo 0)
  echo "    coolify db dump: $size bytes"
  # And a plain SQL version for inventory queries
  sudo docker exec "$COOLIFY_DB" pg_dump -U coolify coolify > "$OUT/coolify-internal.sql" 2>>"$OUT/coolify-internal.err"
fi

echo ""
echo "[*] Compressing everything into a single tarball"
cd /tmp
tar czf "dbdumps-$TS.tar.gz" "dbdumps-$TS/" 2>&1
size=$(stat -c %s "dbdumps-$TS.tar.gz")
echo ""
echo "===================================================="
echo "FINAL ARTIFACT: /tmp/dbdumps-$TS.tar.gz"
echo "Size: $size bytes"
ls -la "/tmp/dbdumps-$TS.tar.gz"
echo "===================================================="
echo ""
echo "Contents:"
tar tzf "/tmp/dbdumps-$TS.tar.gz" | sed 's/^/  /'
