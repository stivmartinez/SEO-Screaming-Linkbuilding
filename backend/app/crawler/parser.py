from dataclasses import dataclass, field

from selectolax.parser import HTMLParser

from app.crawler.language import normalize_locale
from app.crawler.normalize import is_internal, normalize_url


@dataclass
class ExtractedLink:
    url: str
    kind: str
    anchor: str | None
    rel: str | None


@dataclass
class ParsedPage:
    title: str | None = None
    meta_description: str | None = None
    h1: str | None = None
    h1_count: int = 0
    canonical: str | None = None
    robots_meta: str | None = None
    word_count: int = 0
    html_lang: str | None = None
    hreflangs: list[tuple[str, str]] = field(default_factory=list)
    links: list[ExtractedLink] = field(default_factory=list)


def _attr(node, name: str) -> str | None:
    if node is None:
        return None
    value = node.attributes.get(name)
    return value.strip() if value else None


def _meta_content(tree: HTMLParser, name: str) -> str | None:
    for node in tree.css("meta"):
        meta_name = (node.attributes.get("name") or "").strip().lower()
        if meta_name == name:
            return _attr(node, "content")
    return None


def parse_html(html: str, base_url: str, allowed_hosts: set[str]) -> ParsedPage:
    tree = HTMLParser(html)
    parsed = ParsedPage()

    title_node = tree.css_first("title")
    parsed.title = title_node.text(strip=True) if title_node else None
    if parsed.title == "":
        parsed.title = None

    parsed.meta_description = _meta_content(tree, "description")
    parsed.robots_meta = _meta_content(tree, "robots")

    canonical = None
    for node in tree.css("link"):
        rel = (node.attributes.get("rel") or "").strip().lower()
        if rel == "canonical":
            canonical = _attr(node, "href")
            break
    parsed.canonical = normalize_url(canonical, base_url) if canonical else None

    html_node = tree.css_first("html")
    parsed.html_lang = normalize_locale(_attr(html_node, "lang")) if html_node else None
    for node in tree.css("link"):
        rel = (node.attributes.get("rel") or "").strip().lower()
        if rel != "alternate":
            continue
        href = _attr(node, "href")
        lang = normalize_locale(_attr(node, "hreflang"))
        if href and lang:
            target = normalize_url(href, base_url)
            if target:
                parsed.hreflangs.append((lang, target))

    h1_texts = [node.text(strip=True) for node in tree.css("h1") if node.text(strip=True)]
    parsed.h1_count = len(h1_texts)
    parsed.h1 = h1_texts[0] if h1_texts else None

    for tag in tree.css("script, style, noscript, svg"):
        tag.decompose()
    body = tree.body
    text = body.text(separator=" ") if body else tree.text(separator=" ")
    parsed.word_count = len(text.split()) if text else 0

    seen: set[tuple[str, str | None]] = set()
    for anchor in tree.css("a[href]"):
        href = _attr(anchor, "href")
        if not href:
            continue
        url = normalize_url(href, base_url)
        if not url:
            continue
        rel = _attr(anchor, "rel")
        text_anchor = anchor.text(strip=True) or None
        key = (url, text_anchor)
        if key in seen:
            continue
        seen.add(key)
        parsed.links.append(
            ExtractedLink(
                url=url,
                kind="internal" if is_internal(url, allowed_hosts) else "external",
                anchor=text_anchor,
                rel=rel,
            )
        )
    return parsed


def is_indexable(
    status_code: int | None,
    content_type: str | None,
    robots_meta: str | None,
    x_robots_tag: str | None,
) -> bool:
    if status_code != 200:
        return False
    if content_type and "html" not in content_type.lower():
        return False
    directives = " ".join(filter(None, [robots_meta, x_robots_tag])).lower()
    return "noindex" not in directives
