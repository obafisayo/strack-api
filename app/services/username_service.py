import re
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


async def generate_unique_username(db: AsyncSession, seed: str) -> str:
    base = SLUG_PATTERN.sub("", seed.split("@")[0].lower())[:20] or "strack"

    candidate = base
    while await db.scalar(select(User.id).where(User.username == candidate)) is not None:
        candidate = f"{base}{secrets.token_hex(2)}"

    return candidate
