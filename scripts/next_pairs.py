"""Build the next batch of 2-up composites to read.

Two sheets per image halves the number of vision passes without costing
legibility, which matters when there are thousands of forms to get through.
Sheets already transcribed are skipped, so this is safe to re-run.

  python3 scripts/next_pairs.py 20      # 20 composites = 40 sheets
"""
import json, os, sys
from PIL import Image
from common import SHEETS, WORK, load_json, read_transcripts

PAIRS = os.path.join(WORK, "pairs")
H = 1560


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    inv = load_json(os.path.join(WORK, "inventory.json"))
    done = set(read_transcripts().keys())

    todo = []
    for w in sorted(inv["wards"], key=lambda x: (x["lga_code"], x["ward_code"])):
        for p in sorted(w["pus"], key=lambda x: x["pu_code"] or ""):
            if not p.get("doc_url") or p["pu_code"] in done:
                continue
            f = os.path.join(SHEETS, p["pu_code"].replace("/", "-") + ".jpg")
            if os.path.exists(f):
                todo.append((p["pu_code"], f))

    os.makedirs(PAIRS, exist_ok=True)
    for old in os.listdir(PAIRS):
        os.remove(os.path.join(PAIRS, old))

    out = []
    for i in range(0, min(len(todo), n * 2), 2):
        grp = todo[i:i + 2]
        ims = [Image.open(f) for _, f in grp]
        ims = [im.resize((int(im.width * H / im.height), H)) for im in ims]
        W = sum(im.width for im in ims)
        c = Image.new("RGB", (W, H), "white")
        x = 0
        for im in ims:
            c.paste(im, (x, 0)); x += im.width
        name = os.path.join(PAIRS, "b%02d.jpg" % (i // 2))
        c.save(name, quality=82)
        out.append({"file": name, "codes": [g[0] for g in grp]})

    json.dump(out, open(os.path.join(PAIRS, "manifest.json"), "w"), indent=1)
    print("remaining to transcribe: %d" % len(todo))
    for o in out:
        print(os.path.basename(o["file"]), " + ".join(o["codes"]))


if __name__ == "__main__":
    main()
