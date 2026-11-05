# Data model: bookmarks with reviews, for bookstores

Written 2026-10-16 from the need alone (BUSINESS.md rule 5), then checked against
what can actually be obtained. The reality check is the second half of this file.

## The need

A bookseller hands a customer a book they just bought. Inside it is a bookmark that
says something true and worth reading about *that* book: who loved it, who read it,
what the store's own staff thought. It carries the cover and the store's name, so the
store goes home with the reader. The store does not design anything. It picks a title,
picks a line, approves the exact words, and prints.

## Entities

### Book
| field | question it answers for the store |
|---|---|
| `title`, `author` | which book is this bookmark for? |
| `isbn` (any edition) | how do I find the cover and confirm the edition I stock? |
| `cover_url` | what does the front look like without me scanning anything? |
| `first_published` | is this old enough that famous readers wrote about it in public-domain text? |

### Review (one line on a bookmark; a Book has many)
| field | question it answers |
|---|---|
| `kind` | `borrow` (a dated fact), `notable` (a famous reader's own words), `owner` (Aidan's review), `staff` (this store's note) |
| `reader` | who said it / who did it? |
| `text` | the exact words printed, verbatim from the source; never paraphrased |
| `fits` | does it fit a 2 x 7 inch bookmark at a readable size? (character budget) |
| `licence` | may a store print this on something given away with a sold book? |
| `citation` | where can a sceptical customer check it? (work, date, URL) |
| `approved_by` | for `staff`: who signed off on the final words |

### Store
| field | question it answers |
|---|---|
| `name` | whose name is on the back? |
| `city` | the line under the name |
| `own_record` | a book the store already championed in public (staff pick, newsletter, post), with its URL and date; this is what a first sheet opens on |
| `email`, `email_source`, `email_seen` | can we reach a named inbox, and when did we last see it published? |
| `segment` | what kind of store (Twin Cities indie, used/antiquarian, university town, ...) |

### BookmarkSheet (the output)
| field | question it answers |
|---|---|
| `book`, `store` | for which title, for which store |
| `front_line` (Review) | the main line on the front |
| `back_line` (Review, optional) | a second line or the dated fact on the back |
| `layout` | 5 bookmarks, 2 x 7 in, on US Letter landscape, crop marks, front page + back page |

## Joins

- Review -> Book by normalised `(title, author)`; ISBN is only for the cover.
- Store.own_record -> Book the same way, so a store's first sheet is its own pick.
- Sheet = Book x Store x 1-2 Reviews, chosen by the staff member.

## Reality check, field by field (2026-10-16)

| field | source | can we fill it? |
|---|---|---|
| Book.title/author/isbn/cover/first_published | Open Library search + covers API, keyless | **Yes**, for any title in print. Covers are publisher art, used the way every store uses them: to promote a book it sells. |
| Review `borrow` | Shakespeare and Company Project v1.2 (Sylvia Beach's lending cards, Paris 1919-41), **CC BY 4.0**, via `~/Desktop/workspace/marginalia-corpus` | **Yes, for 3,915 titles** borrowed by 253 writers with a library authority record. Factual, dated to the card, citable. Only modernist-era and older titles. |
| Review `notable` | Public-domain published writing by famous readers about a book (Keats, Melville, Lawrence, Woolf's 1925 *Common Reader*, Emerson, Poe), each quote string-checked against the fetched Gutenberg text at build time | **Yes, but narrow**: classics only, a hand-picked set, grows by adding entries to `data/notable.json`. The marginalia corpus's own transcriptions (Melville's Marginalia Online, AOR, Whitman) declare no reuse licence for a sold product and are **excluded**; Derrida's margins are CC BY but are underlinings in French philosophy, not reader-facing reviews. |
| Review `owner` | Aidan's Goodreads reviews (`writing-topology/.../book_review_inventory.json`), verbatim, trimmed only by whole-sentence selection | **Yes, 82 reviews**, 34 of them 5-star. His words, his licence. |
| Review `staff` | the store pastes rough notes; a model tightens them to fit; staff approve the exact text | **Yes for any title.** This is the lane that covers new releases, which are most of a store's stock. The model step needs `ANTHROPIC_API_KEY` on Vercel; without it the tool trims by whole sentences and the staff member edits by hand. |
| Store.own_record | the store's own staff-picks page / newsletter / Instagram | **Partly.** Many indies publish staff picks with a named staffer's note. A store with no public pick is held from outreach, not sent a generic example. |
| Store.email | the store's own site, dated | **Partly**; verified per row in `outreach/round1/ledger.csv`. |

**Verdict: the model fills.** The one field that cannot be filled for every title is a
*famous* reader's line: there is no public-domain famous-reader review of a 2025
novel, and there never will be. That is not a fillable-subset compromise, because the
`staff` lane is the store's own voice and covers every title; famous readers and Beach's
cards are the extra a store gets for the classics and modernists it shelves.

---

# The Writers' Library: a table kit

Written 2026-10-16, from the need alone, before touching the data; checked against
reality below.

## The need

A bookstore wants a display table that tells a story a customer can check: *these are
the books Hemingway actually borrowed in Paris*. The store picks a theme or a writer and
gets everything to set the table: which 12 to 20 books to put out (ones it can order
today), a card standing by each book with the fact and where it comes from, one sign
for the head of the table, and bookmarks for the same books.

## Entities

### Theme
| field | question it answers for the store |
|---|---|
| `id`, `kind` | `writer` (everything one reader borrowed) or `subject` (a topic across readers) |
| `name` | what is this table called on the picker? |
| `header` | the exact words on the table sign, e.g. "What Hemingway borrowed from Sylvia Beach, Paris 1925–1929" |
| `years` | the date range on the sign: computed from the borrow dates of the titles on the table, never typed |
| `titles` | which 12–20 books, in which order |
| `picked_by` | `records` (a deterministic rule) or `model` (a model chose and ordered the titles, from ids it was given) |

### TableTitle (one book on one table)
| field | question it answers |
|---|---|
| `title`, `author` | what do I pull from the shelf / order? |
| `fact` | the one sentence on the card: reader, verb (borrowed/bought), title, date, from the lending card |
| `also` | who else on Beach's cards borrowed it, with years (records only) |
| `citation` | which card, which archive, which licence; the book's Project URL |
| `in_print` | can I order a new copy today? `in_print` with the listing that shows it, or `not_confirmed` |
| `in_print_evidence`, `checked` | where we saw a new copy, its format and price, and when |

### ShelfTalker (output, one per TableTitle)
4 x 6 in portrait card: theme kicker, title, author, fact, `also`, store name, citation.

### HeaderSign (output, one per Theme)
US Letter landscape: the theme `header`, the store's name.

### Bookmark (output)
The existing BookmarkSheet (above) for any TableTitle.

## Joins

- TableTitle -> Book by the same normalised `(title, author surname)` key as the bookmarks.
- Theme.writer -> Shakespeare and Company member URI; titles = that member's borrow events.
- Store.own_record (their staff pick) -> Theme: same title on a table, else same author
  on a table, else a model's pick of the nearest table (labelled as a pick, not a fact).

## Rule

Every fact on a card or sign comes from a lending-card event. A model only picks and
orders title ids from a list it is given; the build rejects any id it was not given and
writes every sentence itself from the record.

## Reality check (2026-10-16)

| field | source | can we fill it? |
|---|---|---|
| Theme `writer` titles | Shakespeare and Company Project events, CC BY 4.0 | **Yes.** 62 readers with a Wikipedia page have 12+ distinct borrowed titles (Hemingway 90, Joyce 97, Stein 43, de Beauvoir 19, Wilder 12). |
| Theme `subject` titles | no subject field in the Project's books table | **Only by a model's pick**, from title + author. Allowed by the rule above (picking, not stating); the sign states the topic as the store's table name, and every card states only the record. |
| `fact`, `also`, `citation`, `years` | lending-card events, with the card's citation and date | **Yes**, all of them. |
| `in_print` | no open in-print register exists. Open Library's editions stop around 1994 for *Buddenbrooks*; Google Books' keyless quota is exhausted and our keys don't carry the Books API; Bookshop.org and IndieCommerce search are Cloudflare-walled to headless | **Partly: Powell's search, read headless,** shows New copies with format and price. A listed new copy confirms the title is orderable; no listing means **not confirmed**, never "out of print". Print-on-demand reprints of public-domain titles count as new copies, which is true but worth a store's glance. |
