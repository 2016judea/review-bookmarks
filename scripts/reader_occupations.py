#!/usr/bin/env python3
"""Wikidata occupations (P106) for every Shakespeare and Company member with a Wikipedia page.
Used to decide which readers get a 'writer' table: a mechanical test, not a hand pick.
Writes cache/reader_occupations.json {member_uri: {"name", "wiki", "occupations": [...]}}."""
import csv, json, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path.home() / "Desktop/workspace/marginalia-corpus/cache/shakeco"
OUT = ROOT / "cache/reader_occupations.json"
UA = {"User-Agent": "review-bookmarks/0.1 (aidan@brickandmortar.dev)"}


def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30))


def main():
    have = json.loads(OUT.read_text()) if OUT.exists() else {}
    members = {}
    with open(SRC / "SCoData_members_v1.2_2022-01.csv", encoding="utf-8-sig") as f:
        for m in csv.DictReader(f):
            if m["wikipedia_url"] and m["is_organization"] != "True" and m["uri"] not in have:
                members[m["uri"]] = (m["name"], urllib.parse.unquote(m["wikipedia_url"].rsplit("/wiki/", 1)[1]).replace("_", " "))
    items = list(members.items())
    for i in range(0, len(items), 40):
        batch = items[i:i + 40]
        q = urllib.parse.urlencode({"action": "query", "prop": "pageprops", "ppprop": "wikibase_item", "redirects": 1, "format": "json", "titles": "|".join(w for _, (_, w) in batch)})
        j = get("https://en.wikipedia.org/w/api.php?" + q)["query"]
        back = {}
        for r in j.get("normalized", []) + j.get("redirects", []):
            back[r["to"]] = r["from"]
        qid = {}
        for p in j["pages"].values():
            t = p["title"]
            while t in back: t = back[t]
            if p.get("pageprops", {}).get("wikibase_item"): qid[t] = p["pageprops"]["wikibase_item"]
        ids = sorted(set(qid.values()))
        occ = {}
        if ids:
            e = get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(ids), "props": "claims", "format": "json"}))["entities"]
            occ = {k: [c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in v.get("claims", {}).get("P106", [])] for k, v in e.items()}
        oq = sorted({o for v in occ.values() for o in v if o})
        labels = {}
        for k in range(0, len(oq), 50):
            e = get("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(oq[k:k + 50]), "props": "labels", "languages": "en", "format": "json"}))["entities"]
            labels.update({x: v.get("labels", {}).get("en", {}).get("value", x) for x, v in e.items()})
        for uri, (name, wiki) in batch:
            q_ = qid.get(wiki)
            have[uri] = {"name": name, "wiki": wiki, "qid": q_, "occupations": [labels.get(o, o) for o in occ.get(q_, []) if o]}
        time.sleep(0.3)
    OUT.write_text(json.dumps(have, ensure_ascii=False, indent=0))
    print(f"{len(have)} readers; with an occupation: {sum(1 for v in have.values() if v['occupations'])}")


if __name__ == "__main__":
    main()
