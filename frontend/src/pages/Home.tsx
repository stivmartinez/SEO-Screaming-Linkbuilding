import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { Callout } from "../components/Callout";
import { StatusBadge } from "../components/StatusBadge";
import type { Crawl, LanguageMode } from "../types";

type SiteGroup = {
  siteId: number;
  name: string;
  crawls: Crawl[];
};

export function Home() {
  const navigate = useNavigate();
  const [crawls, setCrawls] = useState<Crawl[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [useSitemap, setUseSitemap] = useState(true);
  const [languageMode, setLanguageMode] = useState<LanguageMode>("auto");

  const sites = useMemo<SiteGroup[]>(() => {
    const groups = new Map<number, SiteGroup>();
    for (const crawl of crawls) {
      const existing = groups.get(crawl.site_id);
      if (existing) {
        existing.crawls.push(crawl);
      } else {
        groups.set(crawl.site_id, {
          siteId: crawl.site_id,
          name: crawl.site?.name || crawl.site?.primary_host || crawl.seed_url,
          crawls: [crawl],
        });
      }
    }
    return [...groups.values()];
  }, [crawls]);

  async function load() {
    try {
      setCrawls(await api.listCrawls());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load crawls");
    }
  }

  async function removeSite(siteId: number, name: string) {
    if (!window.confirm(`Remove ${name} and all of its crawls?`)) return;
    try {
      await api.deleteSite(siteId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove site");
    }
  }

  async function removeCrawl(crawlId: number, seed: string) {
    if (!window.confirm(`Remove this crawl of ${seed}?`)) return;
    try {
      await api.deleteCrawl(crawlId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove crawl");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const seed = String(form.get("seed_url") || "").trim();
    const extra = String(form.get("allowed_hosts") || "")
      .split(/[\s,]+/)
      .map((item) => item.trim())
      .filter(Boolean);
    const sitemaps = String(form.get("extra_sitemaps") || "")
      .split(/[\n,]+/)
      .map((item) => item.trim())
      .filter(Boolean);
    const defaultLang = String(form.get("default_lang") || "").trim().toLowerCase() || undefined;
    setPending(true);
    setError(null);
    try {
      const crawl = await api.createCrawl({
        seed_url: seed,
        name: String(form.get("name") || "") || undefined,
        allowed_hosts: extra,
        concurrency: Number(form.get("concurrency") || 4),
        delay_seconds: Number(form.get("delay_seconds") || 0.25),
        max_pages: Number(form.get("max_pages") || 10000),
        extra_sitemaps: useSitemap ? sitemaps : [],
        language_mode: languageMode,
        default_lang: defaultLang,
        use_sitemap: useSitemap,
      });
      navigate(`/crawls/${crawl.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start crawl");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="home-layout">
      <div className="guide-strip" aria-label="How it works">
        <div className="guide-item">
          <span className="guide-mark">1</span>
          <div>
            <strong>Seed</strong>
            <span>Homepage you own</span>
          </div>
        </div>
        <div className="guide-item">
          <span className="guide-mark">2</span>
          <div>
            <strong>Discover</strong>
            <span>Links + optional sitemap</span>
          </div>
        </div>
        <div className="guide-item">
          <span className="guide-mark">3</span>
          <div>
            <strong>Review</strong>
            <span>Issues, orphans, languages</span>
          </div>
        </div>
      </div>

      <Callout id="home-first-party" tone="info" title="First-party only">
        Crawl sites you own. Robots.txt is respected. HTML only — no JS rendering.
      </Callout>

      {error && (
        <Callout id={`home-error-${error.slice(0, 24)}`} tone="error" title="Something failed" dismissible={false}>
          {error}
        </Callout>
      )}

      <div className="grid-2">
        <section>
          <div className="page-head">
            <div>
              <h1>New crawl</h1>
              <p className="muted">Defaults work for most sites. Open options only if you need them.</p>
            </div>
          </div>
          <form className="card" onSubmit={onSubmit}>
            <div className="row">
              <label htmlFor="seed_url">Seed URL</label>
              <input id="seed_url" name="seed_url" type="url" required placeholder="https://example.com" />
            </div>
            <div className="row">
              <label htmlFor="name">Project name</label>
              <input id="name" name="name" placeholder="Optional" />
            </div>
            <div className="row">
              <label htmlFor="allowed_hosts">Extra hosts</label>
              <input id="allowed_hosts" name="allowed_hosts" placeholder="www · blog · es.example.com" />
              <p className="hint">Add language or CDN hosts if pages live off the main domain.</p>
            </div>

            <details className="options">
              <summary>Sitemap &amp; languages</summary>
              <div className="options-body">
                <div className="row">
                  <label htmlFor="sitemap_mode">Sitemap</label>
                  <select
                    id="sitemap_mode"
                    value={useSitemap ? "auto" : "off"}
                    onChange={(event) => setUseSitemap(event.target.value === "auto")}
                  >
                    <option value="auto">Auto-discover</option>
                    <option value="off">Skip sitemap</option>
                  </select>
                  <p className="hint">Auto checks robots.txt and common paths. Orphans need a sitemap.</p>
                </div>
                {useSitemap && (
                  <div className="row">
                    <label htmlFor="extra_sitemaps">Custom sitemap URLs</label>
                    <textarea
                      id="extra_sitemaps"
                      name="extra_sitemaps"
                      rows={2}
                      placeholder="https://example.com/wp-sitemap.xml"
                    />
                  </div>
                )}
                <div className="row">
                  <label htmlFor="language_mode">Languages</label>
                  <select
                    id="language_mode"
                    value={languageMode}
                    onChange={(event) => setLanguageMode(event.target.value as LanguageMode)}
                  >
                    <option value="auto">Auto</option>
                    <option value="off">Single language</option>
                    <option value="path">URL prefixes (/en, /es)</option>
                    <option value="hreflang">Hreflang only</option>
                  </select>
                  <p className="hint">
                    {languageMode === "off" && "Treat the site as one language. No missing-translation checks."}
                    {languageMode === "auto" && "Detect from hreflang, html lang, and /xx/ paths."}
                    {languageMode === "path" && "Group by path prefixes like /en/ and /es/."}
                    {languageMode === "hreflang" && "Use alternate links only — ignore path guessing."}
                  </p>
                </div>
                <div className="row">
                  <label htmlFor="default_lang">Default language</label>
                  <input id="default_lang" name="default_lang" placeholder="Auto · e.g. en, es, fr" />
                </div>
              </div>
            </details>

            <details className="options">
              <summary>Crawl speed</summary>
              <div className="options-body">
                <div className="form-grid">
                  <div className="row">
                    <label htmlFor="concurrency">Concurrency</label>
                    <input id="concurrency" name="concurrency" type="number" min={1} max={16} defaultValue={4} />
                  </div>
                  <div className="row">
                    <label htmlFor="delay_seconds">Delay (s)</label>
                    <input
                      id="delay_seconds"
                      name="delay_seconds"
                      type="number"
                      min={0}
                      max={10}
                      step={0.05}
                      defaultValue={0.25}
                    />
                  </div>
                  <div className="row">
                    <label htmlFor="max_pages">Max pages</label>
                    <input id="max_pages" name="max_pages" type="number" min={1} defaultValue={10000} />
                  </div>
                </div>
              </div>
            </details>

            <button className="btn" type="submit" disabled={pending}>
              {pending ? "Starting…" : "Start crawl"}
            </button>
          </form>
        </section>
        <section>
          <h2>Sites</h2>
          <div className="crawl-list" style={{ marginTop: 16 }}>
            {sites.map((group) => (
              <div className="site-group" key={group.siteId}>
                <div className="site-head">
                  <div>
                    <h3>{group.name}</h3>
                    <div className="muted">
                      {group.crawls.length} crawl{group.crawls.length === 1 ? "" : "s"}
                    </div>
                  </div>
                  <button
                    className="btn danger"
                    type="button"
                    onClick={() => void removeSite(group.siteId, group.name)}
                  >
                    Remove site
                  </button>
                </div>
                {group.crawls.map((crawl) => (
                  <div className="crawl-item" key={crawl.id}>
                    <Link to={`/crawls/${crawl.id}`}>
                      <strong>{crawl.seed_url}</strong>
                      <div className="url muted">{crawl.pages_crawled} pages</div>
                    </Link>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <StatusBadge status={crawl.status} />
                      <button
                        className="btn danger"
                        type="button"
                        onClick={() => void removeCrawl(crawl.id, crawl.seed_url)}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ))}
            {crawls.length === 0 && (
              <Callout id="home-empty-sites" tone="empty" title="No sites yet" dismissible={false}>
                Start with a seed URL. Results stay on this machine.
              </Callout>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
