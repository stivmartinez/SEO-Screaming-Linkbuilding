import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <Link to="/" className="brand-name">
            SEO Screaming Link Building
          </Link>
          <span className="brand-by">
            – By{" "}
            <a href="https://stivmartinez.com" target="_blank" rel="noreferrer">
              stivmartinez.com
            </a>
          </span>
        </div>
      </header>
      <main className="main">{children}</main>
    </div>
  );
}
