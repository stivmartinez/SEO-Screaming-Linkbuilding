import json
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.analysis.languages import (
    assign_page_languages,
    crawl_graph,
    language_report,
    list_page_groups,
    page_alternates,
)
from app.analysis.seo import list_issues, list_orphans, page_to_out
from app.api.csv_export import (
    all_zip,
    issues_csv,
    languages_csv,
    links_csv,
    missing_translations_csv,
    orphans_csv,
    pages_csv,
    sitemap_csv,
)
from app.crawler.engine import request_cancel, start_crawl_task
from app.crawler.normalize import expand_hosts, host_of, normalize_url
from app.db import get_session
from app.models import Crawl, Hreflang, Link, Page, Site, SitemapUrl
from app.schemas import (
    CrawlCreate,
    CrawlOut,
    DuplicateTitleGroup,
    GraphOut,
    IssuesOut,
    LanguageReportOut,
    LinkOut,
    OrphanOut,
    PageDetailOut,
    PageGroupListOut,
    PageListOut,
    SiteOut,
)

router = APIRouter(prefix="/api")


def _hosts_list(raw: str) -> list[str]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def _crawl_out(crawl: Crawl, orphan_count: int = 0, issue_count: int = 0) -> CrawlOut:
    site = crawl.site
    return CrawlOut(
        id=crawl.id,
        site_id=crawl.site_id,
        site=SiteOut.model_validate(site) if site else None,
        seed_url=crawl.seed_url,
        allowed_hosts=_hosts_list(crawl.allowed_hosts),
        status=crawl.status,
        started_at=crawl.started_at,
        finished_at=crawl.finished_at,
        pages_crawled=crawl.pages_crawled,
        pages_queued=crawl.pages_queued,
        pages_from_sitemap=crawl.pages_from_sitemap,
        max_pages=crawl.max_pages,
        concurrency=crawl.concurrency,
        delay_seconds=crawl.delay_seconds,
        extra_sitemaps=_hosts_list(getattr(crawl, "extra_sitemaps", None) or "[]"),
        language_mode=getattr(crawl, "language_mode", None) or "auto",
        default_lang=getattr(crawl, "default_lang", None),
        use_sitemap=bool(getattr(crawl, "use_sitemap", True)),
        error=crawl.error,
        message=crawl.message,
        orphan_count=orphan_count,
        issue_count=issue_count,
    )


async def _delete_crawls(session: AsyncSession, crawls: list[Crawl]) -> None:
    for crawl in crawls:
        request_cancel(crawl.id)
    crawl_ids = [crawl.id for crawl in crawls]
    if not crawl_ids:
        return
    await session.execute(delete(Link).where(Link.crawl_id.in_(crawl_ids)))
    await session.execute(delete(Page).where(Page.crawl_id.in_(crawl_ids)))
    await session.execute(delete(SitemapUrl).where(SitemapUrl.crawl_id.in_(crawl_ids)))
    await session.execute(delete(Hreflang).where(Hreflang.crawl_id.in_(crawl_ids)))
    await session.execute(delete(Crawl).where(Crawl.id.in_(crawl_ids)))


async def _get_site(session: AsyncSession, site_id: int) -> Site:
    site = await session.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


async def _get_crawl(session: AsyncSession, crawl_id: int) -> Crawl:
    result = await session.execute(
        select(Crawl).options(selectinload(Crawl.site)).where(Crawl.id == crawl_id)
    )
    crawl = result.scalar_one_or_none()
    if crawl is None:
        raise HTTPException(status_code=404, detail="Crawl not found")
    return crawl


@router.post("/crawls", response_model=CrawlOut)
async def create_crawl(payload: CrawlCreate, session: AsyncSession = Depends(get_session)) -> CrawlOut:
    seed = normalize_url(str(payload.seed_url))
    if not seed:
        raise HTTPException(status_code=400, detail="Invalid seed URL")

    host = host_of(seed)
    if not host:
        raise HTTPException(status_code=400, detail="Seed URL must include a host")

    hosts = sorted(expand_hosts([host, *payload.allowed_hosts]))
    name = payload.name or urlparse(seed).hostname or host

    site = await session.scalar(select(Site).where(Site.primary_host == host))
    if site is None:
        site = Site(name=name, primary_host=host)
        session.add(site)
        await session.flush()

    crawl = Crawl(
        site_id=site.id,
        seed_url=seed,
        allowed_hosts=json.dumps(hosts),
        status="pending",
        max_pages=payload.max_pages,
        concurrency=payload.concurrency,
        delay_seconds=payload.delay_seconds,
        extra_sitemaps=json.dumps([str(url).strip() for url in payload.extra_sitemaps if str(url).strip()]),
        language_mode=payload.language_mode,
        default_lang=(payload.default_lang or "").strip().lower() or None,
        use_sitemap=payload.use_sitemap,
        message="Queued",
    )
    session.add(crawl)
    await session.commit()
    await session.refresh(crawl)
    crawl = await _get_crawl(session, crawl.id)
    start_crawl_task(crawl.id)
    return _crawl_out(crawl)


