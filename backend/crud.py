
import os
from sqlalchemy.orm import Session
from fastapi import Request
from typing import Optional

from .models import Person, MonthlyRecharge
from .schemas import PersonCreate, RechargeCreate


def calculate_status(required_amount, amount_paid, recharged):
    if not recharged:
        return "Not Recharged"
    if amount_paid < required_amount:
        return "Pending"
    return "Paid"


# ---------------- PERSON MANAGEMENT ----------------

def create_person(db: Session, person: PersonCreate):
    new_person = Person(
        name=person.name,
        phone_number=person.phone_number,
        tv_number=person.tv_number,
        place=person.place
    )
    try:
        db.add(new_person)
        db.commit()
        db.refresh(new_person)
    except Exception:
        db.rollback()
        raise
    return new_person


def create_multiple_persons(db: Session, persons: list[PersonCreate]):
    new_persons = [
        Person(
            name=p.name,
            phone_number=p.phone_number,
            tv_number=p.tv_number,
            place=p.place
        )
        for p in persons
    ]
    try:
        db.add_all(new_persons)
        db.commit()
        for person in new_persons:
            db.refresh(person)
    except Exception:
        db.rollback()
        raise
    return new_persons


def get_persons(db: Session, search: str = None):
    query = db.query(Person)
    if search:
        query = query.filter(Person.name.ilike(f"%{search.strip()}%"))
    return query.order_by(Person.id.asc()).all()


def get_person(db: Session, person_id: int):
    return db.query(Person).filter(Person.id == person_id).first()


# ---------------- IMAGE HELPER ----------------

def delete_image(image_path: Optional[str]):
    if not image_path:
        return

    from pathlib import Path

    upload_dir = Path("uploads/payments").resolve()
    path = Path(image_path).resolve()

    # Only delete files directly inside the payment upload directory.
    if path.parent == upload_dir and path.is_file():
        path.unlink()


def get_screenshot_url(image_path, request: Request = None):
    if not image_path or not request:
        return None

    filename = os.path.basename(image_path)
    return (
        f"{str(request.base_url).rstrip('/')}"
        f"/uploads/payments/{filename}"
    )


# ---------------- RECHARGE MANAGEMENT ----------------

def save_recharge(db: Session, data: RechargeCreate):
    status = calculate_status(
        data.required_amount,
        data.amount_paid,
        data.recharged
    )

    existing = db.query(MonthlyRecharge).filter(
        MonthlyRecharge.person_id == data.person_id,
        MonthlyRecharge.year == data.year,
        MonthlyRecharge.month == data.month
    ).first()

    if existing:
        old_image = existing.payment_screenshot

        existing.required_amount = data.required_amount
        existing.amount_paid = data.amount_paid
        existing.status = status
        existing.recharged = data.recharged
        existing.recharge_date = data.recharge_date

        if data.payment_screenshot:
            existing.payment_screenshot = data.payment_screenshot

        try:
            db.commit()
            db.refresh(existing)
        except Exception:
            db.rollback()
            raise

        if (
            data.payment_screenshot
            and old_image
            and old_image != data.payment_screenshot
        ):
            delete_image(old_image)

        return existing

    recharge = MonthlyRecharge(
        person_id=data.person_id,
        year=data.year,
        month=data.month,
        required_amount=data.required_amount,
        amount_paid=data.amount_paid,
        status=status,
        recharged=data.recharged,
        recharge_date=data.recharge_date,
        payment_screenshot=data.payment_screenshot
    )

    try:
        db.add(recharge)
        db.commit()
        db.refresh(recharge)
    except Exception:
        db.rollback()
        raise

    return recharge


# ---------------- RECHARGE RESPONSE FORMAT ----------------

def format_recharge(record, person, request: Request = None):
    return {
        "id": record.id,
        "person_id": record.person_id,
        "person_name": person.name,
        "place": person.place,
        "phone_number": person.phone_number,
        "tv_number": person.tv_number,
        "year": record.year,
        "month": record.month,
        "required_amount": record.required_amount,
        "amount_paid": record.amount_paid,
        "status": record.status,
        "recharged": record.recharged,
        "recharge_date": record.recharge_date,
        "payment_screenshot": get_screenshot_url(
            record.payment_screenshot, request
        ),
        "updated_at": record.updated_at
    }


# ---------------- MONTHLY / PENDING / PAID ----------------

def get_monthly_recharges(
    db: Session, year: int, month: int, request: Request
):
    results = db.query(MonthlyRecharge, Person).join(
        Person, MonthlyRecharge.person_id == Person.id
    ).filter(
        MonthlyRecharge.year == year,
        MonthlyRecharge.month == month
    ).order_by(Person.name.asc()).all()

    return [
        format_recharge(record, person, request)
        for record, person in results
    ]


