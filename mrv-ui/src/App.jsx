import React, { useEffect, useState, useRef } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polygon,
  useMapEvents,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  UploadCloud,
  MapPin,
  Leaf,
  CheckCircle,
  AlertCircle,
  FileJson,
  ExternalLink,
  Trash2,
  ArrowUpRight,
  Copy,
  RotateCcw
} from "lucide-react";

import area from "@turf/area";
import { polygon as turfPolygon } from "@turf/helpers";

/* ------------- EDIT THIS to point at your backend ------------- */
const API_BASE = "https://carbon-mrv-prototype.onrender.com";
/* ------------------------------------------------------------- */

/* Fix Leaflet default icon paths for Vite/ESM */
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

/* Map click handler used to capture location clicks */
function MapClickHandler({ onClick }) {
  useMapEvents({
    click(e) {
      onClick(e.latlng);
    },
  });
  return null;
}

export default function App() {
  const [activeTab, setActiveTab] = useState("create");
  const [farmName, setFarmName] = useState("");
  const [points, setPoints] = useState([]); // polygon points: [[lat, lng], ...]
  const [markerPos, setMarkerPos] = useState(null);
  const [photo, setPhoto] = useState(null);
  const [farmId, setFarmId] = useState("");
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState(null);
  const [result, setResult] = useState(null);
  const [scenario, setScenario] = useState("standard");
  const [basaltMass, setBasaltMass] = useState(10000);
  const [particleSize, setParticleSize] = useState(0.25);
  const mapRef = useRef();

  const SCENARIOS = {
    pilot: { name: "Pilot", mass: 5000, particle: 0.5 },
    standard: { name: "Standard", mass: 10000, particle: 0.25 },
    aggressive: { name: "Aggressive", mass: 20000, particle: 0.1 },
  };

  useEffect(() => {
    const s = SCENARIOS[scenario];
    setBasaltMass(s.mass);
    setParticleSize(s.particle);
  }, [scenario]);

  useEffect(() => {
    if (notification) {
      const t = setTimeout(() => setNotification(null), 4500);
      return () => clearTimeout(t);
    }
  }, [notification]);

  const showNotification = (msg, type = "success") =>
    setNotification({ msg, type });

  const handleMapClick = (latlng) => {
    // add to polygon if drawing, else set marker for application location
    if (activeTab === "create") {
      setPoints((p) => [...p, [latlng.lat, latlng.lng]]);
    } else if (activeTab === "apply") {
      setMarkerPos([latlng.lat, latlng.lng]);
    }
  };

  const undoLastPoint = () => setPoints((p) => p.slice(0, -1));
  const clearPoints = () => {
    setPoints([]);
    setMarkerPos(null);
  };

  const createFarm = async () => {
    if (points.length < 3) {
      showNotification("Draw at least 3 points for polygon", "error");
      return;
    }
    setLoading(true);
    try {
      const coords = points.map((p) => [p[1], p[0]]);
      const geojson = { type: "Polygon", coordinates: [[...coords, coords[0]]] };
  
      const res = await fetch(`${API_BASE}/api/farms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: farmName || "Unnamed Farm", geojson }),
      });
  
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
  
      const data = await res.json();
  
      // Robust farm_id extraction
      const returnedFarmId =
        data.farm_id ||
        data.farmId ||
        data.id ||
        data.farm?.id ||
        data.farm?.farm_id;
  
      if (!returnedFarmId) {
        console.error("Backend returned:", data);
        throw new Error("No farm_id in backend response");
      }
  
      setFarmId(returnedFarmId);
      showNotification("Farm created", "success");
      setActiveTab("apply");
  
    } catch (err) {
      showNotification("Create farm failed: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  };
  

  const submitApplication = async () => {
    if (!farmId) {
      showNotification("Create a farm first", "error");
      return;
    }
    if (!markerPos) {
      showNotification("Click map to place application location", "error");
      return;
    }
    setLoading(true);
    try {
      const form = new FormData();
      form.append("farm_id", farmId);
      form.append("applied_at", new Date().toISOString());
      form.append("basalt_mass_kg", basaltMass);
      form.append("particle_size_mm", particleSize);
      form.append("lat", markerPos[0]);
      form.append("lon", markerPos[1]);
      if (photo) form.append("photo", photo);

      const res = await fetch(`${API_BASE}/api/applications`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setResult(data.result || data);
      showNotification("Application submitted", "success");
      setActiveTab("results");
    } catch (err) {
      showNotification("Submit failed: " + err.message, "error");
    } finally {
      setLoading(false);
    }
  };

  const exportGeoJSON = () => {
    if (points.length < 3) {
      showNotification("Need polygon to export", "error");
      return;
    }
    const coords = points.map((p) => [p[1], p[0]]);
    const geojson = {
      type: "Feature",
      geometry: { type: "Polygon", coordinates: [[...coords, coords[0]]] },
      properties: { name: farmName || "Unnamed Farm" },
    };
    const blob = new Blob([JSON.stringify(geojson, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(farmName || "farm").replace(/\s+/g, "_")}_polygon.geojson`;
    a.click();
    URL.revokeObjectURL(url);
    showNotification("GeoJSON downloaded");
  };

  const copyResultJSON = async () => {
    if (!result) return showNotification("No result to copy", "error");
    await navigator.clipboard.writeText(JSON.stringify(result, null, 2));
    showNotification("Result JSON copied");
  };

  // compute area in hectares using turf if polygon present
  const polygonAreaHa = () => {
    if (points.length < 3) return 0;
    const coords = points.map((p) => [p[1], p[0]]);
    const poly = turfPolygon([[...coords, coords[0]]]);
    const m2 = area(poly);
    return m2 / 10000;
  };

  return (
    <div className="min-h-screen min-w-screen flex bg-gradient-to-br from-slate-900 to-slate-800">
      {/* Notification */}
      {notification && (
        <div
          className={`fixed top-6 right-6 z-50 px-5 py-3 rounded-lg flex items-center gap-3 ${
            notification.type === "success"
              ? "bg-emerald-600/90 text-white"
              : "bg-red-600/90 text-white"
          }`}
        >
          {notification.type === "success" ? (
            <CheckCircle />
          ) : (
            <AlertCircle />
          )}
          <span>{notification.msg}</span>
        </div>
      )}

      {/* Sidebar */}
      <aside className="w-80 p-6 space-y-4 bg-slate-900 border-r border-slate-800">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-emerald-400 to-teal-500 rounded">
            <Leaf color="white" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Enhanced Rock Weathering</h1>
            <div className="text-xs text-slate-400">Alt Carbon · MRV</div>
          </div>
        </div>

        <div className="flex gap-2">
          {[
            { id: "create", label: "Create Farm" },
            { id: "apply", label: "Apply Basalt" },
            { id: "results", label: "Results" },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`flex-1 px-3 py-2 rounded ${
                activeTab === t.id
                  ? "bg-emerald-500/20 border border-emerald-500/40 text-emerald-300"
                  : "text-slate-300 hover:bg-slate-800/30"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Create / apply / results forms */}
        {activeTab === "create" && (
          <div className="space-y-3 mt-2">
            <label className="text-sm text-slate-300">Farm name</label>
            <input
              value={farmName}
              onChange={(e) => setFarmName(e.target.value)}
              placeholder="e.g. Mendel Farm"
              className="w-full p-2 rounded bg-slate-800 border border-slate-700 text-white"
            />

            <div className="flex gap-2">
              <button
                onClick={undoLastPoint}
                disabled={points.length === 0}
                className="flex-1 py-2 bg-slate-800 rounded disabled:opacity-40"
              >
                Undo
              </button>
              <button
                onClick={clearPoints}
                disabled={points.length === 0}
                className="flex-1 py-2 bg-rose-700 rounded disabled:opacity-40"
              >
                Clear
              </button>
            </div>

            <button
              onClick={createFarm}
              disabled={loading || points.length < 3}
              className="w-full py-2 bg-emerald-500 rounded text-black font-semibold disabled:opacity-50"
            >
              {loading ? "Creating..." : "Create Farm"}
            </button>

            <div className="text-xs text-slate-400">
              Draw farm boundary on the map by clicking points (min 3).
            </div>

            <div className="pt-2">
              <div className="text-xs text-slate-400">Polygon area</div>
              <div className="text-sm font-bold">
                {polygonAreaHa().toFixed(3)} ha
              </div>
            </div>
          </div>
        )}

        {activeTab === "apply" && (
          <div className="space-y-3 mt-2">
            <div className="grid grid-cols-3 gap-2">
              {Object.entries(SCENARIOS).map(([k, s]) => (
                <button
                  key={k}
                  onClick={() => setScenario(k)}
                  className={`p-2 rounded border ${
                    scenario === k ? "border-emerald-400" : "border-slate-700"
                  }`}
                >
                  <div className="text-sm font-semibold">{s.name}</div>
                  <div className="text-xs text-slate-400">{s.mass} kg</div>
                </button>
              ))}
            </div>

            <label className="text-sm text-slate-300">Basalt mass (kg)</label>
            <input
              type="number"
              value={basaltMass}
              onChange={(e) => setBasaltMass(Number(e.target.value))}
              className="w-full p-2 rounded bg-slate-800 border border-slate-700 text-white"
            />

            <label className="text-sm text-slate-300">Particle size (mm)</label>
            <input
              type="number"
              step="0.01"
              value={particleSize}
              onChange={(e) => setParticleSize(Number(e.target.value))}
              className="w-full p-2 rounded bg-slate-800 border border-slate-700 text-white"
            />

            <label className="text-sm text-slate-300">Photo (optional)</label>
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setPhoto(e.target.files?.[0])}
              className="w-full text-sm text-slate-300"
            />

            <button
              onClick={submitApplication}
              disabled={loading || !farmId}
              className="w-full py-2 bg-emerald-500 rounded text-black font-semibold disabled:opacity-50"
            >
              {loading ? "Processing..." : "Submit Application"}
            </button>

            <div className="text-xs text-slate-400">
              Click map to set application location.
            </div>

            <div className="text-xs text-slate-400 pt-2">
              Farm ID:
              <span className="ml-2 font-mono text-emerald-300">
                {farmId || "none"}
              </span>
            </div>
          </div>
        )}

        {activeTab === "results" && result && (
          <div className="space-y-3 mt-2">
            <div className="text-xs text-slate-400">Central estimate</div>
            <div className="text-lg font-bold">
              {result.central_co2_t?.toFixed(3) ?? "-"} t CO₂
            </div>

            <div className="text-xs text-slate-400">Weathering fraction</div>
            <div className="text-lg font-bold">
              {result.wf ? (result.wf * 100).toFixed(2) + "%" : "-"}
            </div>

            <div className="flex gap-2 mt-2">
              <button onClick={copyResultJSON} className="flex-1 py-2 bg-slate-800 rounded">
                <FileJson className="inline-block mr-2" /> Copy JSON
              </button>
              <button onClick={exportGeoJSON} className="py-2 px-3 bg-slate-800 rounded">
                <ExternalLink className="inline-block mr-2" /> Export GeoJSON
              </button>
            </div>

            <div className="text-xs text-slate-400 mt-2">Audit hash</div>
            <div className="font-mono text-emerald-300 break-words text-sm">
              {result?.audit_hash ?? "-"}
            </div>
          </div>
        )}

        <div className="text-xs text-slate-500 mt-4">
          Pro tip: draw polygon first → Create farm → Switch to Apply tab →
          click a location inside polygon and Submit application.
        </div>
      </aside>

      {/* Map area */}
      <div className="flex-1 relative">
        <MapContainer
          center={[27.8, 80.9]}
          zoom={6}
          className="h-screen w-full"
          ref={mapRef}
        >
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <MapClickHandler onClick={handleMapClick} />
          {/* polygon preview */}
          {points.length > 0 && (
            <Polygon
              positions={points}
              pathOptions={{ color: "#10b981", fillOpacity: 0.12, weight: 2 }}
            />
          )}

          {/* application marker */}
          {markerPos && (
            <Marker position={markerPos}>
              <Popup>
                <div>
                  <div className="font-semibold">Application location</div>
                  <div className="text-xs text-slate-400">
                    {markerPos[0].toFixed(5)}, {markerPos[1].toFixed(5)}
                  </div>
                </div>
              </Popup>
            </Marker>
          )}
        </MapContainer>

        {/* floating controls */}
        <div className="absolute top-6 right-6 w-64 map-card p-3 rounded-lg shadow-lg">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold">Map tools</div>
            <div className="flex gap-2">
              <button title="Undo" onClick={undoLastPoint} className="p-1 rounded bg-slate-800">
                <RotateCcw size={16} />
              </button>
              <button title="Clear" onClick={clearPoints} className="p-1 rounded bg-rose-700">
                <Trash2 size={16} />
              </button>
            </div>
          </div>
          <div className="mt-2 text-xs text-slate-300">
            Click on map → adds point. In Apply tab, clicks set application location.
          </div>
          <div className="mt-3 flex gap-2 justify-between">
            <button
              onClick={() => {
                if (points.length < 3) return showNotification("Need polygon", "error");
                const c = points[0];
                // fly to centroid (approx)
                const lat = points.reduce((s, p) => s + p[0], 0) / points.length;
                const lng = points.reduce((s, p) => s + p[1], 0) / points.length;
                mapRef.current?.flyTo([lat, lng], 12);
              }}
              className="py-1 px-2 bg-slate-800 rounded text-xs"
            >
              Fly to centroid
            </button>
            <button onClick={exportGeoJSON} className="py-1 px-2 bg-emerald-500 rounded text-xs text-black">
              Export GeoJSON
            </button>
          </div>
          <div className="mt-2 text-xs text-slate-400">Area: {polygonAreaHa().toFixed(3)} ha</div>
        </div>
      </div>
    </div>
  );
}
