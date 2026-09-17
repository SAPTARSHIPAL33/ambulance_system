import { useState, useEffect, useRef, useCallback } from "react";
import api from "./api";
import MapView from "./MapView";
import "./App.css";

const SPECIALIZATIONS = [
  "Cardiology",
  "Neurology",
  "Orthopedics",
  "Emergency Medicine",
  "Pediatrics",
  "Oncology",
  "Dermatology",
  "ENT",
  "General Surgery",
];

const FALLBACK_LAT = 15.9129;
const FALLBACK_LON = 79.7400;

const GEO_OPTIONS = {
  enableHighAccuracy: false,
  maximumAge: 60000,
  timeout: 15000,
};

const GEO_OPTIONS_WATCH = {
  enableHighAccuracy: false,
  maximumAge: 30000,
  timeout: 20000,
};

// Pure helper function for numeric conversion matching backend scoring
function getNumericScore(val) {
  if (typeof val === 'string') {
    if (val === "0-2") return 1;
    if (val === "3-5") return 2;
    if (val === "6-10") return 3;
    if (val === "10+") return 4;
    return 1;
  }
  if (val < 3) return 1;
  if (val < 6) return 2;
  if (val < 10) return 3;
  return 4;
}

function getAvailabilityScore(icu, beds) {
  return getNumericScore(icu) + getNumericScore(beds);
}

// Fallback logic for the colored visual dots
function getAvailabilityConfig(icu, beds) {
  const score = getAvailabilityScore(icu, beds);
  if (score >= 6) return { color: 'bg-green', text: 'High Availability' };
  if (score <= 3) return { color: 'bg-red', text: 'Low Availability' };
  return { color: 'bg-yellow', text: 'Medium Availability' };
}

