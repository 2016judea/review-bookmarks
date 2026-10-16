#!/usr/bin/env python3
"""The Writers' Library: table kits built from Sylvia Beach's lending cards (DATA_MODEL.md, second half).

A theme is a writer (everything one Shakespeare and Company member borrowed) or a subject.
Every sentence on a card or sign is written HERE from a lending-card event. A model is only
asked to pick and order title ids from a list it is given; any id it was not given is dropped.

Reads:
  private/borrows.json             (build_borrows.py)
  private/bundle/full.json.gz      (build_index.py; bookmark lines per title)
  cache/in_print.jsonl             (check_in_print.js; Powell's new-copy listings)
  cache/reader_occupations.json    (reader_occupations.py; Wikidata P106)
  data/library_subjects.json       (subject table names)
Writes:
  private/bundle/full.json.gz      + "library": every theme (served to a password by /api/data)
  site/data/library/free.json      the default theme in full + the index of every theme (names, counts)
  site/data/for/<token>.json       + "library": the theme that overlaps the store's own staff pick
Run after build_index.py and build_for.py (both rewrite what this adds to).
"""
import gzip, hashlib, json, os, re, unicodedata, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_index import norm_author  # same key as the bookmarks

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = "ernest-hemingway"
MAX, TARGET, MIN = 20, 16, 12
WRITER = {"writer", "novelist", "poet", "playwright", "essayist", "author", "literary critic", "short story writer"}
MONTHS = "January February March April May June July August September October November December".split()
PROJECT = "Shakespeare and Company Project, Princeton University Library, CC BY 4.0"
PICKS = ROOT / "cache/library_picks.json"
COVERS = ROOT / "cache/ol_covers.json"
UA = {"User-Agent": "review-bookmarks/0.1 (aidan@brickandmortar.dev)"}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def when(date):
    """'1925-12-05' -> 'December 1925'; '1925' -> '1925'. Straight off the card."""
    m = re.match(r"(\d{4})(?:-(\d{2}))?", date or "")
    if not m:
        return ""
    return f"{MONTHS[int(m.group(2)) - 1]} {m.group(1)}" if m.group(2) else m.group(1)


def who(name):
    return name.split(" / ")[0].strip()


def split_title(t):
    t = t.split(";")[0].strip()
    main, _, sub = t.partition(": ")
    return main.strip(), sub.strip()


def same_author(a, b):
    """Full name, not surname: Kate Moore is not Marianne Moore, Alice Austen is not Jane Austen."""
    f = lambda x: re.sub(r"[^a-z]", "", unicodedata.normalize("NFKD", x.split(" and ")[0].split(";")[0]).encode("ascii", "ignore").decode().lower())
    return bool(f(a)) and f(a) == f(b)


def model_pick(theme_id, prompt, pool, n, lo=MIN):
    """Ask a model for up to n ids from pool (id -> one-line description). Cached by pool + prompt."""
    if os.environ.get("NO_MODEL"):  # layout testing only: the first ids, no model call, nothing cached
        return list(pool)[:n]
    cache = json.loads(PICKS.read_text()) if PICKS.exists() else {}
    h = hashlib.sha256((prompt + "\n" + "\n".join(f"{k}\t{v}" for k, v in sorted(pool.items()))).encode()).hexdigest()[:16]
    if cache.get(theme_id, {}).get("hash") == h:
        return cache[theme_id]["ids"]
    listing = "\n".join(f"{k}: {v}" for k, v in pool.items())
    schema = json.dumps({"type": "object", "properties": {"ids": {"type": "array", "items": {"type": "string"}}}, "required": ["ids"]})
    msg = f"{prompt}\n\n" + (f"Pick {lo} to {n} ids, best first." if n > 1 else "Pick exactly one id.") + f" Use only ids from this list:\n{listing}"
    for attempt in range(3):
        r = subprocess.run(["claude", "-p", "--model", "sonnet", "--system-prompt",
                            "You choose books for a bookstore display table. You only pick ids from the list you are given and reply through the schema. You never invent ids.",
                            "--json-schema", schema, "--output-format", "json", msg], capture_output=True, text=True, timeout=600)
        try:
            out = json.loads(r.stdout).get("structured_output") or {}
            ids = [i for i in dict.fromkeys(out.get("ids", [])) if i in pool][:n]  # drop anything it was not given
        except Exception:
            ids = []
        if len(ids) >= lo:
            break
        print(f"  [{theme_id}] model returned {len(ids)} valid ids, retrying", file=sys.stderr)
    cache[theme_id] = {"hash": h, "ids": ids, "at": time.strftime("%Y-%m-%d")}
    PICKS.write_text(json.dumps(cache, indent=1))
    return ids


