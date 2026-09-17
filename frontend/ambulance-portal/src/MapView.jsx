import { useMemo, useState, useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Polyline,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// ════════════════════════════════════════════
// CUSTOM MARKER ICONS (emoji-based, no external images)
// ════════════════════════════════════════════

function emojiIcon(emoji, size = 32) {
  return L.divIcon({
    html: `<span style="font-size:${size}px;line-height:1;">${emoji}</span>`,
    className: "emoji-marker",
    iconSize: [size, size],
    iconAnchor: [size / 2, size],
    popupAnchor: [0, -size],
  });
}

const ICON_AMBULANCE = emojiIcon("🚑", 34);
const ICON_VICTIM = emojiIcon("🆘", 30);
const ICON_HOSPITAL = emojiIcon("🏥", 28);
const ICON_BEST = emojiIcon("⭐", 34);

// ════════════════════════════════════════════
// Helper: auto-fit map bounds when data changes
// ════════════════════════════════════════════

function FitBounds({ points }) {
  const map = useMap();

  useMemo(() => {
    if (points.length >= 2) {
      const bounds = L.latLngBounds(points);
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    } else if (points.length === 1) {
      map.setView(points[0], 13);
    }
  }, [points, map]);

  return null;
}

// ════════════════════════════════════════════
// Helper: trigger resize exactly when toggling fullscreen
// ════════════════════════════════════════════

function MapResizer({ isFullscreen }) {
  const map = useMap();

  useEffect(() => {
    // Let CSS transition finish before recalibrating
    const timeout = setTimeout(() => {
      map.invalidateSize();
    }, 350);
    return () => clearTimeout(timeout);
  }, [isFullscreen, map]);

  return null;
}

// ════════════════════════════════════════════
// MapView Component
// ════════════════════════════════════════════

export default function MapView({
  ambulanceLat,
  ambulanceLon,
  victimLat,
  victimLon,
  hospitals,
  lockedHospital,
  navigationStarted,
  isOffline
}) {
  // Use strictly the lockedHospital target determined by App.jsx
  const bestHospital = lockedHospital;

  const [apiRouteAmbToVic, setApiRouteAmbToVic] = useState(null);
  const [apiRouteVicToHosp, setApiRouteVicToHosp] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    // If navigation hasn't started, don't attempt any fetching/loading
    if (!navigationStarted || !bestHospital || victimLat == null || victimLon == null) {
      return;
    }

    // OFFLINE MODE: Load strictly from localStorage
    if (!navigator.onLine || isOffline) {
      console.log("Using cached route");
      const cachedVicToHosp = localStorage.getItem("cachedRouteVicToHosp");
      if (cachedVicToHosp) setApiRouteVicToHosp(JSON.parse(cachedVicToHosp));
      
      const cachedAmbToVic = localStorage.getItem("cachedRouteAmbToVic");
      if (cachedAmbToVic) setApiRouteAmbToVic(JSON.parse(cachedAmbToVic));
      
      return;
    }

    // ONLINE MODE: Fetch from LocationIQ
    const fetchRoutes = async () => {
      try {
        const apiKey = import.meta.env.VITE_LOCATIONIQ_KEY;
        if (!apiKey) {
           console.warn("No LocationIQ Key found. Falling back to straight lines.");
           console.log("Using fallback route");
           setApiRouteVicToHosp(null);
           setApiRouteAmbToVic(null);
           return;
        }
        
        console.log("Fetching route...");
        
        // Prepare fetching: longitude FIRST, latitude SECOND
        const urlVicToHosp = `https://us1.locationiq.com/v1/directions/driving/${victimLon},${victimLat};${bestHospital.longitude},${bestHospital.latitude}?key=${apiKey}&geometries=geojson`;
        console.log("API URL (Vic -> Hosp):", urlVicToHosp);
        const fetchPromises = [fetch(urlVicToHosp)];
        
        // Also do Amb -> Vic if available
        let urlAmbToVic = null;
        if (ambulanceLat != null && ambulanceLon != null) {
          urlAmbToVic = `https://us1.locationiq.com/v1/directions/driving/${ambulanceLon},${ambulanceLat};${victimLon},${victimLat}?key=${apiKey}&geometries=geojson`;
          console.log("API URL (Amb -> Vic):", urlAmbToVic);
          fetchPromises.push(fetch(urlAmbToVic));
        }

        const responses = await Promise.all(fetchPromises);
        
        // Process Vic -> Hosp
        console.log("Response status (Vic -> Hosp):", responses[0].status);
        if (responses[0].ok) {
          const data = await responses[0].json();
          if (data.routes && data.routes[0] && data.routes[0].geometry && data.routes[0].geometry.coordinates.length > 0) {
            const coords = data.routes[0].geometry.coordinates;
            console.log("Coordinates length (Vic -> Hosp):", coords.length);
            const latLngs = coords.map(([lng, lat]) => [lat, lng]);
            setApiRouteVicToHosp(latLngs);
            localStorage.setItem("cachedRouteVicToHosp", JSON.stringify(latLngs));
          } else {
             console.log("Using fallback route");
          }
        } else {
             console.log("Using fallback route");
        }

        // Process Amb -> Vic
        if (responses.length > 1) {
          console.log("Response status (Amb -> Vic):", responses[1].status);
          if (responses[1].ok) {
            const data = await responses[1].json();
            if (data.routes && data.routes[0] && data.routes[0].geometry && data.routes[0].geometry.coordinates.length > 0) {
              const coords = data.routes[0].geometry.coordinates;
              console.log("Coordinates length (Amb -> Vic):", coords.length);
              const latLngs = coords.map(([lng, lat]) => [lat, lng]);
              setApiRouteAmbToVic(latLngs);
              localStorage.setItem("cachedRouteAmbToVic", JSON.stringify(latLngs));
            } else {
               console.log("Using fallback route");
            }
          } else {
             console.log("Using fallback route");
          }
        }
      } catch (err) {
        console.error("Routing error:", err);
        console.log("Using fallback route");
      }
    };

    fetchRoutes();
  }, [navigationStarted, bestHospital?.id, isOffline, victimLat, victimLon, ambulanceLat, ambulanceLon]);

  // Collect all points for auto-fitting bounds
  const allPoints = useMemo(() => {
    const pts = [];
    if (victimLat != null && victimLon != null) pts.push([victimLat, victimLon]);
    if (ambulanceLat != null && ambulanceLon != null)
      pts.push([ambulanceLat, ambulanceLon]);
    hospitals.forEach((h) => pts.push([h.latitude, h.longitude]));
    return pts;
  }, [ambulanceLat, ambulanceLon, victimLat, victimLon, hospitals]);

  // Polyline: Ambulance → Victim
  const ambulanceToVictim = useMemo(() => {
    if (
      ambulanceLat != null &&
      ambulanceLon != null &&
      victimLat != null &&
      victimLon != null
    ) {
      return [
        [ambulanceLat, ambulanceLon],
        [victimLat, victimLon],
      ];
    }
    return null;
  }, [ambulanceLat, ambulanceLon, victimLat, victimLon]);

  // Polyline: Victim → Best Hospital
  const victimToBest = useMemo(() => {
    if (victimLat != null && victimLon != null && bestHospital) {
      return [
        [victimLat, victimLon],
        [bestHospital.latitude, bestHospital.longitude],
      ];
    }
    return null;
  }, [victimLat, victimLon, bestHospital]);

  // Map center defaults to victim location
  const center = victimLat != null ? [victimLat, victimLon] : [15.9, 79.7];

  return (
    <div className={isFullscreen ? "map-fullscreen" : "map-wrapper"}>
      <button 
        className="fullscreen-btn" 
        onClick={() => setIsFullscreen(!isFullscreen)}
      >
        {isFullscreen ? "✖ Exit Fullscreen" : "⛶ Fullscreen"}
      </button>

      <MapContainer
        center={center}
        zoom={13}
        scrollWheelZoom={true}
        style={{ height: "100%", width: "100%", borderRadius: isFullscreen ? "0" : "10px" }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Auto-fit bounds */}
        <FitBounds points={allPoints} />
        
        {/* Responsive map invalidation */}
        <MapResizer isFullscreen={isFullscreen} />

        {/* ── Ambulance Marker ── */}
        {ambulanceLat != null && ambulanceLon != null && (
          <Marker position={[ambulanceLat, ambulanceLon]} icon={ICON_AMBULANCE}>
            <Popup>
              <strong>🚑 Ambulance</strong>
              <br />
              {ambulanceLat.toFixed(4)}, {ambulanceLon.toFixed(4)}
            </Popup>
          </Marker>
        )}

        {/* ── Victim Marker ── */}
        {victimLat != null && victimLon != null && (
          <Marker position={[victimLat, victimLon]} icon={ICON_VICTIM}>
            <Popup>
              <strong>🆘 Victim Location</strong>
              <br />
              {victimLat.toFixed(4)}, {victimLon.toFixed(4)}
            </Popup>
          </Marker>
        )}

        {/* ── Hospital Markers ── */}
        {hospitals.map((h, i) => (
          <Marker
            key={h.id}
            position={[h.latitude, h.longitude]}
            icon={bestHospital && h.id === bestHospital.id ? ICON_BEST : ICON_HOSPITAL}
          >
            <Popup>
              <strong>{bestHospital && h.id === bestHospital.id ? "⭐ " : "🏥 "}{h.name}</strong>
              {bestHospital && h.id === bestHospital.id && <em> (Current Route)</em>}
              <br />
              📍 {h.distance_km} km &nbsp; 🛏️ ICU: {h.icu_available} &nbsp; Beds: {h.emergency_beds}
              <br />
              {h.specialization && <span>🏷️ {h.specialization}</span>}
            </Popup>
          </Marker>
        ))}

        {/* ── Route: Ambulance → Victim (dashed blue api or straight) ── */}
        {apiRouteAmbToVic ? (
          <Polyline
            positions={apiRouteAmbToVic}
            pathOptions={{
              color: "#4a9eff",
              weight: 3,
              dashArray: "8 6",
              opacity: 0.8,
            }}
          />
        ) : ambulanceToVictim ? (
          <Polyline
            positions={ambulanceToVictim}
            pathOptions={{
              color: "#4a9eff",
              weight: 3,
              dashArray: "8 6",
              opacity: 0.8,
            }}
          />
        ) : null}

        {/* ── Route: Victim → Best Hospital (solid green api or straight) ── */}
        {apiRouteVicToHosp ? (
          <Polyline
            positions={apiRouteVicToHosp}
            pathOptions={{
              color: "#4ade80",
              weight: 4,
              opacity: 0.9,
            }}
          />
        ) : victimToBest ? (
          <Polyline
            positions={victimToBest}
            pathOptions={{
              color: "#4ade80",
              weight: 3,
              opacity: 0.9,
            }}
          />
        ) : null}
      </MapContainer>
    </div>
  );
}
