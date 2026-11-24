from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint, Boolean
from .database import Base

class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone_number = Column(String)
    tv_number = Column(String)
    place = Column(String)
    created_at = Column(DateTime, default=datetime.now)

class MonthlyRecharge(Base):
    __tablename__ = "monthly_recharges"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    required_amount = Column(Float, nullable=False, default=0)
    amount_paid = Column(Float, nullable=False, default=0)
    status = Column(String, nullable=False)
    recharge_date = Column(String)
    recharged = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    payment_screenshot = Column(String, nullable=True)

    __table_args__ = (UniqueConstraint("person_id", "year", "month", name="unique_person_month"),)