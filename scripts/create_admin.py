import asyncio
import os
import bcrypt
from sqlalchemy import select
from bimcalc.db.connection import get_session
from bimcalc.db.models import UserModel

async def create_initial_admin():
    username = os.getenv("BIMCALC_USERNAME", "admin")
    password = os.getenv("BIMCALC_PASSWORD", "changeme")
    
    async with get_session() as session:
        # Check if user exists
        stmt = select(UserModel).where(UserModel.email == username)
        result = await session.execute(stmt)
        existing_user = result.scalars().first()
        
        if existing_user:
            print(f"User {username} already exists.")
            return
            
        print(f"Creating initial admin user: {username}")
        # bcrypt.hashpw returns bytes, we decode to store as string
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
        
        admin_user = UserModel(
            email=username,
            password_hash=password_hash,
            full_name="System Admin",
            role="admin",
            is_active=True
        )
        session.add(admin_user)
        await session.commit()
        print("Admin user created successfully.")

if __name__ == "__main__":
    asyncio.run(create_initial_admin())
