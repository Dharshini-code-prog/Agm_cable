
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from fastapi import Request
from datetime import datetime
from ..database import get_db
from ..crud import get_year_data, clear_monthly_database
now = datetime.now()

router = APIRouter(
    prefix="/reports",
    tags=["Reports"]
)


@router.get("/year/{year}")
def year_data(year: int, db: Session = Depends(get_db)):
    result = get_year_data(db, year)

    return result


@router.delete("/year/reset")
def reset_year(db: Session = Depends(get_db)):
    clear_monthly_database(db)

    return {
        "message": "Monthly recharge database cleared"
    }
