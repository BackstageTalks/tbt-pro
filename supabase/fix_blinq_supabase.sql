-- BlinQ Supabase repair
-- Fixes: "Database error saving new user" and schema mismatch.
-- Safe approach: remove the broken auth.users trigger and let the BlinQ API
-- create the access row after the user signs in for the first time.

begin;

-- Remove old trigger/function that referenced non-existent legacy columns.
drop trigger if exists on_auth_user_created_blinq_access on auth.users;
drop trigger if exists on_auth_user_created on auth.users;
drop function if exists public.create_blinq_access_for_new_user() cascade;

-- Keep the existing table, but ensure all columns required by the current API exist.
create table if not exists public.blinq_access (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  access_status text not null default 'FREE_ACTIVE',
  plan_code text not null default 'FREE_20',
  credits_granted integer not null default 20,
  credits_used integer not null default 0,
  trial_used boolean not null default true,
  access_requested_at timestamptz,
  paid_at timestamptz,
  paid_until timestamptz,
  payment_reference text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.blinq_access add column if not exists email text;
alter table public.blinq_access add column if not exists access_status text default 'FREE_ACTIVE';
alter table public.blinq_access add column if not exists plan_code text default 'FREE_20';
alter table public.blinq_access add column if not exists credits_granted integer default 20;
alter table public.blinq_access add column if not exists credits_used integer default 0;
alter table public.blinq_access add column if not exists trial_used boolean default true;
alter table public.blinq_access add column if not exists access_requested_at timestamptz;
alter table public.blinq_access add column if not exists paid_at timestamptz;
alter table public.blinq_access add column if not exists paid_until timestamptz;
alter table public.blinq_access add column if not exists payment_reference text;
alter table public.blinq_access add column if not exists created_at timestamptz default now();
alter table public.blinq_access add column if not exists updated_at timestamptz default now();

-- Normalize legacy values without deleting user data.
update public.blinq_access
set access_status = case upper(coalesce(access_status, ''))
  when 'ACTIVE' then 'FREE_ACTIVE'
  when 'FREE' then 'FREE_ACTIVE'
  when 'MANUAL' then 'PRO_ACTIVE'
  when 'ADMIN' then 'PRO_ACTIVE'
  when 'PENDING' then 'PAYMENT_PENDING'
  else upper(coalesce(nullif(access_status, ''), 'FREE_ACTIVE'))
end;

update public.blinq_access
set
  email = coalesce(nullif(email, ''), 'unknown-' || user_id::text || '@invalid.local'),
  plan_code = coalesce(nullif(plan_code, ''), 'FREE_20'),
  credits_granted = coalesce(credits_granted, 20),
  credits_used = coalesce(credits_used, 0),
  trial_used = coalesce(trial_used, true),
  created_at = coalesce(created_at, now()),
  updated_at = coalesce(updated_at, now());

alter table public.blinq_access alter column access_status set default 'FREE_ACTIVE';
alter table public.blinq_access alter column plan_code set default 'FREE_20';
alter table public.blinq_access alter column credits_granted set default 20;
alter table public.blinq_access alter column credits_used set default 0;
alter table public.blinq_access alter column trial_used set default true;

-- The browser must never modify access records directly.
alter table public.blinq_access enable row level security;
revoke all on public.blinq_access from anon, authenticated;

-- Atomic credit consumption used only by the server-side service role.
create or replace function public.consume_blinq_credit(p_user_id uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  touched integer;
begin
  update public.blinq_access
     set credits_used = credits_used + 1,
         updated_at = now()
   where user_id = p_user_id
     and access_status = 'FREE_ACTIVE'
     and credits_used < credits_granted;

  get diagnostics touched = row_count;
  return touched = 1;
end;
$$;

revoke all on function public.consume_blinq_credit(uuid) from public, anon, authenticated;
grant execute on function public.consume_blinq_credit(uuid) to service_role;

commit;
