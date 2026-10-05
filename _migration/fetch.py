#!/usr/bin/env python3
"""
Snapshot the live WordPress site into a local cache for wp_import.py.

Usage:  python3 _migration/fetch.py [cache_dir]      (default: _migration/cache)

Needs curl. The site blocks curl's default user agent, so a browser UA is sent.
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "_migration", "cache")
SITE = "https://keepmebreathing.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def curl(url, out):
    r = subprocess.run(["curl", "-sfL", "-H", f"User-Agent: {UA}", "-o", out, "-w", "%{http_code}", url],
                       capture_output=True, text=True)
    return r.stdout


def main():
    os.makedirs(os.path.join(CACHE, "raw"), exist_ok=True)
    api = f"{SITE}/wp-json/wp/v2"
    for t in ("pages", "posts", "events", "partners"):
        print(t, curl(f"{api}/{t}?per_page=100&_embed=wp:featuredmedia,wp:term", os.path.join(CACHE, f"{t}_embed.json")))
    print("categories", curl(f"{api}/categories?per_page=100", os.path.join(CACHE, "categories.json")))
    print("products", curl(f"{SITE}/wp-json/wc/store/v1/products?per_page=100", os.path.join(CACHE, "products.json")))

    urls = []
    for t in ("pages", "posts", "events", "partners"):
        urls += [p["link"] for p in json.load(open(os.path.join(CACHE, f"{t}_embed.json")))]
    urls += [p["permalink"] for p in json.load(open(os.path.join(CACHE, "products.json")))]

    def get(u):
        name = u.replace(SITE + "/", "").strip("/").replace("/", "__") or "index"
        return u, curl(u, os.path.join(CACHE, "raw", name + ".html"))

    with ThreadPoolExecutor(6) as ex:
        for u, code in ex.map(get, urls):
            if code != "200":
                print("  ", code, u)
    print(f"{len(urls)} pages cached")

    # The homepage is one big Custom HTML block - keep it on its own for reference.
    from bs4 import BeautifulSoup
    s = BeautifulSoup(open(os.path.join(CACHE, "raw", "index.html")).read(), "lxml")
    w = s.select_one(".elementor-widget-html .elementor-widget-container")
    if w:
        open(os.path.join(CACHE, "home_widget.html"), "w").write(w.decode_contents())


if __name__ == "__main__":
    main()
