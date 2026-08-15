#!/bin/sh
# Wrapper for the launchd agent: run one poll and append to the log.
# Kept deliberately dumb so a failure never wedges the schedule.
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR" || exit 1
mkdir -p work
{
  echo "--- $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  /usr/bin/python3 scripts/poll.py 2>&1
} >> work/poll.log
# Keep the log from growing without bound.
tail -n 2000 work/poll.log > work/poll.log.tmp && mv work/poll.log.tmp work/poll.log
