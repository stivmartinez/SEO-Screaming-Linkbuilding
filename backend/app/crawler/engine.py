from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crawler.normalize import expand_hosts, is_internal, normalize_url
from app.crawler.parser import is_indexable, parse_html
from app.crawler.robots import RobotsCache, sitemap_candidates
from app.crawler.sitemap import fetch_sitemap_urls
from app.db import SessionLocal
from app.models import Crawl, Hreflang, Link, Page, SitemapUrl
from app.analysis.languages import assign_page_languages
from app.analysis.seo import recompute_depths, recompute_link_counts

logger = logging.getLogger(__name__)

_running: dict[int, asyncio.Task] = {}
_cancel: dict[int, asyncio.Event] = {}


def is_running(crawl_id: int) -> bool:
    task = _running.get(crawl_id)
    return bool(task and not task.done())


def request_cancel(crawl_id: int) -> bool:
    event = _cancel.get(crawl_id)
    if event is None:
        return False
    event.set()
    return True


def start_crawl_task(crawl_id: int) -> None:
    if is_running(crawl_id):
        return
    _cancel[crawl_id] = asyncio.Event()
    _running[crawl_id] = asyncio.create_task(run_crawl(crawl_id))


async def _set_status(
    session: AsyncSession,
    crawl: Crawl,
    **fields,
) -> None:
    for key, value in fields.items():
        setattr(crawl, key, value)
    await session.commit()


async def run_crawl(crawl_id: int) -> None:
    cancel = _cancel.setdefault(crawl_id, asyncio.Event())
    async with SessionLocal() as session:
        crawl = await session.get(Crawl, crawl_id)
        if crawl is None:
            return
        try:
            await _set_status(
                session,
                crawl,
                status="running",
                started_at=datetime.utcnow(),
                message="Starting crawl",
                error=None,
            )
            await _execute(session, crawl, cancel)
            crawl = await session.get(Crawl, crawl_id)
            if crawl is None:
                return
            if cancel.is_set():
                await _set_status(
                    session,
                    crawl,
                    status="cancelled",
                    finished_at=datetime.utcnow(),
                    message="Cancelled",
                )
            else:
                await _set_status(session, crawl, message="Computing link metrics")
                crawl = await session.get(Crawl, crawl_id)
                if crawl:
                    await recompute_link_counts(session, crawl_id)
                    await recompute_depths(session, crawl_id, crawl.seed_url)
                    await assign_page_languages(session, crawl_id, crawl.seed_url)
                crawl = await session.get(Crawl, crawl_id)
                if crawl:
                    await _set_status(
                        session,
                        crawl,
                        status="completed",
                        finished_at=datetime.utcnow(),
                        message="Done",
                    )
        except Exception as exc:
            logger.exception("Crawl %s failed", crawl_id)
            crawl = await session.get(Crawl, crawl_id)
            if crawl:
                await _set_status(
                    session,
                    crawl,
                    status="failed",
                    finished_at=datetime.utcnow(),
                    error=str(exc),
                    message="Failed",
                )
        finally:
            _running.pop(crawl_id, None)
            _cancel.pop(crawl_id, None)


