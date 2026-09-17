import { useState } from "react";
import api from "./api";
import "./App.css";

const RANGE_OPTIONS = ["0-2", "3-5", "6-10", "10+"];

function App() {
  const [hospitalId, setHospitalId] = useState("");
  const [icuRange, setIcuRange] = useState("3-5");
  const [bedsRange, setBedsRange] = useState("3-5");

  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");

  const handleUpdate = async () => {
    if (!hospitalId || isNaN(Number(hospitalId))) {
      setError("Please enter a valid Hospital ID.");
      setSuccess("");
      return;
    }

    setLoading(true);
    setError("");
    setSuccess("");

    try {
      const res = await api.post("/hospital/update-resources-range", {
        hospital_id: Number(hospitalId),
        icu_range: icuRange,
        beds_range: bedsRange,
      });

      setSuccess("✔ Resources updated successfully");
    } catch (err) {
      if (err.response) {
        setError(`Error: ${err.response.data.detail || "Unknown error"}`);
      } else {
        setError("Network error — is the backend running on port 8001?");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <h1>🏥 Hospital Control Panel</h1>
      <p className="subtitle">Update real-time resource availability</p>

      <div className="main-card">
        <div className="form-section">
          <div className="field">
            <label htmlFor="hospital-id">🏥 Hospital ID</label>
            <input
              id="hospital-id"
              type="number"
              min="1"
              placeholder="e.g. 1"
              value={hospitalId}
              onChange={(e) => setHospitalId(e.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="icu-range">⚕️ ICU Available (Range)</label>
            <select
              id="icu-range"
              value={icuRange}
              onChange={(e) => setIcuRange(e.target.value)}
            >
              {RANGE_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="beds-range">🛏️ Emergency Beds (Range)</label>
            <select
              id="beds-range"
              value={bedsRange}
              onChange={(e) => setBedsRange(e.target.value)}
            >
              {RANGE_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>

          <button onClick={handleUpdate} disabled={loading}>
            {loading ? "Updating…" : "Update Availability"}
          </button>
        </div>
        
        {/* Feedback Messages */}
        {success && <div className="msg success">{success}</div>}
        {error && <div className="msg error">{error}</div>}
      </div>
    </div>
  );
}

export default App;
