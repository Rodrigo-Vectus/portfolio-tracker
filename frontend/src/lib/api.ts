/**
 * Cliente HTTP de la API.
 *
 * Tres decisiones que vale la pena entender:
 *
 * 1. El access token vive **en memoria**, no en localStorage. Cualquier script
 *    inyectado en la página puede leer localStorage; una variable de módulo,
 *    no. El costo es que al recargar hay que renovarlo, y para eso está la
 *    cookie de refresh.
 *
 * 2. Ante un 401 se intenta **una sola vez** renovar el token y repetir el
 *    pedido. Un solo reintento evita bucles infinitos si el refresh también
 *    falla.
 *
 * 3. Los errores se devuelven como valor, no como excepción. Una falla de red
 *    tiene que poder mostrarse como estado en pantalla, no romperla.
 */

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

let accessToken: string | null = null;
let onSessionLost: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setSessionLostHandler(fn: () => void): void {
  onSessionLost = fn;
}

/** Lee la cookie CSRF, que a diferencia del refresh sí es legible por JS. */
export function readCsrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)pt_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; status: number };

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean;
  csrf?: boolean;
  retryOn401?: boolean;
}

async function raw<T>(path: string, opts: RequestOptions = {}): Promise<ApiResult<T>> {
  const {
    method = "GET",
    body,
    auth = true,
    csrf = false,
    retryOn401 = true,
  } = opts;

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth && accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
  if (csrf) headers["X-CSRF-Token"] = readCsrfToken();

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method,
      headers,
      credentials: "include",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    return {
      ok: false,
      status: 0,
      error: e instanceof Error ? e.message : "No se pudo conectar con el servidor.",
    };
  }

  if (res.status === 401 && auth && retryOn401) {
    const renewed = await refreshSession();
    if (renewed) {
      return raw<T>(path, { ...opts, retryOn401: false });
    }
    onSessionLost?.();
  }

  if (res.status === 204) {
    return { ok: true, data: undefined as T };
  }

  let payload: unknown;
  try {
    payload = await res.json();
  } catch {
    payload = null;
  }

  if (!res.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : `Error ${res.status}`;
    return { ok: false, status: res.status, error: detail };
  }

  return { ok: true, data: payload as T };
}

export const api = {
  get: <T>(path: string) => raw<T>(path),
  post: <T>(path: string, body?: unknown, csrf = false) =>
    raw<T>(path, { method: "POST", body, csrf }),
};

// --------------------------------------------------------------------------
// Sesión
// --------------------------------------------------------------------------

export interface User {
  id: string;
  email: string;
  name: string;
  role: "ADMIN" | "USER";
  is_active: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

let refreshInFlight: Promise<boolean> | null = null;

/** Renueva el access token. Si hay varias llamadas simultáneas, comparten una. */
export function refreshSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const res = await raw<TokenResponse>("/auth/refresh", {
      method: "POST",
      auth: false,
      csrf: true,
      retryOn401: false,
    });
    if (res.ok) {
      setAccessToken(res.data.access_token);
      return true;
    }
    setAccessToken(null);
    return false;
  })();

  try {
    return refreshInFlight;
  } finally {
    void refreshInFlight.finally(() => {
      refreshInFlight = null;
    });
  }
}

export const login = (email: string, password: string) =>
  raw<TokenResponse>("/auth/login", {
    method: "POST",
    body: { email, password },
    auth: false,
    retryOn401: false,
  });

export const logout = () =>
  raw<void>("/auth/logout", { method: "POST", csrf: true, retryOn401: false });

export const changePassword = (current_password: string, new_password: string) =>
  raw<User>("/auth/change-password", {
    method: "POST",
    body: { current_password, new_password },
    csrf: true,
  });

export const fetchMe = () => raw<User>("/auth/me");
export const fetchUsers = () => raw<User[]>("/users");
