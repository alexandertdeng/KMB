#!/usr/bin/env python3
"""
One-off importer: WordPress (keepmebreathing.com) -> Jekyll source for GitHub Pages.

It reads a cache of the WordPress REST API + rendered HTML (see fetch step in
_migration/README.md), turns the Elementor markup into clean, house-style HTML,
downloads every referenced image into assets/uploads/, and writes:

  pages/*.html          converted WordPress pages (permalinks preserved)
  _posts/*.html         converted blog posts (permalinks preserved)
  _data/products.yml    shop products
  _data/events.yml      events (upcoming / past / talks)
  _data/partners.yml    partners & sponsors
  _data/redirects.yml   old URLs that no longer exist -> new homes

Hand-built pages (index, contribute, shop, events, updates, contact ...) are
NOT generated here - see SKIP_PAGES.

Usage:  python3 _migration/wp_import.py <cache_dir>
"""
import html
import html as _html
import json
import os
import re
import subprocess
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import yaml
from bs4 import BeautifulSoup, Comment, NavigableString, Tag

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "_migration", "cache")
SITE = "https://keepmebreathing.com"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
BASE = "{{ site.baseurl }}"

# --------------------------------------------------------------------------
# Page metadata: nicer titles, eyebrows and ledes for the house-style hero.
# drop_heading: first heading in the content that duplicates the hero title.
# --------------------------------------------------------------------------
PAGE_META = {
    "medical-endorsement-of-keep-me-breathing": dict(title="Medical endorsement", eyebrow="Take a breath · make a change",
        lede="Over 130 doctors, scientists and medical professionals have endorsed Keep Me Breathing’s accelerated plan to develop treatments for CCHS."),
    "keep-me-breathing-team-and-advisory-board": dict(title="Our team & advisory board", eyebrow="About KMB",
        lede="The people, clinicians and partners working to bring the world’s first CCHS treatments to every child who needs them."),
    "cchs-for-patients-and-parents": dict(title="What is CCHS? For patients & parents", eyebrow="CCHS",
        lede="A plain-language guide to Congenital Central Hypoventilation Syndrome - what it is, how it is treated today, and where research is heading."),
    "cchs-for-professionals": dict(title="CCHS for professionals", eyebrow="CCHS",
        lede="Clinical background, research priorities and the treatment pathway Keep Me Breathing is funding."),
    "what-is-the-cause-of-congenital-central-hypoventilation-syndrome": dict(title="What causes CCHS?", eyebrow="CCHS",
        lede="The genetics behind Congenital Central Hypoventilation Syndrome and the PHOX2B gene."),
    "caspersstory": dict(title="Casper’s story", eyebrow="Stories"),
    "beaus-story": dict(title="Beau’s story", eyebrow="Stories"),
    "more-cchs-stories": dict(title="More CCHS stories", eyebrow="Stories",
        lede="Families from around the world share what life with CCHS is really like."),
    "how-many-patients-with-cchs": dict(title="How many patients have CCHS?", eyebrow="CCHS"),
    "cchs-mask-vs-tracheostomy-vs-pacer": dict(title="Mask vs tracheostomy vs pacer", eyebrow="CCHS",
        lede="Comparing the ventilation options available to children and adults living with CCHS."),
    "cchs-treatment-and-options": dict(title="CCHS treatment and options", eyebrow="CCHS"),
    "cchs-newborn-and-diagnosis-what-to-do-next-specialists-and-new-treatments": dict(
        title="A newborn diagnosis: what to do next", eyebrow="CCHS",
        lede="Specialists, support and the new treatments on the horizon for families facing a CCHS diagnosis."),
    "cchsqualityoflife": dict(title="CCHS: patient quality of life and caregiver burden", eyebrow="Research"),
    "technology-update": dict(title="Technology update", eyebrow="Research"),
    "read-our-bi-monthly-news-bulletins-below": dict(title="News bulletins", eyebrow="Updates",
        lede="Our bi-monthly bulletins on research, fundraising and the KMB community."),
    "keep-me-breathing-press": dict(title="Press & media", eyebrow="Updates",
        lede="Keep Me Breathing in the news - newspapers, radio and television."),
    "sm-version-fundraising": dict(title="Fundraise for Keep Me Breathing", eyebrow="Get involved",
        lede="Run, ride, bake or climb - every pound raised goes straight to CCHS research."),
    "volunteer-network": dict(title="Volunteers needed", eyebrow="Get involved",
        lede="Lend your skills and time to our volunteer network and events across the year."),
    "south-downs-challenge": dict(title="South Downs Challenge", eyebrow="Events"),
    "skydiving": dict(title="Skydive for CCHS", eyebrow="Events"),
    "jacks-haircut": dict(title="Jack’s hair-raising challenge", eyebrow="Events"),
    "jogle-3-peaks": dict(title="JOGLE + 3 Peaks", eyebrow="Events"),
    "subscribe-for-our-news-and-updates": None,  # hand-built
}

# Hand-built in the repo (or retired) - never generated by the importer.
SKIP_PAGES = {
    "keep-me-breathing-cchs-treatments",  # homepage -> index.html
    "home",  # old 2018 homepage
    "contribute", "shop", "cart", "checkout", "my-account", "events", "updates",
    "contact-page", "partners", "gallery", "all-past-events", "conferences",
    "subscribe-for-our-news-and-updates", "thanks", "signup", "raffle", "dashboard",
    "donor-dashboard", "donation-confirmation", "donation-failed", "terms", "research",
}

