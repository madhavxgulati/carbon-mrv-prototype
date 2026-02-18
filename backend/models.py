# backend/models.py
from sqlalchemy import Column, String, Float, DateTime, Integer, Text
from datetime import datetime
from .database import Base

class Farm(Base):
    __tablename__ = "farms"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    geojson = Column(Text)   # store polygon as GeoJSON string
    created_at = Column(DateTime, default=datetime.utcnow)

class Application(Base):
    __tablename__ = "applications"
    id = Column(String, primary_key=True, index=True)
    farm_id = Column(String, index=True)
    applied_at = Column(DateTime, default=datetime.utcnow)
    basalt_mass_kg = Column(Float)
    particle_size_mm = Column(Float)
    lat = Column(Float)
    lon = Column(Float)
    photo_filename = Column(String, nullable=True)
    result_json = Column(Text, nullable=True)
    audit_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class NDVIRecord(Base):
    __tablename__ = "ndvi"
    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(String, index=True)
    ndvi = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

class WeatherRecord(Base):
    __tablename__ = "weather"
    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(String, index=True)
    temperature = Column(Float)
    rainfall = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

class FieldLog(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    field_id = Column(String, index=True)
    note = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
