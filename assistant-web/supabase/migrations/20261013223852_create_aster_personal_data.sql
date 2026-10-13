create table public.user_profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text not null default '' check (char_length(display_name) <= 80),
  assistant_name text not null default 'Aster' check (char_length(assistant_name) between 1 and 40),
  about_me text not null default '' check (char_length(about_me) <= 6000),
  life_areas text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.life_entries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  kind text not null check (kind in ('task', 'goal', 'journal', 'memory')),
  title text not null check (char_length(title) between 1 and 180),
  content text not null default '' check (char_length(content) <= 12000),
  status text not null default 'open' check (status in ('open', 'in_progress', 'done', 'archived')),
  priority text not null default 'normal' check (priority in ('low', 'normal', 'high')),
  due_at timestamptz,
  tags text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index life_entries_user_created_idx on public.life_entries (user_id, created_at desc);
create index life_entries_user_due_idx on public.life_entries (user_id, due_at) where due_at is not null;

create table public.assistant_conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  title text not null default 'New conversation' check (char_length(title) between 1 and 180),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, user_id)
);

create table public.assistant_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null,
  user_id uuid not null references auth.users (id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null check (char_length(content) between 1 and 20000),
  created_at timestamptz not null default now(),
  foreign key (conversation_id, user_id)
    references public.assistant_conversations (id, user_id) on delete cascade
);

create index assistant_conversations_user_updated_idx on public.assistant_conversations (user_id, updated_at desc);
create index assistant_messages_conversation_created_idx on public.assistant_messages (conversation_id, created_at);

alter table public.user_profiles enable row level security;
alter table public.life_entries enable row level security;
alter table public.assistant_conversations enable row level security;
alter table public.assistant_messages enable row level security;

grant select, insert, update, delete on public.user_profiles to authenticated;
grant select, insert, update, delete on public.life_entries to authenticated;
grant select, insert, update, delete on public.assistant_conversations to authenticated;
grant select, insert, update, delete on public.assistant_messages to authenticated;

create policy "profiles_read_own" on public.user_profiles for select to authenticated using ((select auth.uid()) = id);
create policy "profiles_insert_own" on public.user_profiles for insert to authenticated with check ((select auth.uid()) = id);
create policy "profiles_update_own" on public.user_profiles for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);
create policy "profiles_delete_own" on public.user_profiles for delete to authenticated using ((select auth.uid()) = id);

create policy "life_entries_read_own" on public.life_entries for select to authenticated using ((select auth.uid()) = user_id);
create policy "life_entries_insert_own" on public.life_entries for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "life_entries_update_own" on public.life_entries for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "life_entries_delete_own" on public.life_entries for delete to authenticated using ((select auth.uid()) = user_id);

create policy "conversations_read_own" on public.assistant_conversations for select to authenticated using ((select auth.uid()) = user_id);
create policy "conversations_insert_own" on public.assistant_conversations for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "conversations_update_own" on public.assistant_conversations for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "conversations_delete_own" on public.assistant_conversations for delete to authenticated using ((select auth.uid()) = user_id);

create policy "messages_read_own" on public.assistant_messages for select to authenticated using ((select auth.uid()) = user_id);
create policy "messages_insert_own" on public.assistant_messages for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "messages_update_own" on public.assistant_messages for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "messages_delete_own" on public.assistant_messages for delete to authenticated using ((select auth.uid()) = user_id);
