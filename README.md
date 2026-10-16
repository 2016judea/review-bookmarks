# Review Bookmarks

**Live:** https://review-bookmarks.vercel.app

A bookstore picks a title and prints a sheet of five bookmarks for the copies it
sells: the cover, a short review of that book, and the store's name on the back.
It is a shelf-talker that goes home inside the book.

The page opens on *Moby-Dick*, with D. H. Lawrence's line on the front and Sylvia
Beach's lending card on the back, ready to print.

## Where the lines come from

| lane | source | licence | coverage |
|---|---|---|---|
| **Famous readers** | their own published words about the book (Keats's letters, Lawrence 1923, Woolf's *Common Reader* 1925, Melville 1850) | public domain; every line is checked word for word against the Project Gutenberg text at build time, and the build fails on a mismatch | 12 lines (`data/notable.json`; add an entry to add one) |
| **Borrowed from Sylvia Beach** | Shakespeare and Company lending cards, Paris 1919-1941: "Nathalie Sarraute borrowed Moby-Dick ... in 1939", with the card's citation | CC BY 4.0, Shakespeare and Company Project, Princeton | 2,323 titles, readers with a Wikipedia page, most-known first |
| **A reader's review** | Aidan Jude's Goodreads reviews, verbatim; trimmed only by unticking whole sentences | his own | 70 titles |
| **Your staff's note** | the store pastes rough notes, a model fits them to the bookmark (adds nothing that isn't in the notes), staff edit and approve the exact words before it can print | the store's own | any title |

Excluded on purpose: the transcriptions in Melville's Marginalia Online, the
Archaeology of Reading and the Whitman Archive (no licence that covers a sold
product), and Folger play text (CC BY-NC). See `DATA_MODEL.md`.

Covers come from Open Library. The sheet is US Letter landscape, two pages, 2 x 7 in
bookmarks with crop marks; print double-sided, flip on short edge, 100% scale.

## Price

**$80, once.** Hypothesis, 2026-10-16. A custom run of 250 2 x 7 in bookmarks from
a print shop is $68.99 (Helloprint, read 2026-10-16), before anyone designs it. A
store that runs one staff pick a month spends about 12 x $69 = $828 a year on that,
and $80 is about a tenth of it. Untested against a buyer; revise on checkouts vs
payments, not on feel.

Free: the preloaded book (or, on a `/for/<token>/` page, the store's own staff
pick with its name on the back), printable. Paid: any title, your store's name, every
line we hold, unlimited sheets.

## The paywall

A port of `msp-house-index` via `salon-rates` (`site/paywall.js`, `site/api/`,
`site/offer.json`). `/api/data` returns every line to a password; the password is
minted at Stripe embedded Checkout and emailed by the webhook. `/api/tighten`
(the staff-note model step) also needs a password, and `ANTHROPIC_API_KEY` on
Vercel; without the key the page trims notes by whole sentences.

Vercel env: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `ACCESS_SECRET`,
`MAILGUN_*`. Comp password: `python3 scripts/issue_password.py "comp:<who>"`.
Lost password: `python3 scripts/fulfil.py <session>`.

## Build

    python3 scripts/build_borrows.py   # Beach's cards -> private/borrows.json
    python3 scripts/build_index.py     # all lanes -> private/bundle/full.json.gz + site/data/free.json
    python3 scripts/build_for.py       # outreach ledger -> site/data/for/<token>.json
    VERCEL_TOKEN=... python3 scripts/deploy.py

`build_borrows.py` reads the Shakespeare and Company CSVs from
`~/Desktop/marginalia-corpus/cache/shakeco/`; `build_index.py` reads Aidan's
reviews from `~/Desktop/writing-topology`.

MIT for the code. The data keeps its own licences, above.
