from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import User, Role
from app.core.security import hash_password
from app.core.config import settings

ROLES = ["admin", "user", "auditor"]

async def seed_roles_and_admin():
    async with AsyncSessionLocal() as session:
        for r_name in ROLES:
            res = await session.execute(select(Role).where(Role.name == r_name))
            if not res.scalar_one_or_none():
                session.add(Role(name=r_name))
        await session.commit()

        res = await session.execute(select(User))
        users = res.unique().scalars().all()
        if not users:
            admin_role = (await session.execute(select(Role).where(Role.name == "admin"))).scalar_one()
            admin = User(
                username=settings.BOOTSTRAP_ADMIN_USER,
                email="admin@local",
                password_hash=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
                is_active=True,
                roles=[admin_role]
            )
            session.add(admin)
            await session.commit()
