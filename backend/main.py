# backend/main.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import uuid, datetime, json, hashlib, os

from .database import Base, engine, SessionLocal
from .models import Farm, Application
from .routers import ndvi, weather, logs

from .data_sources import fetch_environment_snapshot
from .calculations import SoilContext, compute_weathering_fraction, compute_co2_removal_kg, conservative_band, optimistic_band, estimate_dic_export, permanence_score

# create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Mini-Feluda Local MRV (Beerling-style)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# mount frontend static if exists (optional)
front_dir = os.path.join(os.path.dirname(__file__), "../frontend")
if os.path.isdir(front_dir):
    try:
        app.mount("/frontend", StaticFiles(directory=front_dir), name="frontend")
    except Exception:
        pass

@app.get("/")
def root():
    return {"status": "Backend is running!"}

app.include_router(ndvi.router)
app.include_router(weather.router)
app.include_router(logs.router)

class FarmIn(BaseModel):
    name: Optional[str]
    geojson: dict

@app.post('/api/farms')
async def create_farm(payload: FarmIn):
    db = SessionLocal()
    farm_id = str(uuid.uuid4())
    farm = Farm(id=farm_id, name=payload.name or 'Farm-'+farm_id[:6], geojson=json.dumps(payload.geojson))
    db.add(farm)
    db.commit()
    db.refresh(farm)
    db.close()
    return {"farm_id": farm_id}

@app.get('/api/farms/{farm_id}')
async def get_farm(farm_id: str):
    db = SessionLocal()
    farm = db.query(Farm).filter(Farm.id==farm_id).first()
    db.close()
    if not farm:
        raise HTTPException(status_code=404, detail='Farm not found')
    return {"farm_id": farm.id, "name": farm.name, "geojson": json.loads(farm.geojson)}

@app.post('/api/applications')
async def create_application(
    farm_id: str = Form(...),
    applied_at: str = Form(...),
    basalt_mass_kg: float = Form(...),
    particle_size_mm: float = Form(...),
    lat: float = Form(...),
    lon: float = Form(...),
    photo: Optional[UploadFile] = File(None)
):
    db = SessionLocal()
    farm = db.query(Farm).filter(Farm.id==farm_id).first()
    if not farm:
        db.close()
        raise HTTPException(status_code=404, detail='Farm not found')

    app_id = str(uuid.uuid4())
    applied_dt = datetime.datetime.fromisoformat(applied_at.replace("Z", "+00:00"))


    photo_filename = None
    if photo:
        uploads_dir = os.path.join(os.getcwd(), 'uploads')
        os.makedirs(uploads_dir, exist_ok=True)
        photo_filename = f"{app_id}_{photo.filename}"
        with open(os.path.join(uploads_dir, photo_filename), 'wb') as f:
            f.write(await photo.read())

    app_row = Application(
        id=app_id, farm_id=farm_id, applied_at=applied_dt,
        basalt_mass_kg=basalt_mass_kg, particle_size_mm=particle_size_mm,
        lat=lat, lon=lon, photo_filename=photo_filename
    )
    db.add(app_row)
    db.commit()
    db.refresh(app_row)

    # --- fetch authoritative environment snapshot ---
    env = fetch_environment_snapshot(lat, lon)

    # ensure correct types & units (data_sources returns already converted depth-weighted values)
    soil_pH = env.get("soil_pH")
    clay_pct = env.get("clay_pct")
    bulk_density = env.get("bulk_density")
    annual_rain = env.get("annual_rainfall_mm")
    mean_temp = env.get("mean_temp_c")
    slope_pct = env.get("slope_percent", 5.0)

    # Build soil context
    soil = SoilContext(
        pH=soil_pH,
        clay_pct=clay_pct,
        bulk_density=bulk_density,
        annual_rain=annual_rain,
        mean_temp=mean_temp
    )

    # Weathering fraction (Beerling-style simplified)
    wf = compute_weathering_fraction(soil, particle_size_mm)

    # CO2 removal (kg)
    co2_kg = compute_co2_removal_kg(basalt_mass_kg, wf)
    conservative_kg = conservative_band(co2_kg)
    optimistic_kg = optimistic_band(co2_kg)

    # Runoff / DIC export estimate (use simple runoff proxy)
    runoff_index = min(max((annual_rain / 2000.0) * (slope_pct / 10.0), 0.0), 1.0)
    dic_export_kg = estimate_dic_export(co2_kg, runoff_index)

    perm = permanence_score(slope_pct, clay_pct)

    result = {
        "methodology_version": "beerling-simplified-v1",
        "wf": wf,
        "central_co2_t": co2_kg / 1000.0,
        "conservative_co2_t": conservative_kg / 1000.0,
        "optimistic_co2_t": optimistic_kg / 1000.0,
        "dic_export_t": dic_export_kg / 1000.0,
        "permanence_score": perm,
        "env_snapshot": env
    }

    # canonical JSON for audit (include input params)
    canonical = json.dumps({
        "application_id": app_row.id,
        "farm_id": app_row.farm_id,
        "applied_at": app_row.applied_at.isoformat() if app_row.applied_at else None,
        "basalt_mass_kg": app_row.basalt_mass_kg,
        "particle_size_mm": app_row.particle_size_mm,
        "wf": wf,
        "central_co2_t": result["central_co2_t"]
    }, sort_keys=True, separators=(',',':'))

    audit_hash = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    result["audit_hash"] = audit_hash

    # save result
    app_row.audit_hash = audit_hash
    app_row.result_json = json.dumps(result)
    db.add(app_row)
    db.commit()
    db.refresh(app_row)
    db.close()

    return {"application_id": app_id, "result": result}

@app.get('/api/applications/{app_id}')
async def get_application(app_id: str):
    db = SessionLocal()
    app_row = db.query(Application).filter(Application.id==app_id).first()
    db.close()
    if not app_row:
        raise HTTPException(status_code=404, detail='Application not found')
    return {
        "application_id": app_row.id,
        "farm_id": app_row.farm_id,
        "applied_at": app_row.applied_at.isoformat() if app_row.applied_at else None,
        "basalt_mass_kg": app_row.basalt_mass_kg,
        "particle_size_mm": app_row.particle_size_mm,
        "lat": app_row.lat,
        "lon": app_row.lon,
        "photo_filename": app_row.photo_filename,
        "result": json.loads(app_row.result_json) if app_row.result_json else None,
        "audit_hash": app_row.audit_hash
    }
