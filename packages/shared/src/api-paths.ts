// API 경로 상수 — 프론트/백엔드가 같은 문자열을 참조하도록 한 곳에 모음.
export const API = {
  auth: {
    signup: '/api/auth/signup',
    login: '/api/auth/login',
    me: '/api/auth/me',
  },
  complaints: {
    list: '/api/complaints',
    create: '/api/complaints',
    detail: (id: string) => `/api/complaints/${id}`,
    draft: (id: string) => `/api/complaints/${id}/draft`, // F4 생성
    drafts: (id: string) => `/api/complaints/${id}/drafts`, // F4 이력
    similarCases: (id: string) => `/api/complaints/${id}/similar-cases`, // F5
  },
  escalations: {
    list: '/api/escalations', // F8 (admin·mdt)
    create: '/api/escalations', // F8 이관 요청 (teacher·admin)
    update: (id: string) => `/api/escalations/${id}`,
  },
  cases: {
    list: '/api/cases', // F5 지식베이스
    create: '/api/cases',
  },
  dashboard: {
    stats: '/api/dashboard/stats', // F9
  },
} as const;
