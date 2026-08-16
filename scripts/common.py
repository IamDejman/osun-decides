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


def party_column(r):
    """Return (sum, illegible_codes). Missing party keys count as 0.
    An explicit null on a party row means that row could not be read."""
    v = r.get("votes") or {}
    illegible = [p for p in PARTIES if p in v and v[p] is None]
    s = 0
    for p in PARTIES:
        if p in v and v[p] is None:
            continue
        s += int(v.get(p) or 0)
    return s, illegible


def validate(r):
    """Arithmetic cross-checks on one EC8A. Returns (reasons, ok).

    The public report uses the fifteen party figures whenever that column
    can be read. Box #7 and the stationery identities are checks: they are
    reported when they fail, but they do not withhold the unit.

    A unit is held only when the party column itself is unusable: a party
    row is null, or the form has no party figures and no box #7.
    """
    critical, accounting = [], []
    s, illegible = party_column(r)
    valid = r.get("valid")
    acc = r.get("accredited")
    reg = r.get("registered")
    rej = r.get("rejected")
    spo = r.get("spoiled")
    used = r.get("used")
    issued = r.get("issued")
    unused = r.get("unused")

    if illegible:
        critical.append("party row%s unreadable: %s"
                        % ("s" if len(illegible) > 1 else "", ", ".join(illegible)))
    elif s == 0 and valid is None:
        critical.append("no legible party figures or total valid votes")

    if valid is None:
        if s:
            accounting.append("box 7 blank, using party total %s" % s)
    elif s != valid:
        accounting.append("party votes total %s but sheet records %s valid" % (s, valid))

    if acc is not None and valid is not None and valid > acc:
        accounting.append("valid votes %s exceed accredited %s" % (valid, acc))

    if None not in (used, valid, rej, spo):
        if used != valid + rej + spo:
            accounting.append("used ballots %s but valid+rejected+spoiled = %s"
                              % (used, valid + rej + spo))
    elif used is not None:
        accounting.append("used-ballot identity untestable: a term is illegible")

    note = (r.get("unclear") or "")
    if note:
        accounting.append(note)

    if reg is not None and acc is not None and acc > reg:
        accounting.append("accredited %s exceeds registered %s" % (acc, reg))
    if None not in (issued, unused, used) and issued != unused + used:
        accounting.append("issued %s but unused+used = %s" % (issued, unused + used))

    return critical + accounting, not critical
