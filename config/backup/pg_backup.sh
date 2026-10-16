#!/usr/bin/env bash
# Daily logical Postgres backup to Backblaze B2 — canonical, app-agnostic (fleet decision 2026-10-14).
#
# Subcommands:
#   run                 (default) loop every 60s; once per local day at/after BACKUP_HOUR_LOCAL do a backup
#   now                 run one backup immediately into predeploy/, exit 0/1 (manual + "backup before deploy")
#   healthcheck         exit 1 if the last success is older than 26h (container-start grace, see below)
#   select-expired N    stdin: names, one per line -> stdout: what retention deletes (testable)
#
# Env (everything app-specific comes from compose):
#   BACKUP_APP            app slug, prefix of the object names           (required)
#   B2_PRIVATE_BUCKET     the app's private bucket                       (required unless BACKUP_DRY_RUN=1)
#   B2_PRIVATE_KEY_ID     keyID of the app's private key                 (required unless BACKUP_DRY_RUN=1)
#   B2_PRIVATE_APP_KEY    its secret (from .env)                         (required unless BACKUP_DRY_RUN=1)
#   POSTGRES_PASSWORD     DB password (from .env); POSTGRES_USER / POSTGRES_DB select role / database
#   PGHOST                default /var/run/postgresql (direct socket; NEVER pgbouncer: pg_dump needs a
#                         real session and long transactions would pin a pooled server connection)
#   BACKUP_HOUR_LOCAL     default 3 (apps are idle 22h-06h)
#   BACKUP_DRY_RUN=1      dump + validate, skip every B2 call
#   BACKUP_DIR            default /backup (volume: dump temp file + state)
#
# Retention (user decisions 2026-10-14): 7 days + 4 weekly, logical dump until it no longer fits the
# night window. Started as "1 daily + 4 weekly"; the user widened it the same day so a corruption noticed
# days later can still be restored from the day before it (not only from last Sunday).
# Layout at the bucket ROOT, outside prod/ and staging/:
#   backups/postgres/daily/<app>-<YYYY-MM-DDTHHMM>.dump       scheduled run, 1 per day, 7 most recent days
#   backups/postgres/weekly/<app>-<YYYY-MM-DD>.dump           Sunday copy, 4 most recent
#   backups/postgres/predeploy/<app>-<YYYY-MM-DDTHHMM>.dump   `now` (before a deploy), ONLY the newest one
# Pre-deploy dumps live apart (user decision 2026-10-16): they used to land in daily/, and a day with 9
# deploys kept 9 files. A new deploy makes the previous pre-deploy dump useless, so only the last is kept.
set -euo pipefail

TZ="${TZ:-America/Sao_Paulo}"
export TZ
BACKUP_DIR="${BACKUP_DIR:-/backup}"
BACKUP_HOUR_LOCAL="${BACKUP_HOUR_LOCAL:-3}"
BACKUP_DRY_RUN="${BACKUP_DRY_RUN:-0}"
TICK_SECONDS=60
RETRY_BACKOFF_SECONDS=900
HEALTHY_MAX_AGE_SECONDS=$((26 * 3600))
DAILY_PREFIX="backups/postgres/daily"
WEEKLY_PREFIX="backups/postgres/weekly"
PREDEPLOY_PREFIX="backups/postgres/predeploy"
KEEP_DAILY=7
KEEP_WEEKLY=4
KEEP_PREDEPLOY=1
STATE_DIR="$BACKUP_DIR/state"
DUMP_DIR="$BACKUP_DIR/dump"
# tmpfs (container fs is read-only): reset on every container start, so it doubles as "started at" marker.
STARTED_FILE="${STARTED_FILE:-/tmp/pg_backup.started}"
HEARTBEAT_FILE="$STATE_DIR/last_success_epoch"
LAST_DATE_FILE="$STATE_DIR/last_success_date"

