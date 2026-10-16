# Review Bookmarks

**Live:** https://review-bookmarks.vercel.app

A bookstore picks a title and prints a sheet of five bookmarks for the copies it
sells: the cover, a short review of that book, and the store's name on the back.
It is a shelf-talker that goes home inside the book.

The page opens on *Moby-Dick*, with D. H. Lawrence's line on the front and Sylvia
Beach's lending card on the back, ready to print.

## The Writers' Library (`/library/`)

A display table of books famous writers actually borrowed from Sylvia Beach's
Shakespeare and Company in Paris. A store picks a writer or a subject and gets:

- the list of 12 to 20 books, in-print titles first, each one marked **in print** (a new
  copy listed at Powell's, with format, price and date) or **not confirmed**;
- a 4 x 6 card for each book: the fact ("Ernest Hemingway borrowed this book from Sylvia
  Beach's lending library ... in October 1925"), who else borrowed it, the lending
  card's citation, and the store's name;
- one sign for the table ("What Ernest Hemingway borrowed from Sylvia Beach, Paris
  1925–1929"), the years computed from the cards on the table;
- the bookmarks for any of those books, one tap away.

It opens on Hemingway's table. Every sentence on a card or sign is written by
`scripts/build_library.py` from a lending-card event. A model only picks and orders
title ids from a list it is given (which of a writer's in-print titles make the 16;
which titles belong on a subject table); the build drops any id it was not given. A
writer's table is every member whose Wikidata occupation is a writer's and who has
12+ titles on her cards. `/for/<token>/library/` opens on the table that overlaps that
store's own staff pick.

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

**$80, once, now including every Writers' Library table.** Hypothesis, 2026-10-16. A custom run of 250 2 x 7 in bookmarks from
a print shop is $68.99 (Helloprint, read 2026-10-16), before anyone designs it. A
store that runs one staff pick a month spends about 12 x $69 = $828 a year on that,
and $80 is about a tenth of it. Untested against a buyer; revise on checkouts vs
payments, not on feel.

The table kit is folded into the $80 rather than priced on its own (hypothesis,
2026-10-16). Two prices on one page is a bundle, and the one number under test is
still whether a store pays $80 at all; round 1 has not gone out, so there is no
checkout-to-payment ratio yet to set a second price against. Folding it in raises
what the $80 buys without asking twice: same arithmetic as above, one price.
Revise on evidence: if `/library/` pages draw `checkout_open` events that the bookmark
page doesn't, the kit earns its own price.

Free: the preloaded book (or, on a `/for/<token>/` page, the store's own staff
pick with its name on the back), printable. Paid: any title, your store's name, every
line we hold, unlimited sheets. Library: Hemingway's table is free to print (on a
`/for/` page, the store's own overlapping table with its name); paid opens every
table and puts the store's name on the cards and sign.

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
    node scripts/check_in_print.js 4   # Powell's new-copy listings -> cache/in_print.jsonl (resumable, ~40 min)
    python3 scripts/reader_occupations.py   # Wikidata occupations -> cache/reader_occupations.json
    python3 scripts/build_library.py   # tables -> bundle + site/data/library/ + "library" on each /for/ page
    VERCEL_TOKEN=... python3 scripts/deploy.py

`build_borrows.py` reads the Shakespeare and Company CSVs from
`~/Desktop/marginalia-corpus/cache/shakeco/`; `build_index.py` reads Aidan's
reviews from `~/Desktop/writing-topology`.

MIT for the code. The data keeps its own licences, above.

## Outreach, round 1 (drafts only, nothing sent)

`node scripts/find_picks.js` walks each store in `outreach/stores*.csv` with headless
Chromium (IndieCommerce sites sit behind a Cloudflare check that refuses curl and
challenges the second page of a browser session, so every page gets a fresh context).
It records the store's own staff pick, the bookseller's exact words, and an email
published on the store's own site. `python3 scripts/build_for.py` turns that into
`site/data/for/<token>.json` (the page opens on their pick, their name on the back),
`outreach/round1/ledger.csv` and `outreach/round1/drafts/` (both gitignored).

2026-10-16: 226 stores read, 53 sendable (twin-cities 4, university-town 17,
regional 31, used-antiquarian 1). The 173 held say why in the ledger; almost all
publish no staff pick in a bookseller's own words. Used and antiquarian shops
mostly don't publish staff picks at all.
