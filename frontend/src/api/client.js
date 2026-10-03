// Cienki klient HTTP: dokleja nagłówek Authorization, parsuje błędy API
// w formacie {error, message, details} i automatycznie odświeża
// access token raz, jeśli serwer odpowie 401.

const ACCESS_KEY = "tp_access_token";
const REFRESH_KEY = "tp_refresh_token";
const ROLE_KEY = "tp_role";

export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRole() {
  return localStorage.getItem(ROLE_KEY);
}

export function isAuthenticated() {
  return Boolean(getAccessToken());
}

export function setSession({ accessToken, refreshToken, role }) {
  localStorage.setItem(ACCESS_KEY, accessToken);
  if (refreshToken) localStorage.setItem(REFRESH_KEY, refreshToken);
  if (role) localStorage.setItem(ROLE_KEY, role);
}

export function clearSession() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(ROLE_KEY);
}

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.message || body?.error || `Błąd API (${status})`);
    this.status = status;
    this.code = body?.error;
    this.details = body?.details || [];
  }
}

async function rawRequest(path, { method = "GET", body, auth = true, query } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth) {
    const token = getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let url = `/api/v1${path}`;
  if (query) {
    const qs = new URLSearchParams(
      Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== "")
    ).toString();
    if (qs) url += `?${qs}`;
  }

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return null;

  let data = null;
  try {
    data = await res.json();
  } catch {
    // brak ciała odpowiedzi
  }

  if (!res.ok) {
    throw new ApiError(res.status, data);
  }
  return data;
}

let refreshInFlight = null;

async function tryRefresh() {
  const refreshToken = localStorage.getItem(REFRESH_KEY);
  if (!refreshToken) return false;

  if (!refreshInFlight) {
    refreshInFlight = rawRequest("/auth/refresh", {
      method: "POST",
      body: { refreshToken },
      auth: false,
    })
      .then((data) => {
        localStorage.setItem(ACCESS_KEY, data.accessToken);
        localStorage.setItem(REFRESH_KEY, data.refreshToken);
        return true;
      })
      .catch(() => {
        clearSession();
        return false;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

export async function request(path, options = {}) {
  try {
    return await rawRequest(path, options);
  } catch (err) {
    const isAuthEndpoint = path.startsWith("/auth/");
    if (err instanceof ApiError && err.status === 401 && options.auth !== false && !isAuthEndpoint) {
      const refreshed = await tryRefresh();
      if (refreshed) {
        return rawRequest(path, options);
      }
    }
    throw err;
  }
}

export const api = {
  get: (path, query) => request(path, { method: "GET", query }),
  post: (path, body, opts) => request(path, { method: "POST", body, ...opts }),
  patch: (path, body) => request(path, { method: "PATCH", body }),
  put: (path, body) => request(path, { method: "PUT", body }),
  del: (path, body) => request(path, { method: "DELETE", body }),
};
