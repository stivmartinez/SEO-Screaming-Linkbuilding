from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.crawler.normalize import host_of


class RobotsCache:
    def __init__(self, client: httpx.AsyncClient, user_agent: str) -> None:
        self._client = client
        self._user_agent = user_agent
        self._parsers: dict[str, RobotFileParser] = {}
        self._sitemaps: dict[str, list[str]] = {}
        self._delays: dict[str, float | None] = {}

    async def load(self, host: str, scheme: str = "https") -> None:
        if host in self._parsers:
            return
        parser = RobotFileParser()
        robots_url = f"{scheme}://{host}/robots.txt"
        try:
            response = await self._client.get(robots_url, follow_redirects=True)
            if response.status_code >= 400:
                parser.parse([])
                self._sitemaps[host] = []
                self._delays[host] = None
            else:
                lines = response.text.splitlines()
                parser.parse(lines)
                self._sitemaps[host] = list(parser.site_maps() or [])
                self._delays[host] = parser.crawl_delay(self._user_agent)
        except httpx.HTTPError:
            parser.parse([])
            self._sitemaps[host] = []
            self._delays[host] = None
        self._parsers[host] = parser

    def can_fetch(self, url: str) -> bool:
        host = host_of(url)
        if not host:
            return False
        parser = self._parsers.get(host)
        if parser is None:
            return True
        return parser.can_fetch(self._user_agent, url)

    def crawl_delay(self, url: str) -> float | None:
        host = host_of(url)
        if not host:
            return None
        return self._delays.get(host)

    def sitemaps(self, host: str) -> list[str]:
        return list(self._sitemaps.get(host, []))


def sitemap_candidates(seed_url: str, extra: list[str] | None = None) -> list[str]:
    parsed = urlparse(seed_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    urls = [
        f"{origin}/sitemap.xml",
        f"{origin}/sitemap_index.xml",
        f"{origin}/sitemap-index.xml",
        f"{origin}/sitemap.xml.gz",
        f"{origin}/sitemap_index.xml.gz",
        f"{origin}/wp-sitemap.xml",
        f"{origin}/sitemap/sitemap.xml",
        f"{origin}/sitemaps/sitemap.xml",
        f"{origin}/sitemap/index.xml",
    ]
    if extra:
        urls.extend(extra)
    seen: set[str] = set()
    unique: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique
