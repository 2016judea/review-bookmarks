#!/usr/bin/env python3
"""Outreach round 1: one /for/<token>/ page, one ledger row and one draft per store.

Reads outreach/round1/picks.jsonl (scripts/find_picks.js). For each store:
  - their own staff pick: title, author, the staffer's name and exact words, the page it is on
  - an email published on their own site (page + date recorded), domain MX-checked
Writes:
  site/data/for/<token>.json      the page opens on THEIR pick, their name on the back
  outreach/round1/ledger.csv      (gitignored) every store, sendable or held with a reason
  outreach/round1/drafts/<token>.md  (gitignored) DRAFTS. Nothing here sends anything.
"""
import csv, gzip, hashlib, json, re, subprocess, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_index import key, sentences  # same normalisation as the index

ROOT = Path(__file__).resolve().parent.parent
R1 = ROOT / "outreach/round1"
SITE = "https://review-bookmarks.vercel.app"
PRICE = json.loads((ROOT / "site/offer.json").read_text())["price_usd"]
SUBSTACK = "https://randomaidan.substack.com/p/business-prototypes"
MAXC = 260
OPINION = re.compile(r"\b(I|I'm|I've|my|me|loved?|adore|favou?rite|read|reading|you|your|must|best|beautiful|gorgeous|stunning|brilliant|can't|couldn't|wow)\b|!", re.I)
GENERIC = re.compile(r"^(info|books?|store|shop|hello|contact|orders?|bookstore|staff|mail|general|inquiries|events)@", re.I)


def tok(name):
    return hashlib.sha256(("rb1:" + name).encode()).hexdigest()[:8]


def clean(s):
    return re.sub(r"\s+", " ", s).strip()


def default_pick(ss):
    if sum(len(s) + 1 for s in ss) <= MAXC:
        return list(range(len(ss)))
    order = sorted(range(len(ss)), key=lambda i: (-len(OPINION.findall(ss[i])), -i))
    keep, n = [], 0
    for i in order:
        if n + len(ss[i]) + 1 <= MAXC:
            keep.append(i); n += len(ss[i]) + 1
    return sorted(keep) or [order[0]]


def mx_ok(domain):
    try:
        out = subprocess.run(["dig", "+short", "MX", domain], capture_output=True, text=True, timeout=10).stdout.strip()
        return bool(out)
    except Exception:
        return False


def cover_url(isbn):
    if not isbn:
        return ""
    u = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"
    try:
        with urllib.request.urlopen(urllib.request.Request(u, method="HEAD"), timeout=15) as r:
            return f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg" if r.status == 200 else ""
    except Exception:
        return ""


