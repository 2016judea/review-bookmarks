#!/usr/bin/env python3
"""Second in-print source, for titles Powell's search did not confirm: Penguin Random House's own
catalogue search (penguinrandomhouse.com, plain HTTP). A result whose title starts with ours, whose
contributors carry the author's surname, and whose "Available Formats" include a print format counts
as in print. Appends updated rows to cache/in_print.jsonl (the last row per key wins).
Why a second source: Powell's search only shows what Powell's stocks, and missed Light in August."""
import html, json, re, sys, time, unicodedata, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cache/in_print.jsonl"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"}
PRINT = re.compile(r"^(Paperback|Hardcover|Trade Paperback|Mass Market Paperback|Board Book)\b", re.I)


def fold(s): return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
def nt(s):
    s = re.sub(r"[;:(].*$", "", fold(s).lower().replace("&", "and")).strip()
    return re.sub(r"[^a-z0-9]+", "", re.sub(r"^(the|a|an) ", "", s))
def surname(a):
    a = fold(a).lower().split(" and ")[0].split(";")[0]
    return re.sub(r"[^a-z]", "", (a.split(",")[0] if "," in a else (a.split() or [""])[-1]))


def check(row):
    q = f"{row['title'].split(';')[0].split(':')[0].strip()} {row['author'].split(' and ')[0]}"
    url = "https://www.penguinrandomhouse.com/search/site?" + urllib.parse.urlencode({"q": q})
    for attempt in range(3):
        try:
            h = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8", "replace")
            break
        except Exception as e:
            time.sleep(3 * (attempt + 1)); h = None
    if h is None:
        return None
    t, s = nt(row["title"]), surname(row["author"])
    for item in h.split('<div class="result-item')[1:]:
        m = re.search(r'<h1 class="title"><a href="([^"]+)">(.*?)</a>', item, re.S)
        if not m: continue
        title = html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        who = html.unescape(re.sub(r"<[^>]+>", " ", (re.search(r'<h2 class="contributors">(.*?)</h2>', item, re.S) or [None, ""])[1]))
        fmts = [html.unescape(f).strip() for f in re.findall(r'<li><a [^>]*>([^<]+)</a></li>', item)]
        pf = [f for f in fmts if PRINT.match(f)]
        if nt(title).startswith(t) and s and s in fold(who).lower() and pf:
            return {"title": title, "author": " ".join(who.split()), "format": re.sub(r"\s*\(\d+\)$", "", pf[0]), "price": "", "condition": "New",
                    "source": "Penguin Random House", "url": "https://www.penguinrandomhouse.com" + m.group(1)}
    return False


def main():
    last = {}
    for l in OUT.read_text().splitlines():
        if l.strip():
            r = json.loads(l); last[r["key"]] = r
    todo = [r for r in last.values() if r["status"] != "in_print" and not r.get("prh_checked")]
    print(f"{len(todo)} not confirmed by Powell's; checking Penguin Random House")
    hits = 0
    with ThreadPoolExecutor(4) as ex:
        for r, res in zip(todo, ex.map(check, todo)):
            if res is None:
                continue
            r = dict(r, prh_checked=time.strftime("%Y-%m-%d"))
            if res:
                r.update(status="in_print", evidence=res); hits += 1
            with OUT.open("a") as f:
                f.write(json.dumps(r) + "\n")
    print(f"PRH confirmed {hits} more")


if __name__ == "__main__":
    main()
