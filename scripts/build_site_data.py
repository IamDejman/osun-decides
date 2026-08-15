"""Compose the JSON the website reads from the inventory + transcripts.

Every published figure here comes from a sheet somebody actually read. Units
that are uploaded but not yet transcribed are counted as coverage, never as
votes, so partial transcription can never look like a complete result.
"""
import os, time
from common import (DATA, PARTIES, PORTAL, WORK, load_json, read_transcripts,
                    save_json, validate)

INV = os.path.join(WORK, "inventory.json")


def blank():
    return {p: 0 for p in PARTIES}


def add(into, votes):
    for p, n in votes.items():
        if p in into:
            into[p] += n


def rollup(units):
    """Aggregate only over units whose sheet has been transcribed and passes checks."""
    t = {"votes": blank(), "registered": 0, "accredited": 0, "valid": 0,
         "rejected": 0, "spoiled": 0, "pu_total": 0, "pu_uploaded": 0,
         "pu_transcribed": 0, "pu_review": 0}
    for u in units:
        t["pu_total"] += 1
        if u["status"] == "awaiting":
            continue
        t["pu_uploaded"] += 1
        if u["status"] == "review":
            t["pu_review"] += 1
            continue
        if u["status"] != "transcribed":
            continue
        t["pu_transcribed"] += 1
        add(t["votes"], u["votes"])
        for k in ("registered", "accredited", "valid", "rejected", "spoiled"):
            t[k] += u.get(k) or 0
    return t


def merge(dst, src):
    add(dst["votes"], src["votes"])
    for k in ("registered", "accredited", "valid", "rejected", "spoiled",
              "pu_total", "pu_uploaded", "pu_transcribed", "pu_review"):
        dst[k] += src[k]


def main():
    inv = load_json(INV)
    if not inv:
        raise SystemExit("no inventory yet - run: python3 scripts/poll.py --full")
    tx = read_transcripts()

    lgas = {}
    review_queue = []
    for w in sorted(inv["wards"], key=lambda x: (x["lga_code"], x["ward_code"])):
        L = lgas.setdefault(w["lga_code"], {"code": w["lga_code"], "name": w["lga_name"], "wards": []})
        units = []
        for p in sorted(w["pus"], key=lambda x: x["pu_code"] or ""):
            r = tx.get(p["pu_code"])
            u = {"code": p["pu_code"], "name": p["pu_name"],
                 "img": p.get("doc_url"), "uploaded_at": p.get("doc_time")}
            if not p.get("doc_url"):
                u["status"] = "awaiting"
            elif not r:
                u["status"] = "pending"
            else:
                reasons, ok = validate(r)
                u["status"] = "transcribed" if ok else "review"
                u["votes"] = {k: r["votes"].get(k, 0) for k in PARTIES}
                for k in ("registered", "accredited", "issued", "unused",
                          "spoiled", "rejected", "valid", "used", "sn", "po"):
                    if r.get(k) is not None:
                        u[k] = r[k]
                if reasons:
                    u["review_reasons"] = reasons
                    review_queue.append({
                        "code": u["code"], "name": u["name"], "img": u["img"],
                        "lga": w["lga_name"], "ward": w["ward_name"],
                        "reasons": reasons,
                        "votes": u["votes"],
                        "valid": r.get("valid"), "accredited": r.get("accredited"),
                        "registered": r.get("registered"),
                        "rejected": r.get("rejected"), "spoiled": r.get("spoiled"),
                    })
            units.append(u)
        W = {"code": w["ward_code"], "name": w["ward_name"], "pus": units}
        W["totals"] = rollup(units)
        L["wards"].append(W)

    state = {"votes": blank(), "registered": 0, "accredited": 0, "valid": 0,
             "rejected": 0, "spoiled": 0, "pu_total": 0, "pu_uploaded": 0,
             "pu_transcribed": 0, "pu_review": 0}
    out_lgas = []
    for code in sorted(lgas):
        L = lgas[code]
        t = {"votes": blank(), "registered": 0, "accredited": 0, "valid": 0,
             "rejected": 0, "spoiled": 0, "pu_total": 0, "pu_uploaded": 0,
             "pu_transcribed": 0, "pu_review": 0}
        for W in L["wards"]:
            merge(t, W["totals"])
        L["totals"] = t
        merge(state, t)
        out_lgas.append(L)

    meta = {
        "election": "Osun State Governorship Election",
        "election_date": "2026-08-15",
        "state_code": "29",
        "parties": PARTIES,
        "polled_at": inv.get("polled_at"),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "remote_documents": inv.get("remote_documents"),
        "source": PORTAL,
        "totals": state,
    }
    save_json(os.path.join(DATA, "results.json"), {"meta": meta, "lgas": out_lgas})
    save_json(os.path.join(DATA, "status.json"), meta, indent=1)
    # The review queue is an operator artefact, not published: it stays in work/
    # so the website only ever carries figures that passed every check.
    save_json(os.path.join(WORK, "review.json"),
              {"built_at": meta["built_at"], "items": review_queue}, indent=1)

    t = state
    print("units %d | uploaded %d | transcribed %d | flagged %d | pending %d"
          % (t["pu_total"], t["pu_uploaded"], t["pu_transcribed"], t["pu_review"],
             t["pu_uploaded"] - t["pu_transcribed"] - t["pu_review"]))
    lead = sorted(t["votes"].items(), key=lambda kv: -kv[1])[:4]
    print("leading so far:", ", ".join("%s %s" % (k, v) for k, v in lead if v))


if __name__ == "__main__":
    main()
