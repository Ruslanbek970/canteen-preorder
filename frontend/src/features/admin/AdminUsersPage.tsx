import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { apiGet, apiPatch, apiPost, qs } from '@/api/client';
import type { AdminUser, AdminUserList, Role } from '@/api/types';
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
  Select,
} from '@/components/ui';
import { useErrorMessage } from '@/components/ui/errors';

import { ADMIN_KEY, useAdminCanteens, useAdminGroups } from './api';
import { AdminShell } from './AdminShell';

const ROLES: Role[] = ['student', 'teacher', 'cook', 'cashier', 'canteen_manager', 'admin'];
const STAFF: Role[] = ['cook', 'cashier', 'canteen_manager'];
const PAGE = 50;
const USERS_KEY = [...ADMIN_KEY, 'users'] as const;

export function AdminUsersPage() {
  const { t } = useTranslation();
  const [q, setQ] = useState('');
  const [role, setRole] = useState<Role | ''>('');
  const [offset, setOffset] = useState(0);
  const [creating, setCreating] = useState(false);
  const query = useQuery({
    queryKey: [...USERS_KEY, q, role, offset],
    queryFn: () =>
      apiGet<AdminUserList>(`/admin/users${qs({ q: q.trim(), role, limit: PAGE, offset })}`),
    placeholderData: keepPreviousData,
  });
  return (
    <AdminShell title={t('admin.users.title')}>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Field label={t('admin.users.search')}>
          <Input
            type="search"
            value={q}
            placeholder={t('admin.users.searchHint')}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
          />
        </Field>
        <Field label={t('admin.users.role')}>
          <Select
            value={role}
            onChange={(e) => {
              setRole(e.target.value as Role | '');
              setOffset(0);
            }}
          >
            <option value="">{t('admin.users.allRoles')}</option>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {t(`roles.${r}`)}
              </option>
            ))}
          </Select>
        </Field>
        <Button variant="secondary" onClick={() => setCreating((v) => !v)}>
          {t('admin.users.add')}
        </Button>
      </div>
      {creating && <CreateUser onDone={() => setCreating(false)} />}
      {query.isPending ? (
        <LoadingState />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : query.data.items.length === 0 ? (
        <EmptyState>{t('admin.users.empty')}</EmptyState>
      ) : (
        <>
          <p className="mb-2 text-sm text-slate-500">
            {t('admin.users.total', { count: query.data.total })}
          </p>
          <ul className="space-y-2">
            {query.data.items.map((user) => (
              <UserRow key={`${user.id}-${user.role}-${user.is_active}`} user={user} />
            ))}
          </ul>
          {query.data.total > PAGE && (
            <div className="mt-4 flex items-center gap-2">
              <Button
                variant="secondary"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE))}
              >
                {t('admin.users.prev')}
              </Button>
              <span className="text-sm text-slate-500">
                {offset + 1}–{Math.min(offset + PAGE, query.data.total)}
              </span>
              <Button
                variant="secondary"
                disabled={offset + PAGE >= query.data.total}
                onClick={() => setOffset(offset + PAGE)}
              >
                {t('admin.users.next')}
              </Button>
            </div>
          )}
        </>
      )}
    </AdminShell>
  );
}

interface LinkFields {
  role: Role;
  canteen_id: string;
  group_id: string;
}

/** Role with the canteen (staff) or group (student) it needs. */
function RoleFields({ value, onChange }: { value: LinkFields; onChange: (v: LinkFields) => void }) {
  const { t } = useTranslation();
  const canteens = useAdminCanteens();
  const groups = useAdminGroups();
  return (
    <>
      <Field label={t('admin.users.role')}>
        <Select
          value={value.role}
          onChange={(e) => onChange({ ...value, role: e.target.value as Role })}
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {t(`roles.${r}`)}
            </option>
          ))}
        </Select>
      </Field>
      {STAFF.includes(value.role) && (
        <Field label={t('admin.users.canteen')}>
          <Select
            value={value.canteen_id}
            onChange={(e) => onChange({ ...value, canteen_id: e.target.value })}
          >
            <option value="">—</option>
            {canteens.data?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>
      )}
      {value.role === 'student' && (
        <Field label={t('auth.group')}>
          <Select
            value={value.group_id}
            onChange={(e) => onChange({ ...value, group_id: e.target.value })}
          >
            <option value="">—</option>
            {groups.data?.map((g) => (
              <option key={g.id} value={g.id}>
                {g.code}
              </option>
            ))}
          </Select>
        </Field>
      )}
    </>
  );
}

