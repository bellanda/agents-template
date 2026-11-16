#!/usr/bin/env bash
# Restarts containers Docker reports as "unhealthy" (audit 2026-11-13 core-performance-04).
# Why: Docker Compose `restart: always` only reacts to the process EXITING; a container whose
# healthcheck fails stays up forever, so a deadlocked backend meant 504s until somebody noticed.
# Runs from docker-autoheal.timer (every minute) as root on the VPS. One install per host: it covers
# every compose project on it. Safety valves: a container is restarted at most once per 5 minutes
# (a crash loop must not become a restart storm) and pg-backup / cloudflared are skipped (their
# "unhealthy" means "backup is stale" / "tunnel down", which a restart does not fix).
set -euo pipefail

COOLDOWN_SECONDS=300
STATE_DIR=/run/docker-autoheal
mkdir -p "${STATE_DIR}"

docker ps --filter health=unhealthy --format '{{.Names}}' | while read -r name; do
    [[ -n "${name}" ]] || continue
    case "${name}" in *-pg-backup | *-cloudflared) continue ;; esac
    stamp="${STATE_DIR}/${name}"
    now=$(date +%s)
    if [[ -f "${stamp}" ]] && (( now - $(cat "${stamp}") < COOLDOWN_SECONDS )); then
        continue
    fi
    echo "${now}" > "${stamp}"
    logger -t docker-autoheal "restarting unhealthy container ${name}"
    docker restart "${name}" > /dev/null
done
