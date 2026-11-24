
from fastapi import (
    APIRouter, Depends, UploadFile, File,
    Form, HTTPException, Request
)
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import datetime
from uuid import uuid4
from typing import Optional

from ..database import get_db
from ..schemas import RechargeCreate
from ..crud import (
    save_recharge,
    get_monthly_recharges,
    get_pending_recharges,
    get_paid_recharges,
    get_paid_tv_numbers
)
from ..models import MonthlyRecharge


router = APIRouter(prefix="/recharges", tags=["Recharges"])

UPLOAD_DIR = Path("uploads/payments").resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_SIZE = 5 * 1024 * 1024
now = datetime.now()


# ---------------- Image helper ----------------
def delete_image(image_path: Optional[str]):
    if not image_path:
        return

    path = Path(image_path).resolve()

    # Only delete files inside the payment upload directory.
    if path.parent != UPLOAD_DIR:
        return

    if path.is_file():
        path.unlink()


# ---------------- Save Recharge ----------------
@router.post("/")
async def recharge(
    person_id: int = Form(...),
    year: int = Form(now.year),
    month: int = Form(now.month),
    required_amount: float = Form(...),
    amount_paid: float = Form(...),
    recharged: bool = Form(...),
    recharge_date: str = Form(now.strftime("%Y-%m-%d")),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    image_path = None

    if not 1 <= month <= 12:
        raise HTTPException(400, "Month must be between 1 and 12")

    if year < 2000:
        raise HTTPException(400, "Invalid year")

    if required_amount <= 0:
        raise HTTPException(400, "Required amount must be greater than zero")

    if amount_paid < 0:
        raise HTTPException(400, "Amount paid cannot be negative")

    try:
        if image:
            allowed_types = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp"
            }

            if image.content_type not in allowed_types:
                raise HTTPException(
                    400,
                    "Only JPG, PNG and WEBP images are allowed"
                )

            content = await image.read(MAX_UPLOAD_SIZE + 1)

            if len(content) > MAX_UPLOAD_SIZE:
                raise HTTPException(
                    400,
                    "Image size must be below 5 MB"
                )

            filename = f"{uuid4().hex}{allowed_types[image.content_type]}"
            image_path = str(UPLOAD_DIR / filename)

            with open(image_path, "wb") as f:
                f.write(content)

        data = RechargeCreate(
            person_id=person_id,
            year=year,
            month=month,
            required_amount=required_amount,
            amount_paid=amount_paid,
            recharged=recharged,
            recharge_date=recharge_date,
            payment_screenshot=image_path
        )

        return save_recharge(db, data)

    except Exception:
        db.rollback()

        # Remove newly uploaded image if database save fails.
        if image_path:
            delete_image(image_path)

        raise

    finally:
        if image:
            await image.close()


# ---------------- Monthly Recharge ----------------
@router.get("/")
def monthly_recharge(
    request: Request,
    year: int = now.year,
    month: int = now.month,
    db: Session = Depends(get_db)
):
    if not 1 <= month <= 12:
        raise HTTPException(400, "Month must be between 1 and 12")

    return get_monthly_recharges(db, year, month, request)


# ---------------- Delete Recharge ----------------
@router.delete("/")
def delete_recharge(
    person_id: int,
    year: int = now.year,
    month: int = now.month,
    db: Session = Depends(get_db)
):
    result = db.query(MonthlyRecharge).filter(
        MonthlyRecharge.person_id == person_id,
        MonthlyRecharge.year == year,
        MonthlyRecharge.month == month
    ).first()

    if not result:
        raise HTTPException(
            status_code=404,
            detail="Recharge not found"
        )

    # Keep the image path before deleting the database record.
    image_path = result.payment_screenshot

    try:
        db.delete(result)
        db.commit()
    except Exception:
        db.rollback()
        raise

    # Delete screenshot only after successful database commit.
    delete_image(image_path)

    return {
        "message": "Recharge and its payment screenshot deleted successfully"
    }


# ---------------- Pending Recharge ----------------
@router.get("/pending")
def pending_recharges(
    request: Request,
    year: int = now.year,
    month: int = now.month,
    db: Session = Depends(get_db)
):
    if not 1 <= month <= 12:
        raise HTTPException(400, "Month must be between 1 and 12")

    return get_pending_recharges(db, year, month, request)


# ---------------- Paid Recharge ----------------
@router.get("/paid")
def paid_recharges(
    request: Request,
    year: int = now.year,
    month: int = now.month,
    db: Session = Depends(get_db)
):
    if not 1 <= month <= 12:
        raise HTTPException(400, "Month must be between 1 and 12")

    return get_paid_recharges(db, year, month, request)


# ---------------- Paid TV Numbers ----------------
@router.get("/paid/tv-numbers")
def paid_tv_numbers(
    year: int = now.year,
    month: int = now.month,
    db: Session = Depends(get_db)
):
    if not 1 <= month <= 12:
        raise HTTPException(400, "Month must be between 1 and 12")

    return get_paid_tv_numbers(db, year, month)
