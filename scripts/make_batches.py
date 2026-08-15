"""Partition untranscribed sheets into disjoint per-agent batches.

Each agent gets its own directory of 2-up composites and its own output file,
so parallel readers never contend for the same image or the same line of the
transcript. Merging happens later, in merge_parts.py.

  python3 scripts/make_batches.py w1 8 20   # wave w1: 8 agents, 20 composites each

Waves are additive. A new wave never touches an earlier wave's directories,
because earlier agents may still be reading them, and it never hands out a
sheet another wave has already claimed.
"""
import json, os, sys
from PIL import Image
from common import SHEETS, WORK, load_json, read_transcripts

BATCHES = os.path.join(WORK, "batches")
PARTS = os.path.join(WORK, "parts")
H = 1560


def main():
    wave = sys.argv[1]
    n_agents = int(sys.argv[2])
    per_agent = int(sys.argv[3])

    inv = load_json(os.path.join(WORK, "inventory.json"))
    done = set(read_transcripts().keys())
    # Also skip anything already claimed by a part file, so re-running this
    # while agents are mid-flight does not hand the same sheet out twice.
    if os.path.isdir(PARTS):
        for f in os.listdir(PARTS):
            if not f.endswith(".jsonl"):
                continue
            for line in open(os.path.join(PARTS, f)):
                line = line.strip()
                if line:
                    try:
                        done.add(json.loads(line)["pu_code"])
                    except Exception:      # noqa: BLE001 - a half-written line is fine to ignore
                        pass

    # Sheets already handed to a live agent are claimed, even if that agent has
    # not written anything yet.
    for d in (os.listdir(BATCHES) if os.path.isdir(BATCHES) else []):
        mf = os.path.join(BATCHES, d, "manifest.json")
        if os.path.exists(mf):
            for pair in json.load(open(mf)):
                done.update(pair["codes"])

    todo = []
    for w in sorted(inv["wards"], key=lambda x: (x["lga_code"], x["ward_code"])):
        for p in sorted(w["pus"], key=lambda x: x["pu_code"] or ""):
            if not p.get("doc_url") or p["pu_code"] in done:
                continue
            f = os.path.join(SHEETS, p["pu_code"].replace("/", "-") + ".jpg")
            if os.path.exists(f):
                todo.append((p["pu_code"], f))

    os.makedirs(BATCHES, exist_ok=True)
    os.makedirs(PARTS, exist_ok=True)

    # Deal sheets out in contiguous runs so each agent stays within a few wards.
    # Sheets from one ward share a handwriting style and layout quirks, which
    # makes a reader working a contiguous run more consistent than one hopping
    # around the state.
    need = n_agents * per_agent * 2
    todo = todo[:need]
    chunk = (len(todo) + n_agents - 1) // n_agents
    manifest = []
    for a in range(n_agents):
        mine = todo[a * chunk:(a + 1) * chunk]
        if not mine:
            break
        d = os.path.join(BATCHES, "%s_agent%02d" % (wave, a))
        os.makedirs(d, exist_ok=True)
        pairs = []
        for i in range(0, len(mine), 2):
            grp = mine[i:i + 2]
            ims = [Image.open(f) for _, f in grp]
            ims = [im.resize((int(im.width * H / im.height), H)) for im in ims]
            W = sum(im.width for im in ims)
            c = Image.new("RGB", (W, H), "white")
            x = 0
            for im in ims:
                c.paste(im, (x, 0)); x += im.width
            name = os.path.join(d, "p%02d.jpg" % (i // 2))
            c.save(name, quality=82)
            pairs.append({"file": name, "codes": [g[0] for g in grp]})
        manifest.append({"agent": a, "dir": d, "out": os.path.join(PARTS, "%s_agent%02d.jsonl" % (wave, a)),
                         "pairs": pairs, "sheets": len(mine)})
        json.dump(pairs, open(os.path.join(d, "manifest.json"), "w"), indent=1)

    json.dump(manifest, open(os.path.join(BATCHES, "wave_%s.json" % wave), "w"), indent=1)
    print("staged %d sheets across %d agents" % (sum(m["sheets"] for m in manifest), len(manifest)))
    for m in manifest:
        first = m["pairs"][0]["codes"][0]
        last = m["pairs"][-1]["codes"][-1]
        print("  %s_agent%02d: %2d composites, %d sheets, %s .. %s"
              % (wave, m["agent"], len(m["pairs"]), m["sheets"], first, last))


if __name__ == "__main__":
    main()
