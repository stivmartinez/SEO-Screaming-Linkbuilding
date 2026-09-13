import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Crawl, GraphNode, Issues, Orphan, PageDetail, SiteGraph } from "../types";
import { Callout } from "./Callout";
import { HttpBadge, StatusBadge } from "./StatusBadge";

type Filter = "all" | "orphans" | "issues" | "missing";

function pathLabel(url: string): string {
  try {
    const path = new URL(url).pathname;
    return path === "/" ? "/" : path.replace(/\/$/, "");
  } catch {
    return url;
  }
}

function pageTitle(node: GraphNode): string {
  return node.title || pathLabel(node.url);
}

function seedNode(nodes: GraphNode[], defaultLang: string): GraphNode | undefined {
  const preferred = nodes.filter((node) => node.lang === defaultLang);
  return preferred.find((node) => node.depth === 0) ?? preferred[0] ?? nodes[0];
}

function issueIndex(issues: Issues | null): Map<number, string[]> {
  const map = new Map<number, string[]>();
  if (!issues) return map;
  const add = (pageId: number | undefined, label: string) => {
    if (!pageId) return;
    const list = map.get(pageId) ?? [];
    if (!list.includes(label)) list.push(label);
    map.set(pageId, list);
  };
  for (const page of issues.broken) add(page.id, "broken");
  for (const page of issues.redirects) add(page.id, "redirect");
  for (const page of issues.missing_title) add(page.id, "no title");
  for (const page of issues.missing_h1) add(page.id, "no H1");
  for (const page of issues.noindex) add(page.id, "noindex");
  for (const group of issues.duplicate_titles) {
    for (const page of group.pages) add(page.id, "duplicate title");
  }
  return map;
}

const ISSUE_HELP: Record<string, { title: string; body: string }> = {
  broken: {
    title: "Broken URL",
    body: "This page returned an error status (4xx/5xx). Fix the link or restore the page so users and search engines don’t hit a dead end.",
  },
  redirect: {
    title: "Redirect",
    body: "The URL redirects before the final page. Prefer linking directly to the destination to avoid extra hops and diluted signals.",
  },
  "no title": {
    title: "Missing title",
    body: "No <title> tag was found. Titles are a primary ranking and click signal in search results — add a unique, descriptive one.",
  },
  "no H1": {
    title: "Missing H1",
    body: "No H1 heading was detected. Use one clear H1 that matches the page topic to help structure and relevance.",
  },
  noindex: {
    title: "Noindex",
    body: "Robots meta (or equivalent) tells search engines not to index this page. Keep it only if the page should stay out of search.",
  },
  "duplicate title": {
    title: "Duplicate title",
    body: "Another crawled page shares this same title. Duplicate titles confuse search engines and hurt click clarity — make each title unique.",
  },
};

function orphanHelp(hasSitemap: boolean): { title: string; body: string } {
  return {
    title: "Sitemap orphan",
    body: hasSitemap
      ? "Listed in the sitemap but has no internal inbound links. Users may never reach it from navigation — add contextual links or remove it from the sitemap."
      : "No internal inbound links were found. Without a sitemap, orphan detection is limited — add internal links if this page should be discoverable.",
  };
}

function missingLangHelp(langs: string[]): { title: string; body: string } {
  const list = langs.join(", ");
  return {
    title: `Missing translation${langs.length === 1 ? "" : "s"} (${list})`,
    body: `No equivalent page was found for ${list}. Add translated versions (or hreflang) if this content should exist in those languages.`,
  };
}

function wordGapHelp(gap: number): { title: string; body: string } {
  return {
    title: "Thin translation gap",
    body: `Language versions differ by about ${gap} words. Large gaps often mean a translation is incomplete or thinner than the source — review content parity.`,
  };
}

type Article = {
  id: string;
  title: string;
  depth: number;
  versions: GraphNode[];
  missing: string[];
  orphan: boolean;
  issues: string[];
  wordGap: number | null;
};

function buildArticles(
  graph: SiteGraph,
  orphanIds: Set<number>,
  orphanUrls: Set<string>,
  issuesByPage: Map<number, string[]>,
): Article[] {
  const grouped = new Map<string, GraphNode[]>();
  for (const node of graph.nodes) {
    const row = grouped.get(node.group_id) ?? [];
    row.push(node);
    grouped.set(node.group_id, row);
  }
  return [...grouped.entries()].map(([id, versions]) => {
    const preferred =
      versions.find((node) => node.lang === graph.default_lang) ??
      versions.slice().sort((a, b) => (a.depth ?? 99) - (b.depth ?? 99))[0];
    const present = new Set(versions.map((node) => node.lang));
    const missing = graph.languages.filter((lang) => !present.has(lang));
    const words = versions.map((node) => node.word_count);
    const wordGap = words.length > 1 ? Math.max(...words) - Math.min(...words) : null;
    const issues = [...new Set(versions.flatMap((node) => (node.page_id ? issuesByPage.get(node.page_id) ?? [] : [])))];
    const orphan = versions.some(
      (node) => (node.page_id != null && orphanIds.has(node.page_id)) || orphanUrls.has(node.url),
    );
    return {
      id,
      title: pageTitle(preferred),
      depth: preferred.depth ?? 99,
      versions,
      missing,
      orphan,
      issues,
      wordGap,
    };
  });
}

