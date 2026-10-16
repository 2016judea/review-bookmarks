// POST /api/tighten { notes, title, author, max } -> { text }
// The staff lane: a bookseller pastes rough notes, a model tightens them to bookmark length.
// It may cut and reorder their words; it may not add a claim, a fact or a name that is not in
// the notes. The staff member then edits and approves the exact text in the page before it
// can print. Needs a password (this is part of the full tool) and ANTHROPIC_API_KEY; without
// the key it answers 503 and the page trims by whole sentences instead.
const { checkPassword, nonceIsPaid } = require("./_lib");

const SYSTEM = `You fit a bookseller's rough notes about a book onto a printed bookmark.
Rules:
- Use only what the notes say. Never add a fact, opinion, comparison, name or detail that is not in the notes.
- Keep the bookseller's own words and voice wherever you can; cut filler, fix spelling and grammar.
- Plain words. No hype words the notes do not use. No hashtags, no emoji, no quotation marks around the whole thing.
- Stay under the character limit you are given. One to three sentences.
- Output only the bookmark text, nothing else.`;

module.exports = async (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  const ok = checkPassword(req.headers["x-password"]);
  if (!ok) return res.status(401).json({ error: "Fitting notes is part of the full tool." });
  try { if (ok.kind === "paid" && !(await nonceIsPaid(ok.nonce))) return res.status(402).json({ error: "payment not confirmed" }); }
  catch (e) { return res.status(502).json({ error: "Couldn't check the password right now." }); }
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) return res.status(503).json({ error: "not configured", fallback: true });
  const b = req.body || {};
  const notes = String(b.notes || "").slice(0, 4000).trim();
  const max = Math.max(80, Math.min(400, Number(b.max) || 240));
  if (!notes) return res.status(400).json({ error: "Paste your notes first." });
  try {
    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json" },
      body: JSON.stringify({
        model: process.env.TIGHTEN_MODEL || "claude-haiku-4-5", max_tokens: 300, system: SYSTEM,
        messages: [{ role: "user", content: `Book: ${String(b.title || "").slice(0, 200)} by ${String(b.author || "").slice(0, 120)}\nCharacter limit: ${max}\n\nNotes:\n${notes}` }],
      }),
    });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error?.message || r.status);
    const text = (j.content || []).map((c) => c.text || "").join("").trim();
    res.status(200).json({ text });
  } catch (e) {
    console.error("[tighten]", e.message);
    res.status(503).json({ error: "The fitting step is down; trimming by sentences instead.", fallback: true });
  }
};