def main():
    index = json.load(gzip.open(ROOT / "private/bundle/full.json.gz", "rt"))["books"]
    recs = [json.loads(l) for l in (R1 / "picks.jsonl").read_text().splitlines() if l.strip()]
    (ROOT / "site/data/for").mkdir(parents=True, exist_ok=True)
    (R1 / "drafts").mkdir(parents=True, exist_ok=True)
    rows = []
    for r in recs:
        t = tok(r["name"])
        host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", r["site"]).split("/")[0])
        row = {"token": t, "segment": r["segment"], "store": r["name"], "city": r["city"], "site": r["site"], "status": "hold", "hold_reason": "",
               "email": "", "email_source": "", "mx": "", "staffer": "", "title": "", "author": "", "record_url": "", "record_seen": r["seen"],
               "fact": "", "page_url": f"{SITE}/for/{t}/", "subject": "", "draft": ""}
        picks = [p for p in r.get("picks", []) if p.get("title") and p.get("blurb")]
        if not picks:
            row["hold_reason"] = "no staff pick with the staffer's own words found on their site" + ("" if r.get("staff_url") else " (no staff picks page)")
            rows.append(row); continue
        for p in picks:
            p["_key"] = key(p["title"], p["author"] or "")
            p["_idx"] = [l for l in index.get(p["_key"], {}).get("lines", []) if l["kind"] in ("borrow", "notable")]
        p = sorted(picks, key=lambda p: (-len(p["_idx"]), abs(len(p["blurb"]) - 220)))[0]
        blurb = clean(p["blurb"])
        ss = [s.strip().strip('"“”').strip() for s in sentences(blurb)]
        ss = [s for s in ss if s]
        pick = default_pick(ss)
        title = p["title"].split(":")[0].strip()
        staffer = p["staffer"].strip(" .")
        cov = cover_url(p.get("isbn", ""))
        lines = [{"kind": "store", "reader": staffer, "text": blurb, "sentences": ss, "pick": pick,
                  "cite": f"{staffer}, staff pick, {r['name']}."}] + p["_idx"]
        page = {"token": t, "store": {"name": r["name"], "city": r["city"]},
                "book": {"title": title, "author": p["author"], "isbn": p.get("isbn", ""), "cover_url": cov, "key": p["_key"]},
                "lines": lines, "source": {"url": p["url"], "seen": r["seen"]}}
        (ROOT / f"site/data/for/{t}.json").write_text(json.dumps(page, ensure_ascii=False, indent=1))
        row.update(staffer=staffer, title=title, author=p["author"], record_url=p["url"])
        # email
        em = [e for e in r.get("emails", []) if "@" in e["email"]]
        own = [e for e in em if e["email"].split("@")[1].endswith(host.split(".", 1)[-1] if host.count(".") > 1 else host)]
        pool = sorted(own or em, key=lambda e: (not GENERIC.match(e["email"]), len(e["email"])))
        if not pool:
            row["hold_reason"] = "no email published on their own site (contact form only?)"
            rows.append(row); continue
        e = pool[0]
        dom = e["email"].split("@")[1]
        row.update(email=e["email"], email_source=f"{e['page']} (published on their own site, read {r['seen']})", mx="yes" if mx_ok(dom) else "NO")
        if row["mx"] != "yes":
            row["hold_reason"] = f"no MX record for {dom}"
            rows.append(row); continue
        # the draft
        first = ss[pick[0]] if pick else ss[0]
        if len(first) > 150:
            first = first[:147].rsplit(" ", 1)[0] + "…"
        b = next((l for l in p["_idx"] if l["kind"] == "borrow"), None)
        n = next((l for l in p["_idx"] if l["kind"] == "notable"), None)
        if b:
            fact = f"And one thing you might not know: {b['reader']} borrowed {title} from Sylvia Beach's Shakespeare and Company in Paris in {b['text'].rsplit(' ', 1)[-1].rstrip('.')}. It's on her lending card. So that went on the back, under your name."
            row["fact"] = b["text"]
        elif n:
            fact = f"And {n['reader']} wrote about it too, in {n['when']}. That line is on there as an option."
            row["fact"] = n["text"]
        else:
            fact = f"So I set {staffer}'s words on a bookmark. Cover on the front, your name on the back, five to a sheet of letter paper, crop marks for the cutter."
            row["fact"] = "(none: their words on a bookmark)"
        subject = f"{staffer}'s pick, {title}, as a bookmark"
        body = f"""Hi {r['name']},

{staffer}'s staff pick on your site is {title}: "{first}"

{fact}

It's ready to print, no login: {row['page_url']}

Any other title, with your name on it, is ${PRICE}, once.

Best,
Aidan
{SUBSTACK}
"""
        draft = f"DRAFT, not sent\nTo: {r['name']} <{e['email']}>\nOrganisation: {r['name']} ({r['segment']})\nTheir record: {p['url']}\nSubject: {subject}\n\n{body}"
        (R1 / f"drafts/{t}.md").write_text(draft)
        row.update(status="sendable", subject=subject, draft=f"outreach/round1/drafts/{t}.md")
        rows.append(row)
    with open(R1 / "ledger.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    by = {}
    for x in rows:
        by.setdefault(x["segment"], [0, 0])[x["status"] == "sendable" and 0 or 1] += 1
    print(f"{sum(1 for x in rows if x['status']=='sendable')} sendable of {len(rows)}; by segment (sendable, held): {by}")


if __name__ == "__main__":
    main()