export function Workspace({
  crawl,
  graph,
  orphans,
  issues,
  initialPageId,
  onSelectPage,
}: {
  crawl: Crawl;
  graph: SiteGraph;
  orphans: Orphan[];
  issues: Issues | null;
  initialPageId?: number;
  onSelectPage?: (pageId: number) => void;
}) {
  const byId = useMemo(() => new Map(graph.nodes.map((node) => [node.id, node])), [graph.nodes]);
  const issuesByPage = useMemo(() => issueIndex(issues), [issues]);
  const orphanIds = useMemo(
    () => new Set(orphans.map((item) => item.page_id).filter((id): id is number => id != null)),
    [orphans],
  );
  const orphanUrls = useMemo(() => new Set(orphans.map((item) => item.url)), [orphans]);
  const articles = useMemo(
    () => buildArticles(graph, orphanIds, orphanUrls, issuesByPage),
    [graph, orphanIds, orphanUrls, issuesByPage],
  );

  const [selectedId, setSelectedId] = useState(() => {
    if (initialPageId) {
      const match = graph.nodes.find((node) => node.page_id === initialPageId);
      if (match) return match.id;
    }
    return seedNode(graph.nodes, graph.default_lang)?.id ?? "";
  });
  const [trail, setTrail] = useState<string[]>(() => (selectedId ? [selectedId] : []));
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [page, setPage] = useState<PageDetail | null>(null);

  const selected = byId.get(selectedId) ?? seedNode(graph.nodes, graph.default_lang);

  useEffect(() => {
    if (!initialPageId) return;
    const match = graph.nodes.find((node) => node.page_id === initialPageId);
    if (match && match.id !== selectedId) {
      setSelectedId(match.id);
      setTrail([match.id]);
    }
  }, [initialPageId, graph.nodes]);

  useEffect(() => {
    if (!selected?.page_id) {
      setPage(null);
      return;
    }
    let cancelled = false;
    void api
      .getPage(crawl.id, selected.page_id)
      .then((next) => {
        if (!cancelled) setPage(next);
      })
      .catch(() => {
        if (!cancelled) setPage(null);
      });
    return () => {
      cancelled = true;
    };
  }, [crawl.id, selected?.page_id]);

  const article = articles.find((item) => item.versions.some((node) => node.id === selected?.id));

  const neighbors = useMemo(() => {
    const empty = { contentIn: [] as GraphNode[], navIn: [] as GraphNode[], contentOut: [] as GraphNode[], navOut: [] as GraphNode[] };
    if (!selected) return empty;
    const contentIn: GraphNode[] = [];
    const navIn: GraphNode[] = [];
    const contentOut: GraphNode[] = [];
    const navOut: GraphNode[] = [];
    const seenIn = new Set<string>();
    const seenOut = new Set<string>();
    for (const edge of graph.edges) {
      if (edge.kind !== "link") continue;
      if (edge.target === selected.id) {
        const node = byId.get(edge.source);
        if (!node || seenIn.has(node.id)) continue;
        seenIn.add(node.id);
        (edge.sitewide ? navIn : contentIn).push(node);
      }
      if (edge.source === selected.id) {
        const node = byId.get(edge.target);
        if (!node || seenOut.has(node.id)) continue;
        seenOut.add(node.id);
        (edge.sitewide ? navOut : contentOut).push(node);
      }
    }
    const sortIn = (a: GraphNode, b: GraphNode) =>
      b.inbound_internal - a.inbound_internal || pageTitle(a).localeCompare(pageTitle(b));
    const sortOut = (a: GraphNode, b: GraphNode) =>
      (a.depth ?? 99) - (b.depth ?? 99) || b.inbound_internal - a.inbound_internal;
    contentIn.sort(sortIn);
    navIn.sort(sortIn);
    contentOut.sort(sortOut);
    navOut.sort(sortOut);
    return { contentIn, navIn, contentOut, navOut };
  }, [byId, graph.edges, selected]);

  const missingCount = articles.filter((item) => item.missing.length > 0).length;
  const issueCount = issues?.issue_count ?? crawl.issue_count;
  const multilingual = graph.multilingual && crawl.language_mode !== "off";
  const hasSitemap = crawl.use_sitemap && crawl.pages_from_sitemap > 0;
  const sitemapSkipped = !crawl.use_sitemap;
  const sitemapMissing = crawl.use_sitemap && crawl.pages_from_sitemap === 0;

  useEffect(() => {
    if (!multilingual && filter === "missing") setFilter("all");
    if (!hasSitemap && filter === "orphans") setFilter("all");
  }, [multilingual, hasSitemap, filter]);

  const outline = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = articles.filter((item) => {
      if (filter === "orphans" && !item.orphan) return false;
      if (filter === "issues" && item.issues.length === 0) return false;
      if (filter === "missing" && item.missing.length === 0) return false;
      if (!needle) return true;
      return item.versions.some(
        (node) => pageTitle(node).toLowerCase().includes(needle) || node.url.toLowerCase().includes(needle),
      );
    });
    const byDepth = new Map<number, Article[]>();
    for (const item of filtered) {
      const row = byDepth.get(item.depth) ?? [];
      row.push(item);
      byDepth.set(item.depth, row);
    }
    return [...byDepth.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([depth, items]) => ({
        depth,
        items: items.slice().sort((a, b) => a.title.localeCompare(b.title)),
      }));
  }, [articles, filter, query]);

  function select(id: string, mode: "jump" | "walk") {
    const node = byId.get(id);
    setSelectedId(id);
    setTrail((prev) => {
      if (mode === "jump") return [id];
      return prev[prev.length - 1] === id ? prev : [...prev, id];
    });
    if (node?.page_id) onSelectPage?.(node.page_id);
  }

  if (!selected) {
    return <p className="muted">No pages in this crawl yet.</p>;
  }

  const selectedIssues = selected.page_id ? issuesByPage.get(selected.page_id) ?? [] : [];
  const external = page?.outbound.filter((link) => link.kind === "external") ?? [];
  const isOrphan = Boolean(article?.orphan || (selected.page_id != null && orphanIds.has(selected.page_id)));
  const pageWarnings = [
    ...selectedIssues.map((code) => ISSUE_HELP[code] ?? { title: code, body: "Review this SEO issue." }),
    ...(isOrphan ? [orphanHelp(hasSitemap)] : []),
    ...(multilingual && article && article.missing.length > 0 ? [missingLangHelp(article.missing)] : []),
    ...(article && article.wordGap != null && article.wordGap >= 150 ? [wordGapHelp(article.wordGap)] : []),
  ];

  return (
    <div className="workspace-page">
      <header className="workspace-head">
        <div>
          <p className="muted">
            <Link to="/">Crawls</Link>
            <span> / {crawl.site?.name || crawl.seed_url}</span>
          </p>
          <h1>{crawl.site?.name || crawl.seed_url}</h1>
        </div>
        <div className="workspace-actions">
          <StatusBadge status={crawl.status} />
          {["pending", "running"].includes(crawl.status) && (
            <button className="btn secondary" type="button" onClick={() => void api.cancelCrawl(crawl.id)}>
              Cancel
            </button>
          )}
          {crawl.status === "completed" && (
            <a className="btn secondary" href={`/api/crawls/${crawl.id}/export/all.zip`}>
              Export
            </a>
          )}
        </div>
      </header>

      <div className="workspace-stats">
        <Stat active={filter === "all"} onClick={() => setFilter("all")} label={`${articles.length} pages`} />
        <Stat
          active={filter === "orphans"}
          onClick={() => hasSitemap && setFilter(filter === "orphans" ? "all" : "orphans")}
          label={hasSitemap ? `${orphans.length} orphans` : "Orphans n/a"}
        />
        <Stat
          active={filter === "issues"}
          onClick={() => setFilter(filter === "issues" ? "all" : "issues")}
          label={`${issueCount} issues`}
        />
        {multilingual ? (
          <Stat
            active={filter === "missing"}
            onClick={() => missingCount > 0 && setFilter(filter === "missing" ? "all" : "missing")}
            label={
              missingCount > 0
                ? `${missingCount} missing translations`
                : `${articles.length}/${articles.length} translations`
            }
          />
        ) : (
          <span className="stat-pill muted">Single language</span>
        )}
        <span className="muted">
          {multilingual ? graph.languages.join(" · ") : graph.default_lang || "—"}
          {crawl.message ? ` · ${crawl.message}` : ""}
        </span>
      </div>

      {crawl.error && (
        <Callout id={`crawl-error-${crawl.id}`} tone="error" title="Crawl error" dismissible={false}>
          {crawl.error}
        </Callout>
      )}
      {sitemapSkipped && (
        <Callout id={`sitemap-off-${crawl.id}`} tone="info" title="Sitemap skipped">
          Discovery used links only. Orphan checks are unavailable for this crawl.
        </Callout>
      )}
      {sitemapMissing && (
        <Callout id={`sitemap-miss-${crawl.id}`} tone="warn" title="No sitemap found">
          Checked robots.txt and common paths. Add a custom sitemap URL next time, or keep crawling via links.
        </Callout>
      )}
      {!multilingual && crawl.language_mode === "auto" && (
        <Callout id={`lang-mono-${crawl.id}`} tone="info" title="One language detected">
          Translation gaps are hidden. Switch to Path or Hreflang on the next crawl if this is wrong.
        </Callout>
      )}
      {articles.length === 0 && (
        <Callout id={`empty-pages-${crawl.id}`} tone="empty" title="No pages" dismissible={false}>
          Nothing was fetched. Check the seed URL, hosts, and robots.txt.
        </Callout>
      )}

      {trail.length > 1 && (
        <div className="flow-crumb">
          {trail.map((id, index) => {
            const node = byId.get(id);
            if (!node) return null;
            return (
              <span key={`${id}-${index}`}>
                {index > 0 && <span className="muted"> → </span>}
                <button
                  type="button"
                  className={`flow-crumb-btn${id === selected.id ? " active" : ""}`}
                  onClick={() => {
                    setSelectedId(id);
                    setTrail(trail.slice(0, index + 1));
                    if (node.page_id) onSelectPage?.(node.page_id);
                  }}
                >
                  {pathLabel(node.url)}
                </button>
              </span>
            );
          })}
        </div>
      )}

      <div className="flow-explorer">
        <aside className="flow-outline">
          <div className="flow-col-head">
            <input placeholder="Find a page" value={query} onChange={(event) => setQuery(event.target.value)} />
          </div>
          <div className="flow-outline-list">
            {outline.map((group) => (
              <section key={group.depth}>
                <div className="flow-depth-label">
                  {group.depth === 99 ? "Unknown depth" : group.depth === 0 ? "Homepage" : `${group.depth} click${group.depth === 1 ? "" : "s"} from home`}
                  <span className="muted"> · {group.items.length}</span>
                </div>
                {group.items.map((item) => {
                  const active = item.versions.some((node) => node.id === selected.id);
                  return (
                    <button
                      key={item.id}
                      type="button"
                      className={`flow-outline-item${active ? " selected" : ""}`}
                      onClick={() => {
                        const next =
                          item.versions.find((node) => node.lang === selected.lang) ??
                          item.versions.find((node) => node.lang === graph.default_lang) ??
                          item.versions[0];
                        select(next.id, "jump");
                      }}
                    >
                      <strong>{item.title}</strong>
                      <span className="url muted">
                        {pathLabel((item.versions.find((node) => node.lang === graph.default_lang) ?? item.versions[0]).url)}
                      </span>
                      <span className="outline-meta">
                        {multilingual &&
                          graph.languages.map((lang) => (
                            <i
                              key={lang}
                              className={`lang-dot lang-${lang}${item.versions.some((node) => node.lang === lang) ? "" : " missing"}`}
                              title={item.versions.some((node) => node.lang === lang) ? lang : `${lang} missing`}
                            />
                          ))}
                        {item.orphan && <span className="pill warn">orphan</span>}
                        {item.issues.length > 0 && <span className="pill err">{item.issues[0]}</span>}
                        {multilingual && item.missing.length > 0 && (
                          <span className="pill warn">missing {item.missing.join(" ")}</span>
                        )}
                      </span>
                    </button>
                  );
                })}
              </section>
            ))}
            {outline.length === 0 && (
              <Callout id={`outline-empty-${crawl.id}-${filter}`} tone="empty" title="Nothing here" dismissible={false}>
                {filter === "orphans" && !hasSitemap
                  ? "Orphans need a sitemap."
                  : filter === "all"
                    ? "No pages in this outline."
                    : "Nothing matches this filter."}
              </Callout>
            )}
          </div>
        </aside>

        <div className="flow-board">
          <NeighborColumn
            key={`${selected.id}-in`}
            title="Links here"
            content={neighbors.contentIn}
            nav={neighbors.navIn}
            onPick={(id) => select(id, "walk")}
          />
          <article className="flow-focus">
            <div className="focus-kicker">
              <HttpBadge code={page?.status_code ?? null} />
              {multilingual && <span className="muted">{selected.lang}</span>}
            </div>
            <h2>{pageTitle(selected)}</h2>
            <p className="url">{selected.url}</p>
            {multilingual && (
              <div className="lang-row">
                {graph.languages.map((lang) => {
                  const version = article?.versions.find((node) => node.lang === lang);
                  if (!version) {
                    return (
                      <span key={lang} className="lang-chip missing" title={`No ${lang} version found for this page`}>
                        {lang} missing
                      </span>
                    );
                  }
                  return (
                    <button
                      key={lang}
                      type="button"
                      className={`lang-chip${version.id === selected.id ? " active" : ""}`}
                      onClick={() => select(version.id, "jump")}
                    >
                      {lang} · {version.word_count}
                    </button>
                  );
                })}
              </div>
            )}
            <dl className="flow-focus-meta">
              <div>
                <dt>Depth</dt>
                <dd>{selected.depth ?? "—"}</dd>
              </div>
              <div>
                <dt>In</dt>
                <dd>{selected.inbound_internal}</dd>
              </div>
              <div>
                <dt>Out</dt>
                <dd>{selected.outbound_internal}</dd>
              </div>
              <div>
                <dt>Words</dt>
                <dd>{selected.word_count}</dd>
              </div>
            </dl>
            {page && (
              <div className="focus-seo">
                <div>
                  <span className="muted">H1</span> {page.h1 || "—"}
                </div>
                <div>
                  <span className="muted">Title</span> {page.title || "—"}
                </div>
                <div>
                  <span className="muted">Meta</span> {page.meta_description || "—"}
                </div>
                <div>
                  <span className="muted">Canonical</span>{" "}
                  <span className="url">{page.canonical ? pathLabel(page.canonical) : "—"}</span>
                </div>
                <div>
                  <span className="muted">Robots</span> {page.robots_meta || "indexable"}
                  {page.indexable ? "" : " · not indexable"}
                </div>
                {page.redirect_chain.length > 0 && (
                  <div>
                    <span className="muted">Redirect</span> {page.redirect_chain.length} hops
                  </div>
                )}
              </div>
            )}
            {pageWarnings.length > 0 && (
              <div className="focus-warnings">
                <div className="focus-warnings-label">Warnings</div>
                {pageWarnings.map((item) => (
                  <div className="focus-warning" key={item.title}>
                    <strong>{item.title}</strong>
                    <p>{item.body}</p>
                  </div>
                ))}
              </div>
            )}
          </article>
          <NeighborColumn
            key={`${selected.id}-out`}
            title="Links out"
            content={neighbors.contentOut}
            nav={neighbors.navOut}
            external={external.map((link) => link.to_url)}
            onPick={(id) => select(id, "walk")}
          />
        </div>
      </div>
    </div>
  );
}