async def _execute(session: AsyncSession, crawl: Crawl, cancel: asyncio.Event) -> None:
    seed = normalize_url(crawl.seed_url)
    if not seed:
        raise ValueError("Invalid seed URL")

    allowed = expand_hosts(json.loads(crawl.allowed_hosts))
    seed_host = urlparse(seed).hostname
    if seed_host:
        allowed |= expand_hosts([seed_host])

    timeout = httpx.Timeout(settings.request_timeout)
    headers = {"User-Agent": settings.user_agent, "Accept": "text/html,application/xhtml+xml"}
    limits = httpx.Limits(max_connections=crawl.concurrency + 2, max_keepalive_connections=crawl.concurrency)

    async with httpx.AsyncClient(
        timeout=timeout,
        headers=headers,
        follow_redirects=True,
        limits=limits,
    ) as client:
        robots = RobotsCache(client, settings.user_agent)
        for host in sorted(allowed):
            if cancel.is_set():
                return
            await robots.load(host, scheme=urlparse(seed).scheme)

        await _set_status(session, crawl, message="Fetching sitemaps")
        sitemap_urls: list[str] = []
        sitemap_hreflangs: list[tuple[str, str, str]] = []
        if getattr(crawl, "use_sitemap", True):
            extra_sitemaps: list[str] = []
            for host in allowed:
                extra_sitemaps.extend(robots.sitemaps(host))
            try:
                custom = json.loads(getattr(crawl, "extra_sitemaps", None) or "[]")
                if isinstance(custom, list):
                    extra_sitemaps.extend(str(item) for item in custom if item)
            except json.JSONDecodeError:
                pass
            sitemap_urls, sitemap_hreflangs = await fetch_sitemap_urls(
                client,
                sitemap_candidates(seed, extra_sitemaps),
                allowed,
            )
        for url in sitemap_urls:
            session.add(SitemapUrl(crawl_id=crawl.id, url=url))
        for source, lang, target in sitemap_hreflangs:
            session.add(Hreflang(crawl_id=crawl.id, from_url=source, lang=lang, to_url=target))
        crawl.pages_from_sitemap = len(sitemap_urls)
        await session.commit()

        depths: dict[str, int | None] = {}
        queue: asyncio.PriorityQueue[tuple[int, int, str]] = asyncio.PriorityQueue()
        write_lock = asyncio.Lock()
        crawled = 0
        queued = 0
        active = 0
        seq = 0

        def enqueue(url: str, depth: int | None) -> None:
            nonlocal queued, seq
            if crawled >= crawl.max_pages:
                return
            if url in depths:
                current = depths[url]
                if depth is not None and (current is None or depth < current):
                    depths[url] = depth
                return
            depths[url] = depth
            seq += 1
            sort_key = depth if depth is not None else 1_000_000
            queue.put_nowait((sort_key, seq, url))
            queued += 1

        async def reserve_slot() -> bool:
            nonlocal crawled
            async with write_lock:
                if crawled >= crawl.max_pages:
                    return False
                crawled += 1
                crawl.pages_crawled = crawled
                crawl.pages_queued = queued
                crawl.message = f"Crawled {crawled} pages"
                await session.commit()
                return True

        enqueue(seed, 0)
        for url in sitemap_urls:
            enqueue(url, None)

        crawl.pages_queued = queued
        await _set_status(session, crawl, message="Crawling pages", pages_queued=queued)

        async def worker() -> None:
            nonlocal crawled, queued, active
            while not cancel.is_set():
                try:
                    _sort, _seq, url = await asyncio.wait_for(queue.get(), timeout=0.4)
                except asyncio.TimeoutError:
                    if queue.empty() and active == 0:
                        return
                    continue
                active += 1
                reserved = False
                try:
                    if not is_internal(url, allowed):
                        continue
                    if not await reserve_slot():
                        continue
                    reserved = True
                    if not robots.can_fetch(url):
                        async with write_lock:
                            session.add(
                                Page(
                                    crawl_id=crawl.id,
                                    url=url,
                                    status_code=None,
                                    indexable=False,
                                    depth=depths.get(url),
                                    error="Blocked by robots.txt",
                                    fetched_at=datetime.utcnow(),
                                )
                            )
                            await session.commit()
                        continue

                    delay = crawl.delay_seconds
                    robots_delay = robots.crawl_delay(url)
                    if robots_delay is not None:
                        delay = max(delay, float(robots_delay))
                    if delay:
                        await asyncio.sleep(delay)

                    await _fetch_one(
                        session=session,
                        client=client,
                        crawl=crawl,
                        url=url,
                        depth=depths.get(url),
                        allowed=allowed,
                        write_lock=write_lock,
                        enqueue=enqueue,
                    )
                except Exception as exc:
                    logger.warning("Failed to fetch %s: %s", url, exc)
                    if reserved:
                        async with write_lock:
                            existing = await session.scalar(
                                select(Page).where(Page.crawl_id == crawl.id, Page.url == url)
                            )
                            if existing is None:
                                session.add(
                                    Page(
                                        crawl_id=crawl.id,
                                        url=url,
                                        depth=depths.get(url),
                                        error=str(exc),
                                        fetched_at=datetime.utcnow(),
                                        indexable=False,
                                    )
                                )
                                await session.commit()
                finally:
                    active -= 1
                    queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(max(1, crawl.concurrency))]
        await asyncio.gather(*workers)


async def _fetch_one(
    *,
    session: AsyncSession,
    client: httpx.AsyncClient,
    crawl: Crawl,
    url: str,
    depth: int | None,
    allowed: set[str],
    write_lock: asyncio.Lock,
    enqueue,
) -> None:
    try:
        response = await client.get(url)
    except httpx.HTTPError as exc:
        async with write_lock:
            session.add(
                Page(
                    crawl_id=crawl.id,
                    url=url,
                    depth=depth,
                    error=str(exc),
                    fetched_at=datetime.utcnow(),
                    indexable=False,
                )
            )
            await session.commit()
        return

    body = response.content[: settings.max_response_bytes]
    truncated = len(response.content) > settings.max_response_bytes

    content_type = response.headers.get("content-type", "")
    final_url = normalize_url(str(response.url)) or str(response.url)
    chain = [str(item.url) for item in response.history]
    if not chain or chain[-1] != str(response.url):
        chain.append(str(response.url))

    title = meta = h1 = canonical = robots_meta = html_lang = None
    h1_count = word_count = 0
    extracted_links: list[Link] = []
    extracted_hreflang: list[Hreflang] = []

    is_html = "html" in content_type.lower() or content_type == ""
    if is_html and body:
        parsed = parse_html(body.decode(response.encoding or "utf-8", errors="replace"), final_url, allowed)
        title = parsed.title
        meta = parsed.meta_description
        h1 = parsed.h1
        h1_count = parsed.h1_count
        canonical = parsed.canonical
        robots_meta = parsed.robots_meta
        word_count = parsed.word_count
        html_lang = parsed.html_lang
        for lang, target in parsed.hreflangs:
            extracted_hreflang.append(Hreflang(crawl_id=crawl.id, from_url=url, lang=lang, to_url=target))
        for item in parsed.links:
            extracted_links.append(
                Link(
                    crawl_id=crawl.id,
                    from_url=url,
                    to_url=item.url,
                    kind=item.kind,
                    anchor=item.anchor,
                    rel=item.rel,
                )
            )
            if item.kind == "internal":
                next_depth = depth + 1 if depth is not None else None
                enqueue(item.url, next_depth)

    x_robots = response.headers.get("x-robots-tag")
    page = Page(
        crawl_id=crawl.id,
        url=url,
        final_url=final_url,
        status_code=response.status_code,
        content_type=content_type.split(";")[0].strip() if content_type else None,
        title=title,
        meta_description=meta,
        h1=h1,
        h1_count=h1_count,
        canonical=canonical,
        robots_meta=robots_meta,
        indexable=is_indexable(response.status_code, content_type, robots_meta, x_robots),
        word_count=word_count,
        depth=depth,
        redirect_chain=json.dumps(chain),
        html_lang=html_lang,
        fetched_at=datetime.utcnow(),
        error="Response truncated" if truncated else None,
    )

    async with write_lock:
        session.add(page)
        session.add_all(extracted_links)
        session.add_all(extracted_hreflang)
        await session.commit()
