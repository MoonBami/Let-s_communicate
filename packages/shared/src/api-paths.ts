// API 경로 상수 — 프론트/백엔드가 같은 문자열을 참조하도록 한 곳에 모음.
export const API = {
  auth: {
    login: '/api/auth/login',
    me: '/api/auth/me',
  },
  complaints: {
    list: '/api/complaints',
    create: '/api/complaints',
    detail: (id: string) => `/api/complaints/${id}`,
    draft: (id: string) => `/api/complaints/${id}/draft`, // F4
  },
  dashboard: {
    stats: '/api/dashboard/stats', // F9
  },
} as const;