def get_pending_recharges(
    db: Session, year: int, month: int, request: Request
):
    results = db.query(MonthlyRecharge, Person).join(
        Person, MonthlyRecharge.person_id == Person.id
    ).filter(
        MonthlyRecharge.year == year,
        MonthlyRecharge.month == month,
        MonthlyRecharge.amount_paid < MonthlyRecharge.required_amount
    ).order_by(Person.name.asc()).all()

    return [
        format_recharge(record, person, request)
        for record, person in results
    ]


def get_paid_recharges(
    db: Session, year: int, month: int, request: Request
):
    results = db.query(MonthlyRecharge, Person).join(
        Person, MonthlyRecharge.person_id == Person.id
    ).filter(
        MonthlyRecharge.year == year,
        MonthlyRecharge.month == month,
        MonthlyRecharge.required_amount > 0,
        MonthlyRecharge.amount_paid >= MonthlyRecharge.required_amount
    ).order_by(Person.name.asc()).all()

    return [
        format_recharge(record, person, request)
        for record, person in results
    ]


# ---------------- PAYMENT HISTORY ----------------

def get_person_history(
    db: Session,
    person_id: int,
    year: int,
    selected_month: int,
    months: int,
    request: Request
):
    if months < 1 or not 1 <= selected_month <= 12:
        return []

    end_index = year * 12 + selected_month - 1
    start_index = end_index - months + 1

    results = db.query(MonthlyRecharge, Person).join(
        Person, MonthlyRecharge.person_id == Person.id
    ).filter(
        MonthlyRecharge.person_id == person_id,
        (
            MonthlyRecharge.year * 12
            + MonthlyRecharge.month - 1
        ) >= start_index,
        (
            MonthlyRecharge.year * 12
            + MonthlyRecharge.month - 1
        ) <= end_index
    ).order_by(
        MonthlyRecharge.year.asc(),
        MonthlyRecharge.month.asc()
    ).all()

    return [
        format_recharge(record, person, request)
        for record, person in results
    ]


# ---------------- NOT RECHARGED REPORT ----------------

def get_not_recharged_persons(
    db: Session,
    months: int,
    year: int,
    month: int,
    search: str = None,
    person_id: int = None
):
    if months < 1 or not 1 <= month <= 12:
        return []

    end_index = year * 12 + month - 1
    start_index = end_index - months + 1

    month_list = []

    for value in range(start_index, end_index + 1):
        y = value // 12
        m = value % 12 + 1
        month_list.append({"year": y, "month": m})

    query = db.query(Person)

    if person_id is not None:
        query = query.filter(Person.id == person_id)
    elif search:
        query = query.filter(
            Person.name.ilike(f"%{search.strip()}%")
        )

    persons = query.order_by(Person.name.asc()).all()

    if not persons:
        return []

    person_ids = [person.id for person in persons]

    recharge_records = db.query(
        MonthlyRecharge.person_id,
        MonthlyRecharge.year,
        MonthlyRecharge.month
    ).filter(
        MonthlyRecharge.person_id.in_(person_ids),
        (
            MonthlyRecharge.year * 12
            + MonthlyRecharge.month - 1
        ) >= start_index,
        (
            MonthlyRecharge.year * 12
            + MonthlyRecharge.month - 1
        ) <= end_index
    ).all()

    recharged_map = {}

    for record in recharge_records:
        recharged_map.setdefault(record.person_id, set()).add(
            (record.year, record.month)
        )

    result = []

    for person in persons:
        existing_months = recharged_map.get(person.id, set())

        missing_months = [
            item for item in month_list
            if (item["year"], item["month"]) not in existing_months
        ]

        if missing_months:
            result.append({
                "person_id": person.id,
                "name": person.name,
                "place": person.place,
                "phone_number": person.phone_number,
                "tv_number": person.tv_number,
                "not_recharged_months": missing_months
            })

    return result


# ---------------- PAID TV NUMBERS ----------------

def get_paid_tv_numbers(db: Session, year: int, month: int):
    records = db.query(Person.tv_number).join(
        MonthlyRecharge,
        Person.id == MonthlyRecharge.person_id
    ).filter(
        MonthlyRecharge.year == year,
        MonthlyRecharge.month == month,
        MonthlyRecharge.required_amount > 0,
        MonthlyRecharge.amount_paid >= MonthlyRecharge.required_amount
    ).all()

    return [record.tv_number for record in records]


# ---------------- YEARLY REPORT ----------------

def get_year_data(db: Session, year: int):
    return db.query(MonthlyRecharge).filter(
        MonthlyRecharge.year == year
    ).all()


def clear_monthly_database(db: Session):
    try:
        db.query(MonthlyRecharge).delete()
        db.commit()
    except Exception:
        db.rollback()
        raise
