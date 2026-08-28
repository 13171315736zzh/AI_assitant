from fastapi import Depends
from fastapi.responses import JSONResponse
from pycore.api import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.api.responses import error, success
from src.db.session import get_db
from src.models.ticket import TicketCreateRequest
from src.models.user import UserPublic
from src.repositories.session import SessionRepository
from src.repositories.ticket import TicketRepository
from src.services.ticket import TicketService

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


def _ticket_service(db: AsyncSession) -> TicketService:
    return TicketService(TicketRepository(db), SessionRepository(db))


@router.post("")
async def create_ticket(
    body: TicketCreateRequest,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _ticket_service(db)
    try:
        ticket = await svc.create_ticket(current_user.id, body)
    except ValueError as exc:
        return JSONResponse(status_code=400, content=error(str(exc), code=400))
    return success(ticket.model_dump())


@router.get("/{ticket_id}")
async def get_ticket(
    ticket_id: str,
    current_user: UserPublic = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = _ticket_service(db)
    ticket = await svc.get_ticket(current_user.id, ticket_id)
    if ticket is None:
        return JSONResponse(status_code=404, content=error("工单不存在", code=404))
    return success(ticket.model_dump())
