import axios from "axios";

// Axios instance pointing at FastAPI backend
const api = axios.create({
  baseURL: "http://127.0.0.1:8001/api",
  headers: {
    "X-Role": "ambulance", // Role-based access header
  },
});

export default api;
