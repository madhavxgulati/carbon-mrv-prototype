# backend/data_sources.py
import requests
import math, time

def safe_get_json(url, params=None, timeout=10):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[data_sources] fetch failed for {url} : {e}")
        return None

# NASA POWER daily averages (long period) -> returns mean temp & annual precip estimate
def fetch_weather_nasa_power(lat, lon, start_date="20240101", end_date="20241231"):
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "T2M,PRECTOT",
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": start_date,
        "end": end_date,
        "format": "JSON"
    }
    r = safe_get_json(url, params)
    if not r:
        return None
    try:
        t2m = r["properties"]["parameter"].get("T2M", {})
        pr = r["properties"]["parameter"].get("PRECTOT", {})
        temps = list(t2m.values())
        rains = list(pr.values())
        avg_temp = sum(temps)/len(temps) if temps else None
        # NASA PRECTOT is mm/day totals — convert to approximate annual mm
        avg_daily_rain = sum(rains)/len(rains) if rains else None
        annual_rain = avg_daily_rain * 365.0 if avg_daily_rain is not None else None
        return {"mean_temp_c": avg_temp, "annual_rainfall_mm": annual_rain, "raw": r}
    except Exception as e:
        print("[fetch_weather_nasa_power] parse error", e)
        return None

# Open-Meteo fallback
def fetch_weather_open_meteo(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31"
    }
    r = safe_get_json(url, params)
    if not r:
        return None
    try:
        temps = r.get("hourly", {}).get("temperature_2m", [])
        precs = r.get("hourly", {}).get("precipitation", [])
        avg_temp = sum(temps)/len(temps) if temps else None
        # convert hourly precip (mm) to approximate annual (sum over hours -> mm), but arrays can be large
        avg_hourly = sum(precs)/len(precs) if precs else None
        annual_rain = avg_hourly * 24.0 * 365.0 if avg_hourly is not None else None
        return {"mean_temp_c": avg_temp, "annual_rainfall_mm": annual_rain, "raw": r}
    except Exception as e:
        print("[fetch_weather_open_meteo] parse error", e)
        return None

# SoilGrids robust parser with depth-weighted 0-30cm extraction and unit conversion
def parse_soilgrids_depth_weighted(r, depth_target_cm=30):
    try:
        props = r.get("properties", {})
        layers = props.get("layers", [])
    except Exception:
        layers = []

    ph_entries = []
    clay_entries = []
    bd_entries = []

    for layer in layers:
        name = layer.get("name", "").lower()
        depths = layer.get("depths", []) or []
        for d in depths:
            top = d.get("range", {}).get("top_depth", 0)
            bottom = d.get("range", {}).get("bottom_depth", 0)
            thickness = bottom - top if bottom and top is not None else 0
            mean_val = None
            try:
                mean_val = d.get("values", {}).get("mean")
            except Exception:
                mean_val = None
            if mean_val is None:
                continue
            if "ph" in name or "phh2o" in name:
                ph_entries.append((mean_val, thickness))
            if "clay" in name:
                clay_entries.append((mean_val, thickness))
            if "bdod" in name or "bulk" in name:
                bd_entries.append((mean_val, thickness))

    def depth_weighted(arr):
        if not arr:
            return None
        tot_w = 0.0; tot_v = 0.0
        for val, th in arr:
            if tot_w >= depth_target_cm:
                break
            use = min(th, depth_target_cm - tot_w) if th else 0
            if use <= 0:
                continue
            tot_v += val * use
            tot_w += use
        if tot_w == 0:
            return None
        return tot_v / tot_w

    ph_raw = depth_weighted(ph_entries)
    clay_raw = depth_weighted(clay_entries)
    bd_raw = depth_weighted(bd_entries)

    # Unit conversions (SoilGrids uses scaled units):
    # phh2o often returned as pH*10
    soil_pH = (ph_raw / 10.0) if ph_raw is not None else None
    # clay often returned as g/kg * 10 (check: many SoilGrids fields are scaled by 10)
    clay_pct = (clay_raw / 10.0) if clay_raw is not None else None
    # bdod might be in cm3/g scaled; in many SoilGrids bdod is in ??? we'll attempt best-effort convert:
    bulk_density = (bd_raw / 100.0) if bd_raw is not None else None

    return {"soil_pH": soil_pH, "clay_pct": clay_pct, "bulk_density": bulk_density, "raw": r}

def fetch_soil_soilgrids(lat, lon):
    url = f"https://rest.isric.org/soilgrids/v2.0/properties/query?lon={lon}&lat={lat}&property=phh2o&property=clay&property=bdod&value=mean"
    r = safe_get_json(url)
    if not r:
        return None
    parsed = parse_soilgrids_depth_weighted(r)
    return parsed

def fetch_elevation_opentopodata(lat, lon):
    url = "https://api.opentopodata.org/v1/eudem25m"
    params = {"locations": f"{lat},{lon}"}
    r = safe_get_json(url, params)
    if not r:
        return None
    try:
        elev = r["results"][0]["elevation"]
        return {"elevation_m": elev, "raw": r}
    except Exception as e:
        print("[fetch_elevation_opentopodata] parse error", e)
        return None

def fetch_environment_snapshot(lat, lon):
    out = {}
    w = fetch_weather_nasa_power(lat, lon)
    if w:
        out["mean_temp_c"] = w.get("mean_temp_c")
        out["annual_rainfall_mm"] = w.get("annual_rainfall_mm")
        out["weather_raw"] = w.get("raw")
    else:
        w2 = fetch_weather_open_meteo(lat, lon)
        if w2:
            out["mean_temp_c"] = w2.get("mean_temp_c")
            out["annual_rainfall_mm"] = w2.get("annual_rainfall_mm")
            out["weather_raw"] = w2.get("raw")

    s = fetch_soil_soilgrids(lat, lon)
    if s:
        out["soil_pH"] = s.get("soil_pH")
        out["clay_pct"] = s.get("clay_pct")
        out["bulk_density"] = s.get("bulk_density")
        out["soil_raw"] = s.get("raw")

    e = fetch_elevation_opentopodata(lat, lon)
    if e:
        out["elevation_m"] = e.get("elevation_m")
        out["elev_raw"] = e.get("raw")

    # slope proxy
    if out.get("elevation_m") is not None:
        out["slope_percent"] = min(max((out["elevation_m"]/1000.0)*5.0, 0.0), 45.0)

    # defaults
    defaults = {
        "annual_rainfall_mm": 1500.0,
        "mean_temp_c": 22.0,
        "soil_pH": 6.8,
        "clay_pct": 18.0,
        "slope_percent": 5.0,
        "bulk_density": 1.2,
        "elevation_m": None
    }
    for k,v in defaults.items():
        if k not in out or out.get(k) is None:
            out[k] = v

    return out
