
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Union
from ..database import get_db
from ..schemas import PersonCreate
from ..crud import *

router = APIRouter(
    prefix="/persons",
    tags=["Persons"]
)


# Add single person
@router.post("/")
def add_person(person: PersonCreate, db: Session = Depends(get_db)):
    return create_person(db, person)


# Bulk upload persons
@router.post("/bulk")
def add_multiple_persons(persons: list[PersonCreate],db: Session = Depends(get_db)):
    if not persons:
        raise HTTPException(status_code=400,detail="Person list cannot be empty")

    return create_multiple_persons(db, persons)


@router.get("/")
def persons(search: str = "", db: Session = Depends(get_db)):
    people = get_persons(db, search)

    return [
        {
            "id": p.id,
            "name": p.name,
            "phone_number": p.phone_number,
            "tv_number": p.tv_number,
            "place": p.place
        }
        for p in people
    ]


@router.get("/{person_id}")
def person(person_id: int, db: Session = Depends(get_db)):
    result = get_person(db, person_id) 
    return result  


@router.delete("/{person_id}")
def delete_person(person_id: int, db: Session = Depends(get_db)):
    result = get_person(db, person_id)

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Person not found"
        )

    db.delete(result)
    db.commit()

    return {"message": "Person deleted successfully"}
