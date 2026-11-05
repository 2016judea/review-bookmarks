#!/usr/bin/env python3
"""Sylvia Beach's lending cards -> one dated fact per title: who borrowed it, when.

Source: Shakespeare and Company Project datasets v1.2 (2022-01), Princeton,
doi:10.34770/7hfq-ft27 ... licence CC BY 4.0 (re-checked in marginalia-corpus/ingest/shakeco.py).
Read from the copy marginalia-corpus already fetched: cache/shakeco/*.csv.

Readers kept: members with a Wikipedia page (a mechanical, not hand-picked, test of
"a reader a customer might know"). Fame rank = Wikidata sitelink count, fetched once
and cached in cache/wiki_sitelinks.json.

Writes private/borrows.json: {book_key: {title, author, year, uri, borrows:[...]}}
"""
import csv, json, re, sys, time, urllib.parse, urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path.home() / "Desktop/workspace/marginalia-corpus/cache/shakeco"
CACHE = ROOT / "cache/wiki_sitelinks.json"
UA = {"User-Agent": "review-bookmarks/0.1 (aidan@brickandmortar.dev)"}


def rows(name):
    with open(SRC / name, encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def norm(s):
    s = s.lower().replace("&", "and")
    s = re.sub(r"[;:(].*$", "", s)  # drop subtitles: "Moby-Dick; Or, the Whale" -> "moby-dick"
    s = re.sub(r"^(the|a|an) ", "", s.strip())
    return re.sub(r"[^a-z0-9]+", "", s)


def sitelinks(titles):
    have = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    todo = [t for t in titles if t not in have]
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        q = urllib.parse.urlencode({"action": "query", "prop": "pageprops", "ppprop": "wikibase_item",
                                    "redirects": 1, "format": "json", "titles": "|".join(batch)})
        j = json.load(urllib.request.urlopen(urllib.request.Request("https://en.wikipedia.org/w/api.php?" + q, headers=UA)))
        back = {}
        for r in j["query"].get("redirects", []) + j["query"].get("normalized", []):
            back[r["to"]] = r["from"]
        qid = {}
        for p in j["query"]["pages"].values():
            t = p["title"]
            while t in back: t = back[t]
            if p.get("pageprops", {}).get("wikibase_item"):
                qid[t] = p["pageprops"]["wikibase_item"]
        ids = list(qid.values())
        if ids:
            q2 = urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(ids), "props": "sitelinks", "format": "json"})
            e = json.load(urllib.request.urlopen(urllib.request.Request("https://www.wikidata.org/w/api.php?" + q2, headers=UA)))["entities"]
            for t, i_ in qid.items():
                have[t] = len(e.get(i_, {}).get("sitelinks", {}))
        for t in batch: have.setdefault(t, 0)
        time.sleep(0.5)
    CACHE.write_text(json.dumps(have, indent=0, sort_keys=True))
    return have


def main():
    members = {}
    for m in rows("SCoData_members_v1.2_2022-01.csv"):
        if m["wikipedia_url"] and m["is_organization"] != "True":
            members[m["uri"]] = m
    wt = {u: urllib.parse.unquote(m["wikipedia_url"].rsplit("/wiki/", 1)[1]).replace("_", " ") for u, m in members.items()}
    fame = sitelinks(sorted(set(wt.values())))
    books = {b["uri"]: b for b in rows("SCoData_books_v1.2_2022-01.csv")}
    out = {}
    n_ev = 0
    for e in rows("SCoData_events_v1.2_2022-01.csv"):
        if e["event_type"] not in ("Borrow", "Purchase") or not e["item_uri"]:
            continue
        b = books.get(e["item_uri"])
        if not b or b["format"] != "Book" or b["uncertain"] == "True" or not b["author"]:
            continue
        for uri, name in zip(e["member_uris"].split(";"), e["member_names"].split(";")):
            uri, name = uri.strip(), name.strip()
            if uri not in members:
                continue
            year = (e["start_date"] or "")[:4]
            if not re.fullmatch(r"19[1-4]\d", year):
                continue
            last, _, first = b["author"].partition(", ")
            # "Grimm, Jacob;Grimm, Wilhelm" -> "Jacob Grimm and Wilhelm Grimm"
            author = " and ".join(" ".join(reversed([x.strip() for x in a.split(", ", 1)])) for a in b["author"].split(";"))
            key = norm(b["title"]) + "|" + norm(last.split(";")[0])
            rec = out.setdefault(key, {"title": b["title"], "author": author, "year": b["year"], "uri": b["uri"], "events": int(b["event_count"] or 0), "borrows": []})
            rec["borrows"].append({
                "reader": name, "reader_uri": uri, "fame": fame.get(wt[uri], 0),
                "verb": "bought" if e["event_type"] == "Purchase" else "borrowed",
                "date": e["start_date"], "year": int(year),
                "card": e["source_citation"], "image": e["source_image"],
            })
            n_ev += 1
    for rec in out.values():
        rec["borrows"].sort(key=lambda r: (-r["fame"], r["date"]))
        # one line per reader: their earliest
        seen, keep = set(), []
        for r in sorted(rec["borrows"], key=lambda r: (-r["fame"], r["date"])):
            if r["reader_uri"] in seen: continue
            seen.add(r["reader_uri"]); keep.append(r)
        rec["borrows"] = keep
    (ROOT / "private").mkdir(exist_ok=True)
    (ROOT / "private/borrows.json").write_text(json.dumps(out, ensure_ascii=False))
    print(f"{len(members)} readers with a Wikipedia page, {n_ev} borrow/purchase events, {len(out)} titles")


if __name__ == "__main__":
    main()
