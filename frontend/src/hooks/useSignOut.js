import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from './useAuth';
import { logoutServer } from '../services/api';

// One sign-out sequence for every entry point (sidebar button, command palette).
export function useSignOut() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  return useCallback(() => {
    logoutServer(); // revoke server-side (best effort, fire-and-forget)
    logout();
    navigate('/login');
  }, [logout, navigate]);
}