@router.get("/crawls", response_model=list[CrawlOut])
async def list_crawls(session: AsyncSession = Depends(get_session)) -> list[CrawlOut]:
    result = await session.execute(
        select(Crawl).options(selectinload(Crawl.site)).order_by(Crawl.id.desc())
    )
    return [_crawl_out(item) for item in result.scalars().all()]


@router.get("/crawls/{crawl_id}", response_model=CrawlOut)
async def get_crawl(crawl_id: int, session: AsyncSession = Depends(get_session)) -> CrawlOut:
    crawl = await _get_crawl(session, crawl_id)
    orphan_count = 0
    issue_count = 0
    if crawl.status == "completed":
        orphan_count = len(await list_orphans(session, crawl_id))
        issue_count = (await list_issues(session, crawl_id)).issue_count
    return _crawl_out(crawl, orphan_count=orphan_count, issue_count=issue_count)


@router.delete("/crawls/{crawl_id}", status_code=204)
async def delete_crawl(crawl_id: int, session: AsyncSession = Depends(get_session)) -> None:
    crawl = await _get_crawl(session, crawl_id)
    site_id = crawl.site_id
    await _delete_crawls(session, [crawl])
    remaining = await session.scalar(select(func.count(Crawl.id)).where(Crawl.site_id == site_id))
    if not remaining:
        site = await session.get(Site, site_id)
        if site:
            await session.delete(site)
    await session.commit()


@router.get("/sites", response_model=list[SiteOut])
async def list_sites(session: AsyncSession = Depends(get_session)) -> list[SiteOut]:
    result = await session.execute(select(Site).order_by(Site.name))
    return [SiteOut.model_validate(item) for item in result.scalars().all()]


@router.delete("/sites/{site_id}", status_code=204)
async def delete_site(site_id: int, session: AsyncSession = Depends(get_session)) -> None:
    site = await _get_site(session, site_id)
    crawls = (await session.execute(select(Crawl).where(Crawl.site_id == site_id))).scalars().all()
    await _delete_crawls(session, list(crawls))
    await session.delete(site)
    await session.commit()


@router.post("/crawls/{crawl_id}/cancel", response_model=CrawlOut)
async def cancel_crawl(crawl_id: int, session: AsyncSession = Depends(get_session)) -> CrawlOut:
    crawl = await _get_crawl(session, crawl_id)
    if crawl.status not in {"pending", "running"}:
        raise HTTPException(status_code=400, detail="Crawl is not running")
    if not request_cancel(crawl_id):
        crawl.status = "cancelled"
        await session.commit()
    return _crawl_out(crawl)


