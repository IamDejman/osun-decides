# Osun 2026 Polling Unit Results

A static site publishing polling-unit results for the 15 August 2026 Osun State
governorship election, transcribed from the Form EC8A sheets that INEC publishes
on its IReV portal.

The portal serves photographs of the sheets and no machine-readable figures, so
every number here was read off an image and recorded against its polling unit
code. The site is an independent transcription with no official standing.

## Deploy to Vercel

No build step and no dependencies: it is plain HTML, CSS, JS plus JSON in
`data/`.

```bash
npx vercel deploy --prod
```

Or push the folder to a Git repo and import it at vercel.com. When Vercel asks
for a framework preset, choose **Other**; leave build command and output
directory empty.

`vercel.json` sets a 30 second CDN cache on `/data/*` so a redeploy shows new
figures quickly while still being cached for readers.

## How data gets in

Three stages, deliberately separate, because only the middle one needs a human
or a model in the loop:

| Stage | What runs | What it does |
| --- | --- | --- |
| Poll | `scripts/poll.py` | Asks IReV what is published, downloads any sheet image it does not have |
| Transcribe | a reader working through `scripts/next_pairs.py` output | Reads the handwriting, appends a record to `work/extract.jsonl` |
| Build | `scripts/build_site_data.py` | Merges inventory + transcripts into `data/results.json` |

```bash
python3 scripts/poll.py --full     # first run: sweep all 332 wards
python3 scripts/poll.py            # thereafter: stats + 100 most recent uploads
python3 scripts/next_pairs.py 12   # stage 12 composites (24 sheets) to read
python3 scripts/build_site_data.py # regenerate what the site serves
```

`poll.py` calls `build_site_data.py` itself, so the site data is never stale
relative to the inventory.

### The every-minute poller

`~/Library/LaunchAgents/com.osun.results.poll.plist` runs `scripts/run-poll.sh`
every 60 seconds. It is already loaded. To manage it:

```bash
launchctl unload ~/Library/LaunchAgents/com.osun.results.poll.plist
launchctl load ~/Library/LaunchAgents/com.osun.results.poll.plist
tail -f work/poll.log
```

The poller keeps the *inventory* current and pulls images. It cannot produce
vote figures: reading handwriting is the part that needs a reader. So the count
of published sheets always runs ahead of the count of transcribed ones. The
public site reports only what has been counted; the backlog is operator state.

If a burst of uploads outruns the 100-item recent feed, the poller notices its
inventory drifting from the portal's own document count and falls back to a full
sweep on its own.

## Checking a transcription

Each EC8A states its figures twice, in digits and in words, and carries several
arithmetic identities. `scripts/common.py::validate` splits them by what they
actually tell you about the votes:

**Vote-critical** — failing one means the reading may be wrong, so the unit is
held out of every total on the site:

- the fifteen party scores sum to the total valid votes on the sheet
- used ballots equal valid + rejected + spoiled
- valid votes do not exceed accredited voters
- anything the reader marked `unclear`

**Ballot accounting** — constrains stationery, not votes. Presiding officers
miswrite these boxes fairly often and it says nothing about whether the party
figures were read correctly, so the unit is still counted, and still reported:

- ballots issued equal unused + used
- accredited voters do not exceed registered voters

Everything with any failure lands in `work/review.json` for a human to check
against the image. That file is deliberately **not** published: the website
carries only figures that passed.

## Adding a transcription

Append one JSON object per line to `work/extract.jsonl`. Later lines win, so
correcting a unit means appending a new line rather than editing an old one.

```json
{"pu_code":"29/01/01/001","pu_name":"TOWN HALL IWARA","sn":"0000001",
 "registered":949,"accredited":217,"issued":949,"unused":732,
 "spoiled":0,"rejected":4,"valid":213,"used":217,
 "votes":{"A":110,"AA":1,"AAC":1,"ADC":9,"ADP":0,"APC":90,"APGA":0,"APM":0,
          "APP":0,"BP":0,"NNPP":0,"PRP":0,"SDP":0,"YPP":1,"ZLP":1},
 "po":"OLUGBODI TIMILEHIN","date":"15/08/2026"}
```

Set a field to `null` when a box is genuinely illegible, and add an `unclear`
string to force the unit into review.

## Layout

```
index.html  styles.css  app.js     the site
data/       results.json, status.json, osun-lgas.geojson   what it serves
scripts/    poll, transcribe helper, build, shared validation
work/       inventory, sheet images, transcripts, review queue, logs  (gitignored)
```

`work/` is local operator state and is not deployed. Sheet images on the site
are linked from INEC's own storage rather than rehosted.

## Sources

- Portal: https://www.inecelectionresults.ng/elections/6a7f788adcbc755a763f082a
- LGA boundaries: geoBoundaries NGA ADM2 (open data), clipped to Osun's 30 LGAs
