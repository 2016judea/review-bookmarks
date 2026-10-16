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
| Review `borrow` | Shakespeare and Company Project v1.2 (Sylvia Beach's lending cards, Paris 1919-41), **CC BY 4.0**, via `~/Desktop/marginalia-corpus` | **Yes, for 3,915 titles** borrowed by 253 writers with a library authority record. Factual, dated to the card, citable. Only modernist-era and older titles. |
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