@router.get("/crawls/{crawl_id}/pages", response_model=PageListOut)
async def list_pages(
    crawl_id: int,
    q: str | None = None,
    lang: str | None = None,
    status: int | None = None,
    indexable: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> PageListOut:
    crawl = await _get_crawl(session, crawl_id)
    if lang:
        await assign_page_languages(session, crawl_id, crawl.seed_url)
    filters = [Page.crawl_id == crawl_id]
    if q:
        like = f"%{q}%"
        filters.append(
            or_(
                Page.url.ilike(like),
                Page.title.ilike(like),
                Page.h1.ilike(like),
            )
        )
    if status is not None:
        filters.append(Page.status_code == status)
    if indexable is not None:
        filters.append(Page.indexable == indexable)
    if lang:
        filters.append(Page.lang == lang)

    total = await session.scalar(select(func.count(Page.id)).where(*filters))
    result = await session.execute(
        select(Page)
        .where(*filters)
        .order_by(Page.depth.asc().nulls_last(), Page.url.asc())
        .offset(offset)
        .limit(limit)
    )
    items = [page_to_out(page) for page in result.scalars().all()]
    return PageListOut(items=items, total=total or 0)


@router.get("/crawls/{crawl_id}/page-groups", response_model=PageGroupListOut)
async def get_page_groups(
    crawl_id: int,
    q: str | None = None,
    lang: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> PageGroupListOut:
    crawl = await _get_crawl(session, crawl_id)
    return await list_page_groups(
        session,
        crawl_id,
        crawl.seed_url,
        q=q,
        lang=lang,
        offset=offset,
        limit=limit,
    )


@router.get("/crawls/{crawl_id}/graph", response_model=GraphOut)
async def get_graph(crawl_id: int, session: AsyncSession = Depends(get_session)) -> GraphOut:
    crawl = await _get_crawl(session, crawl_id)
    return await crawl_graph(session, crawl_id, crawl.seed_url)


@router.get("/crawls/{crawl_id}/pages/{page_id}", response_model=PageDetailOut)
async def get_page(
    crawl_id: int,
    page_id: int,
    session: AsyncSession = Depends(get_session),
) -> PageDetailOut:
    await _get_crawl(session, crawl_id)
    page = await session.scalar(select(Page).where(Page.id == page_id, Page.crawl_id == crawl_id))
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")

    inbound = (
        await session.execute(
            select(Link)
            .where(Link.crawl_id == crawl_id, Link.to_url == page.url, Link.kind == "internal")
            .order_by(Link.from_url)
        )
    ).scalars().all()
    outbound = (
        await session.execute(
            select(Link).where(Link.crawl_id == crawl_id, Link.from_url == page.url).order_by(Link.kind, Link.to_url)
        )
    ).scalars().all()

    base = page_to_out(page)
    return PageDetailOut(
        **base.model_dump(),
        inbound=[LinkOut.model_validate(item) for item in inbound],
        outbound=[LinkOut.model_validate(item) for item in outbound],
        alternates=await page_alternates(session, crawl_id, page.url),
    )


@router.get("/crawls/{crawl_id}/orphans", response_model=list[OrphanOut])
async def get_orphans(
    crawl_id: int,
    lang: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[OrphanOut]:
    crawl = await _get_crawl(session, crawl_id)
    items = await list_orphans(session, crawl_id)
    if not lang:
        return items
    await assign_page_languages(session, crawl_id, crawl.seed_url)
    pages = (
        await session.execute(select(Page).where(Page.crawl_id == crawl_id, Page.lang == lang))
    ).scalars().all()
    urls = {page.url for page in pages}
    return [item for item in items if item.url in urls]


@router.get("/crawls/{crawl_id}/issues", response_model=IssuesOut)
async def get_issues(
    crawl_id: int,
    lang: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> IssuesOut:
    crawl = await _get_crawl(session, crawl_id)
    if lang:
        await assign_page_languages(session, crawl_id, crawl.seed_url)
    issues = await list_issues(session, crawl_id)
    if not lang:
        return issues

    def match(pages: list) -> list:
        return [page for page in pages if page.lang == lang]

    duplicates = [
        DuplicateTitleGroup(title=group.title, pages=match(group.pages))
        for group in issues.duplicate_titles
        if match(group.pages)
    ]
    broken = match(issues.broken)
    redirects = match(issues.redirects)
    missing_title = match(issues.missing_title)
    missing_h1 = match(issues.missing_h1)
    noindex = match(issues.noindex)
    return IssuesOut(
        broken=broken,
        redirects=redirects,
        missing_title=missing_title,
        missing_h1=missing_h1,
        noindex=noindex,
        duplicate_titles=duplicates,
        issue_count=(
            len(broken)
            + len(redirects)
            + len(missing_title)
            + len(missing_h1)
            + len(noindex)
            + sum(len(group.pages) for group in duplicates)
        ),
    )


@router.get("/crawls/{crawl_id}/languages", response_model=LanguageReportOut)
async def get_languages(crawl_id: int, session: AsyncSession = Depends(get_session)) -> LanguageReportOut:
    crawl = await _get_crawl(session, crawl_id)
    return await language_report(session, crawl_id, crawl.seed_url)


def _export_name(crawl: Crawl, suffix: str) -> str:
    host = crawl.site.primary_host if crawl.site else f"crawl-{crawl.id}"
    safe = "".join(char if char.isalnum() or char in "-._" else "-" for char in host)
    return f"{safe}-crawl-{crawl.id}-{suffix}"


async def _export_payload(session: AsyncSession, crawl_id: int) -> tuple[Crawl, list[Page], list[Link], list[SitemapUrl]]:
    crawl = await _get_crawl(session, crawl_id)
    pages = (
        await session.execute(
            select(Page).where(Page.crawl_id == crawl_id).order_by(Page.depth.asc().nulls_last(), Page.url.asc())
        )
    ).scalars().all()
    links = (
        await session.execute(select(Link).where(Link.crawl_id == crawl_id).order_by(Link.from_url, Link.to_url))
    ).scalars().all()
    sitemap_urls = (
        await session.execute(select(SitemapUrl).where(SitemapUrl.crawl_id == crawl_id).order_by(SitemapUrl.url))
    ).scalars().all()
    return crawl, list(pages), list(links), list(sitemap_urls)


@router.get("/crawls/{crawl_id}/export/pages.csv")
async def export_pages_csv(crawl_id: int, session: AsyncSession = Depends(get_session)) -> Response:
    crawl, pages, _links, _sitemap = await _export_payload(session, crawl_id)
    return Response(
        content=pages_csv(pages),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_export_name(crawl, "pages.csv")}"'},
    )


@router.get("/crawls/{crawl_id}/export/links.csv")
async def export_links_csv(crawl_id: int, session: AsyncSession = Depends(get_session)) -> Response:
    crawl, _pages, links, _sitemap = await _export_payload(session, crawl_id)
    return Response(
        content=links_csv(links),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_export_name(crawl, "links.csv")}"'},
    )


@router.get("/crawls/{crawl_id}/export/orphans.csv")
async def export_orphans_csv(crawl_id: int, session: AsyncSession = Depends(get_session)) -> Response:
    crawl = await _get_crawl(session, crawl_id)
    return Response(
        content=orphans_csv(await list_orphans(session, crawl_id)),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_export_name(crawl, "orphans.csv")}"'},
    )


@router.get("/crawls/{crawl_id}/export/issues.csv")
async def export_issues_csv(crawl_id: int, session: AsyncSession = Depends(get_session)) -> Response:
    crawl = await _get_crawl(session, crawl_id)
    return Response(
        content=issues_csv(await list_issues(session, crawl_id)),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_export_name(crawl, "issues.csv")}"'},
    )


