const environment = import.meta.env as Record<string, unknown>;
const apiUrl = environment.VITE_API_URL;

export const authorName = "Santiago Ondris";
export const sourceUrl = "https://github.com/santiago-ondris/homevision";

export const API_URL = (typeof apiUrl === "string" ? apiUrl : "http://localhost:8080").replace(
  /\/+$/,
  "",
);
