import type { ReactNode } from 'react';
import type { UserRole } from '@sotong/shared';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/auth';

type NavigationIcon = 'inbox' | 'escalations' | 'dashboard' | 'file' | 'compose' | 'teachers';

interface NavigationItem {
  to: string;
  label: string;
  description: string;
  icon: NavigationIcon;
}

interface WorkspaceStyle {
  name: string;
  sidebarClass: string;
  brandClass: string;
  activeClass: string;
  mobileActiveClass: string;
}

const navigationByRole: Record<UserRole, NavigationItem[]> = {
  parent: [
    { to: '/parent', label: '내 민원', description: '처리 상황 확인', icon: 'file' },
    { to: '/parent/new', label: '새 민원 접수', description: '문의 내용 전달', icon: 'compose' },
  ],
  teacher: [
    { to: '/inbox', label: '민원함', description: '배정 민원 확인', icon: 'inbox' },
  ],
  admin: [
    { to: '/dashboard', label: '대시보드', description: '학교 민원 통계', icon: 'dashboard' },
    { to: '/inbox', label: '전체 민원', description: '접수 현황 관리', icon: 'inbox' },
    { to: '/teachers', label: '교사 배정', description: '담당 학년·반 지정', icon: 'teachers' },
    { to: '/escalations', label: '이관 관리', description: 'MDT 요청 확인', icon: 'escalations' },
  ],
  mdt: [
    { to: '/escalations', label: '이관 업무', description: '요청 접수·처리', icon: 'escalations' },
    { to: '/inbox', label: '검토 민원', description: '민원 내용 확인', icon: 'inbox' },
    { to: '/dashboard', label: '현황 통계', description: '유형별 현황 확인', icon: 'dashboard' },
  ],
};

const workspaceByRole: Record<UserRole, WorkspaceStyle> = {
  parent: {
    name: '학부모 민원 안내',
    sidebarClass: 'bg-emerald-950',
    brandClass: 'bg-emerald-500',
    activeClass: 'bg-emerald-600',
    mobileActiveClass: 'bg-emerald-600 text-white',
  },
  teacher: {
    name: '교사 민원 지원',
    sidebarClass: 'bg-slate-950',
    brandClass: 'bg-blue-600',
    activeClass: 'bg-blue-600',
    mobileActiveClass: 'bg-blue-600 text-white',
  },
  admin: {
    name: '학교 관리자 콘솔',
    sidebarClass: 'bg-slate-950',
    brandClass: 'bg-indigo-500',
    activeClass: 'bg-indigo-600',
    mobileActiveClass: 'bg-indigo-600 text-white',
  },
  mdt: {
    name: '민원대응팀 업무공간',
    sidebarClass: 'bg-violet-950',
    brandClass: 'bg-violet-500',
    activeClass: 'bg-violet-600',
    mobileActiveClass: 'bg-violet-600 text-white',
  },
};

const roleLabel: Record<UserRole, string> = {
  teacher: '교사',
  parent: '학부모',
  admin: '관리자',
  mdt: '민원대응팀',
};

