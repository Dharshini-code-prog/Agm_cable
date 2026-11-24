from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime

from ..database import get_db
from ..crud import (
    get_person,
    get_person_history,
    get_not_recharged_persons
)

router = APIRouter(prefix="/persons", tags=["Payment History"])

@router.get("/{person_id}/history")
def person_history(
    person_id: int,
    request: Request,
    months: int = 6,
    year: int = datetime.now().year,
    selected_month: int = datetime.now().month,
    db: Session = Depends(get_db)
):
    if months < 1:
        raise HTTPException(400, "Months must be greater than zero")

    if not 1 <= selected_month <= 12:
        raise HTTPException(400, "Month must be between 1 and 12")

    person = get_person(db, person_id)

    if not person:
        raise HTTPException(404, "Person not found")

    history = get_person_history(
        db, person_id, year, selected_month, months, request
    )

    return {
        "person_id": person.id,
        "person_name": person.name,
        "place": person.place,
        "history": history
    }

@router.get("/not-recharged")
def not_recharged_persons(
    months: int,
    year: int = datetime.now().year,
    month: int = datetime.now().month,
    search: str = None,
    person_id: int = None,
    db: Session = Depends(get_db)
):
    if months < 1:
        raise HTTPException(400, "Months must be greater than zero")

    if not 1 <= month <= 12:
        raise HTTPException(400, "Month must be between 1 and 12")

    return get_not_recharged_persons(
        db, months, year, month, search, person_id
    )