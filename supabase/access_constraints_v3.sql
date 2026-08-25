-- BlinQ access migration v3
-- Aligns an older blinq_access table with the current FREE_10 / PRO model.

alter table public.blinq_access add column if not exists role text not null default 'USER';
alter table public.blinq_access add column if not exists access_status text not null default 'FREE_ACTIVE';
alter table public.blinq_access add column if not exists plan_code text not null default 'FREE_10';
alter table public.blinq_access add column if not exists credits_granted integer not null default 10;
alter table public.blinq_access add column if not exists credits_used integer not null default 0;
alter table public.blinq_access add column if not exists paid_at timestamptz;
alter table public.blinq_access add column if not exists paid_until timestamptz;
alter table public.blinq_access add column if not exists payment_reference text;
alter table public.blinq_access add column if not exists created_at timestamptz not null default now();
alter table public.blinq_access add column if not exists updated_at timestamptz not null default now();

-- Normalize legacy values before adding the current constraints.
update public.blinq_access
set role = case when upper(coalesce(role, 'USER')) = 'ADMIN' then 'ADMIN' else 'USER' end,
    access_status = case
      when upper(coalesce(access_status, '')) in ('ADMIN') then 'ADMIN'
      when upper(coalesce(access_status, '')) in ('PRO_ACTIVE', 'PRO') then 'PRO_ACTIVE'
      when upper(coalesce(access_status, '')) in ('PRO_PLUS_ACTIVE', 'PRO_PLUS') then 'PRO_PLUS_ACTIVE'
      when upper(coalesce(access_status, '')) in ('BLOCKED', 'DISABLED') then 'BLOCKED'
      when upper(coalesce(access_status, '')) = 'PAYMENT_PENDING' then 'PAYMENT_PENDING'
      when upper(coalesce(access_status, '')) in ('INACTIVE', 'EXPIRED') then 'INACTIVE'
      else 'FREE_ACTIVE'
    end,
    plan_code = case
      when upper(coalesce(plan_code, '')) in ('PRO_PLUS', 'PRO_PLUS_90D') then 'PRO_PLUS_90D'
      when upper(coalesce(plan_code, '')) in ('PRO', 'PRO_30D') then 'PRO_30D'
      when upper(coalesce(plan_code, '')) = 'ADMIN' then 'ADMIN'
      else 'FREE_10'
    end,
    credits_granted = greatest(coalesce(credits_granted, 10), 0),
    credits_used = greatest(coalesce(credits_used, 0), 0),
    updated_at = now();

-- Remove legacy CHECK constraints whose allowed values conflict with the current model.
do $$
declare constraint_row record;
begin
  for constraint_row in
    select conname
    from pg_constraint
    where conrelid = 'public.blinq_access'::regclass
      and contype = 'c'
  loop
    execute format('alter table public.blinq_access drop constraint %I', constraint_row.conname);
  end loop;
end $$;

alter table public.blinq_access
  add constraint blinq_access_role_check
    check (role in ('USER', 'ADMIN')),
  add constraint blinq_access_status_check
    check (access_status in ('FREE_ACTIVE','PRO_ACTIVE','PRO_PLUS_ACTIVE','PAYMENT_PENDING','INACTIVE','BLOCKED','ADMIN')),
  add constraint blinq_access_plan_check
    check (plan_code in ('FREE_10','PRO_30D','PRO_PLUS_90D','ADMIN')),
  add constraint blinq_access_credits_granted_check
    check (credits_granted >= 0),
  add constraint blinq_access_credits_used_check
    check (credits_used >= 0);

create or replace function public.handle_new_blinq_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.blinq_access (
    user_id, email, role, access_status, plan_code,
    credits_granted, credits_used
  ) values (
    new.id, lower(coalesce(new.email, '')), 'USER',
    'FREE_ACTIVE', 'FREE_10', 10, 0
  )
  on conflict (user_id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created_blinq on auth.users;
create trigger on_auth_user_created_blinq
after insert on auth.users
for each row execute procedure public.handle_new_blinq_user();

create or replace function public.consume_blinq_credit(p_user_id uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare changed integer;
begin
  update public.blinq_access
     set credits_used = credits_used + 1,
         updated_at = now()
   where user_id = p_user_id
     and access_status = 'FREE_ACTIVE'
     and credits_used < credits_granted;
  get diagnostics changed = row_count;
  return changed = 1;
end;
$$;

revoke all on function public.consume_blinq_credit(uuid)
  from public, anon, authenticated;
grant execute on function public.consume_blinq_credit(uuid)
  to service_role;
