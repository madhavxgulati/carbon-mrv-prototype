# backend/routers/logs.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import FieldLog

router = APIRouter(prefix="/logs", tags=["Logs"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/add")
def add_log(field_id: str, note: str, db: Session = Depends(get_db)):
    new_log = FieldLog(field_id=field_id, note=note)
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return {"status": "saved", "log": new_log.note}
