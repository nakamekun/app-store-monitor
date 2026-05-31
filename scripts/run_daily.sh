#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${APP_DIR}"

mkdir -p logs reports data

RUN_DATE="$(date +%F)"
LOG_PATH="logs/daily_${RUN_DATE}.log"

exec >> "${LOG_PATH}" 2>&1

echo "== app-store-monitor daily start: $(date '+%Y-%m-%d %H:%M:%S') =="
echo "working_directory=${APP_DIR}"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  . ".env"
  set +a
  echo ".env loaded"
else
  echo "warning: .env not found"
fi

if [ -n "${PYTHON:-}" ]; then
  PYTHON_BIN="${PYTHON}"
elif uname -s 2>/dev/null | grep -Eq '^(MINGW|MSYS|CYGWIN)' \
  && command -v python >/dev/null 2>&1 \
  && python -c 'import sys' >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1 && python3 -c 'import sys' >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1 && python -c 'import sys' >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  PYTHON_BIN="python3"
fi
echo "python_bin=${PYTHON_BIN}"

echo "date_strategy=latest_fetchable_daily_segment"

echo "-- check-config --"
"${PYTHON_BIN}" -m src.cli check-config
CHECK_STATUS=$?
if [ "${CHECK_STATUS}" -ne 0 ]; then
  echo "check-config failed with status ${CHECK_STATUS}; continuing for log visibility"
fi

echo "-- sync-apps --"
"${PYTHON_BIN}" -m src.cli sync-apps
SYNC_STATUS=$?
if [ "${SYNC_STATUS}" -ne 0 ]; then
  echo "sync-apps failed with status ${SYNC_STATUS}; continuing"
fi

echo "-- create-report-request --"
"${PYTHON_BIN}" -m src.cli create-report-request --all
REQUEST_STATUS=$?
if [ "${REQUEST_STATUS}" -ne 0 ]; then
  echo "create-report-request failed with status ${REQUEST_STATUS}; continuing"
fi

echo "-- fetch --"
"${PYTHON_BIN}" -m src.cli fetch --latest --all
FETCH_STATUS=$?
if [ "${FETCH_STATUS}" -ne 0 ]; then
  echo "fetch failed with status ${FETCH_STATUS}; continuing to report"
fi

echo "-- report --"
REPORT_ARGS=(report --latest --print)
if [ "${DISCORD_ENABLED:-false}" = "true" ]; then
  REPORT_ARGS+=(--notify)
  REPORT_ARGS+=(--notify-once)
  echo "discord notification enabled with once-per-metric-date guard"
else
  echo "discord notification disabled"
fi

"${PYTHON_BIN}" -m src.cli "${REPORT_ARGS[@]}"
REPORT_STATUS=$?
if [ "${REPORT_STATUS}" -ne 0 ]; then
  echo "report failed with status ${REPORT_STATUS}"
fi

echo "== app-store-monitor daily end: $(date '+%Y-%m-%d %H:%M:%S') =="

# Keep launchd green while fetch/report availability stabilizes. Failures are logged above.
exit 0
