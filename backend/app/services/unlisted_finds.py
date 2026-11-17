from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CountingSession, Project, UnlistedFind


class UnlistedFindError(ValueError):
    pass


def record_unlisted_find(
    db: Session,
    *,
    session_id: UUID,
    part_num: str | None,
    color_ref: str | None,
    label: str,
    qty: int,
) -> UnlistedFind:
    counting_session = db.get(CountingSession, session_id)
    if counting_session is None:
        raise UnlistedFindError("Zählbereich nicht gefunden.")

    find = UnlistedFind(
        session_id=session_id,
        part_num=part_num,
        color_ref=color_ref,
        label=label,
        qty=qty,
    )
    db.add(find)
    db.flush()
    return find


def project_unlisted_finds(db: Session, project_id: UUID) -> list[UnlistedFind]:
    if db.get(Project, project_id) is None:
        raise UnlistedFindError("Projekt nicht gefunden.")

    return list(
        db.scalars(
            select(UnlistedFind)
            .join(CountingSession, UnlistedFind.session_id == CountingSession.id)
            .where(CountingSession.project_id == project_id)
            .order_by(UnlistedFind.created_at, UnlistedFind.id)
        )
    )


def unlisted_find_data(find: UnlistedFind) -> dict[str, object]:
    return {
        "id": str(find.id),
        "session_id": str(find.session_id),
        "part_num": find.part_num,
        "color_ref": find.color_ref,
        "label": find.label,
        "qty": find.qty,
        "resolution_status": find.resolution_status,
    }
