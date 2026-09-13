from collections import defaultdict
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crawler.language import discover_prefix_langs, infer_default_lang, lang_from_path, normalize_locale
from app.crawler.normalize import expand_hosts, host_of
from app.crawler.robots import sitemap_candidates
from app.crawler.sitemap import fetch_sitemap_urls
from app.models import Crawl, Hreflang, Link, Page
from app.schemas import (
    GraphEdgeOut,
    GraphNodeOut,
    GraphOut,
    LanguageGroupOut,
    LanguageReportOut,
    LanguageStatOut,
    LanguageVersionOut,
    PageGroupListOut,
)


def page_language(page: Page, prefix_langs: set[str], default_lang: str) -> str:
    if page.lang:
        return page.lang
    html = normalize_locale(page.html_lang)
    if html:
        return html
    return lang_from_path(page.url, prefix_langs) or default_lang


def _union_find(pairs: list[tuple[str, str]]) -> dict[str, set[str]]:
    parent: dict[str, str] = {}

    def find(item: str) -> str:
        parent.setdefault(item, item)
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for left, right in pairs:
        union(left, right)

    groups: dict[str, set[str]] = defaultdict(set)
    for item in parent:
        groups[find(item)].add(item)
    return groups


def _slug_clusters(pages: list[Page], prefix_langs: set[str], default_lang: str) -> dict[str, dict[str, str]]:
    by_slug: dict[str, dict[str, str]] = defaultdict(dict)
    for page in pages:
        lang = page_language(page, prefix_langs, default_lang)
        by_slug[strip_lang_prefix(page.url, prefix_langs)][lang] = page.url
    return {key: mapping for key, mapping in by_slug.items() if len(mapping) > 1 or prefix_langs}


async def ensure_hreflang(session: AsyncSession, crawl_id: int, seed_url: str) -> None:
    existing = await session.scalar(select(func.count(Hreflang.id)).where(Hreflang.crawl_id == crawl_id))
    if existing:
        return
    host = host_of(seed_url)
    allowed = expand_hosts([host] if host else [])
    timeout = httpx.Timeout(settings.request_timeout)
    headers = {"User-Agent": settings.user_agent}
    try:
        async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
            _urls, pairs = await fetch_sitemap_urls(client, sitemap_candidates(seed_url), allowed)
    except httpx.HTTPError:
        return
    for source, lang, target in pairs:
        session.add(Hreflang(crawl_id=crawl_id, from_url=source, lang=lang, to_url=target))
    if pairs:
        await session.commit()


async def assign_page_languages(session: AsyncSession, crawl_id: int, seed_url: str) -> str:
    crawl = await session.get(Crawl, crawl_id)
    mode = (getattr(crawl, "language_mode", None) if crawl else None) or "auto"
    override = (getattr(crawl, "default_lang", None) if crawl else None) or None

    pages = (await session.execute(select(Page).where(Page.crawl_id == crawl_id))).scalars().all()
    rows = (await session.execute(select(Hreflang).where(Hreflang.crawl_id == crawl_id))).scalars().all()
    pairs = [(row.from_url, row.lang, row.to_url) for row in rows]

    if mode == "off":
        default_lang = override or "default"
        changed = False
        for page in pages:
            if page.lang != default_lang:
                page.lang = default_lang
                changed = True
        if changed:
            await session.commit()
        return default_lang

    prefix_langs = discover_prefix_langs([page.url for page in pages]) if mode in {"auto", "path"} else set()
    html_langs = [lang for lang in (normalize_locale(page.html_lang) for page in pages) if lang]
    default_lang = override or infer_default_lang(pairs, seed_url, html_langs)

    url_lang: dict[str, str] = {}
    if mode in {"auto", "hreflang"}:
        for row in rows:
            if row.lang != "x-default":
                url_lang[row.to_url] = row.lang

    changed = False
    for page in pages:
        if mode == "path":
            lang = lang_from_path(page.url, prefix_langs) or normalize_locale(page.html_lang) or default_lang
        elif mode == "hreflang":
            lang = url_lang.get(page.url) or normalize_locale(page.html_lang) or default_lang
        else:
            lang = url_lang.get(page.url) or page_language(page, prefix_langs, default_lang)
        if page.lang != lang:
            page.lang = lang
            changed = True
    if changed:
        await session.commit()
    return default_lang