# One JSON line per step. jq builds the JSON so file names / messages are always escaped correctly.
log_step() { # event status [file] [bytes] [seconds] [message]
  jq -nc --arg event "$1" --arg status "$2" --arg app "${BACKUP_APP:-}" --arg file "${3:-}" \
    --argjson bytes "${4:-0}" --argjson seconds "${5:-0}" --arg message "${6:-}" \
    '{ts: (now | todate), event: $event, app: $app, file: $file, bytes: $bytes, seconds: $seconds, status: $status}
     + (if $message != "" then {message: $message} else {} end)'
}

# Keep the NEWEST name of each of the N most recent distinct days (names embed an ISO timestamp, so they
# sort chronologically), print the rest. One survivor per day also sweeps the pre-deploy dumps that
# landed in daily/ before 2026-10-16; for predeploy/ with N=1 it keeps exactly the last file.
select_expired() {
  local keep="$1"
  [[ "$keep" =~ ^[0-9]+$ ]] || { echo "select-expired: N must be a non-negative integer, received '$keep'" >&2; return 2; }
  # Interval-free regex on purpose: the image's awk is mawk, which may not support {4}.
  grep -v '^[[:space:]]*$' | sort -u | sort -r | awk -v keep="$keep" '
    {
      day = $0
      if (match($0, /[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]/)) day = substr($0, RSTART, RLENGTH)
      if (day in seen) { print; next }
      seen[day] = 1; days++
      if (days > keep) print
    }' || true
}

