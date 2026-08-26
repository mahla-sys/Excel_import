#!/usr/bin/env bash
#
# Nightly backup for the School Data Intake Portal.
#
# Backs up:
#   1. PostgreSQL database (pg_dump, custom format)
#   2. Private Excel storage (tar.gz of the volume)
#
# Outputs are written to $BACKUP_DIR (default: /var/backups/intake),
# optionally GPG-encrypted if $BACKUP_PASSPHRASE_FILE is set to a file
# containing the passphrase. Encryption is strongly recommended for any
# backup that leaves the server.
#
# Retention: files older than $RETENTION_DAYS (default 7) are deleted.
#
# Intended to be run from cron on the Docker host, e.g.:
#   0 3 * * * /opt/intake-portal/backend/scripts/backup.sh >> /var/log/intake-backup.log 2>&1

set -euo pipefail

COMPOSE_CMD="${COMPOSE_CMD:-docker compose -f docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/intake}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
POSTGRES_DB="${POSTGRES_DB:-intake}"
POSTGRES_USER="${POSTGRES_USER:-intake}"
PRIVATE_VOLUME="${PRIVATE_VOLUME:-school-intake-portal_private_files}"
TIMESTAMP="$(date +%Y-%m-%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"

echo "[$(date -Iseconds)] starting backup (db=$POSTGRES_DB, volume=$PRIVATE_VOLUME)"

# --- 1. PostgreSQL dump -----------------------------------------------------
DUMP_FILE="$BACKUP_DIR/db-$TIMESTAMP.dump"
$COMPOSE_CMD exec -T db pg_dump \
    -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$DUMP_FILE"
echo "  wrote $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"

# --- 2. Private storage archive --------------------------------------------
FILES_FILE="$BACKUP_DIR/files-$TIMESTAMP.tar.gz"
# Run tar inside a throwaway container mounting the same volume.
docker run --rm \
    -v "$PRIVATE_VOLUME":/data:ro \
    -v "$BACKUP_DIR":/backup \
    alpine tar czf "/backup/$(basename "$FILES_FILE")" -C /data .
echo "  wrote $FILES_FILE ($(du -h "$FILES_FILE" | cut -f1))"

# --- 3. Optional encryption -------------------------------------------------
if [ -n "${BACKUP_PASSPHRASE_FILE:-}" ] && [ -f "$BACKUP_PASSPHRASE_FILE" ]; then
    echo "  encrypting backups with GPG..."
    gpg --batch --yes --symmetric --cipher-algo AES256 \
        --passphrase-file "$BACKUP_PASSPHRASE_FILE" "$DUMP_FILE"
    rm -f "$DUMP_FILE"
    gpg --batch --yes --symmetric --cipher-algo AES256 \
        --passphrase-file "$BACKUP_PASSPHRASE_FILE" "$FILES_FILE"
    rm -f "$FILES_FILE"
fi

# --- 4. Retention -----------------------------------------------------------
find "$BACKUP_DIR" -type f -mtime "+$RETENTION_DAYS" -delete
echo "[$(date -Iseconds)] backup complete; retaining $RETENTION_DAYS days"
