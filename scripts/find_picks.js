// Find each store's own staff pick (title, author, staffer, their exact words) and a published email.
// Reads outreach/stores.csv, writes outreach/round1/picks.jsonl. Headless Chromium, because most
// indie sites sit on IndieCommerce behind a Cloudflare check that refuses curl (403) and lets a browser in.
//   node scripts/find_picks.js [name-filter]
const fs = require("fs");
const path = require("path");
const { chromium } = require(process.env.PLAYWRIGHT || (process.env.HOME + "/Desktop/workspace/pricing-vintage-baseball-cards/node_modules/playwright"));
const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "outreach/round1/picks.jsonl");
const today = new Date().toISOString().slice(0, 10);

function csv(file) {
  const [head, ...rows] = fs.readFileSync(file, "utf8").trim().split("\n");
  const keys = head.split(",");
  return rows.map((r) => { const v = r.split(","); return Object.fromEntries(keys.map((k, i) => [k, (v[i] || "").trim()])); });
}
const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
const BAD = /(example|sentry|wixpress|godaddy|domain\.com|\.png|\.jpg|indiecommerce|bookweb|aba\.|privacy@|noreply|no-reply)/i;

async function text(h) { try { return await h.page.evaluate(() => document.body ? document.body.innerText : ""); } catch (e) { return ""; } }
// Each navigation in a FRESH browser context: IndieCommerce's Cloudflare lets the first page of a
// session through and challenges every page after it ("Just a moment...", never solves headless).
let BROWSER = null, CTX = null;
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36";
async function go(holder, u, wait = 2500) {
  if (CTX) await CTX.close().catch(() => {});
  CTX = await BROWSER.newContext({ userAgent: UA });
  const p = await CTX.newPage();
  holder.page = p;
  return go1(p, u, wait);
}
async function go1(p, u, wait) {
  try {
    const r = await p.goto(u, { waitUntil: "domcontentloaded", timeout: 20000 }); await p.waitForTimeout(wait);
    // Cloudflare's "Just a moment..." answers 403 and then solves itself in a real browser; wait it out.
    for (let i = 0; i < 8 && /just a moment/i.test(await p.title()); i++) await p.waitForTimeout(1500);
    if (/just a moment/i.test(await p.title())) return 403;
    const st = r ? r.status() : 0;
    return st === 403 || st === 503 ? ((await p.evaluate(() => document.body.innerText.length)) > 400 ? 200 : st) : st;
  } catch (e) { return -1; }
}
async function links(h) { try { return await h.page.evaluate(() => [...document.querySelectorAll("a[href]")].map((a) => ({ h: a.href, t: (a.innerText || "").trim() }))); } catch (e) { return []; } }

