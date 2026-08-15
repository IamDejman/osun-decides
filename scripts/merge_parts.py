"""Fold per-agent transcript parts into the single append-only transcript.

Validation runs here, centrally, rather than trusting each reader's own
verdict: the transcript is the thing the site is built from, so the checks
that gate it should be applied in one place by one implementation.
"""
import json, os, sys
from common import WORK, PARTIES, validate, read_transcripts

PARTS = os.path.join(WORK, "parts")
OUT = os.path.join(WORK, "extract.jsonl")


def main():
    have = set(read_transcripts().keys())
    added = held = skipped = bad = 0
    with open(OUT, "a") as out:
        for f in sorted(os.listdir(PARTS)) if os.path.isdir(PARTS) else []:
            if not f.endswith(".jsonl"):
                continue
            for line in open(os.path.join(PARTS, f)):
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    bad += 1
                    continue
                code = r.get("pu_code")
                if not code or not isinstance(r.get("votes"), dict):
                    bad += 1
                    continue
                if code in have:
                    skipped += 1
                    continue
                r["votes"] = {p: int(r["votes"].get(p) or 0) for p in PARTIES}
                r["sum_parties"] = sum(r["votes"].values())
                reasons, ok = validate(r)
                r["checks_ok"] = ok
                r["reasons"] = reasons
                r["source"] = f
                out.write(json.dumps(r) + "\n")
                have.add(code)
                added += 1
                if not ok:
                    held += 1
    print("merged %d new (%d held for review), %d duplicates skipped, %d unusable"
          % (added, held, skipped, bad))


if __name__ == "__main__":
    main()
