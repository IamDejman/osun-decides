#!/bin/sh
# Wrapper for the launchd agent: run one poll and append to the log.
# Kept deliberately dumb so a failure never wedges the schedule.
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR" || exit 1
mkdir -p work
if [ -f "$DIR/work/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$DIR/work/.env"
  set +a
fi
{
  echo "--- $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  /usr/bin/python3 scripts/poll.py 2>&1
} >> work/poll.log
READ_OUT="$(/usr/bin/python3 scripts/transcribe_unread.py 2>&1)" || true
printf '%s\n' "$READ_OUT" >> work/poll.log
# Keep the log from growing without bound.
tail -n 2000 work/poll.log > work/poll.log.tmp && mv work/poll.log.tmp work/poll.log
# If the reader wrote anything this run, fold it in and push.
case "$READ_OUT" in
  *"transcribe: wrote "[1-9]*)
    BRANCH=main PUSH=1 /bin/sh "$DIR/scripts/publish.sh" >> work/publish.log 2>&1 || true
    ;;
esac
