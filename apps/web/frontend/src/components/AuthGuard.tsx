import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { isAuthenticated } from '../api/auth';

interface AuthGuardProps {
  children: ReactNode;
}

/**
 * Wraps routes that require authentication.
 * Redirects to /login if no token is present.
 */
export function AuthGuard({ children }: AuthGuardProps) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}