require_env() {
  local missing=() name
  for name in "$@"; do [[ -n "${!name:-}" ]] || missing+=("$name"); done
  if ((${#missing[@]})); then
    echo "missing required env: ${missing[*]}" >&2
    exit 2
  fi
}

b2_setup() {
  # The CLI reads these two names; compose/.env use the repo's own naming.
  export B2_APPLICATION_KEY_ID="$B2_PRIVATE_KEY_ID"
  export B2_APPLICATION_KEY="$B2_PRIVATE_APP_KEY"
  # Read-only rootfs: keep the CLI's sqlite account cache on the volume.
  export B2_ACCOUNT_INFO="$BACKUP_DIR/b2_account_info"
}

b2_upload() { # local_path object_key
  b2 file upload --no-progress "$B2_PRIVATE_BUCKET" "$1" "$2" >/dev/null
}

# Verify the object landed with the exact local size (the CLI already checks sha1 during upload).
b2_confirm_size() { # object_key expected_bytes
  local remote
  remote=$(b2 file info "b2://$B2_PRIVATE_BUCKET/$1" | jq -r '.size')
  [[ "$remote" == "$2" ]] || { echo "size mismatch for $1: remote=$remote local=$2" >&2; return 1; }
}

# Parts of interrupted large uploads are billed until cancelled. This job is the only writer under
# backups/ and runs serially, so at the start of a run anything unfinished there is a leftover from a
# crashed run (older than 1 day or not — it is dead either way; the CLI listing has no timestamp).
b2_cancel_stale_unfinished() {
  local file_id file_name
  b2 file large unfinished list "b2://$B2_PRIVATE_BUCKET" | while read -r file_id file_name _; do
    [[ "$file_name" == backups/* ]] || continue
    b2 file large unfinished cancel "b2id://$file_id" >/dev/null
    log_step cancel_unfinished ok "$file_name"
  done
}

# Bucket is versioned: `rm --versions` removes EVERY version (and hide markers) of the expired name,
# otherwise the "deleted" dump would stay stored and billed.
retain_prefix() { # prefix keep_count newest_name
  local prefix="$1" keep="$2" newest="$3" names expired name
  names=$(b2 ls --json --versions -r "b2://$B2_PRIVATE_BUCKET/$prefix/" | jq -r '.[].fileName' \
    | grep -E "^${prefix}/${BACKUP_APP}-.*\.dump\$" || true)
  # Never delete anything unless the file we just uploaded is visible in the listing.
  if ! grep -qxF "$newest" <<<"$names"; then
    echo "retention aborted: new object $newest not found in listing of $prefix/" >&2
    return 1
  fi
  expired=$(select_expired "$keep" <<<"$names")
  while IFS= read -r name; do
    [[ -n "$name" ]] || continue
    b2 rm --versions -r --with-wildcard --no-progress "b2://$B2_PRIVATE_BUCKET/$name" >/dev/null
    log_step retention_delete ok "$name"
  done <<<"$expired"
}

do_backup() { # kind: scheduled | predeploy
  local kind="$1" started stamp day dump_file daily_key weekly_key bytes t0
  started=$(date +%s)
  stamp=$(date +%Y-%m-%dT%H%M)
  day=$(date +%F)
  mkdir -p "$STATE_DIR" "$DUMP_DIR"
  dump_file="$DUMP_DIR/$BACKUP_APP-$stamp.$$.dump"
  # The RETURN trap is global once set: it must reset itself, or it fires again when main() returns,
  # outside this function, where $dump_file is unbound (set -u) → exit 1 after a successful "done"
  # (found on the first real run, 2026-10-14; the dry run never hit it because it clears the trap).
  trap 'rm -f "$dump_file"; trap - RETURN' RETURN

  t0=$(date +%s)
  PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_dump -Fc --compress=zstd \
    -h "${PGHOST:-/var/run/postgresql}" -U "${POSTGRES_USER:?}" -d "${POSTGRES_DB:?}" -f "$dump_file"
  bytes=$(stat -c %s "$dump_file")
  log_step dump ok "$(basename "$dump_file")" "$bytes" "$(($(date +%s) - t0))"

  t0=$(date +%s)
  pg_restore --list "$dump_file" >/dev/null
  log_step validate ok "$(basename "$dump_file")" "$bytes" "$(($(date +%s) - t0))"

  if [[ "$BACKUP_DRY_RUN" == "1" ]]; then
    log_step dry_run ok "$(basename "$dump_file")" "$bytes" "$(($(date +%s) - started))" "B2 skipped"
    # Dry run keeps the dump so it can be restore-tested; opt out of the RETURN cleanup.
    trap - RETURN
    return 0
  fi

  b2_setup
  b2_cancel_stale_unfinished

  if [[ "$kind" == "predeploy" ]]; then
    upload_predeploy "$dump_file" "$stamp" "$bytes"
    log_step "done" ok "$PREDEPLOY_PREFIX/$BACKUP_APP-$stamp.dump" "$bytes" "$(($(date +%s) - started))"
    return 0
  fi

  daily_key="$DAILY_PREFIX/$BACKUP_APP-$stamp.dump"
  t0=$(date +%s)
  b2_upload "$dump_file" "$daily_key"
  b2_confirm_size "$daily_key" "$bytes"
  log_step upload_daily ok "$daily_key" "$bytes" "$(($(date +%s) - t0))"

  if [[ "$(date +%u)" == "7" ]]; then
    weekly_key="$WEEKLY_PREFIX/$BACKUP_APP-$day.dump"
    t0=$(date +%s)
    b2_upload "$dump_file" "$weekly_key"
    b2_confirm_size "$weekly_key" "$bytes"
    log_step upload_weekly ok "$weekly_key" "$bytes" "$(($(date +%s) - t0))"
    retain_prefix "$WEEKLY_PREFIX" "$KEEP_WEEKLY" "$weekly_key"
  fi
  # Daily retention only after the new object is uploaded AND confirmed: never ends up with zero backups.
  retain_prefix "$DAILY_PREFIX" "$KEEP_DAILY" "$daily_key"

  date +%s >"$HEARTBEAT_FILE"
  echo "$day" >"$LAST_DATE_FILE"
  log_step "done" ok "$daily_key" "$bytes" "$(($(date +%s) - started))"
}

# Pre-deploy dump: no heartbeat / last-date update on purpose — it must not stand in for the scheduled
# 03:00 run (a deploy at 02:00 would otherwise skip that day's daily/ copy).
upload_predeploy() { # dump_file stamp bytes
  local key="$PREDEPLOY_PREFIX/$BACKUP_APP-$2.dump" t0
  t0=$(date +%s)
  b2_upload "$1" "$key"
  b2_confirm_size "$key" "$3"
  log_step upload_predeploy ok "$key" "$3" "$(($(date +%s) - t0))"
  retain_prefix "$PREDEPLOY_PREFIX" "$KEEP_PREDEPLOY" "$key"
}

# do_backup runs in a child process: bash ignores `set -e` inside anything on the left of `||`, so a
# subshell would silently continue past a failed step (and then delete things). The child keeps errexit.
run_once() { # kind
  local rc=0
  "$0" __backup "$1" || rc=$?
  if ((rc != 0)); then
    log_step failed error "" 0 0 "backup failed (exit $rc); B2 retention not applied past the failing step"
  fi
  return "$rc"
}

is_due() {
  local hour today last=""
  hour=$((10#$(date +%H)))
  today=$(date +%F)
  [[ -f "$LAST_DATE_FILE" ]] && last=$(<"$LAST_DATE_FILE")
  # `>=` (not `==`): a restart after 03:00 still catches up the missed day.
  ((hour >= 10#$BACKUP_HOUR_LOCAL)) && [[ "$last" != "$today" ]]
}

run_loop() {
  local next_attempt=0
  mkdir -p "$STATE_DIR"
  date +%s >"$STARTED_FILE"
  log_step start ok "" 0 0 "hour=$BACKUP_HOUR_LOCAL tz=$TZ dry_run=$BACKUP_DRY_RUN"
  while true; do
    if is_due && (($(date +%s) >= next_attempt)); then
      if ! run_once scheduled; then next_attempt=$(($(date +%s) + RETRY_BACKOFF_SECONDS)); fi
      # Dry-run never records a success date; avoid re-dumping every tick.
      if [[ "$BACKUP_DRY_RUN" == "1" ]]; then date +%F >"$LAST_DATE_FILE"; fi
    fi
    sleep "$TICK_SECONDS"
  done
}

# Healthy if the last success is < 26h old. Missing/old heartbeat is tolerated for the first 26h after
# the container started (fresh deploy, or host back from downtime, has not had its 03:00 yet).
check_health() {
  local now last started
  now=$(date +%s)
  last=0; [[ -f "$HEARTBEAT_FILE" ]] && last=$(<"$HEARTBEAT_FILE")
  ((now - last < HEALTHY_MAX_AGE_SECONDS)) && return 0
  started=$now; [[ -f "$STARTED_FILE" ]] && started=$(<"$STARTED_FILE")
  ((now - started < HEALTHY_MAX_AGE_SECONDS)) && return 0
  echo "unhealthy: last success epoch=$last, container started epoch=$started" >&2
  return 1
}

main() {
  local cmd="${1:-run}"
  case "$cmd" in
    select-expired) select_expired "${2:?usage: select-expired N}" ;;
    healthcheck) check_health ;;
    __backup) require_env BACKUP_APP POSTGRES_USER POSTGRES_DB; do_backup "${2:?usage: __backup scheduled|predeploy}" ;;
    run | now)
      require_env BACKUP_APP POSTGRES_USER POSTGRES_DB
      [[ "$BACKUP_DRY_RUN" == "1" ]] || require_env B2_PRIVATE_BUCKET B2_PRIVATE_KEY_ID B2_PRIVATE_APP_KEY
      if [[ "$cmd" == "now" ]]; then run_once predeploy; else run_loop; fi
      ;;
    *) echo "unknown command '$cmd' (run | now | healthcheck | select-expired N)" >&2; exit 2 ;;
  esac
}

main "$@"