// Books named on a staff-pick list page, with the list's own heading ("Gretchen's Picks"): their
// record even where no bookseller wrote a note. Used only when our index has a line for the title.
async function listed(h, rec) {
  try {
    const got = await h.page.evaluate(() => {
      const head = (document.querySelector("h1") || {}).innerText || "";
      const out = []; let cur = null;
      for (const a of document.querySelectorAll("a[href]")) {
        const t = (a.innerText || "").trim();
        if (/\/book\/97[89]\d{10}/.test(a.href) && t && !/read more|add to/i.test(t) && t !== t.toUpperCase()) {
          if (!cur || cur.title !== t) { cur = { title: t, author: "", isbn: (a.href.match(/97[89]\d{10}/) || [""])[0], list: head.trim(), url: location.href.split("?")[0] }; out.push(cur); }
        } else if (cur && !cur.author && /type=author|\/author\//.test(a.href) && t) cur.author = t;
      }
      return out;
    });
    rec.listed.push(...got.slice(0, 40));
  } catch (e) {}
}

async function staffReview(h, url) {
  if ((await go(h, url)) !== 200) return null;
  return h.page.evaluate(() => {
    const t = document.body.innerText;
    const m = t.match(/STAFF REVIEWS?\s*\n([\s\S]*?)\n\s*[—–-]\s*([^\n]{1,60})\n/i);
    if (!m) return null;
    const h1 = document.querySelector("h1");
    const title = h1 ? h1.innerText.trim() : "";
    let author = "";
    const a = document.querySelector('.abaproduct-authors, [class*="author"] a, a[href*="/author/"], a[href*="search/author"]');
    if (a) author = a.innerText.trim().replace(/^by\s+/i, "");
    const isbn = (location.pathname.match(/97[89]\d{10}/) || [""])[0];
    return { title, author, isbn, blurb: m[1].trim(), staffer: m[2].trim(), url: location.href };
  }).catch(() => null);
}

(async () => {
  const arg = process.argv[2] || "";
  const sh = arg.match(/^(\d+)\/(\d+)$/); // "i/n": every n-th store from i, so n processes run side by side
  const stores = csv(path.join(ROOT, process.env.STORES || "outreach/stores.csv")).filter((s, i) => s.site && (sh ? i % +sh[2] === +sh[1] : s.name.includes(arg)));
  const done = new Set(fs.existsSync(OUT) ? fs.readFileSync(OUT, "utf8").trim().split("\n").filter(Boolean).map((l) => JSON.parse(l).name) : []);
  BROWSER = await chromium.launch({ args: ["--disable-blink-features=AutomationControlled"] });
  const p = { page: null };
  for (const s of stores) {
    if (done.has(s.name)) continue;
    try { await one(s, p); } catch (e) { console.log(`${s.name}: ERROR ${e.message.slice(0, 80)}`); }
  }
  await BROWSER.close();
})();

async function one(s, p) {
  {
    const site = s.site.replace(/\/$/, "");
    const host = new URL(site).hostname.replace(/^www\./, "");
    const rec = { ...s, seen: today, picks: [], emails: [], email_pages: [], staff_url: "" };
    // emails: home + contact-ish pages
    const homeStatus = await go(p, site);
    rec.home_status = homeStatus;
    const L = homeStatus === 200 ? await links(p) : [];
    const pages = new Set([site]);
    for (const l of L) if (/contact|about|store-info|visit|hours|faq/i.test(l.h + " " + l.t) && l.h.includes(host)) pages.add(l.h.split("#")[0]);
    for (const extra of ["/contact-us", "/contact", "/about-us", "/store-info"]) pages.add(site + extra);
    const seenE = new Map();
    for (const u of [...pages].slice(0, 5)) {
      if (u !== site && (await go(p, u, 1800)) !== 200) continue;
      const t = await text(p);
      const mt = await p.page.evaluate(() => [...document.querySelectorAll('a[href^="mailto:"]')].map((a) => a.href.slice(7).split("?")[0])).catch(() => []);
      for (const e of [...(t.match(EMAIL) || []), ...mt]) { const k = decodeURIComponent(e).toLowerCase().replace(/\.$/, ""); if (!BAD.test(k) && !seenE.has(k)) seenE.set(k, u); }
    }
    rec.emails = [...seenE].map(([e, u]) => ({ email: e, page: u }));
    // staff picks
    let staffUrl = "";
    if ((await go(p, site + "/staff-picks")) === 200 && /staff/i.test(await p.page.title() + (await text(p)).slice(0, 4000))) staffUrl = site + "/staff-picks";
    else {
      const cand = L.find((l) => /staff/i.test(l.t + " " + l.h) && /pick|rec|favo|select/i.test(l.t + " " + l.h) && l.h.includes(host));
      if (cand && (await go(p, cand.h)) === 200) staffUrl = cand.h;
    }
    rec.staff_url = staffUrl;
    rec.listed = [];
    if (staffUrl) {
      await listed(p, rec);
      let L2 = await links(p);
      let books = [...new Set(L2.map((l) => l.h).filter((h) => /\/book\/97[89]\d{10}/.test(h) && h.includes(host)))];
      if (books.length < 2) {
        const lists = [...new Set(L2.filter((l) => l.h !== staffUrl && ((l.h.includes(host) && /pick|list|staff|favorite|recommend|\/node\/\d+/i.test(l.h)) || /\/list\//.test(l.h)) && !/kid|children|teen|young|ya-|alum|login|cart|wishlist/i.test(l.h + l.t)).map((l) => l.h.split("#")[0]))].slice(0, 5);
        for (const u of lists) { if ((await go(p, u)) === 200) { L2 = await links(p); await listed(p, rec); books.push(...L2.map((l) => l.h).filter((h) => /\/book\/97[89]\d{10}/.test(h))); } if (books.length >= 6) break; }
        books = [...new Set(books)];
      }
      for (const u of books.slice(0, 6)) {
        const r = await staffReview(p, u);
        if (r && r.blurb.length >= 40) rec.picks.push(r);
        if (rec.picks.length >= 3) break;
      }
    }
    fs.appendFileSync(OUT, JSON.stringify(rec) + "\n");
    console.log(`${s.name}: home ${homeStatus}, staff ${staffUrl ? "yes" : "no"}, picks ${rec.picks.length}, emails ${rec.emails.map((e) => e.email).join(" ")}`);
  }
}
