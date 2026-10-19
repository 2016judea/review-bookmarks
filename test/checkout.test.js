// node --test test/*.test.js
// /api/checkout sends the buyer back to the page they bought from. The library pages
// (/library/, /library/<theme>/, /for/<token>/library/) are buy pages too (README:
// "if /library/ pages draw checkout_open events..."), so a return_url that falls back
// to / for them lands the buyer on the bookmark page, off the table they were buying.
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

process.env.STRIPE_SECRET_KEY = "sk_test_x";
process.env.ACCESS_SECRET = "test-secret";
const checkout = require(path.join(__dirname, "..", "site", "api", "checkout.js"));
const OFFER = require(path.join(__dirname, "..", "site", "offer.json"));

function run(body) {
  const calls = [];
  global.fetch = async (url, opts) => {
    calls.push({ url, form: Object.fromEntries(new URLSearchParams(opts.body)) });
    return { ok: true, json: async () => ({ client_secret: "cs_test_secret" }) };
  };
  const res = { code: 0, body: null, status(c) { this.code = c; return this; }, json(b) { this.body = b; return this; } };
  return checkout({ method: "POST", body }, res).then(() => ({ res, form: calls[0] && calls[0].form }));
}

for (const [from, back] of [
  ["/", "/"],
  ["/for/0c8da5d4/", "/for/0c8da5d4/"],
  ["/for/0c8da5d4", "/for/0c8da5d4"],
  ["/library/", "/library/"],
  ["/library", "/library"],
  ["/library/hemingway/", "/library/hemingway/"],
  ["/for/0c8da5d4/library/", "/for/0c8da5d4/library/"],
  ["/for/0c8da5d4/library", "/for/0c8da5d4/library"],
]) {
  test(`checkout from ${from} returns the buyer to ${back}`, async () => {
    const { res, form } = await run({ path: from });
    assert.equal(res.code, 200);
    assert.equal(form.return_url, `${OFFER.site}${back}?paid={CHECKOUT_SESSION_ID}`);
  });
}

for (const bad of ["https://evil.example/", "//evil.example", "/admin", "/for/../x", "/library/<script>", ""]) {
  test(`a path we do not serve (${JSON.stringify(bad)}) returns to /`, async () => {
    const { form } = await run({ path: bad });
    assert.equal(form.return_url, `${OFFER.site}/?paid={CHECKOUT_SESSION_ID}`);
  });
}

test("the minted password rides in the session metadata and the invoice footer", async () => {
  const { form } = await run({ path: "/" });
  const pw = form["metadata[password]"];
  assert.match(pw, /^[2-9B-DF-HJ-NP-TV-Z]{4}-[2-9B-DF-HJ-NP-TV-Z]{4}-[2-9B-DF-HJ-NP-TV-Z]{4}$/);
  assert.ok(form["invoice_creation[invoice_data][footer]"].includes(pw));
  assert.equal(form["line_items[0][price_data][unit_amount]"], String(OFFER.price_usd * 100));
});
