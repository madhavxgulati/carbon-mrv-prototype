# backend/routers/ndvi.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from random import uniform
from ..database import SessionLocal
from ..models import NDVIRecord

router = APIRouter(prefix="/ndvi", tags=["NDVI"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/fetch")
def fetch_ndvi(field_id: str, db: Session = Depends(get_db)):
    ndvi_value = round(uniform(0.2, 0.9), 3)
    record = NDVIRecord(field_id=field_id, ndvi=ndvi_value)
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"field_id": field_id, "ndvi": ndvi_value}