async def _translation_groups(
    session: AsyncSession, crawl_id: int, seed_url: str
) -> tuple[str, list[str], list[LanguageGroupOut], dict[str, int]]:
    crawl = await session.get(Crawl, crawl_id)
    mode = (getattr(crawl, "language_mode", None) if crawl else None) or "auto"

    await ensure_hreflang(session, crawl_id, seed_url)
    default_lang = await assign_page_languages(session, crawl_id, seed_url)
    pages = (await session.execute(select(Page).where(Page.crawl_id == crawl_id).order_by(Page.url))).scalars().all()
    html_pages = [page for page in pages if page.status_code == 200]
    prefix_langs = discover_prefix_langs([page.url for page in pages]) if mode in {"auto", "path"} else set()
    rows = (await session.execute(select(Hreflang).where(Hreflang.crawl_id == crawl_id))).scalars().all()
    page_by_url = {page.url: page for page in html_pages}

    if mode == "off":
        site_langs = [default_lang]
        groups: list[LanguageGroupOut] = []
        for page in html_pages:
            versions = {
                default_lang: LanguageVersionOut(
                    lang=default_lang,
                    url=page.url,
                    page_id=page.id,
                    title=page.title,
                    word_count=page.word_count,
                )
            }
            groups.append(
                LanguageGroupOut(
                    source_url=page.url,
                    source_lang=default_lang,
                    versions=versions,
                    missing=[],
                    word_gap=None,
                )
            )
        return default_lang, site_langs, groups, {}

    if rows and mode in {"auto", "hreflang"}:
        clusters = _union_find([(row.from_url, row.to_url) for row in rows])
        url_to_root = {url: root for root, members in clusters.items() for url in members}
        lang_urls: dict[str, dict[str, str]] = defaultdict(dict)
        for row in rows:
            if row.lang == "x-default":
                continue
            root = url_to_root.get(row.to_url) or url_to_root.get(row.from_url) or row.to_url
            lang_urls[root][row.lang] = row.to_url
    elif mode in {"auto", "path"}:
        lang_urls = _slug_clusters(html_pages, prefix_langs, default_lang)
    else:
        lang_urls = {}

    site_langs = sorted(
        {page_language(page, prefix_langs, default_lang) for page in html_pages}
        | {lang for mapping in lang_urls.values() for lang in mapping}
    )
    if not site_langs:
        site_langs = [default_lang]

    if len(site_langs) <= 1 or mode == "off":
        lang = site_langs[0]
        groups = []
        for page in html_pages:
            versions = {
                lang: LanguageVersionOut(
                    lang=lang,
                    url=page.url,
                    page_id=page.id,
                    title=page.title,
                    word_count=page.word_count,
                )
            }
            groups.append(
                LanguageGroupOut(
                    source_url=page.url,
                    source_lang=lang,
                    versions=versions,
                    missing=[],
                    word_gap=None,
                )
            )
        return default_lang, [lang], groups, {}

    groups = []
    missing_by_lang: dict[str, int] = defaultdict(int)
    grouped_urls: set[str] = set()
    for mapping in lang_urls.values():
        versions: dict[str, LanguageVersionOut] = {}
        for lang in site_langs:
            url = mapping.get(lang)
            page = page_by_url.get(url) if url else None
            versions[lang] = LanguageVersionOut(
                lang=lang,
                url=url,
                page_id=page.id if page else None,
                title=page.title if page else None,
                word_count=page.word_count if page else None,
            )
            if url:
                grouped_urls.add(url)
        present = [lang for lang, item in versions.items() if item.url]
        if len(present) >= 2:
            for lang in site_langs:
                if versions[lang].page_id is None:
                    missing_by_lang[lang] += 1
        if len(present) < 2 and not rows:
            continue
        source = versions.get(default_lang) or next((item for item in versions.values() if item.url), None)
        groups.append(
            LanguageGroupOut(
                source_url=source.url if source and source.url else next(iter(mapping.values()), ""),
                source_lang=default_lang if default_lang in mapping else (present[0] if present else default_lang),
                versions=versions,
                missing=[lang for lang in site_langs if versions[lang].page_id is None],
                word_gap=word_gap(versions),
            )
        )

    for page in pages:
        if page.url in grouped_urls:
            continue
        lang = page_language(page, prefix_langs, default_lang)
        versions = {
            item: LanguageVersionOut(lang=item, url=None, page_id=None, title=None, word_count=None)
            for item in site_langs
        }
        versions[lang] = LanguageVersionOut(
            lang=lang,
            url=page.url,
            page_id=page.id,
            title=page.title,
            word_count=page.word_count,
        )
        groups.append(
            LanguageGroupOut(
                source_url=page.url,
                source_lang=lang,
                versions=versions,
                missing=[item for item in site_langs if item != lang],
                word_gap=None,
            )
        )
    return default_lang, site_langs, groups, missing_by_lang


