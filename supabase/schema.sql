-- Canonical BlinQ Supabase schema.
-- Safe, idempotent migration. Preserves users and existing credit balances.
begin;

create table if not exists public.blinq_access (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  role text not null default 'USER',
  access_status text not null default 'FREE_ACTIVE',
  plan_code text not null default 'FREE_10',
  credits_granted integer not null default 10,
  credits_used integer not null default 0,
  trial_used boolean not null default true,
  access_requested_at timestamptz,
  paid_at timestamptz,
  paid_until timestamptz,
  payment_reference text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.blinq_access add column if not exists role text default 'USER';
alter table public.blinq_access add column if not exists access_status text default 'FREE_ACTIVE';
alter table public.blinq_access add column if not exists plan_code text default 'FREE_10';
alter table public.blinq_access add column if not exists credits_granted integer default 10;
alter table public.blinq_access add column if not exists credits_used integer default 0;
alter table public.blinq_access add column if not exists trial_used boolean default true;
alter table public.blinq_access add column if not exists access_requested_at timestamptz;
alter table public.blinq_access add column if not exists paid_at timestamptz;
alter table public.blinq_access add column if not exists paid_until timestamptz;
alter table public.blinq_access add column if not exists payment_reference text;
alter table public.blinq_access add column if not exists created_at timestamptz default now();
alter table public.blinq_access add column if not exists updated_at timestamptz default now();

update public.blinq_access
set role = case when upper(coalesce(role, 'USER')) = 'ADMIN' then 'ADMIN' else 'USER' end,
    access_status = case
      when upper(coalesce(access_status, '')) in ('ADMIN') then 'ADMIN'
      when upper(coalesce(access_status, '')) in ('PRO_ACTIVE', 'PRO', 'MANUAL') then 'PRO_ACTIVE'
      when upper(coalesce(access_status, '')) in ('PRO_PLUS_ACTIVE', 'PRO_PLUS') then 'PRO_PLUS_ACTIVE'
      when upper(coalesce(access_status, '')) in ('PAYMENT_PENDING', 'PENDING') then 'PAYMENT_PENDING'
      when upper(coalesce(access_status, '')) in ('BLOCKED', 'DISABLED') then 'BLOCKED'
      when upper(coalesce(access_status, '')) in ('INACTIVE', 'EXPIRED') then 'INACTIVE'
      else 'FREE_ACTIVE'
    end,
    plan_code = case
      when upper(coalesce(plan_code, '')) in ('PRO_PLUS', 'PRO_PLUS_90D') then 'PRO_PLUS_90D'
      when upper(coalesce(plan_code, '')) in ('PRO', 'PRO_30D', 'MANUAL') then 'PRO_30D'
      when upper(coalesce(plan_code, '')) = 'ADMIN' then 'ADMIN'
      else 'FREE_10'
    end,
    email = coalesce(nullif(lower(email), ''), 'unknown-' || user_id::text || '@invalid.local'),
    credits_granted = greatest(coalesce(credits_granted, 10), coalesce(credits_used, 0), 0),
    credits_used = greatest(coalesce(credits_used, 0), 0),
    trial_used = coalesce(trial_used, true),
    created_at = coalesce(created_at, now()),
    updated_at = now();

alter table public.blinq_access alter column role set default 'USER';
alter table public.blinq_access alter column role set not null;
alter table public.blinq_access alter column access_status set default 'FREE_ACTIVE';
alter table public.blinq_access alter column access_status set not null;
alter table public.blinq_access alter column plan_code set default 'FREE_10';
alter table public.blinq_access alter column plan_code set not null;
alter table public.blinq_access alter column credits_granted set default 10;
alter table public.blinq_access alter column credits_granted set not null;
alter table public.blinq_access alter column credits_used set default 0;
alter table public.blinq_access alter column credits_used set not null;
alter table public.blinq_access alter column trial_used set default true;
alter table public.blinq_access alter column trial_used set not null;

-- Remove only CHECK constraints on the access table, then install the canonical set.
do $$
declare r record;
begin
  for r in
    select conname from pg_constraint
    where conrelid = 'public.blinq_access'::regclass and contype = 'c'
  loop
    execute format('alter table public.blinq_access drop constraint %I', r.conname);
  end loop;
end $$;

alter table public.blinq_access
  add constraint blinq_access_role_check check (role in ('USER','ADMIN')),
  add constraint blinq_access_status_check check (access_status in ('FREE_ACTIVE','PRO_ACTIVE','PRO_PLUS_ACTIVE','PAYMENT_PENDING','INACTIVE','BLOCKED','ADMIN')),
  add constraint blinq_access_plan_check check (plan_code in ('FREE_10','PRO_30D','PRO_PLUS_90D','ADMIN')),
  add constraint blinq_access_credits_check check (credits_granted >= 0 and credits_used >= 0 and credits_used <= credits_granted);

create index if not exists blinq_access_email_idx on public.blinq_access (lower(email));
create index if not exists blinq_access_status_idx on public.blinq_access (access_status, paid_until);

create table if not exists public.blinq_credit_ledger (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  delta integer not null,
  operation text not null,
  reason text,
  balance_after integer not null,
  created_at timestamptz not null default now(),
  constraint blinq_credit_ledger_operation_check check (operation in ('INITIAL_GRANT','ADMIN_ADD','PREDICTION_CONSUME','ADMIN_SET')),
  constraint blinq_credit_ledger_balance_check check (balance_after >= 0)
);
create index if not exists blinq_credit_ledger_user_idx on public.blinq_credit_ledger (user_id, created_at desc);

alter table public.blinq_access enable row level security;
alter table public.blinq_credit_ledger enable row level security;
revoke all on public.blinq_access from anon, authenticated;
revoke all on public.blinq_credit_ledger from anon, authenticated;
grant all on public.blinq_access to service_role;
grant all on public.blinq_credit_ledger to service_role;

create or replace function public.handle_new_blinq_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.blinq_access (user_id,email,role,access_status,plan_code,credits_granted,credits_used)
  values (new.id, lower(coalesce(new.email,'')), 'USER','FREE_ACTIVE','FREE_10',10,0)
  on conflict (user_id) do nothing;
  if found then
    insert into public.blinq_credit_ledger(user_id,delta,operation,reason,balance_after)
    values(new.id,10,'INITIAL_GRANT','New account',10);
  end if;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created_blinq_access on auth.users;
drop trigger if exists on_auth_user_created on auth.users;
drop trigger if exists on_auth_user_created_blinq on auth.users;
create trigger on_auth_user_created_blinq
after insert on auth.users for each row execute function public.handle_new_blinq_user();

-- Backfill users that existed before the trigger. Existing rows and balances are preserved.
insert into public.blinq_access(user_id,email,role,access_status,plan_code,credits_granted,credits_used)
select u.id, lower(coalesce(u.email,'')), 'USER','FREE_ACTIVE','FREE_10',10,0
from auth.users u
on conflict (user_id) do nothing;

create or replace function public.consume_blinq_credit(p_user_id uuid)
returns boolean language plpgsql security definer set search_path = public as $$
declare new_balance integer;
begin
  update public.blinq_access
     set credits_used = credits_used + 1, updated_at = now()
   where user_id = p_user_id
     and access_status = 'FREE_ACTIVE'
     and credits_used < credits_granted
  returning credits_granted - credits_used into new_balance;
  if not found then return false; end if;
  insert into public.blinq_credit_ledger(user_id,delta,operation,reason,balance_after)
  values(p_user_id,-1,'PREDICTION_CONSUME','Successful prediction',new_balance);
  return true;
end;
$$;

-- One-time addition. Example: 4 remaining + 30 becomes 34 and stays 34 until consumed.
create or replace function public.add_blinq_credits(p_user_id uuid, p_amount integer, p_reason text default null)
returns integer language plpgsql security definer set search_path = public as $$
declare new_balance integer;
begin
  if p_amount is null or p_amount <= 0 or p_amount > 100000 then
    raise exception 'p_amount must be between 1 and 100000';
  end if;
  update public.blinq_access
     set credits_granted = credits_granted + p_amount, updated_at = now()
   where user_id = p_user_id
  returning credits_granted - credits_used into new_balance;
  if not found then raise exception 'BlinQ user not found'; end if;
  insert into public.blinq_credit_ledger(user_id,delta,operation,reason,balance_after)
  values(p_user_id,p_amount,'ADMIN_ADD',nullif(trim(p_reason),''),new_balance);
  return new_balance;
end;
$$;

revoke all on function public.consume_blinq_credit(uuid) from public, anon, authenticated;
revoke all on function public.add_blinq_credits(uuid,integer,text) from public, anon, authenticated;
grant execute on function public.consume_blinq_credit(uuid) to service_role;
grant execute on function public.add_blinq_credits(uuid,integer,text) to service_role;

commit;
