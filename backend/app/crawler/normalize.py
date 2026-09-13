from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "gclid",
    "fbclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
}

SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "sms:", "whatsapp:")


def expand_hosts(hosts: list[str]) -> set[str]:
    out: set[str] = set()
    for raw in hosts:
        host = raw.lower().strip()
        if not host:
            continue
        host = host.removeprefix("https://").removeprefix("http://")
        host = host.split("/")[0].split(":")[0]
        if host.startswith("www."):
            out.add(host)
            out.add(host[4:])
        else:
            out.add(host)
            out.add(f"www.{host}")
    return out


def host_of(url: str) -> str | None:
    host = urlparse(url).hostname
    return host.lower() if host else None


def is_internal(url: str, allowed_hosts: set[str]) -> bool:
    host = host_of(url)
    return bool(host and host in allowed_hosts)


def normalize_url(url: str, base: str | None = None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if not url or url.startswith("#") or url.lower().startswith(SKIP_SCHEMES):
        return None
    if base:
        url = urljoin(base, url)
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None

    host = parsed.hostname.lower()
    if parsed.port and parsed.port not in (80, 443):
        netloc = f"{host}:{parsed.port}"
    else:
        netloc = host

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    ]
    query = urlencode(query_pairs)
    return urlunparse((parsed.scheme.lower(), netloc, path, "", query, ""))