async def language_report(session: AsyncSession, crawl_id: int, seed_url: str) -> LanguageReportOut:
    default_lang, site_langs, groups, missing_by_lang = await _translation_groups(session, crawl_id, seed_url)
    pages = (await session.execute(select(Page).where(Page.crawl_id == crawl_id))).scalars().all()
    html_pages = [page for page in pages if page.status_code == 200]
    prefix_langs = discover_prefix_langs([page.url for page in pages])

    clusters = [group for group in groups if sum(1 for item in group.versions.values() if item.url) >= 2]
    clusters.sort(key=lambda item: (-len(item.missing), item.source_url))
    missing_groups = [group for group in clusters if group.missing]
    thin_groups = [
        group for group in clusters if not group.missing and group.word_gap is not None and group.word_gap >= 150
    ]
    thin_groups.sort(key=lambda item: -(item.word_gap or 0))

    stats = []
    for lang in site_langs:
        lang_pages = [page for page in html_pages if page_language(page, prefix_langs, default_lang) == lang]
        words = [page.word_count for page in lang_pages]
        stats.append(
            LanguageStatOut(
                lang=lang,
                is_default=lang == default_lang,
                pages=len(lang_pages),
                words=sum(words),
                avg_words=round(sum(words) / len(words), 1) if words else 0,
                missing_translations=missing_by_lang[lang],
            )
        )

    return LanguageReportOut(
        default_lang=default_lang,
        languages=stats,
        groups=missing_groups,
        thin_groups=thin_groups[:80],
        group_count=len(clusters),
        complete_groups=len(clusters) - len(missing_groups),
    )


def _group_matches(group: LanguageGroupOut, q: str | None, lang: str | None) -> bool:
    if lang:
        version = group.versions.get(lang)
        if version is None or version.page_id is None:
            return False
    if not q:
        return True
    needle = q.lower()
    for version in group.versions.values():
        haystack = " ".join(filter(None, [version.url, version.title, version.lang]))
        if needle in haystack.lower():
            return True
    return needle in group.source_url.lower()


async def list_page_groups(
    session: AsyncSession,
    crawl_id: int,
    seed_url: str,
    q: str | None = None,
    lang: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> PageGroupListOut:
    default_lang, site_langs, groups, _missing = await _translation_groups(session, crawl_id, seed_url)
    groups.sort(key=lambda item: (len(item.missing), item.source_url))
    filtered = [group for group in groups if _group_matches(group, q, lang)]
    return PageGroupListOut(
        items=filtered[offset : offset + limit],
        total=len(filtered),
        languages=site_langs,
        default_lang=default_lang,
    )


async def crawl_graph(session: AsyncSession, crawl_id: int, seed_url: str) -> GraphOut:
    default_lang, site_langs, groups, _missing = await _translation_groups(session, crawl_id, seed_url)
    pages = (await session.execute(select(Page).where(Page.crawl_id == crawl_id))).scalars().all()
    page_by_url = {page.url: page for page in pages}

    def group_sort_key(group: LanguageGroupOut) -> tuple[int, str]:
        source = group.versions.get(default_lang) or group.versions.get(group.source_lang)
        page = page_by_url.get(source.url) if source and source.url else None
        depth = page.depth if page and page.depth is not None else 999
        return (depth, group.source_url)

    nodes: list[GraphNodeOut] = []
    url_to_id: dict[str, str] = {}
    for group in sorted(groups, key=group_sort_key):
        group_id = group.source_url
        for lang in site_langs:
            version = group.versions.get(lang)
            if not version or not version.url or not version.page_id:
                continue
            page = page_by_url.get(version.url)
            node_id = f"p{version.page_id}"
            url_to_id[version.url] = node_id
            nodes.append(
                GraphNodeOut(
                    id=node_id,
                    page_id=version.page_id,
                    url=version.url,
                    title=version.title,
                    lang=lang,
                    group_id=group_id,
                    word_count=version.word_count or 0,
                    depth=page.depth if page else None,
                    inbound_internal=page.inbound_internal if page else 0,
                    outbound_internal=page.outbound_internal if page else 0,
                )
            )

    edges: list[GraphEdgeOut] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def add_edge(source: str, target: str, kind: str, sitewide: bool = False, weight: int = 1) -> None:
        if source == target:
            return
        key = (source, target, kind)
        reverse = (target, source, kind)
        if kind == "hreflang" and reverse in seen_edges:
            return
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append(
            GraphEdgeOut(
                id=f"{kind}-{source}-{target}",
                source=source,
                target=target,
                kind=kind,
                sitewide=sitewide,
                weight=weight,
            )
        )

    for group in groups:
        present = [group.versions[lang] for lang in site_langs if group.versions.get(lang) and group.versions[lang].page_id]
        for left, right in zip(present, present[1:]):
            source = url_to_id.get(left.url or "")
            target = url_to_id.get(right.url or "")
            if source and target:
                add_edge(source, target, "hreflang")

    links = (
        await session.execute(
            select(Link.from_url, Link.to_url).where(
                Link.crawl_id == crawl_id,
                Link.kind == "internal",
                Link.from_url != Link.to_url,
            )
        )
    ).all()
    node_by_id = {node.id: node for node in nodes}
    lang_page_count: dict[str, int] = defaultdict(int)
    for node in nodes:
        lang_page_count[node.lang] += 1

    incoming: dict[str, set[str]] = defaultdict(set)
    directed: list[tuple[str, str]] = []
    for from_url, to_url in links:
        source = url_to_id.get(from_url)
        target = url_to_id.get(to_url)
        if not source or not target:
            continue
        directed.append((source, target))
        incoming[target].add(source)

    for source, target in directed:
        target_node = node_by_id[target]
        threshold = max(3, int(lang_page_count.get(target_node.lang, 0) * 0.4))
        sitewide = len(incoming[target]) >= threshold
        add_edge(source, target, "link", sitewide=sitewide, weight=1)

    return GraphOut(
        languages=site_langs,
        default_lang=default_lang,
        multilingual=len(site_langs) > 1,
        nodes=nodes,
        edges=edges,
    )


def strip_lang_prefix(url: str, prefix_langs: set[str]) -> str:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if parts and lang_from_path(url, prefix_langs):
        parts = parts[1:]
    path = "/" + "/".join(parts) if parts else "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


async def page_alternates(session: AsyncSession, crawl_id: int, url: str) -> list[LanguageVersionOut]:
    rows = (await session.execute(select(Hreflang).where(Hreflang.crawl_id == crawl_id))).scalars().all()
    if not rows:
        return []
    clusters = _union_find([(row.from_url, row.to_url) for row in rows])
    members = next((group for group in clusters.values() if url in group), {url})
    pages = (
        await session.execute(select(Page).where(Page.crawl_id == crawl_id, Page.url.in_(members)))
    ).scalars().all()
    page_by_url = {page.url: page for page in pages}
    seen: dict[str, LanguageVersionOut] = {}
    for row in rows:
        if row.lang == "x-default" or row.to_url not in members:
            continue
        page = page_by_url.get(row.to_url)
        seen[row.lang] = LanguageVersionOut(
            lang=row.lang,
            url=row.to_url,
            page_id=page.id if page else None,
            title=page.title if page else None,
            word_count=page.word_count if page else None,
        )
    return list(seen.values())


def word_gap(versions: dict[str, LanguageVersionOut]) -> int | None:
    counts = [item.word_count for item in versions.values() if item.word_count]
    if len(counts) < 2:
        return None
    return max(counts) - min(counts)