def cover_ids(recs):
    have = json.loads(COVERS.read_text()) if COVERS.exists() else {}
    for k, rec in recs:
        if k in have:
            continue
        q = urllib.parse.urlencode({"title": split_title(rec["title"])[0], "author": rec["author"].split(" and ")[0], "limit": 1, "fields": "cover_i"})
        try:
            with urllib.request.urlopen(urllib.request.Request("https://openlibrary.org/search.json?" + q, headers=UA), timeout=20) as r:
                docs = json.load(r).get("docs") or []
                have[k] = docs[0].get("cover_i") if docs else None
        except Exception:
            continue  # not cached: tried again next build
        time.sleep(0.15)
    COVERS.write_text(json.dumps(have))
    return have


def main():
    borrows = json.loads((ROOT / "private/borrows.json").read_text())
    full = json.load(gzip.open(ROOT / "private/bundle/full.json.gz", "rt"))
    ip = {}
    for l in (ROOT / "cache/in_print.jsonl").read_text().splitlines():
        if l.strip():
            r = json.loads(l); ip[r["key"]] = r
    occ = json.loads((ROOT / "cache/reader_occupations.json").read_text())
    subjects = json.loads((ROOT / "data/library_subjects.json").read_text())["subjects"]

    def in_print(k):
        r = ip.get(k)
        if not r or r["status"] != "in_print":
            return {"status": "not_confirmed", "checked": r["checked"] if r else ""}
        e = r["evidence"]
        src = e.get("source", "Powell's")
        listing = f"New {e['format'].lower()}, {e['price']}, at Powell's" if src == "Powell's" else f"{e['format']}, listed by {src}"
        return {"status": "in_print", "checked": r.get("prh_checked") or r["checked"], "listing": listing, "as_listed": e["title"]}

    def table_title(k, b):
        rec = borrows[k]
        main, sub = split_title(rec["title"])
        others = [x for x in rec["borrows"] if x["reader_uri"] != b["reader_uri"]][:3]
        return {
            "key": k, "title": main, "sub": sub, "author": rec["author"],
            "reader": who(b["reader"]), "verb": b["verb"], "when": when(b["date"]), "year": b["year"], "date": b["date"],
            "fact": f"{who(b['reader'])} {b['verb']} this book from Sylvia Beach's {'lending library, ' if b['verb'] == 'borrowed' else ''}Shakespeare and Company, Paris, in {when(b['date'])}.",
            "also": [f"{who(x['reader'])} ({x['year']})" for x in others],
            "cite": f"{b['card']} {PROJECT}.", "url": rec["uri"], "in_print": in_print(k),
        }

    def finish(theme, titles):
        yrs = sorted(t["year"] for t in titles)
        span = f"{yrs[0]}–{yrs[-1]}" if yrs[0] != yrs[-1] else f"{yrs[0]}"
        if theme["kind"] == "writer":
            verbs = "borrowed and bought" if any(t["verb"] == "bought" for t in titles) and any(t["verb"] == "borrowed" for t in titles) else titles[0]["verb"] if len({t['verb'] for t in titles}) == 1 else "borrowed"
            theme["header"] = f"What {theme['reader']} {verbs} from Sylvia Beach, Paris {span}"
        else:
            theme["header"] = f"{theme['name']}: borrowed from Sylvia Beach, Paris {span}"
        theme["years"] = span
        theme["titles"] = titles
        theme["in_print"] = sum(1 for t in titles if t["in_print"]["status"] == "in_print")
        return theme

    themes = {}
    # writers: every member whose Wikidata occupation is a writer's, with 12+ distinct titles on her cards
    per = {}
    for k, rec in borrows.items():
        for b in rec["borrows"]:
            per.setdefault(b["reader_uri"], []).append((k, b))
    for uri, kb in sorted(per.items(), key=lambda x: -x[1][0][1]["fame"]):
        if len(kb) < MIN or not (WRITER & set(occ.get(uri, {}).get("occupations", []))):
            continue
        name = who(kb[0][1]["reader"])
        tid = slug(name)
        yes = [x for x in kb if in_print(x[0])["status"] == "in_print"]
        no = sorted([x for x in kb if x not in yes], key=lambda x: -borrows[x[0]]["events"])
        picked_by = "records"
        if len(yes) > TARGET:
            pool = {k: f"{split_title(borrows[k]['title'])[0]} ({borrows[k]['author']})" for k, _ in yes}
            ids = model_pick(tid, f"A bookstore is setting a table of books that {name} borrowed from Sylvia Beach's lending library in Paris. Pick the {TARGET} a customer browsing a bookstore today is most likely to recognise or want to pick up, and that together show the range of what {name} read.", pool, TARGET)
            chosen = [x for x in yes if x[0] in ids] if len(ids) >= MIN else yes[:TARGET]
            picked_by = "model" if len(ids) >= MIN else "records"
        else:
            chosen = yes + no[:max(0, MIN - len(yes))]
        chosen.sort(key=lambda x: x[1]["date"])  # the order they read them in
        themes[tid] = finish({"id": tid, "kind": "writer", "name": name, "reader": name, "fame": kb[0][1]["fame"], "picked_by": picked_by,
                              "on_cards": len(kb)}, [table_title(k, b) for k, b in chosen])
    # subjects: a model picks from every title, in-print marked; the card states the most-known borrower
    pool = {}
    for k, rec in borrows.items():
        pool[k] = f"{split_title(rec['title'])[0]} ({rec['author']}){' [in print]' if in_print(k)['status'] == 'in_print' else ''}"
    for s in subjects:
        ids = model_pick(s["id"], f"A bookstore is setting a display table called \"{s['name']}\": {s['brief']}. Every title below was borrowed from Sylvia Beach's lending library in Paris, 1919-1941. Pick {TARGET} that clearly belong on that table, strongly preferring titles marked [in print], and order them as you would lay them out, the strongest first.", pool, TARGET)
        if len(ids) < MIN:
            print(f"  [{s['id']}] skipped: only {len(ids)} valid ids", file=sys.stderr)
            continue
        themes[s["id"]] = finish({"id": s["id"], "kind": "subject", "name": s["name"], "picked_by": "model", "on_cards": len(ids)},
                                 [table_title(k, borrows[k]["borrows"][0]) for k in ids])

    # covers + bookmark lines for every title on a table
    keys = {t["key"] for th in themes.values() for t in th["titles"]}
    cov = cover_ids([(k, borrows[k]) for k in sorted(keys)])
    books = full["books"]
    for th in themes.values():
        for t in th["titles"]:
            t["cover_i"] = cov.get(t["key"])

    index = [{"id": th["id"], "kind": th["kind"], "name": th["name"], "header": th["header"], "n": len(th["titles"]), "in_print": th["in_print"], "picked_by": th["picked_by"]}
             for th in sorted(themes.values(), key=lambda t: (t["kind"] != "writer", -t.get("fame", 0), t["name"]))]
    full["library"] = {"themes": themes, "index": index}
    with gzip.open(ROOT / "private/bundle/full.json.gz", "wt", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, separators=(",", ":"))

    def with_lines(th):
        th = json.loads(json.dumps(th))
        for t in th["titles"]:
            t["lines"] = books.get(t["key"], {}).get("lines", [])
        return th

    (ROOT / "site/data/library").mkdir(parents=True, exist_ok=True)
    (ROOT / "site/data/library/free.json").write_text(json.dumps({"default": with_lines(themes[DEFAULT]), "index": index}, ensure_ascii=False))

    # each store's own staff pick -> the table it overlaps
    tiers = {"title": 0, "author": 0, "model": 0}
    tabs = list(themes.values())
    for p in sorted((ROOT / "site/data/for").glob("*.json")):
        page = json.loads(p.read_text())
        bk, b = page["book"]["key"], page["book"]
        hit = None
        for th in sorted(tabs, key=lambda t: (t["kind"] != "writer", -t.get("fame", 0))):
            t = next((t for t in th["titles"] if t["key"] == bk), None)
            if t:
                hit = ("title", th, t); break
        if not hit:
            for th in sorted(tabs, key=lambda t: (t["kind"] != "writer", -t.get("fame", 0))):
                t = next((t for t in th["titles"] if same_author(t["author"], b.get("author", ""))), None)
                if t:
                    hit = ("author", th, t); break
        if hit:
            tier, th, t = hit
            reason = (f"{t['reader']} {t['verb']} {b['title']} from Sylvia Beach in {t['when']}." if tier == "title"
                      else f"{t['reader']} {t['verb']} {t['author'].split(' and ')[0]}'s {t['title']} from Sylvia Beach in {t['when']}.")
            if tier == "title":
                line = f"{t['reader']} {t['verb']} {b['title']} from Sylvia Beach in {t['when']}. It's on the Writers' Library table “{th['header']}.”"
            else:
                line = f"{t['reader']} {t['verb']} {t['author'].split(' and ')[0]}'s {t['title']} from Sylvia Beach in {t['when']}. It's on the Writers' Library table “{th['header']}.”"
        else:
            tier, reason = "model", ""
            pick = next((l["text"] for l in page["lines"] if l["kind"] == "store"), "")
            pool = {th["id"]: th["header"] for th in tabs}
            ids = model_pick(f"for:{page['token']}", f"A bookstore's staff pick is {b['title']} by {b.get('author', '')}. The bookseller wrote: \"{pick[:400]}\". Which display table below would a reader of that book most enjoy browsing next?", pool, 1, lo=1)
            th = themes.get(ids[0] if ids else DEFAULT, themes[DEFAULT])
            line = f"A Writers' Library table to set beside it: “{th['header']}.”"
        tiers[tier] += 1
        page["library"] = {"tier": tier, "line": line, "reason": reason, "theme": with_lines(th)}
        p.write_text(json.dumps(page, ensure_ascii=False, indent=1))

    w = sum(1 for t in themes.values() if t["kind"] == "writer")
    print(f"{len(themes)} tables ({w} writers, {len(themes) - w} subjects); {len(keys)} titles; "
          f"in print {sum(t['in_print'] for t in themes.values())} of {sum(len(t['titles']) for t in themes.values())} table slots; "
          f"default {DEFAULT}: {len(themes[DEFAULT]['titles'])} titles, {themes[DEFAULT]['in_print']} in print; /for/ overlap {tiers}")


if __name__ == "__main__":
    main()
