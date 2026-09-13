import type {
  Crawl,
  CrawlCreate,
  Issues,
  LanguageReport,
  Orphan,
  PageDetail,
  PageGroupList,
  PageList,
  SiteGraph,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  listCrawls: () => request<Crawl[]>("/api/crawls"),
  getCrawl: (id: number) => request<Crawl>(`/api/crawls/${id}`),
  createCrawl: (payload: CrawlCreate) =>
    request<Crawl>("/api/crawls", { method: "POST", body: JSON.stringify(payload) }),
  cancelCrawl: (id: number) => request<Crawl>(`/api/crawls/${id}/cancel`, { method: "POST" }),
  deleteCrawl: (id: number) => request<void>(`/api/crawls/${id}`, { method: "DELETE" }),
  deleteSite: (id: number) => request<void>(`/api/sites/${id}`, { method: "DELETE" }),
  listPages: (id: number, params: { q?: string; lang?: string; offset?: number; limit?: number }) => {
    const search = new URLSearchParams();
    if (params.q) search.set("q", params.q);
    if (params.lang) search.set("lang", params.lang);
    if (params.offset != null) search.set("offset", String(params.offset));
    if (params.limit != null) search.set("limit", String(params.limit));
    const query = search.toString();
    return request<PageList>(`/api/crawls/${id}/pages${query ? `?${query}` : ""}`);
  },
  getPage: (crawlId: number, pageId: number) =>
    request<PageDetail>(`/api/crawls/${crawlId}/pages/${pageId}`),
  getOrphans: (id: number, lang?: string) =>
    request<Orphan[]>(`/api/crawls/${id}/orphans${lang ? `?lang=${encodeURIComponent(lang)}` : ""}`),
  getIssues: (id: number, lang?: string) =>
    request<Issues>(`/api/crawls/${id}/issues${lang ? `?lang=${encodeURIComponent(lang)}` : ""}`),
  getGraph: (id: number) => request<SiteGraph>(`/api/crawls/${id}/graph`),
  getLanguages: (id: number) => request<LanguageReport>(`/api/crawls/${id}/languages`),
  listPageGroups: (id: number, params: { q?: string; lang?: string; offset?: number; limit?: number }) => {
    const search = new URLSearchParams();
    if (params.q) search.set("q", params.q);
    if (params.lang) search.set("lang", params.lang);
    if (params.offset != null) search.set("offset", String(params.offset));
    if (params.limit != null) search.set("limit", String(params.limit));
    const query = search.toString();
    return request<PageGroupList>(`/api/crawls/${id}/page-groups${query ? `?${query}` : ""}`);
  },
};
