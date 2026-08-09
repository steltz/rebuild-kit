import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import async_session


@pytest.fixture
async def db_session() -> AsyncSession:
    async with async_session() as session:
        yield session
        await session.rollback()
