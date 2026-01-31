import os
import asyncio
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")


def clean_asyncpg_url(db_url: str) -> str:
    """Convert to asyncpg URL and strip psycopg2-only params."""
    # Convert postgresql:// to postgresql+asyncpg://
    db_url = re.sub(r'^postgresql:', 'postgresql+asyncpg:', db_url)

    parsed = urlparse(db_url)
    query_params = parse_qs(parsed.query)

    # Remove unsupported asyncpg params
    for param in ["sslmode", "channel_binding", "gssencmode"]:
        query_params.pop(param, None)

    # Build new query string
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.async_session_factory = None

    async def initialize(self):
        database_url = db_url
        if not database_url:
            raise ValueError("DATABASE_URL environment variable is not set")

        async_database_url = clean_asyncpg_url(database_url)

        self.engine = create_async_engine(
            async_database_url,
            echo=True,  # Set to False in production
            pool_size=20,
            max_overflow=30,
            pool_pre_ping=True,
            pool_recycle=3600
        )

        self.async_session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    # goes through all ORM classes that inherit from Base
    async def create_tables(self):
        from models import Base
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    def get_session(self):
        if not self.async_session_factory:
            raise RuntimeError("Database not initialized. Call await db_manager.initialize() first.")
        return self.async_session_factory()

    async def close(self):
        if self.engine:
            await self.engine.dispose()


db_manager = DatabaseManager()


async def get_db_session():
    async with db_manager.get_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def test_connection():
    try:
        await db_manager.initialize()
        async with db_manager.engine.connect() as conn:
            result = await conn.execute(text("SELECT 'Hello World' as message"))
            print("Database connection successful!")
            print(result.fetchall())
        await db_manager.create_tables()
        print("Tables created successfully!")
    except Exception as e:
        print(f"Database connection failed: {e}")
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(test_connection())