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
import csv, gzip, hashlib, json, re, subprocess, sys, urllib.parse, urllib.request
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
PREF = ["info", "hello", "query", "inquiry", "books", "book", "store", "shop", "contact", "bookstore", "mail", "general", "inquiries", "staff", "words"]
LAST = re.compile(r"^(events?|orders?|internetorders|webhelp|web|sales|returns|donations|consignments?|school|bookfairs|authorvisits|marketing|media|organizations|press|jobs|careers|accounting|billing|ap|bib)\b", re.I)


def email_rank(e):
    local = e.split("@")[0].lower()
    if local in PREF:
        return (0, PREF.index(local))
    if LAST.match(local):
        return (2, 0)
    return (1, len(e))  # a named bookseller, or the store's own gmail


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


def cover_url(isbn, title="", author=""):
    """Open Library cover for that ISBN; else the cover of the work found by title + author."""
    if isbn:
        u = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"
        try:
            with urllib.request.urlopen(urllib.request.Request(u, method="HEAD"), timeout=15) as r:
                if r.status == 200:
                    return f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
        except Exception:
            pass
    if title:
        q = urllib.parse.urlencode({"title": title, "author": author, "limit": 1, "fields": "cover_i"})
        try:
            with urllib.request.urlopen(urllib.request.Request("https://openlibrary.org/search.json?" + q, headers={"User-Agent": "review-bookmarks (aidan@brickandmortar.dev)"}), timeout=20) as r:
                docs = json.load(r).get("docs") or []
                if docs and docs[0].get("cover_i"):
                    return f"https://covers.openlibrary.org/b/id/{docs[0]['cover_i']}-L.jpg"
        except Exception:
            pass
    return ""


