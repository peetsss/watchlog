#!/usr/bin/env bash
set -euo pipefail
umask 077

: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"

postgres_host="${POSTGRES_HOST:-127.0.0.1}"
postgres_port="${POSTGRES_PORT:-5432}"
backup_dir="${WATCHLOG_BACKUP_DIR:-./backups}"
retention_days="${WATCHLOG_BACKUP_RETENTION_DAYS:-14}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="${backup_dir}/${POSTGRES_DB}-${timestamp}.dump"

install -d -m 700 "${backup_dir}"

if [[ "${WATCHLOG_BACKUP_VIA_DOCKER:-0}" == "1" ]]; then
    docker compose exec -T database pg_dump \
        --username="${POSTGRES_USER}" \
        --dbname="${POSTGRES_DB}" \
        --format=custom \
        --no-owner > "${backup_file}"
else
    PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
        --host="${postgres_host}" \
        --port="${postgres_port}" \
        --username="${POSTGRES_USER}" \
        --dbname="${POSTGRES_DB}" \
        --format=custom \
        --no-owner \
        --file="${backup_file}"
fi

chmod 600 "${backup_file}"

find "${backup_dir}" -type f -name "${POSTGRES_DB}-*.dump" -mtime +"${retention_days}" -delete

if [[ -n "${WATCHLOG_BACKUP_REMOTE:-}" ]]; then
    if ! command -v rclone >/dev/null 2>&1; then
        echo "rclone is required when WATCHLOG_BACKUP_REMOTE is set" >&2
        exit 1
    fi
    rclone copy "${backup_file}" "${WATCHLOG_BACKUP_REMOTE}"
fi

echo "wrote ${backup_file}"
