import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { API, type AuthTokens, type SignupRequest, type User } from '@sotong/shared';
import { api } from '@/lib/api';
import { getHomePath } from '@/lib/roleRoutes';
import { useAuthStore } from '@/store/auth';

// 교사 회원가입. 성공하면 바로 로그인되어 민원함으로 이동.
// 관리자 계정은 가입으로 만들 수 없다 — 관리자는 차단 민원 증거까지 열람하므로
// 공개 가입 화면에서 고를 수 있으면 안 된다(운영자가 생성).
// 가입 직후엔 담당 반이 없어 민원이 보이지 않는다. 관리자가 반을 배정해야 한다.
export function SignupPage() {
  const [form, setForm] = useState<SignupRequest>({
    email: '',
    password: '',
    name: '',
    role: 'teacher',
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const setAuth = useAuthStore((s) => s.setAuth);
  const navigate = useNavigate();

  function update<K extends keyof SignupRequest>(key: K, value: SignupRequest[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { data } = await api.post<AuthTokens>(API.auth.signup, form);
      const me = await api.get<User>(API.auth.me, {
        headers: { Authorization: `Bearer ${data.accessToken}` },
      });
      setAuth(data.accessToken, me.data);
      navigate(getHomePath(me.data.role));
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setError(
        status === 409
          ? '이미 가입된 이메일입니다.'
          : status === 400
            ? '입력값을 확인해 주세요 (비밀번호 6자 이상).'
            : '회원가입에 실패했습니다. 백엔드 상태를 확인해 주세요.',
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <form onSubmit={onSubmit} className="w-full max-w-sm bg-white rounded-xl border p-6 space-y-4">
        <div>
          <h1 className="text-xl font-bold text-brand">회원가입</h1>
          <p className="text-sm text-slate-500">교사 계정 만들기</p>
        </div>

        <label className="block space-y-1">
          <span className="text-sm text-slate-600">이름</span>
          <input
            value={form.name}
            onChange={(e) => update('name', e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
            placeholder="홍길동"
            required
          />
        </label>

        <label className="block space-y-1">
          <span className="text-sm text-slate-600">이메일</span>
          <input
            type="email"
            value={form.email}
            onChange={(e) => update('email', e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
            required
          />
        </label>

        <label className="block space-y-1">
          <span className="text-sm text-slate-600">비밀번호 (6자 이상)</span>
          <input
            type="password"
            value={form.password}
            onChange={(e) => update('password', e.target.value)}
            className="w-full rounded-md border px-3 py-2 text-sm"
            minLength={6}
            required
          />
        </label>

        <p className="rounded-md bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500">
          가입 후 학교 관리자가 담당 학년·반을 배정하면 그 반의 민원이 민원함에 표시됩니다.
          관리자 계정이 필요하면 운영 담당자에게 요청해 주세요.
        </p>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-brand text-white py-2 text-sm font-medium hover:bg-brand-fg disabled:opacity-50"
        >
          {loading ? '가입 중...' : '가입하기'}
        </button>

        <p className="text-center text-sm text-slate-500">
          이미 계정이 있으신가요?{' '}
          <Link to="/login" className="text-brand hover:underline">
            로그인
          </Link>
        </p>
      </form>
    </div>
  );
}
