// Is each borrowed title in print today? Evidence = a NEW copy listed in Powell's search
// (powells.com, read headless; curl gets a Cloudflare 403). No listing => "not confirmed",
// never "out of print": a miss only means we could not confirm it.
//   node scripts/check_in_print.js [concurrency]
// Reads private/borrows.json, appends to cache/in_print.jsonl (resumable; one line per title key).
const fs = require("fs");
const path = require("path");
const { chromium } = require(process.env.PLAYWRIGHT || (process.env.HOME + "/Desktop/pricing-vintage-baseball-cards/node_modules/playwright"));
const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "cache/in_print.jsonl");
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36";
const today = new Date().toISOString().slice(0, 10);

const fold = (s) => String(s || "").normalize("NFKD").replace(/[^\x00-\x7f]/g, "");
// same as build_borrows.norm (subtitle dropped, leading article dropped)
function nt(s) { s = fold(s).toLowerCase().replace(/&/g, "and").replace(/[;:(].*$/, "").trim().replace(/^(the|a|an) /, ""); return s.replace(/[^a-z0-9]+/g, ""); }
const surname = (a) => { a = fold(a).toLowerCase().split(";")[0]; return (a.includes(",") ? a.split(",")[0] : a.trim().split(/\s+/).pop() || "").replace(/[^a-z]/g, ""); };
const PRINT_FORMATS = /Trade Paperback|Hardcover|Mass Market|Paperback/i;

function parse(txt) {
  const i = txt.indexOf("Results for");
  if (i < 0) return null;
  const L = txt.slice(i).split("\n").map((s) => s.trim()).filter(Boolean);
  const items = [];
  for (let j = 1; j < L.length - 2; j++) {
    if (/^\$[\d,.]+$/.test(L[j]) && L[j + 1].startsWith("Format:") && L[j + 2].startsWith("Condition:")) {
      const prev2 = L[j - 2] || "", prev1 = L[j - 1];
      const hasAuthor = !(prev2.startsWith("Condition:") || prev2.startsWith("Results for"));
      items.push({ title: hasAuthor ? prev2 : prev1, author: hasAuthor ? prev1 : "", price: L[j], format: L[j + 1].slice(7).trim(), condition: L[j + 2].slice(10).trim() });
    }
  }
  return items;
}

function judge(rec, items) {
  const t = nt(rec.title), s = surname(rec.author);
  const hits = items.filter((it) => /^New/.test(it.condition) && PRINT_FORMATS.test(it.format)
    && nt(it.title).startsWith(t) && (fold(it.author + " " + it.title).toLowerCase().includes(s)));
  // cheapest new copy first: a mainstream paperback undercuts a print-on-demand reprint
  const $ = (it) => parseFloat(it.price.replace(/[$,]/g, "")) || 1e9;
  return hits.sort((a, b) => $(a) - $(b));
}

async function main() {
  const conc = +process.argv[2] || 3;
  const borrows = JSON.parse(fs.readFileSync(path.join(ROOT, "private/borrows.json"), "utf8"));
  const done = new Set(fs.existsSync(OUT) ? fs.readFileSync(OUT, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l).key) : []);
  // titles of the most-read readers first, so the themes are checked before the long tail
  const per = {};
  for (const r of Object.values(borrows)) for (const b of r.borrows) per[b.reader] = (per[b.reader] || 0) + 1;
  const score = (r) => Math.max(...r.borrows.map((b) => (per[b.reader] >= 12 ? 1000 : 0) + b.fame));
  const todo = Object.entries(borrows).filter(([k]) => !done.has(k)).sort((a, b) => score(b[1]) - score(a[1]));
  console.log(`${done.size} done, ${todo.length} to check, concurrency ${conc}`);
  const browser = await chromium.launch({ headless: true });
  let n = 0, yes = 0;
  async function worker() {
    while (todo.length) {
      const [key, rec] = todo.shift();
      const q = `${rec.title.split(/[;:(]/)[0].trim()} ${rec.author.split(";")[0]}`;
      let items = null, err = "";
      for (let a = 0; a < 2 && items === null; a++) {
        const ctx = await browser.newContext({ userAgent: UA });
        const p = await ctx.newPage();
        try {
          await p.goto("https://www.powells.com/searchresults?keyword=" + encodeURIComponent(q), { waitUntil: "domcontentloaded", timeout: 30000 });
          await p.waitForFunction(() => /Results for|No results|didn't find|0 results/i.test(document.body?.innerText || ""), null, { timeout: 15000 }).catch(() => {});
          const txt = await p.evaluate(() => document.body.innerText);
          items = parse(txt);
          if (items === null) err = /Just a moment|security verification/i.test(txt) ? "challenge" : /No results|didn't find/i.test(txt) ? "" : "no results header";
          if (items === null && !err) items = [];
        } catch (e) { err = e.message.slice(0, 80); }
        await ctx.close().catch(() => {});
      }
      const hits = items ? judge(rec, items) : [];
      const hit = hits[0] || null;
      const row = { key, title: rec.title, author: rec.author, query: q, checked: today, status: items === null ? "error" : hit ? "in_print" : "not_confirmed", evidence: hit, also_new: hits.slice(1, 4), err: items === null ? err : undefined };
      fs.appendFileSync(OUT, JSON.stringify(row) + "\n");
      n++; if (hit) yes++;
      if (n % 25 === 0) console.log(`${n} checked, ${yes} in print`);
    }
  }
  await Promise.all(Array.from({ length: conc }, worker));
  await browser.close();
  console.log(`done: ${n} checked, ${yes} in print`);
}
main();
