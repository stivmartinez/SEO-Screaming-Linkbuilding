export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge ${status}`}>{status}</span>;
}

export function HttpBadge({ code }: { code: number | null }) {
  if (code == null) return <span className="muted">—</span>;
  const kind = code >= 400 ? "err" : code >= 300 ? "warn" : "ok";
  return <span className={`badge ${kind}`}>{code}</span>;
}
