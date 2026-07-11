import axios from 'axios';
import { useAuthStore } from '@/store/auth';

// 개발 중엔 vite proxy(/api)로 붙으므로 baseURL 비어 있어도 됨.
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
});

// 요청마다 JWT 자동 첨부
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 401 → 로그아웃 처리
api.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  },
);
