import csv
import io
import zipfile
from collections.abc import Iterable, Sequence

from app.analysis.seo import page_to_out
from app.models import Link, Page, SitemapUrl
from app.schemas import IssuesOut, LanguageReportOut, OrphanOut, PageOut


def _csv_bytes(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _page_row(page: PageOut) -> list[object]:
    return [
        page.id,
        page.url,
        page.final_url,
        page.status_code,
        page.content_type,
        page.title,
        page.meta_description,
        page.h1,
        page.h1_count,
        page.canonical,
        page.robots_meta,
        page.indexable,
        page.word_count,
        page.depth,
        " → ".join(page.redirect_chain),
        page.inbound_internal,
        page.outbound_internal,
        page.outbound_external,
        page.lang,
        page.html_lang,
        page.fetched_at.isoformat() if page.fetched_at else "",
        page.error,
    ]


PAGE_HEADERS = [
    "id",
    "url",
    "final_url",
    "status_code",
    "content_type",
    "title",
    "meta_description",
    "h1",
    "h1_count",
    "canonical",
    "robots_meta",
    "indexable",
    "word_count",
    "depth",
    "redirect_chain",
    "inbound_internal",
    "outbound_internal",
    "outbound_external",
    "lang",
    "html_lang",
    "fetched_at",
    "error",
]


def pages_csv(pages: Sequence[Page]) -> bytes:
    return _csv_bytes(PAGE_HEADERS, (_page_row(page_to_out(page)) for page in pages))


def links_csv(links: Sequence[Link]) -> bytes:
    return _csv_bytes(
        ["id", "from_url", "to_url", "kind", "anchor", "rel"],
        ((link.id, link.from_url, link.to_url, link.kind, link.anchor, link.rel) for link in links),
    )


def orphans_csv(orphans: Sequence[OrphanOut]) -> bytes:
    return _csv_bytes(
        ["url", "page_id", "status_code", "title", "inbound_internal"],
        (
            (item.url, item.page_id, item.status_code, item.title, item.inbound_internal)
            for item in orphans
        ),
    )


def issues_csv(issues: IssuesOut) -> bytes:
    rows: list[list[object]] = []
    for page in issues.broken:
        rows.append([page.url, "broken", page.status_code, page.title, ""])
    for page in issues.redirects:
        rows.append([page.url, "redirect", page.status_code, page.title, " → ".join(page.redirect_chain)])
    for page in issues.missing_title:
        rows.append([page.url, "missing_title", page.status_code, page.title, ""])
    for page in issues.missing_h1:
        rows.append([page.url, "missing_h1", page.status_code, page.title, ""])
    for page in issues.noindex:
        rows.append([page.url, "noindex", page.status_code, page.title, page.robots_meta])
    for group in issues.duplicate_titles:
        for page in group.pages:
            rows.append([page.url, "duplicate_title", page.status_code, page.title, f"{len(group.pages)} pages"])
    return _csv_bytes(["url", "issue_type", "status_code", "title", "detail"], rows)


def sitemap_csv(urls: Sequence[SitemapUrl]) -> bytes:
    return _csv_bytes(["url"], ((item.url,) for item in urls))


def languages_csv(report: LanguageReportOut) -> bytes:
    return _csv_bytes(
        ["lang", "is_default", "pages", "words", "avg_words", "missing_translations"],
        (
            (item.lang, item.is_default, item.pages, item.words, item.avg_words, item.missing_translations)
            for item in report.languages
        ),
    )


def missing_translations_csv(report: LanguageReportOut) -> bytes:
    rows: list[list[object]] = []
    for group in report.groups:
        for lang in group.missing:
            rows.append([group.source_url, group.source_lang, lang, group.word_gap])
    return _csv_bytes(["source_url", "source_lang", "missing_lang", "word_gap"], rows)


def all_zip(
    *,
    pages: Sequence[Page],
    links: Sequence[Link],
    orphans: Sequence[OrphanOut],
    issues: IssuesOut,
    sitemap_urls: Sequence[SitemapUrl],
    languages: LanguageReportOut | None = None,
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("pages.csv", pages_csv(pages))
        archive.writestr("links.csv", links_csv(links))
        archive.writestr("orphans.csv", orphans_csv(orphans))
        archive.writestr("issues.csv", issues_csv(issues))
        archive.writestr("sitemap.csv", sitemap_csv(sitemap_urls))
        if languages:
            archive.writestr("languages.csv", languages_csv(languages))
            archive.writestr("missing-translations.csv", missing_translations_csv(languages))
    return buffer.getvalue()
