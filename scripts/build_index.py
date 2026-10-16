#!/usr/bin/env python3
"""Build every review line a bookmark can carry, keyed by normalised (title, author surname).

Four lanes (DATA_MODEL.md):
  borrow  - Sylvia Beach's lending cards (private/borrows.json, from build_borrows.py), CC BY 4.0
  notable - famous readers' public-domain words (data/notable.json), each verified verbatim
            against the Gutenberg text in cache/gutenberg/ - the build FAILS on a mismatch
  owner   - Aidan's own Goodreads reviews, verbatim (writing-topology personal corpus)
  staff   - typed by the store in the page; nothing to build

Writes:
  private/bundle/full.json.gz  - every line, served to a password by /api/data
  site/data/free.json          - the preloaded example only (the free slice) + counts
"""
import gzip, json, re, sys, unicodedata, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INV = Path.home() / "Desktop/writing-topology/data/personal_corpus/book_review_inventory.json"
EXAMPLE = ("mobydick", "melville")
EXAMPLE_COVER = 11510691  # Open Library cover id, picked by eye
CC = "Shakespeare and Company Project, Princeton University (CC BY 4.0)"


def fold(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def norm_title(s):  # mirrored in site/index.html normTitle()
    s = fold(s).lower().replace("&", "and")
    s = re.split(r"[;:(]|,? or, ", s)[0].strip()
    s = re.sub(r"^(the|a|an) ", "", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def norm_author(s):  # surname of the first author, "Herman Melville" or "Melville, Herman"
    s = fold(s).lower().split(";")[0].split(" and ")[0]
    s = s.split(",")[0] if "," in s else (s.split() or [""])[-1]
    return re.sub(r"[^a-z0-9]+", "", s)


def key(title, author):
    return norm_title(title) + "|" + norm_author(author)


def flat(s):
    s = s.replace("_", "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s)


def sentences(t):
    t = t.strip()
    parts = re.split(r"(?<=[.!?…])\s+|\n+", t)
    return [p.strip() for p in parts if p.strip()]


def main():
    books = {}

    def book(title, author):
        k = key(title, author)
        return books.setdefault(k, {"title": title, "author": author, "lines": []})

    # borrow
    borrows = json.loads((ROOT / "private/borrows.json").read_text())
    for rec in borrows.values():
        b = book(rec["title"].split(";")[0].strip(), rec["author"])
        for r in rec["borrows"][:3]:
            who = r["reader"].split(" / ")[0].strip()
            b["lines"].append({
                "kind": "borrow", "reader": who,
                "text": f"{who} {r['verb']} {b['title']} from Sylvia Beach's Shakespeare and Company, Paris, in {r['year']}.",
                "cite": f"{r['card']} Via the {CC}.", "url": rec["uri"], "licence": "CC BY 4.0", "fame": r["fame"],
            })

    # notable, verified
    nb = json.loads((ROOT / "data/notable.json").read_text())
    texts = {}
    for ln in nb["lines"]:
        g = ln["gutenberg"]
        if g not in texts:
            p = ROOT / f"cache/gutenberg/{g}.txt"
            if not p.exists():
                urllib.request.urlretrieve(f"https://www.gutenberg.org/cache/epub/{g}/pg{g}.txt", p)
            texts[g] = flat(p.read_text(encoding="utf-8", errors="replace"))
        if flat(ln["text"]) not in texts[g]:
            sys.exit(f"NOT VERBATIM in Gutenberg {g}: {ln['reader']} on {ln['title']}: {ln['text'][:60]}")
        src = nb["sources"][g]
        book(ln["title"], ln["author"])["lines"].append({
            "kind": "notable", "reader": ln["reader"], "text": ln["text"], "about": ln.get("about", ""), "when": ln.get("when", ""),
            "cite": f"{ln['reader']}, {src['work']}" + (f" ({ln['when']})" if ln.get("when") else "") + ". Public domain; text via Project Gutenberg.",
            "url": src["url"], "licence": "Public domain",
        })

    # owner (Aidan), verbatim, 3 stars and up
    n_owner = 0
    for b0 in json.loads(INV.read_text()):
        for s in b0["sources"]:
            if s["source"] == "goodreads_review" and s["text"].strip() and (b0.get("rating") or 0) >= 3:
                t = re.sub(r"\n\s*— .*$", "", s["text"].strip())  # drop a trailing self-attribution line
                book(b0["title"], b0["author"])["lines"].append({
                    "kind": "owner", "reader": "Aidan Jude", "text": t, "sentences": sentences(t),
                    "cite": f"Aidan Jude, Goodreads review" + (f", {b0['rating']} of 5 stars" if b0.get("rating") else "") + ".",
                    "url": "https://www.goodreads.com/user/show/86865482", "licence": "Aidan Jude's own words",
                })
                n_owner += 1

    order = {"notable": 0, "borrow": 1, "owner": 2}
    for b in books.values():
        b["lines"].sort(key=lambda l: (order[l["kind"]], -l.get("fame", 0)))
    counts = {k: sum(1 for b in books.values() if any(l["kind"] == k for l in b["lines"])) for k in order}
    counts["titles"] = len(books)

    bundle = ROOT / "private/bundle"
    bundle.mkdir(parents=True, exist_ok=True)
    with gzip.open(bundle / "full.json.gz", "wt", encoding="utf-8") as f:
        json.dump({"books": books, "counts": counts}, f, ensure_ascii=False, separators=(",", ":"))
    ex_key = next(k for k in books if k.startswith(EXAMPLE[0] + "|" + EXAMPLE[1]))
    books[ex_key]["cover_i"] = EXAMPLE_COVER
    (ROOT / "site/data").mkdir(parents=True, exist_ok=True)
    (ROOT / "site/data/free.json").write_text(json.dumps({"example": {"key": ex_key, **books[ex_key]}, "counts": counts}, ensure_ascii=False, indent=1))
    print(f"titles {counts['titles']}: notable {counts['notable']}, borrow {counts['borrow']}, owner {counts['owner']} ({n_owner} reviews); "
          f"example {ex_key} has {len(books[ex_key]['lines'])} lines; bundle {(bundle / 'full.json.gz').stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