@router.get("/crawls/{crawl_id}/export/sitemap.csv")
async def export_sitemap_csv(crawl_id: int, session: AsyncSession = Depends(get_session)) -> Response:
    crawl, _pages, _links, sitemap_urls = await _export_payload(session, crawl_id)
    return Response(
        content=sitemap_csv(sitemap_urls),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_export_name(crawl, "sitemap.csv")}"'},
    )


@router.get("/crawls/{crawl_id}/export/languages.csv")
async def export_languages_csv(crawl_id: int, session: AsyncSession = Depends(get_session)) -> Response:
    crawl = await _get_crawl(session, crawl_id)
    report = await language_report(session, crawl_id, crawl.seed_url)
    return Response(
        content=languages_csv(report),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_export_name(crawl, "languages.csv")}"'},
    )


@router.get("/crawls/{crawl_id}/export/missing-translations.csv")
async def export_missing_csv(crawl_id: int, session: AsyncSession = Depends(get_session)) -> Response:
    crawl = await _get_crawl(session, crawl_id)
    report = await language_report(session, crawl_id, crawl.seed_url)
    return Response(
        content=missing_translations_csv(report),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_export_name(crawl, "missing-translations.csv")}"'},
    )


@router.get("/crawls/{crawl_id}/export/all.zip")
async def export_all_zip(crawl_id: int, session: AsyncSession = Depends(get_session)) -> Response:
    crawl, pages, links, sitemap_urls = await _export_payload(session, crawl_id)
    report = await language_report(session, crawl_id, crawl.seed_url)
    payload = all_zip(
        pages=pages,
        links=links,
        orphans=await list_orphans(session, crawl_id),
        issues=await list_issues(session, crawl_id),
        sitemap_urls=sitemap_urls,
        languages=report,
    )
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{_export_name(crawl, "all.zip")}"'},
    )
