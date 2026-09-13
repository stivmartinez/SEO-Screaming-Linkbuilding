export type Site = {
  id: number;
  name: string;
  primary_host: string;
};

export type LanguageMode = "auto" | "off" | "path" | "hreflang";

export type Crawl = {
  id: number;
  site_id: number;
  site: Site | null;
  seed_url: string;
  allowed_hosts: string[];
  status: string;
  started_at: string | null;
  finished_at: string | null;
  pages_crawled: number;
  pages_queued: number;
  pages_from_sitemap: number;
  max_pages: number;
  concurrency: number;
  delay_seconds: number;
  extra_sitemaps: string[];
  language_mode: LanguageMode;
  default_lang: string | null;
  use_sitemap: boolean;
  error: string | null;
  message: string | null;
  orphan_count: number;
  issue_count: number;
};

export type PageRow = {
  id: number;
  crawl_id: number;
  url: string;
  final_url: string | null;
  status_code: number | null;
  content_type: string | null;
  title: string | null;
  meta_description: string | null;
  h1: string | null;
  h1_count: number;
  canonical: string | null;
  robots_meta: string | null;
  indexable: boolean;
  word_count: number;
  depth: number | null;
  redirect_chain: string[];
  inbound_internal: number;
  outbound_internal: number;
  outbound_external: number;
  lang: string | null;
  html_lang: string | null;
  fetched_at: string | null;
  error: string | null;
};

export type LinkRow = {
  id: number;
  from_url: string;
  to_url: string;
  kind: string;
  anchor: string | null;
  rel: string | null;
};

export type LanguageVersion = {
  lang: string;
  url: string | null;
  page_id: number | null;
  title: string | null;
  word_count: number | null;
};

export type LanguageStat = {
  lang: string;
  is_default: boolean;
  pages: number;
  words: number;
  avg_words: number;
  missing_translations: number;
};

export type LanguageGroup = {
  source_url: string;
  source_lang: string;
  versions: Record<string, LanguageVersion>;
  missing: string[];
  word_gap: number | null;
};

export type LanguageReport = {
  default_lang: string;
  languages: LanguageStat[];
  groups: LanguageGroup[];
  thin_groups: LanguageGroup[];
  group_count: number;
  complete_groups: number;
};

export type PageDetail = PageRow & {
  inbound: LinkRow[];
  outbound: LinkRow[];
  alternates: LanguageVersion[];
};

export type PageList = {
  items: PageRow[];
  total: number;
};

export type PageGroupList = {
  items: LanguageGroup[];
  total: number;
  languages: string[];
  default_lang: string;
};

export type Orphan = {
  url: string;
  page_id: number | null;
  status_code: number | null;
  title: string | null;
  inbound_internal: number;
};

export type Issues = {
  broken: PageRow[];
  redirects: PageRow[];
  missing_title: PageRow[];
  missing_h1: PageRow[];
  noindex: PageRow[];
  duplicate_titles: { title: string; pages: PageRow[] }[];
  issue_count: number;
};

export type GraphNode = {
  id: string;
  page_id: number | null;
  url: string;
  title: string | null;
  lang: string;
  group_id: string;
  word_count: number;
  depth: number | null;
  inbound_internal: number;
  outbound_internal: number;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  kind: "hreflang" | "link" | string;
  sitewide: boolean;
  weight: number;
};

export type SiteGraph = {
  languages: string[];
  default_lang: string;
  multilingual: boolean;
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export type CrawlCreate = {
  seed_url: string;
  name?: string;
  allowed_hosts: string[];
  concurrency: number;
  delay_seconds: number;
  max_pages: number;
  extra_sitemaps: string[];
  language_mode: LanguageMode;
  default_lang?: string;
  use_sitemap: boolean;
};