export function Layout() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const role = user?.role ?? 'teacher';
  const navigation = navigationByRole[role];
  const workspace = workspaceByRole[role];
  const backgroundClass = role === 'parent' ? 'bg-emerald-50/40' : 'bg-slate-50';

  function handleLogout() {
    logout();
    navigate('/login');
  }

  return (
    <div className={`min-h-screen lg:grid lg:grid-cols-[264px_minmax(0,1fr)] ${backgroundClass}`}>
      <aside
        className={`hidden border-r border-white/10 text-white lg:flex lg:min-h-screen lg:flex-col ${workspace.sidebarClass}`}
      >
        <Brand workspace={workspace} />

        <nav className="flex-1 space-y-1 px-3 py-6" aria-label={`${roleLabel[role]} 주요 메뉴`}>
          {navigation.map((item) => (
            <NavigationLink key={item.to} item={item} workspace={workspace} />
          ))}
        </nav>

        <div className="border-t border-white/10 p-4">
          <UserSummary name={user?.name} role={user?.role} />
          <button
            type="button"
            onClick={handleLogout}
            className="mt-3 flex w-full items-center justify-center rounded-lg border border-white/10 px-3 py-2 text-sm font-medium text-slate-300 transition hover:border-white/20 hover:bg-white/5 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/50"
          >
            로그아웃
          </button>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur lg:hidden">
          <div className="flex h-16 items-center justify-between px-4">
            <Brand compact workspace={workspace} />
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
            >
              로그아웃
            </button>
          </div>
          <nav className="flex gap-1 overflow-x-auto px-3 pb-3" aria-label={`${roleLabel[role]} 주요 메뉴`}>
            {navigation.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/parent'}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-lg px-3 py-2 text-sm font-semibold transition ${
                    isActive ? workspace.mobileActiveClass : 'text-slate-500 hover:bg-slate-100'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="mx-auto w-full max-w-7xl px-4 py-7 sm:px-6 sm:py-9 lg:px-10 lg:py-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

function Brand({ workspace, compact = false }: { workspace: WorkspaceStyle; compact?: boolean }) {
  return (
    <div className={compact ? 'flex items-center gap-2.5' : 'flex h-20 items-center gap-3 px-5'}>
      <span
        className={`flex size-9 items-center justify-center rounded-xl text-white shadow-lg shadow-black/15 ${workspace.brandClass}`}
      >
        <svg viewBox="0 0 24 24" fill="none" className="size-5" aria-hidden="true">
          <path
            d="M7.5 17.5 4 20v-4.6A7.5 7.5 0 0 1 3 11.7C3 7.45 7.03 4 12 4s9 3.45 9 7.7-4.03 7.7-9 7.7c-1.65 0-3.2-.38-4.5-1.04"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path d="M8 11h8M8 14h5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        </svg>
      </span>
      <div>
        <p className={`font-bold tracking-tight ${compact ? 'text-slate-950' : 'text-white'}`}>소통해요</p>
        <p className={`text-xs ${compact ? 'text-slate-500' : 'text-slate-400'}`}>{workspace.name}</p>
      </div>
    </div>
  );
}

function NavigationLink({ item, workspace }: { item: NavigationItem; workspace: WorkspaceStyle }) {
  return (
    <NavLink
      to={item.to}
      end={item.to === '/parent'}
      className={({ isActive }) =>
        `group flex items-center gap-3 rounded-xl px-3 py-3 transition ${
          isActive ? `${workspace.activeClass} text-white shadow-lg shadow-black/15` : 'text-slate-400 hover:bg-white/5 hover:text-white'
        }`
      }
    >
      {({ isActive }) => (
        <>
          <span
            className={`flex size-9 shrink-0 items-center justify-center rounded-lg ${
              isActive ? 'bg-white/15' : 'bg-white/5 group-hover:bg-white/10'
            }`}
          >
            <NavIcon name={item.icon} />
          </span>
          <span>
            <span className="block text-sm font-semibold">{item.label}</span>
            <span className={`block text-xs ${isActive ? 'text-white/75' : 'text-slate-500'}`}>
              {item.description}
            </span>
          </span>
        </>
      )}
    </NavLink>
  );
}

function UserSummary({ name, role }: { name?: string; role?: UserRole }) {
  const initial = name?.trim().charAt(0) || '사';

  return (
    <div className="flex items-center gap-3">
      <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-white/10 text-sm font-bold text-white">
        {initial}
      </span>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-white">{name ?? '사용자'}</p>
        <p className="text-xs text-slate-400">{role ? roleLabel[role] : '사용자'}</p>
      </div>
    </div>
  );
}

function NavIcon({ name }: { name: NavigationIcon }) {
  const paths: Record<NavigationIcon, ReactNode> = {
    inbox: (
      <>
        <path d="M4 5.5h16v13H4z" />
        <path d="M4 14h4l1.5 2h5L16 14h4" />
      </>
    ),
    escalations: (
      <>
        <path d="M5 19V5h8" />
        <path d="m11 9 4-4 4 4M15 5v9" />
      </>
    ),
    dashboard: <path d="M4 13h6v7H4zM14 4h6v16h-6zM4 4h6v5H4z" />,
    file: (
      <>
        <path d="M6 3.5h8l4 4V20H6z" />
        <path d="M14 3.5V8h4M9 12h6M9 15.5h4" />
      </>
    ),
    compose: (
      <>
        <path d="M5 19h4L19 9l-4-4L5 15v4Z" />
        <path d="m13.5 6.5 4 4M5 21h14" />
      </>
    ),
    teachers: (
      <>
        <circle cx="9" cy="8" r="3.2" />
        <path d="M3.5 19c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5" />
        <path d="M16 11.5l1.8 1.8 3.2-3.6" />
      </>
    ),
  };

  return (
    <svg viewBox="0 0 24 24" fill="none" className="size-5" aria-hidden="true">
      <g stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        {paths[name]}
      </g>
    </svg>
  );
}
