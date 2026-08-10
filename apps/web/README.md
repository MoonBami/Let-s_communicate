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
├─ components/        # Layout(역할별 네비) · RequireAuth(roles 지원)
└─ pages/
   ├─ LoginPage             # 교사·관리자 로그인
   ├─ SignupPage            # 교사·관리자 회원가입
   ├─ ParentComplaintPage   # 학부모 민원 접수 (F1 진입점)
   ├─ TeacherInboxPage      # 교사 민원함 (필터 통과분)
   ├─ ComplaintDetailPage   # 민원 상세 — F1·F2 분석 / F5 유사사례 / F4 초안 / F8 이관
   ├─ EscalationsPage       # F8 이관 관리 (admin·mdt)
   └─ AdminDashboardPage    # F9 통계 대시보드 (Recharts, admin·mdt)
```

## 규칙

- 도메인 타입·ENUM·API 경로는 `@sotong/shared`에서 가져다 쓸 것 (중복 정의 금지).
- 서버 상태는 TanStack Query, 클라이언트 전역 상태는 Zustand.
- 폼은 React Hook Form + Zod.
- 화면 접근 제어는 `RequireAuth roles={...}` 로 두고, **백엔드 권한 가드와 같은 기준**을
  쓴다. 프론트 가드는 UX용이고 실제 통제는 백엔드(`require_roles`)가 한다.

## 역할별 시작 화면

| 역할 | 시작 화면 | 주요 노출 정보 |
|------|-----------|----------------|
| `parent` | `/parent` | 본인이 접수한 민원의 처리 단계·최근 변경 |
| `teacher` | `/inbox` | 본인에게 배정된 민원·AI 분석·답변 지원 |
| `admin` | `/dashboard` | 학교 민원 통계·전체 민원·이관 관리 |
| `mdt` | `/escalations` | 이관 요청 처리·검토 민원·현황 통계 |

학부모 화면은 직원용 `ComplaintDetailPage`를 재사용하지 않는다. 위험도, AI 분석,
유사 사례, 답변 초안, 내부 이관 사유는 학부모에게 노출하지 않는다.

### 학부모 내 민원 API 연결 계약

프론트 화면은 아래 전용 경로를 사용한다. 백엔드는 반드시 현재 로그인 사용자의
`parent_id` 소유권을 확인한 결과만 반환해야 한다.

| 메서드·경로 | 용도 |
|-------------|------|
| `GET /api/parent/complaints` | 본인 민원 페이지 목록 |
| `GET /api/parent/complaints/{id}` | 본인 민원 상세·처리 상태 |

응답 필드는 `id`, `title`, `body`, `category`, `status`, `createdAt`, `updatedAt`,
`closedAt`만 사용한다. 인증 상태에서 민원을 접수하면 서버가 요청 본문이 아닌 현재
사용자를 기준으로 `parent_id`를 설정해야 한다. API가 연결되기 전에는 학부모 화면이
가짜 민원을 표시하지 않고 연결 준비 상태를 보여준다.
