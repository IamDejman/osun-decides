#!/bin/sh
# Merge whatever the readers have produced and commit the rebuilt data.
#
# Only data/ is committed: work/ is operator state (sheet images, raw parts,
# the review queue) and is gitignored. If nothing changed, this exits without
# making an empty commit, so a quiet five minutes leaves no trace in history.
#
#   BRANCH=live-data scripts/publish.sh      # commit to a branch (default)
#   BRANCH=main PUSH=1 scripts/publish.sh    # commit and push
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DIR"

BRANCH="${BRANCH:-live-data}"
PUSH="${PUSH:-0}"

python3 scripts/merge_parts.py
python3 scripts/build_site_data.py

CURRENT="$(git rev-parse --abbrev-ref HEAD)"
if [ "$CURRENT" != "$BRANCH" ]; then
  git show-ref --verify --quiet "refs/heads/$BRANCH" \
    && git checkout "$BRANCH" \
    || git checkout -b "$BRANCH"
fi

git add data
if git diff --cached --quiet; then
  echo "no data change, nothing to commit"
  exit 0
fi

COUNTED=$(python3 -c "import json;t=json.load(open('data/results.json'))['meta']['totals'];print(t['pu_transcribed'])")
TOTAL=$(python3 -c "import json;t=json.load(open('data/results.json'))['meta']['totals'];print(t['pu_total'])")
git commit -q -m "data: $COUNTED of $TOTAL polling units counted"
echo "committed on $BRANCH: $COUNTED/$TOTAL counted"

if [ "$PUSH" = "1" ]; then
  git push -q origin "$BRANCH"
  echo "pushed to origin/$BRANCH"
fi
