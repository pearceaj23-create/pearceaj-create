alter table public.user_profiles
  add column support_style text not null default ''
  check (char_length(support_style) <= 2000);

alter table public.life_entries
  drop constraint life_entries_kind_check;
alter table public.life_entries
  add constraint life_entries_kind_allowed_check
  check (kind in ('task', 'goal', 'journal', 'memory', 'thought', 'dream', 'project', 'habit'));

create table public.money_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  label text not null check (char_length(label) between 1 and 160),
  direction text not null check (direction in ('income', 'expense')),
  amount numeric(12, 2) not null check (amount > 0),
  frequency text not null default 'monthly'
    check (frequency in ('weekly', 'biweekly', 'monthly', 'quarterly', 'yearly', 'once')),
  category text not null default 'other' check (char_length(category) <= 60),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index money_items_user_created_idx on public.money_items (user_id, created_at desc);

alter table public.money_items enable row level security;
grant select, insert, update, delete on public.money_items to authenticated;

create policy "money_items_read_own" on public.money_items for select to authenticated using ((select auth.uid()) = user_id);
create policy "money_items_insert_own" on public.money_items for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "money_items_update_own" on public.money_items for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "money_items_delete_own" on public.money_items for delete to authenticated using ((select auth.uid()) = user_id);
