from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
import os
from dotenv import load_dotenv, find_dotenv

# грузим .env из корня проекта
load_dotenv(find_dotenv(filename=".env"), override=False)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL не задан. Убедись, что файл urban-tickets-bot/.env существует и содержит DATABASE_URL."
    )

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

async def healthcheck():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))