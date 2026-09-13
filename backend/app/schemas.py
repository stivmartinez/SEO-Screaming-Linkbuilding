from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class CrawlCreate(BaseModel):
    seed_url: HttpUrl
    name: str | None = None
    allowed_hosts: list[str] = Field(default_factory=list)
    concurrency: int = Field(default=4, ge=1, le=16)
    delay_seconds: float = Field(default=0.25, ge=0.0, le=10.0)
    max_pages: int = Field(default=10_000, ge=1, le=500_000)
    extra_sitemaps: list[str] = Field(default_factory=list)
    language_mode: str = Field(default="auto", pattern="^(auto|off|path|hreflang)$")
    default_lang: str | None = Field(default=None, max_length=16)
    use_sitemap: bool = True


class SiteOut(BaseModel):
    id: int
    name: str
    primary_host: str

    model_config = {"from_attributes": True}


class CrawlOut(BaseModel):
    id: int
    site_id: int
    site: SiteOut | None = None
    seed_url: str
    allowed_hosts: list[str]
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    pages_crawled: int
    pages_queued: int
    pages_from_sitemap: int
    max_pages: int
    concurrency: int
    delay_seconds: float
    extra_sitemaps: list[str] = Field(default_factory=list)
    language_mode: str = "auto"
    default_lang: str | None = None
    use_sitemap: bool = True
    error: str | None
    message: str | None
    orphan_count: int = 0
    issue_count: int = 0

    model_config = {"from_attributes": True}


class PageOut(BaseModel):
    id: int
    crawl_id: int
    url: str
    final_url: str | None
    status_code: int | None
    content_type: str | None
    title: str | None
    meta_description: str | None
    h1: str | None
    h1_count: int
    canonical: str | None
    robots_meta: str | None
    indexable: bool
    word_count: int
    depth: int | None
    redirect_chain: list[str]
    inbound_internal: int
    outbound_internal: int
    outbound_external: int
    lang: str | None = None
    html_lang: str | None = None
    fetched_at: datetime | None
    error: str | None

    model_config = {"from_attributes": True}


class LanguageVersionOut(BaseModel):
    lang: str
    url: str | None
    page_id: int | None
    title: str | None
    word_count: int | None


class LinkOut(BaseModel):
    id: int
    from_url: str
    to_url: str
    kind: str
    anchor: str | None
    rel: str | None

    model_config = {"from_attributes": True}


class PageDetailOut(PageOut):
    inbound: list[LinkOut] = Field(default_factory=list)
    outbound: list[LinkOut] = Field(default_factory=list)
    alternates: list[LanguageVersionOut] = Field(default_factory=list)


class PageListOut(BaseModel):
    items: list[PageOut]
    total: int


class OrphanOut(BaseModel):
    url: str
    page_id: int | None
    status_code: int | None
    title: str | None
    inbound_internal: int


class DuplicateTitleGroup(BaseModel):
    title: str
    pages: list[PageOut]


class LanguageGroupOut(BaseModel):
    source_url: str
    source_lang: str
    versions: dict[str, LanguageVersionOut]
    missing: list[str]
    word_gap: int | None


class PageGroupListOut(BaseModel):
    items: list[LanguageGroupOut]
    total: int
    languages: list[str]
    default_lang: str


class LanguageStatOut(BaseModel):
    lang: str
    is_default: bool
    pages: int
    words: int
    avg_words: float
    missing_translations: int


class LanguageReportOut(BaseModel):
    default_lang: str
    languages: list[LanguageStatOut]
    groups: list[LanguageGroupOut]
    thin_groups: list[LanguageGroupOut] = []
    group_count: int
    complete_groups: int


class GraphNodeOut(BaseModel):
    id: str
    page_id: int | None
    url: str
    title: str | None
    lang: str
    group_id: str
    word_count: int
    depth: int | None
    inbound_internal: int = 0
    outbound_internal: int = 0


class GraphEdgeOut(BaseModel):
    id: str
    source: str
    target: str
    kind: str
    sitewide: bool = False
    weight: int = 1


class GraphOut(BaseModel):
    languages: list[str]
    default_lang: str
    multilingual: bool = False
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]


class IssuesOut(BaseModel):
    broken: list[PageOut]
    redirects: list[PageOut]
    missing_title: list[PageOut]
    missing_h1: list[PageOut]
    noindex: list[PageOut]
    duplicate_titles: list[DuplicateTitleGroup]
    issue_count: int
