import json
from collections import defaultdict, deque

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Link, Page, SitemapUrl
from app.schemas import DuplicateTitleGroup, IssuesOut, OrphanOut, PageOut


def page_to_out(page: Page) -> PageOut:
    chain: list[str] = []
    if page.redirect_chain:
        try:
            chain = json.loads(page.redirect_chain)
        except json.JSONDecodeError:
            chain = []
    return PageOut(
        id=page.id,
        crawl_id=page.crawl_id,
        url=page.url,
        final_url=page.final_url,
        status_code=page.status_code,
        content_type=page.content_type,
        title=page.title,
        meta_description=page.meta_description,
        h1=page.h1,
        h1_count=page.h1_count,
        canonical=page.canonical,
        robots_meta=page.robots_meta,
        indexable=page.indexable,
        word_count=page.word_count,
        depth=page.depth,
        redirect_chain=chain,
        inbound_internal=page.inbound_internal,
        outbound_internal=page.outbound_internal,
        outbound_external=page.outbound_external,
        lang=page.lang,
        html_lang=page.html_lang,
        fetched_at=page.fetched_at,
        error=page.error,
    )


async def recompute_link_counts(session: AsyncSession, crawl_id: int) -> None:
    inbound_rows = await session.execute(
        select(Link.to_url, func.count(Link.id))
        .where(
            Link.crawl_id == crawl_id,
            Link.kind == "internal",
            Link.from_url != Link.to_url,
        )
        .group_by(Link.to_url)
    )
    inbound = {url: count for url, count in inbound_rows.all()}

    outbound_rows = await session.execute(
        select(Link.from_url, Link.kind, func.count(Link.id))
        .where(Link.crawl_id == crawl_id)
        .group_by(Link.from_url, Link.kind)
    )
    outbound_internal: dict[str, int] = defaultdict(int)
    outbound_external: dict[str, int] = defaultdict(int)
    for from_url, kind, count in outbound_rows.all():
        if kind == "internal":
            outbound_internal[from_url] = count
        else:
            outbound_external[from_url] = count

    pages = (await session.execute(select(Page).where(Page.crawl_id == crawl_id))).scalars().all()
    for page in pages:
        page.inbound_internal = inbound.get(page.url, 0)
        page.outbound_internal = outbound_internal.get(page.url, 0)
        page.outbound_external = outbound_external.get(page.url, 0)
    await session.commit()


async def recompute_depths(session: AsyncSession, crawl_id: int, seed_url: str) -> None:
    pages = (await session.execute(select(Page).where(Page.crawl_id == crawl_id))).scalars().all()
    links = (
        await session.execute(
            select(Link.from_url, Link.to_url).where(
                Link.crawl_id == crawl_id,
                Link.kind == "internal",
                Link.from_url != Link.to_url,
            )
        )
    ).all()
    graph: dict[str, list[str]] = defaultdict(list)
    for from_url, to_url in links:
        graph[from_url].append(to_url)

    depths: dict[str, int] = {seed_url: 0}
    queue = deque([seed_url])
    while queue:
        current = queue.popleft()
        for dest in graph[current]:
            if dest not in depths:
                depths[dest] = depths[current] + 1
                queue.append(dest)

    for page in pages:
        page.depth = depths.get(page.url)
    await session.commit()


async def list_orphans(session: AsyncSession, crawl_id: int) -> list[OrphanOut]:
    pages = (
        await session.execute(select(Page).where(Page.crawl_id == crawl_id, Page.status_code == 200))
    ).scalars().all()
    page_by_url = {page.url: page for page in pages}

    sitemap_urls = (
        await session.execute(select(SitemapUrl.url).where(SitemapUrl.crawl_id == crawl_id))
    ).scalars().all()

    orphans: list[OrphanOut] = []
    for url in sitemap_urls:
        page = page_by_url.get(url)
        if page is None:
            continue
        if page.inbound_internal == 0:
            orphans.append(
                OrphanOut(
                    url=url,
                    page_id=page.id,
                    status_code=page.status_code,
                    title=page.title,
                    inbound_internal=page.inbound_internal,
                )
            )
    return orphans


async def list_issues(session: AsyncSession, crawl_id: int) -> IssuesOut:
    pages = (
        await session.execute(select(Page).where(Page.crawl_id == crawl_id).order_by(Page.url))
    ).scalars().all()

    broken: list[PageOut] = []
    redirects: list[PageOut] = []
    missing_title: list[PageOut] = []
    missing_h1: list[PageOut] = []
    noindex: list[PageOut] = []
    titles: dict[str, list[Page]] = defaultdict(list)

    for page in pages:
        out = page_to_out(page)
        if page.status_code and page.status_code >= 400:
            broken.append(out)
        chain = out.redirect_chain
        if len(chain) > 1:
            redirects.append(out)
        html = (page.content_type or "").lower()
        is_html = (not page.content_type) or "html" in html
        if page.status_code == 200 and is_html and not page.title:
            missing_title.append(out)
        if page.status_code == 200 and is_html and page.h1_count == 0:
            missing_h1.append(out)
        if page.status_code == 200 and not page.indexable:
            noindex.append(out)
        if page.status_code == 200 and page.title:
            titles[page.title].append(page)

    duplicate_titles = [
        DuplicateTitleGroup(title=title, pages=[page_to_out(p) for p in group])
        for title, group in titles.items()
        if len(group) > 1
    ]
    duplicate_titles.sort(key=lambda item: (-len(item.pages), item.title))

    issue_count = (
        len(broken)
        + len(redirects)
        + len(missing_title)
        + len(missing_h1)
        + len(noindex)
        + sum(len(group.pages) for group in duplicate_titles)
    )
    return IssuesOut(
        broken=broken,
        redirects=redirects,
        missing_title=missing_title,
        missing_h1=missing_h1,
        noindex=noindex,
        duplicate_titles=duplicate_titles,
        issue_count=issue_count,
    )


async def replace_page_links(
    session: AsyncSession,
    crawl_id: int,
    from_url: str,
    links: list[Link],
) -> None:
    await session.execute(delete(Link).where(Link.crawl_id == crawl_id, Link.from_url == from_url))
    session.add_all(links)