const toId = (value: string) => (value ? Number(value) : null);

function UserRow({ user }: { user: AdminUser }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const [open, setOpen] = useState(false);
  const [links, setLinks] = useState<LinkFields>({
    role: user.role,
    canteen_id: user.canteen_id ? String(user.canteen_id) : '',
    group_id: user.group_id ? String(user.group_id) : '',
  });
  const [password, setPassword] = useState('');
  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiPatch<AdminUser>(`/admin/users/${user.id}`, body),
    onSuccess: () => {
      setPassword('');
      void client.invalidateQueries({ queryKey: USERS_KEY });
    },
  });
  const where = user.canteen_name ?? user.group_code;
  return (
    <li>
      <Card className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="font-medium">
              {user.full_name}{' '}
              {!user.is_active && <Badge tone="red">{t('admin.users.blocked')}</Badge>}
            </p>
            <p className="truncate text-sm text-slate-500">
              {user.email} · {t(`roles.${user.role}`)}
              {where ? ` · ${where}` : ''}
            </p>
          </div>
          <Button variant="ghost" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
            {open ? t('common.close') : t('admin.users.edit')}
          </Button>
        </div>
        {open && (
          <div className="grid gap-3 border-t border-slate-200 pt-3 sm:grid-cols-2 dark:border-slate-800">
            {save.isError && (
              <div className="sm:col-span-2">
                <Alert>{errorMessage(save.error)}</Alert>
              </div>
            )}
            {save.isSuccess && (
              <div className="sm:col-span-2">
                <Alert tone="success">{t('common.saved')}</Alert>
              </div>
            )}
            <RoleFields value={links} onChange={setLinks} />
            <Field label={t('admin.users.newPassword')} hint={t('admin.users.passwordHint')}>
              <Input
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            <div className="flex flex-wrap gap-2 sm:col-span-2">
              <Button
                disabled={save.isPending}
                onClick={() =>
                  save.mutate({
                    role: links.role,
                    canteen_id: toId(links.canteen_id),
                    group_id: toId(links.group_id),
                    ...(password ? { password } : {}),
                  })
                }
              >
                {t('common.save')}
              </Button>
              <Button
                variant={user.is_active ? 'danger' : 'secondary'}
                disabled={save.isPending}
                onClick={() => save.mutate({ is_active: !user.is_active })}
              >
                {user.is_active ? t('admin.users.block') : t('admin.users.unblock')}
              </Button>
            </div>
          </div>
        )}
      </Card>
    </li>
  );
}

function CreateUser({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const errorMessage = useErrorMessage();
  const [form, setForm] = useState({ full_name: '', email: '', password: '' });
  const [links, setLinks] = useState<LinkFields>({ role: 'cook', canteen_id: '', group_id: '' });
  const create = useMutation({
    mutationFn: () =>
      apiPost<AdminUser>('/admin/users', {
        ...form,
        role: links.role,
        canteen_id: toId(links.canteen_id),
        group_id: toId(links.group_id),
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: USERS_KEY });
      onDone();
    },
  });
  return (
    <Card className="mb-4 grid gap-3 sm:grid-cols-2">
      <h2 className="font-semibold sm:col-span-2">{t('admin.users.addTitle')}</h2>
      {create.isError && (
        <div className="sm:col-span-2">
          <Alert>{errorMessage(create.error)}</Alert>
        </div>
      )}
      <Field label={t('auth.fullName')}>
        <Input
          value={form.full_name}
          onChange={(e) => setForm({ ...form, full_name: e.target.value })}
        />
      </Field>
      <Field label={t('auth.email')}>
        <Input
          type="email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
      </Field>
      <Field label={t('auth.password')} hint={t('auth.passwordHint')}>
        <Input
          type="password"
          autoComplete="new-password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />
      </Field>
      <RoleFields value={links} onChange={setLinks} />
      <div className="sm:col-span-2">
        <Button disabled={create.isPending} onClick={() => create.mutate()}>
          {t('admin.users.create')}
        </Button>
      </div>
    </Card>
  );
}
