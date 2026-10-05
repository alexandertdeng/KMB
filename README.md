# Keep Me Breathing - website

The keepmebreathing.com website, rebuilt as a static site for **GitHub Pages**.
Every page uses the "house style" of the homepage: navy NHS-blue bands,
Fraunces / Instrument Sans / IBM Plex Mono type, light-blue cards and the
animated capnography trace.

Built with [Jekyll](https://jekyllrb.com/), which GitHub Pages runs for you,
so there is no build pipeline to maintain. Push to `main` and the site updates.

---

## What's where

| Path | What it is |
| --- | --- |
| `_config.yml` | **Site settings**: donate link, email addresses, social links, newsletter link |
| `_data/navigation.yml` | The main menu |
| `_data/events.yml` | Events: upcoming, past and conference talks |
| `_data/partners.yml` | Partners and sponsors |
| `_products/` | One file per shop product |
| `_posts/` | Updates / news articles (`YYYY-MM-DD-title.html`) |
| `pages/` | All other pages (each has a `permalink:` matching its old URL) |
| `index.html` | The homepage |
| `assets/css/kmb.css` | The whole design system. Colours and fonts are tokens at the top |
| `assets/uploads/` | Images and media, same folder layout as WordPress `wp-content/uploads` |
| `_redirects/` | Old URLs (cart, raffle, event pages…) that now forward elsewhere |
| `_migration/` | One-off WordPress import scripts (not part of the site) |

## Everyday edits (all doable in the GitHub web editor)

- **Change where "Donate" goes**: edit `donate.url` in `_config.yml`.
- **Add an update/news post**: add a file to `_posts/` named
  `2026-10-05-my-headline.html` (or `.md`) starting with:
  ```yaml
  ---
  title: My headline
  description: One-sentence summary used on cards and in search results
  image: /assets/uploads/2026/10/my-photo.jpg
  categories: [Updates]
  ---
  ```
  Upload the image to `assets/uploads/2026/10/` first.
- **Add an event**: add an entry to `_data/events.yml` with `kind: upcoming`, a
  `date:` (YYYY-MM-DD), `when`, `where`, `image`, and an optional `link` to book.
  Upcoming events hide themselves automatically once their date has passed.
  Switch `kind` to `past` to show them in the past-events gallery.
- **Add a conference talk**: add an entry with `kind: talk`, `when`, `where` and `date`.
- **Add a product**: copy a file in `_products/`, change the details and images.
- **Edit the menu**: `_data/navigation.yml`.

## Things that changed from WordPress

GitHub Pages only serves static files, so the WordPress plugins that needed a
server have been replaced:

| WordPress feature | Now |
| --- | --- |
| GiveWP donation form (Stripe, Gift Aid, recurring) | `/contribute/` sends supporters to KMB's **JustGiving** charity page, which handles card payments, Gift Aid and monthly giving. Change it in `_config.yml`. |
| WooCommerce shop, cart and checkout | `/shop/` and `/product/*` pages are kept. **Order by email** opens a pre-filled email with the chosen size and quantity. To take card payments, paste a Stripe/PayPal/SumUp **payment link** into a product's `buy_url:` and the button becomes **Buy now**. The book's existing PayPal USD link is kept. |
| Contact Form 7 / Elementor forms | Email cards (`mailto:`), the same pattern the homepage already used. |
| Klaviyo newsletter signup | The **Sign me up** button opens a pre-filled email. Set `newsletter_url` in `_config.yml` to a Klaviyo/Mailchimp hosted signup page to use that instead. |
| Raffle / lottery, donor dashboard, my-account | Retired. The old URLs redirect to the nearest useful page. |
| Event detail pages (`/events/<name>/`) | These were blank on the old site. Events now live as cards on `/events/`, `/gallery/` and `/conferences/`, and old URLs redirect there. |

All page and post URLs are unchanged, so existing links and search rankings carry over.

## Run it locally

```bash
bundle install
bundle exec jekyll serve
```

Then open http://localhost:4000.

## Going live on GitHub Pages

1. Push this repository to GitHub and merge to `main`.
2. **Settings → Pages**: *Source* = "Deploy from a branch", *Branch* = `main` / `(root)`.
3. Under **Custom domain** enter `keepmebreathing.com` (the `CNAME` file already
   says this), then tick **Enforce HTTPS** once the certificate is issued.
4. At the domain registrar, replace the current WordPress host records with:
   - `A` records for `@`: `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   - `CNAME` for `www`: `<github-username>.github.io`
5. Before switching DNS: re-run the import (see `_migration/README.md`) if
   anything new was published on WordPress, and keep the WordPress hosting
   (and a full backup) until you've confirmed the new site is live.

To preview at `https://<user>.github.io/<repo>/` before the domain moves, set
`baseurl: "/<repo>"` and `url: https://<user>.github.io` in `_config.yml`
(set them back to `""` and `https://keepmebreathing.com` for the real domain).