# Retired URLs -> where visitors should land now (rendered by jekyll-redirect-from).
REDIRECTS = {
    "/home/": "/",
    "/research/": "/#research",
    "/terms/": "/",
    "/cart/": "/shop/",
    "/checkout/": "/shop/",
    "/my-account/": "/shop/",
    "/raffle/": "/contribute/",
    "/dashboard/": "/contribute/",
    "/signup/": "/subscribe-for-our-news-and-updates/",
    "/donor-dashboard/": "/contribute/",
    "/donation-confirmation/": "/thanks/",
    "/donation-failed/": "/contribute/",
    "/all-past-events/": "/gallery/",
    "/blog/": "/updates/",
    "/product/order-nowdreaming-of-breathing-the-adventures-of-casper-beau/": "/product/dreaming-of-breathing/",
}

# Typos and slips in the WordPress copy, fixed on every import.
# Literal (old, new) pairs - keep them specific so nothing else is touched.
CORRECTIONS = [
    ("WHat is CCHS?", "What is CCHS?"),
    ("5000+ childrenworldwide", "5000+ children worldwide"),
    ("particularly involentary functions", "particularly involuntary functions"),
    ("blood sugar regulation and digestion..", "blood sugar regulation and digestion."),
    ("having the right clinican.", "having the right clinician."),
    ("we are proud to have a exceptional", "we are proud to have an exceptional"),
    ("Mete has is the first new addition", "Mete is the first new addition"),
    ("numerous events..", "numerous events."),
    ("travelling the world .", "travelling the world."),
    ("Charity is called Keep me Breathing", "Charity is called Keep Me Breathing"),
    ("we are are so unbelievably lucky", "we are so unbelievably lucky"),
    ("my polhydramnios was benign", "my polyhydramnios was benign"),
    ("a bit of cocomelon and thomas the tank engine", "a bit of CoComelon and Thomas the Tank Engine"),
    ("Co2 monitor, Cannulas, BP Cuff and Sa02 monitoring", "CO2 monitor, Cannulas, BP Cuff and SaO2 monitoring"),
    ("General Practioner", "General Practitioner"),
    ("In-Reach practioner", "In-Reach practitioner"),
    ("Neonatel Intensive Care Nurse", "Neonatal Intensive Care Nurse"),
    ("PHD Biological Scienses", "PhD Biological Sciences"),
    ("Keep Me breathing", "Keep Me Breathing"),
    ("Support Nikki and Keep me breathing", "Support Nikki and Keep Me Breathing"),
    ("Introducing nikki", "Introducing Nikki"),
    ("INterested in Partnership?", "Interested in Partnership?"),
    ("Scarfell Pike", "Scafell Pike"),
    ("Clothes or car boot sale sale", "Clothes or car boot sale"),
    ("If its a big enough", "If it’s a big enough"),
    ("Mean commercial investment does not exist", "Meaning commercial investment does not exist"),
    ("data from an SP02 monitor", "data from an SpO2 monitor"),
    ("blood sugar levels..", "blood sugar levels."),
    ("Syndrome (CCHS) ..", "Syndrome (CCHS)."),
    ("finish the volenteer recruitment page", "finish the volunteer recruitment page"),
    ("I’ll make add a live link", "I’ll add a live link"),
    ("Wash dark colours seperately", "Wash dark colours separately"),
    ("Do no dry clean", "Do not dry clean"),
    ("classic cotton logo tee’s", "classic cotton logo tees"),
    ("a range of competitions an fundraising events", "a range of competitions and fundraising events"),
    ("Festival Illuminations have been lighting up", "Festive Illuminations have been lighting up"),
    ("on the same scal</em><em>e</em>", "on the same scale</em>"),
]
# Stray space before a full stop at the end of headings ("The Children .")
SPACE_BEFORE_STOP = re.compile(r"(\w) \.(?=\s*(<|$))")

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
IMAGES = {}  # remote url -> local path (relative to ROOT)


def load(name):
    with open(os.path.join(CACHE, name)) as f:
        return json.load(f)


def esc(s):
    return _html.escape(s, quote=False)


def clean_text(s):
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip()


def local_image(url):
    """Map a wp-content/uploads URL to assets/uploads/... and queue download."""
    if not url:
        return url
    url = html.unescape(url.strip())
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("/wp-content/"):
        url = SITE + url
    m = re.match(r"https?://(?:www\.)?keepmebreathing\.com/wp-content/uploads/(.+)$", url)
    if not m:
        return url
    rel = urllib.parse.unquote(m.group(1).split("?")[0])
    path = "assets/uploads/" + rel
    IMAGES[url.split("?")[0]] = path
    return BASE + "/" + urllib.parse.quote(path)


def local_link(href):
    if not href:
        return href
    href = html.unescape(href.strip())
    if re.search(r"keepmebreathing\.com/wp-content/uploads/", href):
        return local_image(href)
    m = re.match(r"https?://(?:www\.)?keepmebreathing\.com(/.*)?$", href) or re.match(r"(/(?!/).*)$", href)
    if m:
        path = m.group(1) or "/"
        path = re.sub(r"[?&](per_page|context)=[^&#]*", "", path)
        path = REDIRECTS.get(path, REDIRECTS.get(path.rstrip("/") + "/", path)) if path.split("#")[0] in REDIRECTS or path.rstrip("/") + "/" in REDIRECTS else path
        return BASE + path
    return href


def youtube_embed(url):
    url = html.unescape(url or "")
    m = re.search(r"(?:youtu\.be/|v=|embed/|shorts/)([\w-]{11})", url)
    if not m:
        return None
    start = re.search(r"[?&](?:t|start)=(\d+)", url)
    return "https://www.youtube-nocookie.com/embed/" + m.group(1) + (f"?start={start.group(1)}" if start else "")


def embed_block(src, title="Video"):
    return (f'<div class="kmb-embed"><iframe src="{src}" title="{html.escape(title)}" loading="lazy" '
            'allow="accelerometer; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>')


