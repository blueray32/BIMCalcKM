import asyncio
from sqlalchemy import select
from bimcalc.db.connection import get_session
from bimcalc.db.models import ProjectModel


async def check_projects():
    async with get_session() as session:
        # Check count
        stmt = select(ProjectModel).order_by(ProjectModel.created_at.desc())
        result = await session.execute(stmt)
        projects = result.scalars().all()

        print(f"Total projects found: {len(projects)}")
        for p in projects:
            print(
                f"Project: {p.display_name} (ID: {p.project_id}, Org: {p.org_id}, Created: {p.created_at})"
            )

        # Test the specific query I used
        stmt_limit = (
            select(ProjectModel).order_by(ProjectModel.created_at.desc()).limit(1)
        )
        result_limit = await session.execute(stmt_limit)
        latest = result_limit.scalar_one_or_none()

        if latest:
            print(f"\nLatest project query returned: {latest.display_name}")
        else:
            print("\nLatest project query returned: None")


if __name__ == "__main__":
    asyncio.run(check_projects())
