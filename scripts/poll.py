"""Every-minute poller.

Keeps the local inventory of polling units and uploaded result sheets in step
with the IReV portal, and pulls down any newly uploaded sheet image so it is
ready to transcribe. It deliberately does NOT invent vote figures: a sheet it
has just fetched is recorded as awaiting transcription until a reader has
actually read it.

  python3 scripts/poll.py           # fast pass: stats + 100 most recent uploads
  python3 scripts/poll.py --full    # full sweep of all 332 wards
"""
import json, os, subprocess, sys, time, urllib.request
import concurrent.futures as cf
from common import (API, DATA, SHEETS, WORK, get, load_json, save_json)

INV = os.path.join(WORK, "inventory.json")

# A full sweep costs ~40s over 332 wards, so it is not a per-minute operation,
# but it is the only pass that cannot miss a sheet. Force one at least this
# often even when the counts happen to agree.
FULL_SWEEP_EVERY = 600  # seconds


def fetch_structure():
    """LGA -> wards -> polling units, with whatever document each PU has."""
    lgas = get(API + "/lga")["data"]
    tasks = []
    for e in lgas:
        for w in e.get("wards", []):
            tasks.append((e["lga"], w))

    def one(t):
        lga, w = t
        pus = get(API + "/pus?ward=" + w["_id"])["data"] or []
        return {
            "lga_code": lga["code"], "lga_name": lga["name"],
            "ward_code": w["code"], "ward_name": w["name"].strip(),
            "pus": [{
                "pu_code": p.get("pu_code"),
                "pu_name": (p.get("name") or "").strip(),
                "doc_url": (p.get("document") or {}).get("url"),
                "doc_time": (p.get("document") or {}).get("updated_at"),
            } for p in pus],
        }

    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        return list(ex.map(one, tasks))


def download(code, url):
    """Fetch one sheet and downscale it for reading. Returns True if stored."""
    dest = os.path.join(SHEETS, code.replace("/", "-") + ".jpg")
    if os.path.exists(dest):
        return False
    tmp = dest + ".tmp"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "osun-results/1.0"})
        with urllib.request.urlopen(req, timeout=90) as r, open(tmp, "wb") as f:
            f.write(r.read())
    except Exception as e:      # noqa: BLE001 - a failed fetch is retried next minute
        print("  download failed %s: %s" % (code, e))
        if os.path.exists(tmp):
            os.remove(tmp)
        return False
    subprocess.run(["sips", "-Z", "1500", "-s", "formatOptions", "68", tmp, "--out", dest],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(tmp)
    return True


def main():
    full = "--full" in sys.argv
    inv = load_json(INV, default=None)
    if inv is None:
        full = True     # nothing cached yet, so a full sweep is the only option

    stats = get(API + "/result/stats")["data"]
    remote_docs = stats.get("documents")

    # The recent feed is not a reliable tail of everything published: observed
    # in practice reporting nothing new while the portal's own document count
    # had moved by 63. So never trust it alone. Sweep everything whenever the
    # inventory disagrees with the portal at all, or when the last full sweep
    # has aged out.
    if not full and inv is not None:
        local = sum(1 for w in inv["wards"] for p in w["pus"] if p.get("doc_url"))
        age = time.time() - inv.get("full_swept_ts", 0)
        if remote_docs and remote_docs != local:
            print("inventory %d, portal %s: sweeping everything" % (local, remote_docs))
            full = True
        elif age > FULL_SWEEP_EVERY:
            print("last full sweep %d min ago, sweeping everything" % (age / 60))
            full = True

    if full:
        print("full sweep of all wards...")
        inv = {"wards": fetch_structure()}
    else:
        # Cheap path: the 100 most recently uploaded sheets. At observed upload
        # rates that is far more headroom than one minute needs.
        recent = get(API + "/pus/recent")["data"] or []
        by_code = {}
        for w in inv["wards"]:
            for p in w["pus"]:
                by_code[p["pu_code"]] = p
        changed = 0
        for r in recent:
            doc = r.get("document") or {}
            p = by_code.get(r.get("pu_code"))
            if p is None or not doc.get("url"):
                continue
            if p.get("doc_url") != doc["url"]:
                p["doc_url"] = doc["url"]
                p["doc_time"] = doc.get("updated_at")
                changed += 1
        print("recent pass: %d sheet(s) new or replaced" % changed)

    if full:
        inv["full_swept_ts"] = time.time()
    inv["polled_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    inv["remote_documents"] = remote_docs
    save_json(INV, inv)

    # Pull down any sheet image we do not have yet.
    todo = [(p["pu_code"], p["doc_url"]) for w in inv["wards"] for p in w["pus"]
            if p.get("doc_url") and not os.path.exists(
                os.path.join(SHEETS, p["pu_code"].replace("/", "-") + ".jpg"))]
    got = 0
    if todo:
        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            got = sum(ex.map(lambda t: download(*t), todo))
    local_docs = sum(1 for w in inv["wards"] for p in w["pus"] if p.get("doc_url"))
    print("uploads: portal %s, inventory %s, images fetched this run %d"
          % (remote_docs, local_docs, got))

    # Regenerate what the website serves.
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "build_site_data.py")], check=True)


if __name__ == "__main__":
    main()
