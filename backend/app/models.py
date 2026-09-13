from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    primary_host: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    crawls: Mapped[list["Crawl"]] = relationship(back_populates="site")


class Crawl(Base):
    __tablename__ = "crawls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), index=True)
    seed_url: Mapped[str] = mapped_column(String(2048))
    allowed_hosts: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0)
    pages_queued: Mapped[int] = mapped_column(Integer, default=0)
    pages_from_sitemap: Mapped[int] = mapped_column(Integer, default=0)
    max_pages: Mapped[int] = mapped_column(Integer, default=10_000)
    concurrency: Mapped[int] = mapped_column(Integer, default=4)
    delay_seconds: Mapped[float] = mapped_column(Float, default=0.25)
    extra_sitemaps: Mapped[str] = mapped_column(Text, default="[]")
    language_mode: Mapped[str] = mapped_column(String(16), default="auto")
    default_lang: Mapped[str | None] = mapped_column(String(16), nullable=True)
    use_sitemap: Mapped[bool] = mapped_column(default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    message: Mapped[str | None] = mapped_column(String(512), nullable=True)

    site: Mapped[Site] = relationship(back_populates="crawls")
    pages: Mapped[list["Page"]] = relationship(back_populates="crawl")
    links: Mapped[list["Link"]] = relationship(back_populates="crawl")
    sitemap_urls: Mapped[list["SitemapUrl"]] = relationship(back_populates="crawl")


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("crawl_id", "url", name="uq_page_crawl_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    crawl_id: Mapped[int] = mapped_column(ForeignKey("crawls.id"), index=True)
    url: Mapped[str] = mapped_column(String(2048), index=True)
    final_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    h1: Mapped[str | None] = mapped_column(Text, nullable=True)
    h1_count: Mapped[int] = mapped_column(Integer, default=0)
    canonical: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    robots_meta: Mapped[str | None] = mapped_column(String(255), nullable=True)
    indexable: Mapped[bool] = mapped_column(default=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    redirect_chain: Mapped[str | None] = mapped_column(Text, nullable=True)
    inbound_internal: Mapped[int] = mapped_column(Integer, default=0)
    outbound_internal: Mapped[int] = mapped_column(Integer, default=0)
    outbound_external: Mapped[int] = mapped_column(Integer, default=0)
    lang: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    html_lang: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    crawl: Mapped[Crawl] = relationship(back_populates="pages")


class Hreflang(Base):
    __tablename__ = "hreflangs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    crawl_id: Mapped[int] = mapped_column(ForeignKey("crawls.id"), index=True)
    from_url: Mapped[str] = mapped_column(String(2048), index=True)
    lang: Mapped[str] = mapped_column(String(16), index=True)
    to_url: Mapped[str] = mapped_column(String(2048), index=True)


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    crawl_id: Mapped[int] = mapped_column(ForeignKey("crawls.id"), index=True)
    from_url: Mapped[str] = mapped_column(String(2048), index=True)
    to_url: Mapped[str] = mapped_column(String(2048), index=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)
    anchor: Mapped[str | None] = mapped_column(Text, nullable=True)
    rel: Mapped[str | None] = mapped_column(String(255), nullable=True)

    crawl: Mapped[Crawl] = relationship(back_populates="links")


class SitemapUrl(Base):
    __tablename__ = "sitemap_urls"
    __table_args__ = (UniqueConstraint("crawl_id", "url", name="uq_sitemap_crawl_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    crawl_id: Mapped[int] = mapped_column(ForeignKey("crawls.id"), index=True)
    url: Mapped[str] = mapped_column(String(2048))

    crawl: Mapped[Crawl] = relationship(back_populates="sitemap_urls")