def main():
    index = json.load(gzip.open(ROOT / "private/bundle/full.json.gz", "rt"))["books"]
    recs = [json.loads(l) for l in (R1 / "picks.jsonl").read_text().splitlines() if l.strip()]
    (ROOT / "site/data/for").mkdir(parents=True, exist_ok=True)
    for old in (ROOT / "site/data/for").glob("*.json"):
        old.unlink()  # regenerated wholesale; a store that is now held must not keep a page
    for old in (R1 / "drafts").glob("*.md"):
        old.unlink()
    (R1 / "drafts").mkdir(parents=True, exist_ok=True)
    rows = []
    for r in recs:
        t = tok(r["name"])
        host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", r["site"]).split("/")[0])
        row = {"token": t, "segment": r["segment"], "store": r["name"], "city": r["city"], "site": r["site"], "status": "hold", "hold_reason": "",
               "email": "", "email_source": "", "mx": "", "staffer": "", "title": "", "author": "", "record_url": "", "record_seen": r["seen"],
               "fact": "", "page_url": f"{SITE}/for/{t}/", "subject": "", "draft": ""}
        picks = [p for p in r.get("picks", []) if p.get("title") and p.get("blurb")
                 and re.fullmatch(r"[A-Z][\w.'&\- ]{0,40}(, [\w ]{1,30})?", p.get("staffer", "").strip(" ."))
                 and not re.search(r"DESCRIPTION|ABOUT THE AUTHOR|PRAISE|REVIEW", p.get("staffer", ""))]
        wordless = None
        if not picks:
            # A staff list with no notes is still their record, but only worth a page when our index adds a line.
            for it in r.get("listed", []):
                if not it.get("author"):
                    continue
                k = key(it["title"], it["author"])
                idx = [l for l in index.get(k, {}).get("lines", []) if l["kind"] in ("borrow", "notable")]
                m = re.match(r"^(.+?)['’]s?\s+(staff\s+)?(picks?|favou?rites|selections?)", it.get("list", ""), re.I)
                generic = re.fullmatch(r"\s*staff\s+(picks?|favou?rites|selections?)\s*", it.get("list", ""), re.I)
                if idx and (m or generic):
                    who = "" if generic else m.group(1).strip()
                    wordless = {**it, "_key": k, "_idx": idx, "staffer": who.title() if who.isupper() else who, "blurb": ""}
                    break
            if not wordless:
                row["hold_reason"] = "no staff pick with the staffer's own words found on their site" + ("" if r.get("staff_url") else " (no staff picks page)")
                rows.append(row); continue
        for p in picks:
            p["_key"] = key(p["title"], p["author"] or "")
            p["_idx"] = [l for l in index.get(p["_key"], {}).get("lines", []) if l["kind"] in ("borrow", "notable")]
        p = wordless or sorted(picks, key=lambda p: (-len(p["_idx"]), abs(len(p["blurb"]) - 220)))[0]
        p["url"] = p["url"].split("?")[0]
        blurb = clean(p["blurb"])
        ss = [s.strip().strip('"“”').strip() for s in sentences(blurb)] if blurb else []
        ss = [s for s in ss if s]
        pick = default_pick(ss) if ss else []
        title = re.sub(r"\s*\([^)]*\)\s*$", "", p["title"].split(":")[0]).strip()
        staffer = p["staffer"].split(",")[0].strip(" .")  # "Tori, Wild Rumpus" -> "Tori"
        cov = cover_url(p.get("isbn", ""), title, (p.get("author") or "").split(",")[0])
        lines = ([{"kind": "store", "reader": staffer, "text": blurb, "sentences": ss, "pick": pick,
                   "cite": f"{staffer}, staff pick, {r['name']}."}] if blurb else []) + p["_idx"]
        page = {"token": t, "store": {"name": r["name"], "city": r["city"]},
                "book": {"title": title, "author": p["author"], "isbn": p.get("isbn", ""), "cover_url": cov, "key": p["_key"]},
                "lines": lines, "source": {"url": p["url"], "seen": r["seen"]}}
        (ROOT / f"site/data/for/{t}.json").write_text(json.dumps(page, ensure_ascii=False, indent=1))
        row.update(staffer=staffer, title=title, author=p["author"], record_url=p["url"])
        # email
        em = [e for e in r.get("emails", []) if "@" in e["email"]]
        own = [e for e in em if e["email"].split("@")[1].endswith(host.split(".", 1)[-1] if host.count(".") > 1 else host)]
        ownset = {e["email"] for e in own}
        pool = sorted(em, key=lambda e: (email_rank(e["email"])[0], e["email"] not in ownset, email_rank(e["email"])[1]))
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
        first = (ss[pick[0]] if pick else ss[0]) if ss else ""
        if len(first) > 150:
            first = first[:147].rsplit(" ", 1)[0] + "…"
        opener = f'{staffer}\'s staff pick on your site is {title}: "{first}"' if first else (f"{title} is on {staffer}'s staff picks on your site." if staffer else f"{title} is on the staff picks page on your site.")
        b = next((l for l in p["_idx"] if l["kind"] == "borrow"), None)
        n = next((l for l in p["_idx"] if l["kind"] == "notable"), None)
        if b:
            fact = f"And one thing you might not know: {b['reader']} borrowed {title} from Sylvia Beach's Shakespeare and Company in Paris in {b['text'].rsplit(' ', 1)[-1].rstrip('.')}. It's on her lending card. " + ("So that went on the back, under your name." if (blurb or n) else "So that's on the bookmark, under the cover, with your name on the back.")
            row["fact"] = b["text"]
        elif n:
            fact = f"And {n['reader']} wrote about it, in {n['when']}: \"{n['text']}\" That's on the front, under the cover."
            row["fact"] = n["text"]
        else:
            fact = f"So I set {staffer}'s words on a bookmark. Cover on the front, your name on the back, five to a sheet of letter paper, crop marks for the cutter."
            row["fact"] = "(none: their words on a bookmark)"
        subject = f"{staffer}'s pick, {title}, as a bookmark" if staffer else f"Your staff pick, {title}, as a bookmark"
        body = f"""Hi {r['name']},

{opener}

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
        by.setdefault(x["segment"], [0, 0])[0 if x["status"] == "sendable" else 1] += 1
    print(f"{sum(1 for x in rows if x['status']=='sendable')} sendable of {len(rows)}; by segment (sendable, held): {by}")


if __name__ == "__main__":
    main()