def bg_url(el):
    m = re.search(r"background-image:\s*url\(['\"]?([^'\")]+)", el.get("style", "") if el else "")
    return m.group(1) if m else None


def img_tag(src, alt=""):
    if not src or src.startswith("data:"):
        return ""
    return f'<img src="{local_image(src)}" alt="{html.escape(clean_text(alt))}" loading="lazy">'


def img_src(img):
    for attr in ("data-src", "data-lazy-src", "src"):
        v = img.get(attr)
        if v and not v.startswith("data:"):
            return v
    return None


# --------------------------------------------------------------------------
# sanitising rich text (text-editor widgets, post bodies)
# --------------------------------------------------------------------------
KEEP = {"p", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "a", "strong", "em", "br",
        "blockquote", "cite", "figure", "figcaption", "img", "table", "thead", "tbody", "tr",
        "td", "th", "sub", "sup", "hr", "audio", "video", "source", "iframe", "details", "summary"}
RENAME = {"b": "strong", "i": "em", "h1": "h2"}
DROP = {"script", "style", "noscript", "svg", "form", "input", "select", "textarea", "button",
        "label", "link", "meta", "option", "colgroup", "col"}


def sanitize(node):
    """Return clean HTML string for a BeautifulSoup node's children."""
    soup = BeautifulSoup(str(node), "lxml")
    body = soup.body or soup
    for c in body.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for t in body.find_all(list(DROP)):
        t.decompose()
    # icon fonts
    for t in body.select("i[class*=fa-], i.fa, span[class*=icon]"):
        t.decompose()
    for t in body.find_all(True):
        if t.name in RENAME:
            t.name = RENAME[t.name]
        if t.name == "u":
            t.unwrap()
            continue
        if t.name == "iframe":
            src = t.get("src", "")
            yt = youtube_embed(src)
            new = BeautifulSoup(embed_block(yt or src, t.get("title") or "Embedded content"), "lxml").div
            t.replace_with(new)
            continue
        if t.name not in KEEP:
            t.unwrap()
            continue
        attrs = {}
        if t.name == "a" and t.get("href"):
            attrs["href"] = local_link(t["href"])
            if attrs["href"].startswith("http") and "keepmebreathing.com" not in attrs["href"]:
                attrs["rel"] = "noopener"
        if t.name == "img":
            src = img_src(t)
            if not src:
                t.decompose()
                continue
            attrs = {"src": local_image(src), "alt": clean_text(t.get("alt", "")), "loading": "lazy"}
        if t.name in ("audio", "video"):
            attrs["controls"] = ""
            if t.get("src"):
                attrs["src"] = local_link(t["src"])
        if t.name == "source" and t.get("src"):
            attrs = {"src": local_link(t["src"])}  # no type: media may be re-encoded (wav -> m4a)
        if t.name == "a" and t.find_parent(["audio", "video"]) and re.match(r"https?://", t.get_text(strip=True)):
            t.string = "Download the recording"
        if t.name in ("td", "th"):
            for k in ("colspan", "rowspan"):
                if t.get(k):
                    attrs[k] = t[k]
        if t.name == "div" and "kmb-embed" in (t.get("class") or []):
            continue
        t.attrs = attrs
    out = body.decode_contents()
    return tidy(out)


