# @sotong/web — 반응형 웹

교사·학부모·관리자를 하나로 커버하는 반응형 웹 (Vite + React + TS).

## 실행

```bash
# 루트에서 (workspaces 전체 설치)
npm install
npm run dev:web        # → http://localhost:5173

# 또는 이 디렉터리에서
npm run dev
npm run build          # tsc --noEmit + vite build
npm run typecheck
```

`/api` 요청은 `vite.config.ts`의 프록시로 `http://localhost:8000`(FastAPI)에 전달됩니다.

## 구조

```
src/
├─ main.tsx           # 엔트리 (Router + QueryClient)
├─ routes.tsx         # 라우트 정의
├─ lib/
│  ├─ api.ts          # axios 인스턴스 (JWT 자동 첨부, 401 처리)
│  └─ queryClient.ts  # TanStack Query 설정
├─ store/auth.ts      # Zustand 인증 상태 (persist)
├─ components/        # Layout · RequireAuth
└─ pages/
   ├─ LoginPage             # 교사·관리자 로그인
   ├─ ParentComplaintPage   # 학부모 민원 접수 (F1 진입점)
   ├─ TeacherInboxPage      # 교사 민원함 (필터 통과분)
   └─ AdminDashboardPage    # F9 통계 대시보드 (Recharts)
```

## 규칙

- 도메인 타입·ENUM·API 경로는 `@sotong/shared`에서 가져다 쓸 것 (중복 정의 금지).
- 서버 상태는 TanStack Query, 클라이언트 전역 상태는 Zustand.
- 폼은 React Hook Form + Zod.
