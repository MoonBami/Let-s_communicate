import type { UserRole } from '@sotong/shared';

const homePathByRole: Record<UserRole, string> = {
  parent: '/parent',
  teacher: '/inbox',
  admin: '/dashboard',
  mdt: '/escalations',
};

export function getHomePath(role: UserRole): string {
  return homePathByRole[role];
}
