from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
import bcrypt
from uuid import UUID

from bimcalc.db.connection import get_session
from bimcalc.db.models import UserModel
from bimcalc.web.auth import require_admin
from bimcalc.web.dependencies import get_templates
from bimcalc.core.audit_logger import log_action

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_class=HTMLResponse)
async def list_users(
    request: Request,
    username: str = Depends(require_admin),
    templates=Depends(get_templates),
):
    async with get_session() as session:
        result = await session.execute(select(UserModel).order_by(UserModel.full_name))
        users = result.scalars().all()
        
    return templates.TemplateResponse(
        "users.html",
        {"request": request, "users": users, "username": username}
    )

@router.get("/new", response_class=HTMLResponse)
async def new_user_page(
    request: Request,
    username: str = Depends(require_admin),
    templates=Depends(get_templates),
):
    return templates.TemplateResponse(
        "user_edit.html",
        {"request": request, "user": None, "username": username}
    )

@router.post("/new")
async def create_user(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    username: str = Depends(require_admin),
):
    async with get_session() as session:
        # Check if email exists
        stmt = select(UserModel).where(UserModel.email == email)
        result = await session.execute(stmt)
        if result.scalars().first():
            raise HTTPException(status_code=400, detail="Email already exists")
            
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
        
        user = UserModel(
            email=email,
            full_name=full_name,
            password_hash=password_hash,
            role=role,
            is_active=True
        )
        session.add(user)
        await session.commit()
        
        await log_action(
            request, 
            "USER_CREATE", 
            username, 
            resource_type="user", 
            resource_id=str(user.id),
            details={"email": email, "role": role}
        )
        
    return RedirectResponse(url="/users", status_code=302)

@router.get("/{user_id}", response_class=HTMLResponse)
async def edit_user_page(
    request: Request,
    user_id: str,
    username: str = Depends(require_admin),
    templates=Depends(get_templates),
):
    async with get_session() as session:
        user = await session.get(UserModel, UUID(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
    return templates.TemplateResponse(
        "user_edit.html",
        {"request": request, "user": user, "username": username}
    )

@router.post("/{user_id}")
async def update_user(
    request: Request,
    user_id: str,
    email: str = Form(...),
    full_name: str = Form(...),
    role: str = Form(...),
    password: str | None = Form(None),
    is_active: bool = Form(False), # Checkbox
    username: str = Depends(require_admin),
):
    async with get_session() as session:
        user = await session.get(UserModel, UUID(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Track changes
        changes = {}
        if user.email != email: changes["email"] = {"old": user.email, "new": email}
        if user.role != role: changes["role"] = {"old": user.role, "new": role}
        if user.is_active != is_active: changes["is_active"] = {"old": user.is_active, "new": is_active}

        user.email = email
        user.full_name = full_name
        user.role = role
        user.is_active = is_active
        
        if password:
            user.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
            changes["password"] = "changed"
            
        await session.commit()
        
        if changes:
            await log_action(
                request,
                "USER_UPDATE",
                username,
                resource_type="user",
                resource_id=str(user.id),
                details=changes
            )
        
    return RedirectResponse(url="/users", status_code=302)
