from dataclasses import dataclass, field
from xml.etree import ElementTree as ET
import gzip
import io

import httpx

from app.crawler.language import normalize_locale
from app.crawler.normalize import is_internal, normalize_url


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


@dataclass
class SitemapDocument:
    urls: list[str] = field(default_factory=list)
    nested: list[str] = field(default_factory=list)
    hreflangs: list[tuple[str, str, str]] = field(default_factory=list)


def parse_sitemap(xml_text: str) -> SitemapDocument:
    document = SitemapDocument()
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return document

    if _local_tag(root.tag) == "sitemapindex":
        for node in root.iter():
            if _local_tag(node.tag) == "loc" and node.text:
                document.nested.append(node.text.strip())
        return document

    for url_node in root:
        if _local_tag(url_node.tag) != "url":
            continue
        loc = None
        for child in url_node:
            if _local_tag(child.tag) == "loc" and child.text:
                loc = child.text.strip()
                document.urls.append(loc)
            if _local_tag(child.tag) == "link":
                href = child.attrib.get("href")
                hreflang = normalize_locale(child.attrib.get("hreflang"))
                if loc and href and hreflang:
                    document.hreflangs.append((loc, hreflang, href))
    return document


def _decode_sitemap_body(url: str, content_type: str, raw: bytes) -> str | None:
    lowered = url.lower()
    encoding = content_type.lower()
    if lowered.endswith(".gz") or "gzip" in encoding or "x-gzip" in encoding:
        try:
            return gzip.decompress(raw).decode("utf-8", errors="replace")
        except OSError:
            try:
                return gzip.GzipFile(fileobj=io.BytesIO(raw)).read().decode("utf-8", errors="replace")
            except OSError:
                return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


async def fetch_sitemap_urls(
    client: httpx.AsyncClient,
    candidates: list[str],
    allowed_hosts: set[str],
    max_sitemaps: int = 40,
) -> tuple[list[str], list[tuple[str, str, str]]]:
    discovered: list[str] = []
    hreflangs: list[tuple[str, str, str]] = []
    seen_maps: set[str] = set()
    queue = list(candidates)

    while queue and len(seen_maps) < max_sitemaps:
        sitemap_url = queue.pop(0)
        if sitemap_url in seen_maps:
            continue
        seen_maps.add(sitemap_url)
        try:
            response = await client.get(sitemap_url, follow_redirects=True)
            if response.status_code >= 400:
                continue
            content_type = response.headers.get("content-type", "")
            if "html" in content_type and "xml" not in content_type and not sitemap_url.lower().endswith(".gz"):
                continue
            text = _decode_sitemap_body(sitemap_url, content_type, response.content)
            if not text:
                continue
            document = parse_sitemap(text)
            for loc in document.nested:
                normalized = normalize_url(loc)
                queue.append(normalized or loc)
            for loc in document.urls:
                normalized = normalize_url(loc)
                if normalized and is_internal(normalized, allowed_hosts):
                    discovered.append(normalized)
            for source, lang, target in document.hreflangs:
                from_url = normalize_url(source)
                to_url = normalize_url(target)
                if from_url and to_url:
                    hreflangs.append((from_url, lang, to_url))
        except httpx.HTTPError:
            continue

    unique: list[str] = []
    seen_pages: set[str] = set()
    for url in discovered:
        if url not in seen_pages:
            seen_pages.add(url)
            unique.append(url)

    unique_pairs: list[tuple[str, str, str]] = []
    seen_pairs: set[tuple[str, str, str]] = set()
    for pair in hreflangs:
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            unique_pairs.append(pair)
    return unique, unique_pairs
