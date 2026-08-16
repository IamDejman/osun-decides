"""Every-minute poller.

Keeps the local inventory of polling units and uploaded result sheets in step
with the IReV portal, and pulls down any newly uploaded sheet image so it is
ready to transcribe. It deliberately does NOT invent vote figures: a sheet it
has just fetched is recorded as awaiting transcription until a reader has
actually read it.

  python3 scripts/poll.py           # sweep all 332 wards, fetch new images
"""
import json, os, subprocess, sys, time, urllib.request
import concurrent.futures as cf
from common import (API, SHEETS, WORK, get, save_json)

INV = os.path.join(WORK, "inventory.json")

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
    stats = get(API + "/result/stats")["data"]
    remote_docs = stats.get("documents")

    # Always walk every ward. /pus/recent is not a tail of new uploads: it
    # has sat on sheets from 15 minutes ago while /result/stats and the
    # public page had already moved on. A full sweep is ~40s and is the
    # only pass that cannot miss a sheet.
    print("full sweep of all wards (portal %s)..." % remote_docs)
    inv = {"wards": fetch_structure()}
    # /pus?ward= lags /result/stats. Overlay the recent feed so a sheet
    # that stats already counted is not invisible for the next ten minutes.
    by_code = {}
    for w in inv["wards"]:
        for p in w["pus"]:
            by_code[p["pu_code"]] = p
    patched = 0
    for r in (get(API + "/pus/recent")["data"] or []):
        doc = r.get("document") or {}
        p = by_code.get(r.get("pu_code"))
        if p is None or not doc.get("url"):
            continue
        if p.get("doc_url") != doc["url"]:
            p["doc_url"] = doc["url"]
            p["doc_time"] = doc.get("updated_at")
            patched += 1
    latest = (stats.get("latest") or {}).get("document") or {}
    lp = by_code.get((stats.get("latest") or {}).get("pu_code"))
    if lp is not None and latest.get("url") and lp.get("doc_url") != latest["url"]:
        lp["doc_url"] = latest["url"]
        lp["doc_time"] = latest.get("updated_at")
        patched += 1
    if patched:
        print("patched %d unit(s) from recent/latest that the ward listing omitted" % patched)
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