def tidy(s):
    s = s.replace("\xa0", " ")
    s = re.sub(r"<p>\s*(<br/?>\s*)*</p>", "", s)
    s = re.sub(r"<(h[2-6]|strong|em|li)>\s*</\1>", "", s)
    s = re.sub(r"(<br/?>\s*){3,}", "<br><br>", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


# --------------------------------------------------------------------------
# Elementor tree -> blocks
# --------------------------------------------------------------------------
def widget(el, ctx):
    w = el.get("data-widget_type", "").split(".")[0]
    c = el.select_one(".elementor-widget-container") or el

    if w in ("heading", "bagja-title", "theme-post-title"):
        h = c.find(re.compile(r"^h[1-6]$")) or c.find(["p", "div", "span"])
        if not h:
            return []
        text = clean_text(h.get_text(" "))
        if not text:
            return []
        level = int(h.name[1]) if h.name and h.name[0] == "h" and h.name[1:].isdigit() else 3
        level = min(max(level, 2), 4)
        a = h.find("a")
        inner = esc(text)
        if a and a.get("href"):
            inner = f'<a href="{local_link(a["href"])}">{inner}</a>'
        return [f"<h{level}>{inner}</h{level}>"]

    if w in ("text-editor", "theme-post-excerpt", "html"):
        out = sanitize(c)
        return [out] if out else []

    if w in ("image", "theme-post-featured-image"):
        img = c.find("img")
        if not img or not img_src(img):
            return []
        cap = c.find("figcaption")
        tag = img_tag(img_src(img), img.get("alt", ""))
        a = c.find("a")
        if a and a.get("href") and not re.search(r"\.(jpe?g|png|gif|webp)$", a["href"], re.I):
            tag = f'<a href="{local_link(a["href"])}">{tag}</a>'
        if cap and clean_text(cap.get_text()):
            return [f"<figure>{tag}<figcaption>{esc(clean_text(cap.get_text()))}</figcaption></figure>"]
        return [f"<figure>{tag}</figure>"]

    if w == "image-box":
        img = c.find("img")
        title = c.select_one(".elementor-image-box-title")
        desc = c.select_one(".elementor-image-box-description")
        parts = []
        if img and img_src(img):
            parts.append(img_tag(img_src(img), img.get("alt") or (title.get_text() if title else "")))
        if title:
            parts.append(f"<h3>{esc(clean_text(title.get_text()))}</h3>")
        if desc:
            d = sanitize(desc)
            parts.append(d if d.startswith("<") else f"<p>{d}</p>")
        return [f'<div class="kmb-person">{"".join(parts)}</div>'] if parts else []

    if w in ("icon-box", "bagja-texticon"):
        title = c.select_one(".elementor-icon-box-title, .icon-title")
        sub = c.select_one(".icon-subtitle")
        desc = c.select_one(".elementor-icon-box-description, .icon-text")
        parts = []
        if title:
            parts.append(f"<h3>{esc(clean_text(title.get_text()))}</h3>")
        if sub:
            parts.append(f'<p class="kmb-card-sub">{esc(clean_text(sub.get_text()))}</p>')
        if desc:
            d = sanitize(desc)
            parts.append(d if d.startswith("<p") else f"<p>{d}</p>")
        return [f'<div class="kmb-card">{"".join(parts)}</div>'] if parts else []

    if w == "bagja-team":
        img = bg_url(c.select_one(".port-img"))
        h = c.find("h3")
        p = c.find("p")
        parts = [img_tag(img, h.get_text() if h else "")] if img else []
        if h:
            parts.append(f"<h3>{esc(clean_text(h.get_text()))}</h3>")
        if p:
            parts.append(f"<p>{esc(clean_text(p.get_text()))}</p>")
        return [f'<div class="kmb-person">{"".join(parts)}</div>']

    if w == "button":
        a = c.find("a")
        if not a:
            return []
        text = clean_text(a.get_text(" "))
        href = a.get("href") or ""
        if not text or not href or href == "#":
            return []
        if re.search(r"/contribute/?$", href):
            text = text or "Donate"
        return [f'<p class="kmb-actions"><a class="kmb-btn kmb-btn--blue" href="{local_link(href)}">{esc(text)}</a></p>']

    if w == "video":
        try:
            st = json.loads(el.get("data-settings") or "{}")
        except ValueError:
            st = {}
        url = st.get("youtube_url") or st.get("vimeo_url") or ""
        yt = youtube_embed(url)
        if yt:
            return [embed_block(yt)]
        hosted = (st.get("hosted_url") or {}).get("url") if isinstance(st.get("hosted_url"), dict) else None
        v = c.find("video")
        src = hosted or (v.get("src") if v else None)
        if src:
            return [f'<video controls preload="metadata" src="{local_link(src)}"></video>']
        return []

    if w in ("gallery", "media-carousel"):
        urls = []
        for a in c.select("[data-thumbnail], a.e-gallery-item, .swiper-slide-image, .elementor-carousel-image, img"):
            u = a.get("data-thumbnail") or a.get("href") or bg_url(a) or (img_src(a) if a.name == "img" else None)
            if u and re.search(r"\.(jpe?g|png|gif|webp)", u, re.I) and u not in urls:
                urls.append(u)
        if not urls:
            return []
        figs = "".join(f'<figure>{img_tag(u)}</figure>' for u in urls)
        thumbs = all(re.search(r"-(\d{2,3})x(\d{2,3})\.\w+$", u) for u in urls)
        return [f'<div class="{"kmb-faces" if thumbs else "kmb-photo-grid"}">{figs}</div>']

    if w == "rdn-slider":
        out = []
        for sl in c.select(".slide"):
            img = bg_url(sl.select_one(".slider-img-bg"))
            t = sl.select_one(".slider-title")
            txt = sl.select_one(".slider-text, .slider-subtitle, p")
            parts = [img_tag(img, t.get_text() if t else "")] if img else []
            if t:
                parts.append(f"<h3>{esc(clean_text(t.get_text()))}</h3>")
            if txt and clean_text(txt.get_text()):
                parts.append(f"<p>{esc(clean_text(txt.get_text()))}</p>")
            for a in sl.select("a[href]"):
                if clean_text(a.get_text()) and a["href"] != "#":
                    parts.append(f'<p><a class="kmb-arrow-link" href="{local_link(a["href"])}">{esc(clean_text(a.get_text()))}</a></p>')
            if parts:
                out.append(f'<div class="kmb-card">{"".join(parts)}</div>')
        return [f'<div class="kmb-grid">{"".join(out)}</div>'] if out else []

    if w in ("bagja-post", "bagja-post-slider"):
        return ['{% include post-cards.html limit=4 %}']

    if w == "counter":
        title = c.select_one(".elementor-counter-title")
        num = c.select_one(".elementor-counter-number")
        pre = c.select_one(".elementor-counter-number-prefix")
        suf = c.select_one(".elementor-counter-number-suffix")
        if not num:
            return []
        try:
            n = f"{int(float(num.get('data-to-value', '0'))):,}"
        except ValueError:
            n = num.get("data-to-value", "")
        val = (pre.get_text().strip() if pre else "") + n + (suf.get_text().strip() if suf else "")
        return [f'<div class="kmb-figure"><span class="kmb-figure-num">{esc(val)}</span>'
                f'<span class="kmb-figure-label">{esc(clean_text(title.get_text()) if title else "")}</span></div>']

    if w == "testimonial":
        content = c.select_one(".elementor-testimonial-content")
        name = c.select_one(".elementor-testimonial-name")
        job = c.select_one(".elementor-testimonial-job")
        if not content:
            return []
        cite = " · ".join(clean_text(x.get_text()) for x in (name, job) if x and clean_text(x.get_text()))
        return [f'<blockquote><p>{esc(clean_text(content.get_text()))}</p>'
                + (f"<cite>{esc(cite)}</cite>" if cite else "") + "</blockquote>"]

    if w == "toggle":
        out = []
        for item in c.select(".elementor-toggle-item"):
            t = item.select_one(".elementor-toggle-title")
            body = item.select_one(".elementor-tab-content")
            out.append(f"<details><summary>{esc(clean_text(t.get_text()) if t else 'More')}</summary>"
                       f"{sanitize(body) if body else ''}</details>")
        return out

    if w == "icon-list":
        items = []
        for li in c.select("li"):
            txt = clean_text(li.get_text(" "))
            a = li.find("a")
            if not txt:
                continue
            items.append(f'<li><a href="{local_link(a["href"])}">{esc(txt)}</a></li>' if a and a.get("href")
                         else f"<li>{esc(txt)}</li>")
        return [f'<ul class="kmb-ticks">{"".join(items)}</ul>'] if items else []

    if w == "animated-headline":
        txt = " ".join(clean_text(s.get_text()) for s in c.select(".elementor-headline-plain-text, .elementor-headline-dynamic-text.elementor-headline-text-active")
                       ) or clean_text(c.get_text(" "))
        return [f'<p class="kmb-callout">{esc(txt)}</p>'] if txt else []

    if w == "form":
        return ['{% include contact-cta.html %}']

    if w == "embedpress_pdf":
        f = c.find("iframe")
        src = f.get("src", "") if f else ""
        m = re.search(r"file=([^&]+)", src)
        pdf = urllib.parse.unquote(m.group(1)) if m else src
        if pdf:
            return [f'<p class="kmb-actions"><a class="kmb-btn kmb-btn--blue" href="{local_link(pdf)}">Read the report (PDF)</a></p>']
        return []

    if w == "loop-grid":
        return []  # dynamic listings are rebuilt from _data in hand-made pages

    # spacer, divider, social-icons, facebook-page, post-navigation, author-box ...
    return []


def is_column(el):
    cls = el.get("class") or []
    return "elementor-column" in cls or ("e-con" in cls and "e-child" in cls)


def container(el, ctx):
    """Elementor section / flex container. Columns with content become a grid."""
    cols = []
    inner = el
    ec = el.find(class_="elementor-container", recursive=False)
    if ec:
        inner = ec
    ecin = inner.find(class_="e-con-inner", recursive=False)
    if ecin:
        inner = ecin
    children = [c for c in inner.find_all(True, recursive=False)]
    col_children = [c for c in children if is_column(c)]
    if len(col_children) >= 2 and len(col_children) == len(children):
        for col in col_children:
            blocks = walk(col, ctx)
            if blocks:
                cols.append(blocks)
        if len(cols) >= 2:
            # columns that are each a single card -> card grid; otherwise side-by-side columns
            simple = all(len(b) == 1 and re.match(r'<div class="kmb-(card|person)"', b[0]) for b in cols)
            if simple:
                return [f'<div class="kmb-grid">' + "".join(b[0] for b in cols) + "</div>"]
            # columns of short text (e.g. a name + a role) read best as cards
            short = all(len(clean_text(BeautifulSoup("".join(b), "lxml").get_text())) < 600
                        and not re.search(r"<(img|iframe|video|div)", "".join(b)) for b in cols)
            if short:
                return ['<div class="kmb-grid">' + "".join(f'<div class="kmb-card">{"".join(b)}</div>' for b in cols) + "</div>"]
            return ['<div class="kmb-split">' + "".join(f"<div>{''.join(b)}</div>" for b in cols) + "</div>"]
        return cols[0] if cols else []
    out = []
    for c in children:
        out.extend(walk(c, ctx))
    return out


def walk(el, ctx):
    if not isinstance(el, Tag):
        return []
    if el.name in ("script", "style"):
        return []
    if el.get("data-widget_type"):
        return widget(el, ctx)
    cls = el.get("class") or []
    if "elementor-section" in cls or "e-con" in cls:
        return container(el, ctx)
    # plain (non-Elementor) markup: block editor posts etc.
    if not any("elementor" in c for c in cls) and el.name not in ("div", "section", "body", "html"):
        out = sanitize(el)
        return [out] if out else []
    out = []
    for c in el.children:
        if isinstance(c, NavigableString):
            t = str(c).strip()
            if t and not isinstance(c, Comment):
                out.append(f"<p>{esc(t)}</p>")
        else:
            out.extend(walk(c, ctx))
    return out


def merge_grids(body):
    """Join back-to-back <div class="kmb-grid"> rows so cards flow as one grid."""
    soup = BeautifulSoup(body, "html.parser")
    for g in soup.select("div.kmb-grid"):
        nxt = g.find_next_sibling()
        while nxt is not None and nxt.name == "div" and nxt.get("class") == ["kmb-grid"]:
            for child in list(nxt.children):
                g.append(child)
            after = nxt.find_next_sibling()
            nxt.decompose()
            nxt = after
    return str(soup)


def convert(content_html, title=""):
    soup = BeautifulSoup(content_html, "lxml")
    blocks = walk(soup.body or soup, {})
    body = "\n".join(b for b in blocks if b and b.strip())
    # drop an early heading that just repeats the page title
    m = re.search(r"<h[2-4]>(.*?)</h[2-4]>", body[:2500])
    if m and title:
        a = re.sub(r"\W+", "", clean_text(BeautifulSoup(m.group(1), "lxml").get_text()).lower())
        b = re.sub(r"\W+", "", clean_text(title).lower())
        if a and (a in b or b in a):
            body = body[:m.start()] + body[m.end():]
    # merge consecutive button paragraphs into one action row
    while True:
        merged = re.sub(r'(<p class="kmb-actions">(?:(?!</p>).)*)</p>\s*<p class="kmb-actions">', r"\1 ", body, flags=re.S)
        if merged == body:
            break
        body = merged
    # leftover theme footers
    body = re.sub(r"<h[2-6]>[^<]*All Rights Reserved[^<]*</h[2-6]>", "", body)
    # consecutive card rows -> one continuous grid
    body = merge_grids(body)
    # merge consecutive photo grids
    body = re.sub(r"</div>\s*<div class=\"kmb-photo-grid\">", "", body)
    return tidy(body)


# --------------------------------------------------------------------------
# writers
# --------------------------------------------------------------------------
def front_matter(d):
    return "---\n" + yaml.safe_dump(d, sort_keys=False, allow_unicode=True, width=1000) + "---\n"


def excerpt_of(html_s, n=180):
    t = clean_text(BeautifulSoup(html_s or "", "lxml").get_text(" "))
    t = re.sub(r"\[[^\]]*\]", "", t)
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return (t[: n - 1].rsplit(" ", 1)[0] + "…") if len(t) > n else t


def correct(text):
    for old, new in CORRECTIONS:
        text = text.replace(old, new)
    return SPACE_BEFORE_STOP.sub(r"\1.", text)


def write(path, text):
    text = correct(text)
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(text)


def featured(p):
    try:
        return p["_embedded"]["wp:featuredmedia"][0]["source_url"]
    except (KeyError, IndexError, TypeError):
        return None


def import_pages():
    pages = load("pages_embed.json")
    for p in pages:
        slug = p["slug"]
        if slug in SKIP_PAGES:
            continue
        meta = PAGE_META.get(slug) or {}
        title = meta.get("title") or clean_text(p["title"]["rendered"])
        body = convert(p["content"]["rendered"], title)
        fm = {"layout": "page", "title": title,
              "permalink": "/" + p["link"].replace(SITE, "").strip("/") + "/"}
        if meta.get("eyebrow"):
            fm["eyebrow"] = meta["eyebrow"]
        fm["description"] = meta.get("lede") or excerpt_of(body)
        if meta.get("lede"):
            fm["lede"] = meta["lede"]
        img = featured(p)
        if img:
            fm["image"] = local_image(img).replace(BASE, "")
        fm["wp_id"] = p["id"]
        write(f"pages/{slug}.html", front_matter(fm) + body + "\n")
        print("page ", fm["permalink"])


def import_posts():
    posts = load("posts_embed.json")
    cats = {c["id"]: c["name"] for c in load("categories.json")}
    for p in posts:
        title = clean_text(p["title"]["rendered"])
        body = convert(p["content"]["rendered"], title)
        date = p["date"][:10]
        fm = {"layout": "post", "title": title, "date": p["date"].replace("T", " "),
              "permalink": p["link"].replace(SITE, ""),
              "categories": [cats.get(c, "") for c in p.get("categories", []) if cats.get(c) and cats.get(c) not in ("Uncategorized", "Uncategorised")],
              "description": excerpt_of(p["excerpt"]["rendered"]) or excerpt_of(body)}
        img = featured(p)
        if img:
            fm["image"] = local_image(img).replace(BASE, "")
            stem = re.sub(r"(-\d+x\d+|-scaled)?\.\w+$", "", os.path.basename(fm["image"]))
            if stem and stem in body:
                fm["cover"] = False  # the same picture already opens the article
        fm["wp_id"] = p["id"]
        write(f"_posts/{date}-{p['slug']}.html", front_matter(fm) + body + "\n")
        print("post ", fm["permalink"])


def import_products():
    shop = BeautifulSoup(open(os.path.join(CACHE, "raw", "shop.html")).read(), "lxml")
    shop_order = [a["href"].rstrip("/").rsplit("/", 1)[-1] for a in shop.select("li.product a.woocommerce-LoopProduct-link, li.product > a")]
    for p in load("products.json"):
        if p["slug"] == "order-nowdreaming-of-breathing-the-adventures-of-casper-beau":
            continue
        raw = open(os.path.join(CACHE, "raw", "product__" + p["slug"] + ".html")).read()
        s = BeautifulSoup(raw, "lxml")
        paypal = [a["href"] for a in s.select('[data-elementor-type="product"] a[href*="paypal.com"]')]
        desc = sanitize(BeautifulSoup(p["short_description"] + p["description"], "lxml").body)
        desc = re.sub(r"<p>[^<]*Want to pay in USD\?.*?</p>", "", desc, flags=re.S)
        desc = re.sub(r'<a href="#">(.*?)</a>', r"\1", desc)
        prices = p["prices"]
        minor = int(prices.get("currency_minor_unit", 2))
        fm = {
            "title": clean_text(p["name"]),
            "price": f"{int(prices['price']) / 10 ** minor:.2f}",
            "description": excerpt_of(desc, 150),
            "images": [local_image(i["src"]).replace(BASE, "") for i in p["images"]],
            "options": [{"name": a["name"], "values": [t["name"] for t in a["terms"]]} for a in p.get("attributes", [])],
            # Paste a Stripe / PayPal / SumUp payment link here for a direct
            # "Buy now" button. Leave empty to take orders by email.
            "buy_url": "",
            "order": shop_order.index(p["slug"]) + 1 if p["slug"] in shop_order else 99,
        }
        rng = prices.get("price_range")
        if rng and rng.get("max_amount") != rng.get("min_amount"):
            fm["price_max"] = f"{int(rng['max_amount']) / 10 ** minor:.2f}"
        if paypal:
            fm["buy_url_usd"] = paypal[0]
        fm["image"] = fm["images"][0] if fm["images"] else None
        write(f"_products/{p['slug']}.html", front_matter(fm) + desc + "\n")
        print("product", p["slug"])


def card_data(it):
    title = it.select_one(".elementor-widget-theme-post-title, h1, h2, h3")
    img = it.select_one("img")
    texts = [clean_text(t.get_text(" ")) for t in it.select(".elementor-widget-text-editor, .elementor-widget-heading p, .elementor-widget-heading h4, .elementor-widget-heading h5")]
    btn = it.select_one("a.elementor-button")
    return {
        "title": clean_text(title.get_text(" ")) if title else "",
        "image": local_image(img_src(img)).replace(BASE, "") if img and img_src(img) else "",
        "texts": [t for t in texts if t],
        "link": local_link(btn["href"]).replace(BASE, "") if btn and btn.get("href") and btn["href"] != "#" else "",
        "link_text": clean_text(btn.get_text()) if btn else "",
    }


def import_events():
    events = load("events_embed.json")
    terms = {43: "past", 75: "upcoming", 82: "talk"}
    cards = {}
    for page in ("events", "gallery", "conferences"):
        s = BeautifulSoup(open(os.path.join(CACHE, "raw", page + ".html")).read(), "lxml")
        for it in s.select(".e-loop-item"):
            d = card_data(it)
            cards[d["title"]] = d
    out = []
    for e in events:
        title = clean_text(e["title"]["rendered"])
        cats = e.get("event_categories", [])
        kind = next((terms[t] for t in (75, 82, 43) if t in cats), "past")
        card = cards.get(title, {})
        texts = [t for t in card.get("texts", []) if t != title]
        item = {"title": title, "kind": kind, "posted": e["date"][:10]}
        img = featured(e) or None
        if card.get("image"):
            item["image"] = card["image"]
        elif img:
            item["image"] = local_image(img).replace(BASE, "")
        if kind in ("upcoming", "talk") and texts:
            # cards show: date, location (talks) or date, location / blurb (upcoming)
            if kind == "talk":
                item["when"] = " ".join(t for t in texts[:-1]) if len(texts) > 1 else texts[0]
                item["where"] = texts[-1] if len(texts) > 1 else ""
            else:
                for t in texts:
                    if re.search(r"\d{1,2}\s+\w+\s+\d{2}", t) and "when" not in item:
                        item["when"] = t
                    elif "where" not in item and len(t) < 60:
                        item["where"] = t
                    else:
                        item["blurb"] = t
        when = re.findall(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{2,4})", item.get("when", ""))
        if when:
            d, mon, y = when[-1]
            months = "january february march april may june july august september october november december".split()
            mi = next((i for i, m in enumerate(months) if m.startswith(mon.lower()[:3])), None)
            if mi is not None:
                y = int(y) + (2000 if len(y) == 2 else 0)
                item["date"] = f"{y:04d}-{mi + 1:02d}-{int(d):02d}"
        link = card.get("link", "")
        if link and not link.startswith("/events/"):
            item["link"] = link
            item["link_text"] = card.get("link_text") or "Find out more"
        out.append(item)
        REDIRECTS[e["link"].replace(SITE, "")] = "/events/" if kind == "upcoming" else ("/conferences/" if kind == "talk" else "/gallery/")
    out.sort(key=lambda x: x["posted"], reverse=True)
    write("_data/events.yml", "# Events. kind: upcoming | past | talk\n"
          + yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=1000))


