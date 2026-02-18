# backend/calculations.py
import math
from dataclasses import dataclass

@dataclass
class SoilContext:
    pH: float
    clay_pct: float
    bulk_density: float
    annual_rain: float
    mean_temp: float

def particle_factor(size_mm: float):
    size = max(size_mm, 0.05)
    # particles <=0.25mm give near-max factor; larger reduce roughly inverse-proportion
    f = min(0.25 / size, 1.0)
    return f

def pH_factor(pH: float):
    if pH is None:
        return 0.8
    # fastest around neutral 6.5-7.5
    if pH < 5.5:
        return 0.4
    if pH < 6.0:
        return 0.7
    if pH <= 7.5:
        return 1.0
    return 0.85

def clay_factor(clay: float):
    if clay is None:
        return 0.85
    if clay < 15:
        return 1.0
    if clay < 25:
        return 0.9
    if clay < 35:
        return 0.75
    return 0.6

def climate_factor(rain_mm, temp_c):
    rain_f = min(rain_mm / 1500.0, 1.5)  # tropical cap
    temp_f = min((temp_c + 5.0) / 30.0, 1.4)
    return rain_f * temp_f

def compute_weathering_fraction(soil: SoilContext, particle_size_mm: float):
    """
    Produce WF per year (fraction of applied basalt that reacts in 1 year).
    Tuned to produce realistic WF in range ~0.02 - 0.35 for typical inputs.
    """
    pf = particle_factor(particle_size_mm)
    phf = pH_factor(soil.pH)
    cf = clay_factor(soil.clay_pct)
    climf = climate_factor(soil.annual_rain, soil.mean_temp)

    # base_rate derived from literature-style tuning (Beerling-like kinetics simplified)
    base_rate = 0.18  # baseline max fraction for well-conditioned parameters
    wf = base_rate * pf * phf * cf * climf

    # clamp
    wf = max(min(wf, 0.35), 0.005)  # min 0.5% to avoid zero; max 35%
    return wf

def co2_per_kg_basalt():
    # chemically defensible central: 0.33 kg CO2 per kg basalt (depends on CaO+MgO content)
    return 0.33

def compute_co2_removal_kg(basalt_mass_kg, wf):
    return basalt_mass_kg * co2_per_kg_basalt() * wf

def conservative_band(value):
    return value * 0.8

def optimistic_band(value):
    return value * 1.15

def estimate_dic_export(co2_kg, runoff_index):
    # fraction of produced DIC that is exported; conservative 10-40%
    frac = min(max(runoff_index * 0.25, 0.05), 0.4)
    return co2_kg * frac

def permanence_score(slope_pct, clay_pct):
    if slope_pct < 3 and (clay_pct is None or clay_pct < 20):
        return "High"
    if slope_pct < 10:
        return "Medium"
    return "Low"
