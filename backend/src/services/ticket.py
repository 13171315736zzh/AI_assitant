from src.models.ticket import TicketCreateRequest, TicketPublic, TicketStatusPublic
from src.repositories.session import SessionRepository
from src.repositories.ticket import TicketRepository


class TicketService:
    def __init__(self, ticket_repo: TicketRepository, session_repo: SessionRepository):
        self.ticket_repo = ticket_repo
        self.session_repo = session_repo

    async def create_ticket(self, user_id: int, body: TicketCreateRequest) -> TicketPublic:
        session_id = body.session_id
        if session_id:
            session = await self.session_repo.get_by_id(session_id, user_id)
            if session is None:
                session_id = None
        record = await self.ticket_repo.create(
            user_id=user_id,
            session_id=session_id,
            title=body.title,
            description=body.description,
        )
        return TicketPublic(
            id=record.id,
            session_id=record.session_id,
            title=record.title,
            description=record.description,
            status=record.status,
            created_at=record.created_at.isoformat(),
        )

    async def get_ticket(self, user_id: int, ticket_id: str) -> TicketStatusPublic | None:
        record = await self.ticket_repo.get_by_id(ticket_id)
        if record is None or record.user_id != user_id:
            return None
        return TicketStatusPublic(
            id=record.id,
            status=record.status,
            title=record.title,
            created_at=record.created_at.isoformat(),
        )