function App() {
  const [ambulanceLat, setAmbulanceLat] = useState(null);
  const [ambulanceLon, setAmbulanceLon] = useState(null);
  const [ambulanceTracking, setAmbulanceTracking] = useState(false);
  const [ambulanceError, setAmbulanceError] = useState("");
  const [ambulanceFallback, setAmbulanceFallback] = useState(false);
  const watchIdRef = useRef(null);
  const ambulanceRetried = useRef(false);

  const [victimLat, setVictimLat] = useState(null);
  const [victimLon, setVictimLon] = useState(null);
  const [victimCaptured, setVictimCaptured] = useState(false);
  const [victimLoading, setVictimLoading] = useState(false);
  const [victimError, setVictimError] = useState("");
  const [victimStatus, setVictimStatus] = useState(""); 
  const [hasSearched, setHasSearched] = useState(false);

  const [specialization, setSpecialization] = useState("");
  const [hospitals, setHospitals] = useState([]);
  
  // DECISION LOCK STATES
  const [lockedHospital, setLockedHospital] = useState(null);
  const [suggestedHospital, setSuggestedHospital] = useState(null);

  // NAVIGATION & OFFLINE STATES
  const [navigationStarted, setNavigationStarted] = useState(false);
  const [isOffline, setIsOffline] = useState(!navigator.onLine);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Offline detection effect
  useEffect(() => {
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const applyAmbulanceFallback = useCallback(() => {
    setAmbulanceLat(FALLBACK_LAT);
    setAmbulanceLon(FALLBACK_LON);
    setAmbulanceTracking(true);
    setAmbulanceFallback(true);
    setAmbulanceError("");
  }, []);

  useEffect(() => {
    if (!navigator.geolocation) {
      applyAmbulanceFallback();
      setAmbulanceError("Geolocation not supported.");
      return;
    }

    const onSuccess = (position) => {
      setAmbulanceLat(position.coords.latitude);
      setAmbulanceLon(position.coords.longitude);
      setAmbulanceTracking(true);
      setAmbulanceFallback(false);
      setAmbulanceError("");
    };

    const onErrorFinal = (err) => {
      applyAmbulanceFallback();
      setAmbulanceError("GPS unavailable.");
    };

    const onError = (err) => {
      if (err.code === err.PERMISSION_DENIED) {
        applyAmbulanceFallback();
        setAmbulanceError("Permission denied.");
        return;
      }
      if (!ambulanceRetried.current) {
        ambulanceRetried.current = true;
        if (watchIdRef.current !== null) {
          navigator.geolocation.clearWatch(watchIdRef.current);
        }
        watchIdRef.current = navigator.geolocation.watchPosition(onSuccess, onErrorFinal, GEO_OPTIONS_WATCH);
        return;
      }
      applyAmbulanceFallback();
      setAmbulanceError("GPS unavailable.");
    };

    watchIdRef.current = navigator.geolocation.watchPosition(onSuccess, onError, GEO_OPTIONS_WATCH);

    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
      }
    };
  }, [applyAmbulanceFallback]);

  const captureVictimLocation = useCallback(() => {
    if (!navigator.geolocation) {
      setVictimLat(FALLBACK_LAT);
      setVictimLon(FALLBACK_LON);
      setVictimCaptured(true);
      setVictimStatus("Using default location (geolocation not supported).");
      return;
    }

    setVictimLoading(true);
    setVictimError("");
    setVictimCaptured(false);
    setVictimStatus("");

    const onSuccess = (position) => {
      setVictimLat(position.coords.latitude);
      setVictimLon(position.coords.longitude);
      setVictimCaptured(true);
      setVictimLoading(false);
    };

    const applyVictimFallback = (reason) => {
      setVictimLat(FALLBACK_LAT);
      setVictimLon(FALLBACK_LON);
      setVictimCaptured(true);
      setVictimLoading(false);
      setVictimStatus(`Using default location — ${reason}`);
    };

    const onError = (err) => {
      if (err.code === err.PERMISSION_DENIED) {
        applyVictimFallback("permission denied.");
        return;
      }
      navigator.geolocation.getCurrentPosition(
        onSuccess,
        () => applyVictimFallback("signal not available."),
        { ...GEO_OPTIONS, timeout: 10000 }
      );
    };

    navigator.geolocation.getCurrentPosition(onSuccess, onError, GEO_OPTIONS);
  }, []);

  const handleSearch = async () => {
    if (!victimCaptured || victimLat === null) {
      setError("Please capture Patient Location first.");
      return;
    }
    if (ambulanceLat === null) {
      setError("Fetching ambulance location… please wait.");
      return;
    }

    setLoading(true);
    setError("");
    setSuggestedHospital(null); // Clear suggestion on new search
    setHasSearched(true);

    try {
      const params = { victim_lat: victimLat, victim_lon: victimLon };
      if (specialization.trim()) params.specialization = specialization.trim();

      const res = await api.get("/ambulance/eligible-hospitals", { params });
      const data = res.data;
      setHospitals(data);

      if (data.length > 0) {
        if (!lockedHospital) {
          // Initial Route Lock
          setLockedHospital(data[0]);
        } else {
          // Compare against locked route logic
          const lockedNewData = data.find(h => h.id === lockedHospital.id) || lockedHospital;
          const topNew = data[0];

          // Re-sync the lockedHospital with fresh backend numbers
          if (lockedNewData.id === lockedHospital.id) {
            setLockedHospital(lockedNewData);
          }

          // Evaluate for suggested replacement
          if (topNew.id !== lockedHospital.id) {
            const newAvailScore = getAvailabilityScore(topNew.icu_available, topNew.emergency_beds);
            const currentAvailScore = getAvailabilityScore(lockedNewData.icu_available, lockedNewData.emergency_beds);

            // Optional Distance Safety Check (e.g. within 5km maximum threshold beyond current route)
            const isDistanceSafe = topNew.distance_km <= (lockedNewData.distance_km + 5.0);
            
            // Critical Conditions Check
            if (isDistanceSafe && (newAvailScore > currentAvailScore || currentAvailScore <= 3)) {
              setSuggestedHospital(topNew);
            }
          }
        }
      }
    } catch (err) {
      if (err.response) {
        setError(`API Error: ${err.response.data.detail || "Unknown error"}`);
      } else {
        setError("Network error — is the backend running on port 8001?");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSwitchRoute = () => {
    if (suggestedHospital) {
      setLockedHospital(suggestedHospital);
      setSuggestedHospital(null);
      // Let MapView re-fetch the route automatically since lockedHospital changed
    }
  };

  const handleStartNavigation = () => {
    setNavigationStarted(true);
  };

  return (
    <div className="app">
      {isOffline && (
        <div className="offline-banner">
          📡 Offline mode: using cached map and routes
        </div>
      )}

      <div className={`ambulance-banner ${ambulanceTracking && !ambulanceFallback && !ambulanceError ? 'active' : ambulanceError ? 'error' : ''}`}>
        {ambulanceTracking && !ambulanceFallback && !ambulanceError ? (
          <><span className="pulse-dot" /> 🚑 Ambulance GPS Active</>
        ) : ambulanceTracking && ambulanceFallback ? (
          <>🚑 Default Location Active</>
        ) : ambulanceError ? (
          <>⚠️ {ambulanceError}</>
        ) : (
          <>🔄 Acquiring Ambulance GPS...</>
        )}
      </div>

      <h1>🚑 Emergency Routing System</h1>

      <div className="main-card">
        <h2 className="section-title">📍 Patient Location</h2>
        <div className="form-row">
          <button
            className={`btn-secondary ${victimCaptured ? 'success' : ''}`}
            onClick={captureVictimLocation}
            disabled={victimLoading}
          >
            {victimLoading ? "Fetching..." : victimCaptured ? "✅ Patient Location Captured" : "📍 Use Current Location"}
          </button>
          
          {victimStatus && <div style={{fontSize: '0.8rem', color: '#64748b', marginTop: '4px'}}>{victimStatus}</div>}
          {victimError && <div style={{fontSize: '0.8rem', color: '#ef4444', marginTop: '4px'}}>{victimError}</div>}
        </div>

        <div className="form-row">
          <div className="field">
            <label htmlFor="spec">Specialization (Optional)</label>
            <input
              id="spec"
              list="spec-options"
              value={specialization}
              onChange={(e) => setSpecialization(e.target.value)}
              placeholder="Type to search…"
            />
            <datalist id="spec-options">
              {SPECIALIZATIONS.map((s) => (
                <option key={s} value={s} />
              ))}
            </datalist>
          </div>
        </div>

        <button onClick={handleSearch} disabled={loading}>
          Find Best Hospital
        </button>
      </div>

      {error && <div className="error-state">{error}</div>}

      <div className="results">
        {loading && (
          <div className="loading-state">
            🔄 Finding best hospitals...
          </div>
        )}

        {!loading && hasSearched && hospitals.length === 0 && !error && (
          <div className="empty-state">
            No suitable hospitals found nearby
          </div>
        )}

        {!loading && hospitals.length > 0 && (
          <>
            <h2>🏥 Recommended Hospitals</h2>
            
            {/* Suggestion Banner */}
            {suggestedHospital && (
              <div className="suggested-banner">
                <div style={{fontWeight: 700}}>⚠️ Better hospital available nearby</div>
                <button className="btn-switch" onClick={handleSwitchRoute}>Switch Route</button>
              </div>
            )}

            {hospitals.map((h) => {
              const isLocked = lockedHospital && lockedHospital.id === h.id;
              const isSuggested = suggestedHospital && suggestedHospital.id === h.id;
              
              const isRecent = (h.freshness_score || 1) >= 0.7; 
              const conf = h.confidence_level ? h.confidence_level.toLowerCase() : 'medium';
              const availConfig = getAvailabilityConfig(h.icu_available, h.emergency_beds);

              let cardClass = "hospital-card";
              if (isLocked) cardClass += " locked-route";
              if (isSuggested) cardClass += " suggested-route";

              return (
                <div key={h.id} className={cardClass}>
                  {isLocked && <div className="route-badge badge-locked">🚑 CURRENT ROUTE</div>}
                  {isSuggested && <div className="route-badge badge-suggested">⚠️ SUGGESTED</div>}
                  
                  <div className="hospital-header">
                    <div>
                      <div className="hospital-name">{h.name}</div>
                      <div style={{marginTop: '6px', marginBottom: '8px'}}>
                        <span className={`status-indicator ${availConfig.color}`}></span>
                        <span style={{fontSize: '0.85rem', fontWeight: 600, color: '#475569'}}>{availConfig.text}</span>
                      </div>
                    </div>
                    <div className="distance-highlight">
                      {h.distance_km} km away
                    </div>
                  </div>

                  {isLocked && (
                    <div style={{marginBottom: "16px"}}>
                      <button 
                        className={`btn-navigation ${navigationStarted ? "active" : ""}`}
                        onClick={handleStartNavigation}
                      >
                        {navigationStarted ? "🛤️ Navigation Active" : "🚀 Start Navigation"}
                      </button>
                    </div>
                  )}

                  <div className="hospital-details">
                    <div className="detail-item">
                      <span className="detail-label">ICU Available</span>
                      <span className="detail-value">{h.icu_available}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Emergency Beds</span>
                      <span className="detail-value">{h.emergency_beds}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Confidence</span>
                      <span className={`confidence-badge confidence-${conf}`}>{conf.toUpperCase()}</span>
                    </div>
                  </div>

                  <div className="hospital-details" style={{borderBottom: 'none', paddingBottom: 0, marginBottom: 0}}>
                    {h.specialization && (
                      <div className="detail-item" style={{flex: 2}}>
                        <span className="detail-label">Specializations</span>
                        <span style={{fontSize: '0.9rem', color: '#475569', fontWeight: 500}}>{h.specialization}</span>
                      </div>
                    )}
                    <div className="detail-item">
                       <span className="detail-label">Data Freshness</span>
                       <span className={`freshness-tag ${isRecent ? 'freshness-recent timestamp-trust' : 'freshness-stale'}`}>
                          {isRecent ? 'Updated just now' : 'Data may be outdated'}
                       </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </>
        )}
      </div>

      {/* Map Visualization binds dynamically to the locked target */}
      {victimCaptured && victimLat != null ? (
        <MapView
          ambulanceLat={ambulanceLat}
          ambulanceLon={ambulanceLon}
          victimLat={victimLat}
          victimLon={victimLon}
          hospitals={hospitals}
          lockedHospital={lockedHospital}
          navigationStarted={navigationStarted}
          isOffline={isOffline}
        />
      ) : (
        <div className="map-placeholder">
          📍 Capture patient location to view map
        </div>
      )}
    </div>
  );
}

export default App;
