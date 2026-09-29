import type { UserRole } from '@sotong/shared';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { RoleHomeRedirect } from './components/RoleHomeRedirect';
import { LoginPage } from './pages/LoginPage';
import { SignupPage } from './pages/SignupPage';
import { ParentComplaintPage } from './pages/ParentComplaintPage';
import { TeacherInboxPage } from './pages/TeacherInboxPage';
import { ComplaintDetailPage } from './pages/ComplaintDetailPage';
import { EscalationsPage } from './pages/EscalationsPage';
import { AdminDashboardPage } from './pages/AdminDashboardPage';
import { TeacherAssignmentsPage } from './pages/TeacherAssignmentsPage';
import { GuestLookupPage } from './pages/GuestLookupPage';
import { ParentDashboardPage } from './pages/ParentDashboardPage';
import { ParentComplaintDetailPage } from './pages/ParentComplaintDetailPage';
import { RequireAuth } from './components/RequireAuth';

const PARENT_ROLES: readonly UserRole[] = ['parent'];
const STAFF_ROLES: readonly UserRole[] = ['teacher', 'admin', 'mdt'];
const MANAGER_ROLES: readonly UserRole[] = ['admin', 'mdt'];
const ADMIN_ROLES: readonly UserRole[] = ['admin'];

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/signup', element: <SignupPage /> },
  // 학부모 민원 접수는 로그인 여부와 무관하게 접근 가능한 진입점 (필요 시 인증 추가)
  { path: '/complaint', element: <ParentComplaintPage /> },
  { path: '/complaint/lookup', element: <GuestLookupPage /> }, // 비회원 조회 (접수번호 + 4자리)
  {
    path: '/',
    element: (
      <RequireAuth>
        <Layout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <RoleHomeRedirect /> },
      {
        path: 'parent',
        element: (
          <RequireAuth roles={PARENT_ROLES}>
            <ParentDashboardPage />
          </RequireAuth>
        ),
      },
      {
        path: 'parent/new',
        element: (
          <RequireAuth roles={PARENT_ROLES}>
            <ParentComplaintPage />
          </RequireAuth>
        ),
      },
      {
        path: 'parent/complaints/:id',
        element: (
          <RequireAuth roles={PARENT_ROLES}>
            <ParentComplaintDetailPage />
          </RequireAuth>
        ),
      },
      {
        path: 'inbox',
        element: (
          <RequireAuth roles={STAFF_ROLES}>
            <TeacherInboxPage />
          </RequireAuth>
        ),
      },
      {
        path: 'complaints/:id',
        element: (
          <RequireAuth roles={STAFF_ROLES}>
            <ComplaintDetailPage />
          </RequireAuth>
        ),
      },
      {
        path: 'escalations', // F8 이관 관리
        element: (
          <RequireAuth roles={MANAGER_ROLES}>
            <EscalationsPage />
          </RequireAuth>
        ),
      },
      {
        path: 'teachers', // 교사 담당 반 배정 — 배정이 곧 민원 열람 권한이라 관리자만
        element: (
          <RequireAuth roles={ADMIN_ROLES}>
            <TeacherAssignmentsPage />
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
