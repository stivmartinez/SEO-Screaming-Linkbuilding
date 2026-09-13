# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SEO Screaming Link Building."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

SPECDIR = Path(SPECPATH).resolve()
ROOT = SPECDIR.parent
BACKEND = ROOT / "backend"
STATIC = BACKEND / "static"
LAUNCH = SPECDIR / "launch.py"

block_cipher = None

uvicorn_datas, uvicorn_binaries, uvicorn_hidden = collect_all("uvicorn")
anyio_hidden = collect_submodules("anyio")
sqlalchemy_hidden = collect_submodules("sqlalchemy")

a = Analysis(
    [str(LAUNCH)],
    pathex=[str(BACKEND)],
    binaries=uvicorn_binaries,
    datas=uvicorn_datas + [(str(STATIC), "static")],
    hiddenimports=uvicorn_hidden
    + anyio_hidden
    + sqlalchemy_hidden
    + [
        "aiosqlite",
        "selectolax",
        "httpx",
        "pydantic",
        "pydantic_settings",
        "multipart",
        "app",
        "app.main",
        "app.api.routes",
        "app.crawler.engine",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SEOScreamingLinkBuilding",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SEOScreamingLinkBuilding",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="SEO Screaming Link Building.app",
        icon=None,
        bundle_identifier="com.stivmartinez.seoscreaminglinkbuilding",
        info_plist={
            "CFBundleName": "SEO Screaming Link Building",
            "CFBundleDisplayName": "SEO Screaming Link Building",
            "CFBundleGetInfoString": "First-party SEO crawler by stivmartinez.com",
            "NSHighResolutionCapable": True,
        },
    )