def import_partners():
    s = BeautifulSoup(open(os.path.join(CACHE, "raw", "partners.html")).read(), "lxml")
    seen, out = set(), []
    grids = s.select('[data-widget_type="loop-grid.post"]')
    for gi, g in enumerate(grids):
        for it in g.select(".e-loop-item"):
            d = card_data(it)
            if not d["title"] or d["title"] in seen:
                continue
            seen.add(d["title"])
            out.append({"name": d["title"], "headline": gi == 0, "logo": d["image"],
                        "blurb": " ".join(t for t in d["texts"] if t != d["title"]).lstrip(". "), "url": d["link"]})
    for p in load("partners_embed.json"):
        REDIRECTS[p["link"].replace(SITE, "")] = "/partners/"
        name = clean_text(p["title"]["rendered"])
        if name not in seen:
            seen.add(name)
            out.append({"name": name, "headline": False, "logo": "", "blurb": "", "url": ""})
    write("_data/partners.yml", "# Partners & sponsors. headline: true shows them in the top band.\n"
          + yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=1000))


def write_redirects():
    """One stub per retired URL; jekyll-redirect-from turns each into a redirect page."""
    for old, new in sorted(REDIRECTS.items()):
        name = old.strip("/").replace("/", "--") or "root"
        write(f"_redirects/{name}.html", front_matter({"permalink": old, "redirect_to": new}))


