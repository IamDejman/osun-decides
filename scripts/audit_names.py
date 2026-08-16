"""Catch transcriptions attached to the wrong polling unit.

Every arithmetic check in common.py asks "is this record internally
consistent?". None of them can ask "is it the right unit?" - a reader that
slips a row in its manifest produces a record that balances perfectly and is
simply filed against someone else's polling unit. That is the most damaging
error the pipeline can make, because it moves real votes between units and
nothing downstream complains.

The one independent signal is the polling unit name: the reader transcribes it
off the sheet, INEC publishes its own in the register, and the two should share
at least one distinctive word. They are worded differently often enough that a
mismatch is a prompt to look, not a verdict - see the false positive noted in
work/review-names.json when a unit is genuinely named differently at source.

  python3 scripts/audit_names.py
"""
import json, os, re, sys
from common import WORK, load_json, read_transcripts, save_json

# Words too common across polling unit names to distinguish one from another.
STOP = {"THE", "AND", "PRY", "PRIMARY", "SCHOOL", "OPEN", "SPACE", "HALL",
        "TOWN", "AREA", "UNIT", "CENT", "CENTRE", "CENTER", "COMP", "COMPOUND",
        "VILLAGE", "OPPOSITE", "INFRONT", "FRONT", "BESIDE", "ROAD", "STREET",
        "L", "LA", "RCM", "CAC", "NUD", "ANG", "COMM", "II", "III", "IV"}

# Units checked against the image and confirmed correctly keyed, where the
# sheet and the register genuinely name the same place differently. Only add a
# code here after opening the sheet and reading its own state/LGA/ward/unit
# code boxes - never to quieten an alert.
VERIFIED = {
    "29/21/07/005": "sheet reads AKOGUN OPEN SPACE, register says SURAJUDEEN "
                    "PRIMARY SCHOOL; the sheet's own code boxes read 29/21/07/005",
}


def tokens(s):
    return {t for t in re.findall(r"[A-Z0-9]+", (s or "").upper())
            if len(t) > 2 and t not in STOP}


def main():
    inv = load_json(os.path.join(WORK, "inventory.json"))
    if not inv:
        raise SystemExit("no inventory - run: python3 scripts/poll.py --full")
    register = {}
    for w in inv["wards"]:
        for p in w["pus"]:
            register[p["pu_code"]] = p.get("pu_name") or ""

    rows = read_transcripts()
    mismatched, unverifiable, excused = [], 0, 0
    for code, r in sorted(rows.items()):
        read_name = r.get("pu_name") or ""
        reg_name = register.get(code, "")
        a, b = tokens(read_name), tokens(reg_name)
        if not a or not b:
            unverifiable += 1
            continue
        if not (a & b) and code in VERIFIED:
            excused += 1
            continue
        if not (a & b):
            mismatched.append({
                "pu_code": code,
                "read_from_sheet": read_name,
                "inec_register": reg_name,
                "source": r.get("source", "main session"),
                "valid": r.get("valid"),
                "votes": {k: v for k, v in (r.get("votes") or {}).items() if v},
            })

    checked = len(rows) - unverifiable
    save_json(os.path.join(WORK, "review-names.json"),
              {"checked": checked, "unverifiable": unverifiable,
               "excused": excused, "verified_exceptions": VERIFIED,
               "mismatched": mismatched}, indent=1)

    print("names checked %d (%d had no comparable name, %d verified exceptions)"
          % (checked, unverifiable, excused))
    print("MISMATCHED %d" % len(mismatched))
    for m in mismatched:
        print("  %s  sheet=%-32s register=%-32s [%s]"
              % (m["pu_code"], m["read_from_sheet"][:32],
                 m["inec_register"][:32], m["source"]))
    if mismatched:
        print("\nEach needs an eye on the image before its votes are trusted:")
        print("  work/sheets/<code with / replaced by ->.jpg")
    return 1 if mismatched else 0


if __name__ == "__main__":
    sys.exit(main())
