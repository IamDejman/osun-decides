"""Stage held units for an independent second reading.

A held unit is one whose first reading failed a check that bears on the votes.
There are only two explanations: the reader misread a digit, or the sheet
genuinely does not add up. Re-reading resolves which, and it has to be an
INDEPENDENT read - the second reader is given the sheet and the nature of the
problem, never the first reader's figures, so it cannot anchor on them.

  python3 scripts/stage_review.py 12    # 12 reviewers
"""
import json, os, sys
from PIL import Image
from common import SHEETS, WORK, read_transcripts, validate

BATCH = os.path.join(WORK, "review-batches")
H = 1560


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    rows = read_transcripts()

    held = []
    for code, r in sorted(rows.items()):
        reasons, ok = validate(r)
        if ok:
            continue
        f = os.path.join(SHEETS, code.replace("/", "-") + ".jpg")
        if os.path.exists(f):
            held.append((code, f, reasons[0]))

    os.makedirs(BATCH, exist_ok=True)
    chunk = (len(held) + n - 1) // n
    made = 0
    for a in range(n):
        mine = held[a * chunk:(a + 1) * chunk]
        if not mine:
            break
        d = os.path.join(BATCH, "rv_agent%02d" % a)
        os.makedirs(d, exist_ok=True)
        entries = []
        for i in range(0, len(mine), 2):
            grp = mine[i:i + 2]
            ims = [Image.open(f) for _, f, _ in grp]
            ims = [im.resize((int(im.width * H / im.height), H)) for im in ims]
            c = Image.new("RGB", (sum(im.width for im in ims), H), "white")
            x = 0
            for im in ims:
                c.paste(im, (x, 0)); x += im.width
            name = os.path.join(d, "p%02d.jpg" % (i // 2))
            c.save(name, quality=82)
            entries.append({
                "file": name,
                "codes": [g[0] for g in grp],
                # The problem, not the previous figures. Naming the check that
                # failed tells the reader where to look twice; naming the old
                # numbers would just invite agreement with them.
                "known_problem": [g[2] for g in grp],
            })
        json.dump(entries, open(os.path.join(d, "manifest.json"), "w"), indent=1)
        made += 1
        print("  rv_agent%02d: %d composites, %d sheets" % (a, len(entries), len(mine)))

    print("staged %d held units across %d reviewers" % (len(held), made))


if __name__ == "__main__":
    main()
