from uuid import UUID
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from bimcalc.db.models import AuditLogModel
from bimcalc.db.connection import get_session

async def log_action(
    request: Request,
    action: str,
    username: str,
    user_id: str | UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict | None = None,
    session: AsyncSession | None = None,
):
    """Log an action to the audit trail.
    
    Args:
        request: FastAPI request object (for IP address)
        action: Action name (e.g., "LOGIN", "USER_CREATE")
        username: Username of actor
        user_id: User ID of actor
        resource_type: Type of resource affected
        resource_id: ID of resource affected
        details: Additional details
        session: Optional existing DB session. If None, creates a new one.
    """
    ip_address = request.client.host if request.client else None
    
    # Convert user_id to UUID if string
    if isinstance(user_id, str):
        try:
            user_id = UUID(user_id)
        except ValueError:
            user_id = None

    audit_entry = AuditLogModel(
        user_id=user_id,
        username=username,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )

    if session:
        session.add(audit_entry)
        # Caller is responsible for commit if session provided
    else:
        async with get_session() as new_session:
            new_session.add(audit_entry)
            await new_session.commit()
