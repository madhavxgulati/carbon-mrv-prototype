# backend/routers/weather.py
import requests
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import SessionLocal
from ..models import WeatherRecord

router = APIRouter(prefix="/weather", tags=["Weather"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/fetch")
def fetch_weather(field_id: str, lat: float, lon: float, db: Session = Depends(get_db)):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,precipitation"
    r = requests.get(url, timeout=10).json()
    temp_series = r.get("hourly", {}).get("temperature_2m", [])
    precip_series = r.get("hourly", {}).get("precipitation", [])
    temperature = temp_series[0] if temp_series else None
    rainfall = precip_series[0] if precip_series else None
    record = WeatherRecord(field_id=field_id, temperature=temperature or 0.0, rainfall=rainfall or 0.0)
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"field_id": field_id, "temp": temperature, "rainfall": rainfall}