function Stat({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button type="button" className={`stat-link${active ? " active" : ""}`} onClick={onClick}>
      {label}
    </button>
  );
}

function NeighborColumn({
  title,
  content,
  nav,
  external = [],
  onPick,
}: {
  title: string;
  content: GraphNode[];
  nav: GraphNode[];
  external?: string[];
  onPick: (id: string) => void;
}) {
  const [showNav, setShowNav] = useState(false);
  const [showExternal, setShowExternal] = useState(false);
  return (
    <section className="flow-col">
      <div className="flow-col-head">
        <strong>
          {title} <span className="muted">{content.length}</span>
        </strong>
      </div>
      <div className="flow-col-list">
        {content.length === 0 && nav.length === 0 && (
          <p className="muted" style={{ padding: 12 }}>
            None.
          </p>
        )}
        {content.map((node) => (
          <NeighborCard key={node.id} node={node} onPick={onPick} />
        ))}
        {nav.length > 0 && (
          <>
            <button type="button" className="flow-nav-toggle" onClick={() => setShowNav((value) => !value)}>
              {showNav ? "Hide" : "Show"} {nav.length} sitewide nav
            </button>
            {showNav && nav.map((node) => <NeighborCard key={node.id} node={node} onPick={onPick} />)}
          </>
        )}
        {external.length > 0 && (
          <>
            <button type="button" className="flow-nav-toggle" onClick={() => setShowExternal((value) => !value)}>
              {showExternal ? "Hide" : "Show"} {external.length} external
            </button>
            {showExternal &&
              external.map((url) => (
                <div key={url} className="flow-link-card static">
                  <span className="url muted">{url}</span>
                </div>
              ))}
          </>
        )}
      </div>
    </section>
  );
}

function NeighborCard({ node, onPick }: { node: GraphNode; onPick: (id: string) => void }) {
  return (
    <button type="button" className="flow-link-card" onClick={() => onPick(node.id)}>
      <strong>{pageTitle(node)}</strong>
      <span className="url muted">{pathLabel(node.url)}</span>
      <span className="muted">
        {node.depth != null ? `depth ${node.depth}` : "depth —"} · {node.inbound_internal} in · {node.outbound_internal} out
      </span>
    </button>
  );
}
