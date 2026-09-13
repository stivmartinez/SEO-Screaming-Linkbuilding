import { useEffect, useState, type ReactNode } from "react";

type Tone = "info" | "warn" | "error" | "empty";

type Props = {
  id: string;
  tone?: Tone;
  title?: string;
  children: ReactNode;
  dismissible?: boolean;
};

export function Callout({ id, tone = "info", title, children, dismissible = true }: Props) {
  const key = `seo-screaming:dismiss:${id}`;
  const [open, setOpen] = useState(true);

  useEffect(() => {
    if (!dismissible) return;
    try {
      if (localStorage.getItem(key) === "1") setOpen(false);
    } catch {
      /* ignore */
    }
  }, [dismissible, key]);

  if (!open) return null;

  return (
    <aside className={`callout callout-${tone}`} role="status">
      <div className="callout-body">
        {title ? <strong>{title}</strong> : null}
        <div className="callout-text">{children}</div>
      </div>
      {dismissible && (
        <button
          type="button"
          className="callout-dismiss"
          aria-label="Dismiss"
          onClick={() => {
            try {
              localStorage.setItem(key, "1");
            } catch {
              /* ignore */
            }
            setOpen(false);
          }}
        >
          ×
        </button>
      )}
    </aside>
  );
}
