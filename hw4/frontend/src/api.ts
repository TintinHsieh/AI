import type { ChatHistoryResponse, ChatResponse, Product } from "./types";

export const API_ROOT = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const SESSION_KEY = "campus_customs_session";
const FAVORITES_KEY = "campus_customs_favorites";

export interface AuthUser {
  id: number;
  name: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  created_at: string;
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

async function getJson<T>(path: string, headers?: Record<string, string>): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, { headers });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown, headers?: Record<string, string>): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    let message = "Request failed. Please try again.";
    try {
      const payload = await response.json() as { detail?: string };
      message = payload.detail ?? message;
    } catch {
      // Keep the friendly fallback when the API returns a non-JSON error.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function fetchProducts(): Promise<Product[]> {
  return getJson<Product[]>("/api/products");
}

export function fetchProduct(productId: string): Promise<Product> {
  return getJson<Product>(`/api/products/${encodeURIComponent(productId)}`);
}

export function registerAccount(payload: {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  confirm_password: string;
}): Promise<AuthResponse> {
  return postJson<AuthResponse>("/api/auth/register", payload);
}

export function loginAccount(payload: { email: string; password: string }): Promise<AuthResponse> {
  return postJson<AuthResponse>("/api/auth/login", payload);
}

export function sendChatMessage(
  message: string,
  pageContext: Record<string, unknown> = {},
  token?: string,
): Promise<ChatResponse> {
  return postJson<ChatResponse>(
    "/api/chat",
    { message, page_context: pageContext },
    token ? { Authorization: `Bearer ${token}` } : undefined,
  );
}

export function fetchChatHistory(token: string): Promise<ChatHistoryResponse> {
  return getJson<ChatHistoryResponse>("/api/chat/history", {
    Authorization: `Bearer ${token}`,
  });
}

export function saveSession(session: AuthResponse): void {
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function loadSession(): AuthResponse | null {
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) as AuthResponse : null;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  window.localStorage.removeItem(SESSION_KEY);
}

export function loadFavoriteIds(): string[] {
  try {
    const raw = window.localStorage.getItem(FAVORITES_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
  } catch {
    return [];
  }
}

export function saveFavoriteIds(ids: string[]): void {
  try {
    window.localStorage.setItem(FAVORITES_KEY, JSON.stringify(ids));
  } catch {
    // The UI still works for this session if browser storage is unavailable.
  }
}

export function imageUrl(path: string): string {
  return path.startsWith("http") ? path : `${API_ROOT}${path}`;
}
