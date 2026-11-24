from typing import Optional
from pydantic import BaseModel

class PersonCreate(BaseModel):
    name: str
    phone_number: Optional[str] = None
    tv_number: Optional[str] = None
    place: Optional[str] = None


class RechargeCreate(BaseModel):
    person_id: int
    year: int
    month: int
    required_amount: float
    amount_paid: float
    recharged: bool
    recharge_date: Optional[str] = None
    payment_screenshot: Optional[str] = None