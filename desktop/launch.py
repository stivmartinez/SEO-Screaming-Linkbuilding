"""Desktop shell: local API + native window for non-technical users."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_NAME = "SEO Screaming Link Building"
DEFAULT_HOST = "127.0.0.1"


def repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / "SEOScreamingLinkBuilding"
    path.mkdir(parents=True, exist_ok=True)
    return path


def bundled_static_dir() -> Path | None:
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        candidate = meipass / "static"
        if (candidate / "index.html").is_file():
            return candidate
    root = repo_root()
    for candidate in (
        root / "backend" / "static",
        root / "frontend" / "dist",
    ):
        if (candidate / "index.html").is_file():
            return candidate
    return None


def ensure_ui_built(static_dir: Path | None) -> Path:
    if static_dir is not None:
        return static_dir
    if getattr(sys, "frozen", False):
        raise RuntimeError("UI assets missing from the application bundle.")

    root = repo_root()
    frontend = root / "frontend"
    target = root / "backend" / "static"
    if not (frontend / "package.json").is_file():
        raise RuntimeError("frontend/ not found. Build the UI before launching the desktop app.")

    import shutil
    import subprocess

    print("Building UI (first run may take a minute)…")
    subprocess.run(["npm", "install"], cwd=frontend, check=True)
    subprocess.run(["npm", "run", "build"], cwd=frontend, check=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(frontend / "dist", target)
    return target


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((DEFAULT_HOST, 0))
        return int(sock.getsockname()[1])


def wait_for_health(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
            time.sleep(0.1)
    raise RuntimeError(f"Server did not become ready: {last_error}")


def configure_environment(port: int, static_dir: Path, data_dir: Path) -> None:
    db_path = data_dir / "crawler.db"
    origin = f"http://{DEFAULT_HOST}:{port}"
    os.environ["CRAWLER_DATA_DIR"] = str(data_dir)
    os.environ["CRAWLER_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["CRAWLER_STATIC_DIR"] = str(static_dir)
    os.environ["CRAWLER_CORS_ORIGINS"] = f"{origin},http://localhost:{port}"
    os.environ.setdefault(
        "CRAWLER_USER_AGENT",
        "SEOScreamingLinkBuilding/1.0 (+https://stivmartinez.com; first-party SEO analysis)",
    )


def start_server(host: str, port: int):
    import uvicorn

    # Import only after env is configured so settings pick up desktop paths.
    from app.main import app

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="seo-screaming-api", daemon=True)
    thread.start()
    return server, thread


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    server_only = "--server-only" in args

    backend = repo_root() / "backend"
    if backend.is_dir() and str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    data_dir = user_data_dir()
    static_dir = ensure_ui_built(bundled_static_dir())
    port = free_port()
    configure_environment(port, static_dir, data_dir)

    server, _thread = start_server(DEFAULT_HOST, port)
    base = f"http://{DEFAULT_HOST}:{port}"
    wait_for_health(f"{base}/api/health")

    if server_only:
        print(f"{APP_NAME} server ready at {base}")
        print(f"Data directory: {data_dir}")
        try:
            while not server.should_exit:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        server.should_exit = True
        return 0

    try:
        import webview
    except ImportError as exc:
        raise SystemExit(
            "Desktop dependencies missing. Install with:\n"
            "  pip install -r desktop/requirements.txt"
        ) from exc

    window = webview.create_window(
        APP_NAME,
        url=base,
        width=1280,
        height=860,
        min_size=(960, 640),
        text_select=True,
    )

    def _on_closed() -> None:
        server.should_exit = True

    if window is not None:
        window.events.closed += _on_closed

    webview.start()
    server.should_exit = True
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
