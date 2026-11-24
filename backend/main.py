
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from .database import Base, engine
from .router import person, recharge, history, reports
import os


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Recharge Management API",
    version="1.0.0",
    description="Customer and Recharge Management System"
)

os.makedirs("uploads/payments", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
@app.get("/")
def home():
    return {"message": "Recharge API is running"}


# Register routers
app.include_router(history.router)
app.include_router(person.router)
app.include_router(recharge.router)
app.include_router(reports.router)