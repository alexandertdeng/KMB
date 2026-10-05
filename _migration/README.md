# WordPress → Jekyll migration tools

These scripts produced the site content from the live WordPress install
at keepmebreathing.com. They are **not** part of the website build (Jekyll
ignores this folder) and you only need them if you want to re-import - for
example to pick up posts published on WordPress before DNS is switched over.

```bash
pip3 install beautifulsoup4 lxml pyyaml pillow
python3 _migration/fetch.py              # snapshot WP into _migration/cache/
python3 _migration/wp_import.py _migration/cache
```

`wp_import.py` regenerates:

| Output | From |
| --- | --- |
| `pages/*.html` | WordPress pages (except the hand-built ones listed in `SKIP_PAGES`) |
| `_posts/*.html` | WordPress posts, same URLs as before |
| `_products/*.html` | WooCommerce products |
| `_data/events.yml`, `_data/partners.yml` | the `events` / `partners` custom post types |
| `_redirects/*.html` | stubs that send retired URLs (cart, raffle, event detail pages…) somewhere useful |
| `assets/uploads/**` | every image/audio/video/PDF the content references, optimised |

⚠️ Re-running **overwrites** those files. If you have edited a page by hand
since the import, either skip it (add its slug to `SKIP_PAGES`) or re-apply
your edit afterwards. Hand-built pages (homepage, donate, shop, events,
updates, contact, partners, conferences, gallery, subscribe, thanks) are
never touched.

Pass `--no-images` to skip downloading/optimising media.
Media optimisation uses macOS tools (`sips`, `afconvert`, `avconvert`) plus
Ghostscript (`gs`) and Pillow.
