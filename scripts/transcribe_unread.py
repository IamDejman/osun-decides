"""Read unread EC8A sheets with the Claude API and append part files.

The minute poller downloads images. This is the next stage: any unit that
has a sheet on disk and no line in extract.jsonl gets one pass. merge_parts
and publish.sh stay responsible for folding the part into the site.

  python3 scripts/transcribe_unread.py          # up to LIMIT new sheets
  python3 scripts/transcribe_unread.py --limit 2
"""
import base64, json, os, sys, urllib.error, urllib.request
from common import PARTIES, SHEETS, WORK, load_json, read_transcripts

OUT = os.path.join(WORK, "parts", "auto.jsonl")
LIMIT = 6
MODELS = ["claude-sonnet-4-6", "claude-sonnet-4-5", "claude-sonnet-4-20250514"]
API = "https://api.anthropic.com/v1/messages"

PROMPT = """Transcribe this INEC Form EC8A for the 15 August 2026 Osun governorship election.
Return ONE compact JSON object, no markdown, no extra text.

Schema:
{"pu_code":"29/21/01/010","pu_name":"...","sn":"0002404","registered":694,"accredited":314,"issued":694,"unused":379,"spoiled":1,"rejected":1,"valid":313,"used":315,"votes":{"A":101,"AA":0,"AAC":1,"ADC":4,"ADP":0,"APC":205,"APGA":0,"APM":0,"APP":0,"BP":0,"NNPP":1,"PRP":0,"SDP":0,"YPP":1,"ZLP":0},"po":"NAME","date":"15/08/2026"}

Field map: sn = 7-digit serial; registered #1; accredited #2; issued #3; unused #4; spoiled #5; rejected #6; valid #7; used #8; votes = 15 party figures in order A AA AAC ADC ADP APC APGA APM APP BP NNPP PRP SDP YPP ZLP; po = presiding officer; date on the stamp.

Rules: blank/dash party row = 0. Prefer figures. If a box is illegible use null and add "unclear". If party figures do not sum to box #7, still record what you see. Do not invent numbers. pu_code is %s. pu_name is %s if the header is hard to read.

If the sheet is Form EC40G rather than EC8A, the election was cancelled or never held there and no party figures exist. Return the same object with every party at 0, registered and accredited as recorded, every ballot box null, and "not_held" set to the reason the form gives, such as OVERVOTING or VIOLENCE.
"""


def unread():
    inv = load_json(os.path.join(WORK, "inventory.json"), default={"wards": []})
    done = set(read_transcripts().keys())
    if os.path.exists(OUT):
        for line in open(OUT):
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line)["pu_code"])
            except Exception:      # noqa: BLE001
                pass
    todo = []
    for w in inv.get("wards") or []:
        for p in w.get("pus") or []:
            code = p.get("pu_code")
            if not code or not p.get("doc_url") or code in done:
                continue
            f = os.path.join(SHEETS, code.replace("/", "-") + ".jpg")
            if os.path.exists(f):
                todo.append((code, p.get("pu_name") or "", f))
    return todo


def read_sheet(code, name, path, key):
    raw = open(path, "rb").read()
    # The API caps an image at 5MB once base64 has inflated it by a third.
    if len(raw) > 4_000_000:
        raise ValueError("image too large (%d bytes)" % len(raw))
    img = base64.standard_b64encode(raw).decode("ascii")
    last = None
    for model in MODELS:
        body = {
            "model": model,
            "max_tokens": 600,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg", "data": img}},
                    {"type": "text", "text": PROMPT % (code, name)},
                ],
            }],
        }
        req = urllib.request.Request(
            API, data=json.dumps(body).encode(), method="POST",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            })
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                msg = json.loads(r.read().decode())
            break
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", "replace")[:400]
            last = ValueError("HTTP %s %s" % (e.code, err))
            if "credit balance" in err.lower():
                raise last
            if e.code in (404, 400) and "model" in err.lower():
                continue
            raise last
    else:
        raise last
    text = "".join(b.get("text") or "" for b in msg.get("content") or []
                   if b.get("type") == "text").strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    rec = json.loads(text)
    rec["pu_code"] = code
    rec["votes"] = {p: rec.get("votes", {}).get(p, 0) for p in PARTIES}
    if not isinstance(rec.get("votes"), dict):
        raise ValueError("no votes")
    return rec


def load_env():
    path = os.path.join(WORK, ".env")
    if not os.path.exists(path):
        return
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)


def main():
    load_env()
    limit = LIMIT
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("transcribe: no ANTHROPIC_API_KEY, skipped")
        return
    todo = unread()[:limit]
    if not todo:
        print("transcribe: 0 unread")
        return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wrote = 0
    with open(OUT, "a") as out:
        for code, name, path in todo:
            try:
                rec = read_sheet(code, name, path, key)
            except Exception as e:      # noqa: BLE001 - one bad sheet must not stop the rest
                print("transcribe fail %s: %s" % (code, e))
                if "credit balance" in str(e).lower():
                    print("transcribe: Anthropic credits empty, stopping")
                    break
                continue
            out.write(json.dumps(rec, separators=(",", ":")) + "\n")
            out.flush()
            wrote += 1
            print("transcribe %s" % code)
    print("transcribe: wrote %d of %d" % (wrote, len(todo)))


if __name__ == "__main__":
    main()
