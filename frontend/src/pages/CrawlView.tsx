import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Callout } from "../components/Callout";
import { Workspace } from "../components/Workspace";
import { StatusBadge } from "../components/StatusBadge";
import type { Crawl, Issues, Orphan, SiteGraph } from "../types";

export function CrawlView() {
  const { crawlId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const id = Number(crawlId);
  const selectedPageId = searchParams.get("page") ? Number(searchParams.get("page")) : undefined;
  const [crawl, setCrawl] = useState<Crawl | null>(null);
  const [graph, setGraph] = useState<SiteGraph | null>(null);
  const [orphans, setOrphans] = useState<Orphan[]>([]);
  const [issues, setIssues] = useState<Issues | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const next = await api.getCrawl(id);
    setCrawl(next);
    if (next.status === "completed") {
      const [nextGraph, nextOrphans, nextIssues] = await Promise.all([
        api.getGraph(id),
        api.getOrphans(id),
        api.getIssues(id),
      ]);
      setGraph(nextGraph);
      setOrphans(nextOrphans);
      setIssues(nextIssues);
    }
  }

  useEffect(() => {
    if (!id) return;
    void refresh().catch((err) => setError(err instanceof Error ? err.message : "Load failed"));
  }, [id]);

  useEffect(() => {
    if (!crawl || !["pending", "running"].includes(crawl.status)) return;
    const timer = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, 1500);
    return () => window.clearInterval(timer);
  }, [crawl?.status, id]);

  if (!crawl) {
    return (
      <Callout id="crawl-loading" tone={error ? "error" : "empty"} title={error ? "Could not load" : "Loading"} dismissible={false}>
        {error || "Fetching crawl…"}
      </Callout>
    );
  }

  if (graph) {
    return (
      <Workspace
        crawl={crawl}
        graph={graph}
        orphans={orphans}
        issues={issues}
        initialPageId={selectedPageId}
        onSelectPage={(nextId) => setSearchParams({ page: String(nextId) }, { replace: true })}
      />
    );
  }

  return (
    <div className="workspace-page">
      <header className="workspace-head">
        <div>
          <p className="muted">
            <Link to="/">Crawls</Link>
            <span> / {crawl.site?.name || crawl.seed_url}</span>
          </p>
          <h1>{crawl.site?.name || crawl.seed_url}</h1>
          <p className="url muted">{crawl.seed_url}</p>
        </div>
        <div className="workspace-actions">
          <StatusBadge status={crawl.status} />
          {["pending", "running"].includes(crawl.status) && (
            <button className="btn secondary" type="button" onClick={() => void api.cancelCrawl(id)}>
              Cancel
            </button>
          )}
        </div>
      </header>
      <div className="workspace-stats">
        <span>
          {crawl.pages_crawled} crawled · {crawl.pages_queued} queued
          {crawl.use_sitemap ? ` · ${crawl.pages_from_sitemap} sitemap` : " · sitemap off"}
        </span>
      </div>
      {crawl.message && (
        <Callout id={`progress-${crawl.id}`} tone="info" title="In progress" dismissible={false}>
          {crawl.message}
        </Callout>
      )}
      {crawl.error && (
        <Callout id={`run-error-${crawl.id}`} tone="error" title="Failed" dismissible={false}>
          {crawl.error}
        </Callout>
      )}
      {crawl.status === "failed" && !crawl.error && (
        <Callout id={`failed-${crawl.id}`} tone="error" title="Crawl failed" dismissible={false}>
          Check the seed URL and try again with a lower concurrency.
        </Callout>
      )}
      {["pending", "running"].includes(crawl.status) && (
        <Callout id={`wait-${crawl.id}`} tone="info" title="Workspace opens when finished">
          Closing this window cancels an in-process crawl.
        </Callout>
      )}
      {error && (
        <Callout id={`view-error-${crawl.id}`} tone="error" title="Refresh error" dismissible={false}>
          {error}
        </Callout>
      )}
    </div>
  );
}
