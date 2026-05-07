import { useState, useCallback } from 'react';

const TOKEN_KEY = 'snmp_access_token';

export function useAuth() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));

  const login = useCallback((newToken) => {
    localStorage.setItem(TOKEN_KEY, newToken);
    setToken(newToken);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
  }, []);

  const user = token ? _parseToken(token) : null;

  return { token, user, login, logout };
}

function _parseToken(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return { email: payload.sub, role: payload.role };
  } catch {
    return null;
  }
}
