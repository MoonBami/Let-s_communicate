import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { API, type AuthTokens, type User } from '@sotong/shared';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/auth';

export function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const setAuth = useAuthStore((s) => s.setAuth);
  const navigate = useNavigate();

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      // TODO: 실제 백엔드 연동. 지금은 스텁 — 백엔드가 없으면 실패함.
      const { data } = await api.post<AuthTokens>(API.auth.login, { email, password });
      const me = await api.get<User>(API.auth.me, {
        headers: { Authorization: `Bearer ${data.accessToken}` },
      });
      setAuth(data.accessToken, me.data);
      navigate('/inbox');
    } catch {
      setError('로그인 실패 (백엔드 연동 후 동작)');
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <form onSubmit={onSubmit} className="w-full max-w-sm bg-white rounded-xl border p-6 space-y-4">
        <div>
          <h1 className="text-xl font-bold text-brand">소통해요</h1>
          <p className="text-sm text-slate-500">교사·관리자 로그인</p>
        </div>
        <label className="block space-y-1">
          <span className="text-sm text-slate-600">이메일</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
            required
          />
        </label>
        <label className="block space-y-1">
          <span className="text-sm text-slate-600">비밀번호</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
            required
          />
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          className="w-full rounded-md bg-brand text-white py-2 text-sm font-medium hover:bg-brand-fg"
        >
          로그인
        </button>
      </form>
    </div>
  );
}
