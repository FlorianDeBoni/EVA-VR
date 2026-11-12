import { createApi } from "./api.js";

/** The one API client of the app, pointed at VITE_API_URL (see .env.frontend). */
export const api = createApi(import.meta.env.VITE_API_URL);