def download_images():
    def get(item):
        url, path = item
        full = os.path.join(ROOT, path)
        if os.path.exists(full) and os.path.getsize(full) > 0:
            return None
        stem, ext = os.path.splitext(full)
        if any(os.path.exists(stem + alt) for alt in {".png": [".jpg"], ".wav": [".m4a"]}.get(ext.lower(), [])):
            return None  # already downloaded and converted by optimise_media()
        os.makedirs(os.path.dirname(full), exist_ok=True)
        r = subprocess.run(["curl", "-sfL", "-H", f"User-Agent: {UA}", "-o", full, url], capture_output=True)
        if r.returncode != 0:
            if os.path.exists(full):
                os.remove(full)
            return url
        return None

    with ThreadPoolExecutor(8) as ex:
        failed = [u for u in ex.map(get, IMAGES.items()) if u]
    print(f"images: {len(IMAGES)} referenced, {len(failed)} failed")
    for u in failed:
        print("  FAILED", u)


def sips_info(full):
    r = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", "-g", "hasAlpha", full],
                       capture_output=True, text=True).stdout
    get = lambda k: (re.search(k + r": (\S+)", r) or [None, ""])[1]
    try:
        return int(get("pixelWidth")), int(get("pixelHeight")), get("hasAlpha") == "yes"
    except ValueError:
        return 0, 0, False


