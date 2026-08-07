import { createBrowserRouter, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { LoginPage } from './pages/LoginPage';
import { SignupPage } from './pages/SignupPage';
import { ParentComplaintPage } from './pages/ParentComplaintPage';
import { TeacherInboxPage } from './pages/TeacherInboxPage';
import { ComplaintDetailPage } from './pages/ComplaintDetailPage';
import { EscalationsPage } from './pages/EscalationsPage';
import { AdminDashboardPage } from './pages/AdminDashboardPage';
import { RequireAuth } from './components/RequireAuth';

// 관리 화면은 관리자·MDT 전용 (백엔드 권한 가드와 동일 기준)
const MANAGER_ROLES = ['admin', 'mdt'] as const;

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/signup', element: <SignupPage /> },
  // 학부모 민원 접수는 로그인 여부와 무관하게 접근 가능한 진입점 (필요 시 인증 추가)
  { path: '/complaint', element: <ParentComplaintPage /> },
  {
    path: '/',
    element: (
      <RequireAuth>
        <Layout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/inbox" replace /> },
      { path: 'inbox', element: <TeacherInboxPage /> }, // 교사 민원함
      { path: 'complaints/:id', element: <ComplaintDetailPage /> }, // 상세 (F4·F5·F8)
      {
        path: 'escalations', // F8 이관 관리
        element: (
          <RequireAuth roles={MANAGER_ROLES}>
            <EscalationsPage />
          </RequireAuth>
        ),
      },
      {
        path: 'dashboard', // F9 관리자 대시보드
        element: (
          <RequireAuth roles={MANAGER_ROLES}>
            <AdminDashboardPage />
          </RequireAuth>
        ),
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
]);
