const environment = import.meta.env as Record<string, unknown>;
const apiUrl = environment.VITE_API_URL;

export const API_URL = (typeof apiUrl === "string" ? apiUrl : "http://localhost:8080").replace(
  /\/+$/,
  "",
);
