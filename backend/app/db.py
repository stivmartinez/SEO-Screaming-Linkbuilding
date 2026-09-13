from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _add_column_if_missing(sync_conn, table: str, column: str, ddl: str) -> None:
    rows = sync_conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    names = {row[1] for row in rows}
    if column not in names:
        sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


async def init_db() -> None:
    async with engine.begin() as conn:
        from app import models  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(lambda sync_conn: _add_column_if_missing(sync_conn, "pages", "lang", "lang VARCHAR(16)"))
        await conn.run_sync(
            lambda sync_conn: _add_column_if_missing(sync_conn, "pages", "html_lang", "html_lang VARCHAR(32)")
        )
        await conn.run_sync(
            lambda sync_conn: _add_column_if_missing(sync_conn, "crawls", "extra_sitemaps", "extra_sitemaps TEXT DEFAULT '[]'")
        )
        await conn.run_sync(
            lambda sync_conn: _add_column_if_missing(sync_conn, "crawls", "language_mode", "language_mode VARCHAR(16) DEFAULT 'auto'")
        )
        await conn.run_sync(
            lambda sync_conn: _add_column_if_missing(sync_conn, "crawls", "default_lang", "default_lang VARCHAR(16)")
        )
        await conn.run_sync(
            lambda sync_conn: _add_column_if_missing(sync_conn, "crawls", "use_sitemap", "use_sitemap BOOLEAN DEFAULT 1")
        )
