import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models import Base
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = settings.DATABASE_URL + "_test"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

TEST_SYNC_DATABASE_URL = settings.SYNC_DATABASE_URL + "_test"
sync_test_engine = create_engine(TEST_SYNC_DATABASE_URL, echo=False)
TestingSyncSessionLocal = sessionmaker(sync_test_engine)

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    admin = await asyncpg.connect(
        host=settings.POSTGRES_HOST, port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD,
        database="postgres",
    )
    try:
        if not await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", settings.POSTGRES_DB + "_test"):
            await admin.execute(f'CREATE DATABASE "{settings.POSTGRES_DB}_test"')
    finally:
        await admin.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    from app.db import seed
    seed.AsyncSessionLocal = TestingSessionLocal
    await seed.seed_roles_and_admin()
    from app.db import session as db_session
    db_session.SyncSessionLocal = TestingSyncSessionLocal
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def db():
    async with TestingSessionLocal() as session:
        yield session

@pytest_asyncio.fixture
async def client(db):
    async def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
