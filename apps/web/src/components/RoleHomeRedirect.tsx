import { Navigate } from 'react-router-dom';
import { getHomePath } from '@/lib/roleRoutes';
import { useAuthStore } from '@/store/auth';

export function RoleHomeRedirect() {
  const user = useAuthStore((state) => state.user);

  if (user === null) {
    return <Navigate to="/login" replace />;
  }

  return <Navigate to={getHomePath(user.role)} replace />;
}
