import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DbSession
from app.models.undo import UndoAction
from app.services import undo_service

router = APIRouter(prefix="/undo", tags=["undo"])


@router.post("/{undo_action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def undo_action(undo_action_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    action = await db.get(UndoAction, undo_action_id)
    if action is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Undo action not found")

    try:
        await undo_service.apply_undo(db, user, action)
    except undo_service.UndoError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await db.commit()