def png_is_opaque(full):
    """Canva/Photoshop exports often carry an alpha channel that is fully opaque."""
    try:
        from PIL import Image
        with Image.open(full) as im:
            if im.mode in ("RGBA", "LA"):
                return im.getchannel("A").getextrema()[0] == 255
            return im.mode in ("RGB", "L", "P") and "transparency" not in im.info
    except Exception:
        return False


def reencode_jpeg(full, quality=80):
    """Re-save without bloated metadata/ICC blobs; keep whichever file is smaller."""
    try:
        from PIL import Image
        tmp = full + ".tmp.jpg"
        with Image.open(full) as im:
            im.convert("RGB").save(tmp, "JPEG", quality=quality, optimize=True, progressive=True)
        if os.path.getsize(tmp) < os.path.getsize(full):
            os.replace(tmp, full)
        else:
            os.remove(tmp)
    except Exception:
        pass


def optimise_media(max_px=1800):
    """Shrink what WordPress served: resize huge images, convert opaque PNG posters
    to JPEG, WAV -> AAC, compress big PDFs/videos. Rewrites references afterwards."""
    renames = {}
    run = lambda *a: subprocess.run(list(a), capture_output=True)
    for path in sorted(set(IMAGES.values())):
        full = os.path.join(ROOT, path)
        if not os.path.exists(full):
            continue
        ext = os.path.splitext(path)[1].lower()
        size = os.path.getsize(full)
        if ext in (".png", ".jpg", ".jpeg", ".webp"):
            w, h, alpha = sips_info(full)
            if max(w, h) > max_px:
                run("sips", "-Z", str(max_px), full)
            if ext == ".png" and alpha and os.path.getsize(full) > 300_000:
                alpha = not png_is_opaque(full)
            if ext == ".png" and not alpha and os.path.getsize(full) > 300_000:
                new = path[:-4] + ".jpg"
                run("sips", "-s", "format", "jpeg", "-s", "formatOptions", "80", full, "--out", os.path.join(ROOT, new))
                if os.path.exists(os.path.join(ROOT, new)):
                    os.remove(full)
                    renames[path] = new
            elif ext in (".jpg", ".jpeg") and size > 300_000:
                reencode_jpeg(full)
        elif ext == ".wav":
            new = path[:-4] + ".m4a"
            run("afconvert", "-f", "m4af", "-d", "aac", "-b", "96000", full, os.path.join(ROOT, new))
            if os.path.exists(os.path.join(ROOT, new)):
                os.remove(full)
                renames[path] = new
        elif ext == ".pdf" and size > 10_000_000:
            tmp = full + ".tmp.pdf"
            run("gs", "-sDEVICE=pdfwrite", "-dPDFSETTINGS=/ebook", "-dNOPAUSE", "-dQUIET", "-dBATCH", f"-sOutputFile={tmp}", full)
            if os.path.exists(tmp) and 0 < os.path.getsize(tmp) < size:
                os.replace(tmp, full)
            elif os.path.exists(tmp):
                os.remove(tmp)
        elif ext in (".mp4", ".mov") and size > 25_000_000:
            tmp = full + ".tmp.mp4"
            run("avconvert", "--preset", "PresetAppleM4VWiFi", "--source", full, "--output", tmp, "--replace")
            if os.path.exists(tmp) and 0 < os.path.getsize(tmp) < size:
                os.replace(tmp, full)
            elif os.path.exists(tmp):
                os.remove(tmp)
    print(f"optimised media; {len(renames)} files converted")


