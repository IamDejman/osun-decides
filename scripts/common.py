"""Shared config and helpers for the Osun 2026 result pipeline."""
import json, os, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "work")          # inventory, sheet images, transcripts
DATA = os.path.join(ROOT, "data")          # what the website reads
SHEETS = os.path.join(WORK, "sheets")

ELECTION = "6a7f788adcbc755a763f082a"
API = "https://dolphin-app-sleqh.ondigitalocean.app/api/v1/elections/" + ELECTION
PORTAL = "https://www.inecelectionresults.ng/elections/" + ELECTION

PARTIES = ["A", "AA", "AAC", "ADC", "ADP", "APC", "APGA", "APM", "APP",
           "BP", "NNPP", "PRP", "SDP", "YPP", "ZLP"]

for d in (WORK, DATA, SHEETS):
    os.makedirs(d, exist_ok=True)


def get(url, tries=3, timeout=60):
    """GET JSON with retries. Returns parsed body or raises."""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "osun-results/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:      # noqa: BLE001 - retry any transport error
            last = e
    raise last


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def save_json(path, obj, indent=None):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=indent, separators=(",", ":") if indent is None else None)
    os.replace(tmp, path)


def read_transcripts():
    """Every transcribed sheet, keyed by PU code. Later lines win, so a
    re-transcription of the same unit supersedes the earlier one."""
    path = os.path.join(WORK, "extract.jsonl")
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            out[r["pu_code"]] = r
    return out


def validate(r):
    """Arithmetic cross-checks on one EC8A. Returns (reasons, ok).

    The form carries its own redundancy, so a reading that satisfies every
    identity is almost certainly right. But the identities are not equally
    informative about the votes:

    * Vote-critical checks bear directly on the party figures. Failing one
      means the reading may be wrong, so the unit is held out of all totals.
    * Ballot-accounting checks (issued = unused + used) constrain stationery,
      not votes. Presiding officers miswrite these boxes fairly often, and a
      failure there says nothing about whether the party figures were read
      correctly. Those are reported for review but still counted.

    Both kinds are surfaced to the operator either way; only the first kind
    withholds the unit.
    """
    v = r.get("votes") or {}
    critical, accounting = [], []
    s = sum(v.values())
    valid = r.get("valid")
    acc = r.get("accredited")
    reg = r.get("registered")
    rej = r.get("rejected") or 0
    spo = r.get("spoiled") or 0
    used = r.get("used")
    issued = r.get("issued")
    unused = r.get("unused")

    if valid is None or s != valid:
        critical.append("party votes total %s but sheet records %s valid" % (s, valid))
    if used is not None and valid is not None and used != valid + rej + spo:
        critical.append("used ballots %s but valid+rejected+spoiled = %s" % (used, valid + rej + spo))
    if acc is not None and valid is not None and valid > acc:
        critical.append("valid votes %s exceed accredited %s" % (valid, acc))
    if r.get("unclear"):
        critical.append(r["unclear"])

    if reg is not None and acc is not None and acc > reg:
        accounting.append("accredited %s exceeds registered %s" % (acc, reg))
    if None not in (issued, unused, used) and issued != unused + used:
        accounting.append("issued %s but unused+used = %s" % (issued, unused + used))

    return critical + accounting, not critical
