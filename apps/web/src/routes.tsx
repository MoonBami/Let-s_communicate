import { createBrowserRouter, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { LoginPage } from './pages/LoginPage';
import { ParentComplaintPage } from './pages/ParentComplaintPage';
import { TeacherInboxPage } from './pages/TeacherInboxPage';
import { AdminDashboardPage } from './pages/AdminDashboardPage';
import { RequireAuth } from './components/RequireAuth';

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
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
      { path: 'dashboard', element: <AdminDashboardPage /> }, // F9 관리자 대시보드
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
]);