def apply_renames():
    """Point references at converted files (png->jpg, wav->m4a). Safe to re-run."""
    renames = {}
    for path in set(IMAGES.values()):
        if os.path.exists(os.path.join(ROOT, path)):
            continue
        stem, ext = os.path.splitext(path)
        for alt in {".png": [".jpg"], ".wav": [".m4a"]}.get(ext.lower(), []):
            if os.path.exists(os.path.join(ROOT, stem + alt)):
                renames[path] = stem + alt
    targets = ["index.html"]
    for d in ("pages", "_posts", "_products", "_data"):
        targets += [os.path.join(d, f) for f in os.listdir(os.path.join(ROOT, d))]
    for t in targets:
        full = os.path.join(ROOT, t)
        text = open(full).read()
        new = text
        for a, b in renames.items():
            new = new.replace(urllib.parse.quote(a), urllib.parse.quote(b)).replace(a, b)
        if new != text:
            open(full, "w").write(new)
    missing = [p for p in set(IMAGES.values()) if p not in renames and not os.path.exists(os.path.join(ROOT, p))]
    print(f"references updated for {len(renames)} converted files; {len(missing)} missing")


def extra_images():
    """Images used by hand-built templates (logo, homepage, icons)."""
    for u in [
        "/wp-content/uploads/2022/10/KMB-Blue-Logo-RGB.png",
        "/wp-content/uploads/2022/09/KMB-Blue-icon-RGB-300x300.png",
        "/wp-content/uploads/2022/09/KMB-Blue-icon-RGB-150x150.png",
    ]:
        local_image(SITE + u)
    home = open(os.path.join(CACHE, "home_widget.html")).read()
    for u in re.findall(r'src="(https://keepmebreathing\.com/wp-content/uploads/[^"]+)"', home):
        local_image(u)


if __name__ == "__main__":
    import_pages()
    import_posts()
    import_products()
    import_events()
    import_partners()
    extra_images()
    write_redirects()
    if "--no-images" not in sys.argv:
        download_images()
        optimise_media()
    apply_renames()
