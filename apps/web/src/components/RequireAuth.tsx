import { Navigate, useLocation } from 'react-router-dom';
import type { UserRole } from '@sotong/shared';
import { useAuthStore } from '@/store/auth';

export function RequireAuth({
  children,
  roles,
}: {
  children: React.ReactNode;
  roles?: readonly UserRole[];
}) {
  const { token, user } = useAuthStore();
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  // 역할 미달은 로그인 화면으로 되돌리지 않는다(리다이렉트 루프 방지).
  if (roles && user && !roles.includes(user.role)) {
    return <p className="text-sm text-slate-500">이 화면에 접근할 권한이 없습니다.</p>;
  }
  return <>{children}</>;
}
