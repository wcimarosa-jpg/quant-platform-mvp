/**
 * Auth helpers — token storage, login, logout, auth state.
 */

const TOKEN_KEY = 'quant_token';
const USER_KEY = 'quant_user';

export interface AuthUser {
  user_id: string;
  email: string;
  role: string;
  display_name: string;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

export function setAuth(token: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

/**
 * Login — calls the API and stores the token.
 */
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8010';

export async function login(email: string, password: string): Promise<AuthUser> {
  const resp = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!resp.ok) {
    let message = 'Login failed';
    try {
      const data = await resp.json();
      message = data.detail || message;
    } catch {
      // ignore — use default
    }
    throw new Error(message);
  }
  const data = await resp.json();
  const user: AuthUser = {
    user_id: data.user_id,
    email: data.email,
    role: data.role,
    display_name: data.display_name,
  };
  setAuth(data.token, user);
  return user;
}

export function logout(): void {
  clearAuth();
  window.location.href = '/login';
}
