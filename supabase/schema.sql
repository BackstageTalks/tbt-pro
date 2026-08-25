-- BlinQ Supabase schema. Versioned in GitHub; deploy later through Supabase SQL Editor.
create table if not exists public.blinq_access (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  role text not null default 'USER' check (role in ('USER','ADMIN')),
  plan_code text not null default 'FREE' check (plan_code in ('FREE','MANUAL','PRO','PRO_PLUS','ADMIN')),
  access_status text not null default 'ACTIVE' check (access_status in ('ACTIVE','EXPIRED','BLOCKED')),
  credits_granted integer not null default 10 check (credits_granted >= 0),
  credits_used integer not null default 0 check (credits_used >= 0 and credits_used <= credits_granted),
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_login_at timestamptz
);

create index if not exists blinq_access_email_idx on public.blinq_access (lower(email));
create index if not exists blinq_access_status_idx on public.blinq_access (access_status, expires_at);

alter table public.blinq_access enable row level security;
revoke all on public.blinq_access from anon, authenticated;

create or replace function public.create_blinq_access_for_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.blinq_access (user_id, email, role, plan_code, access_status, credits_granted, credits_used)
  values (new.id, lower(coalesce(new.email, '')), 'USER', 'FREE', 'ACTIVE', 10, 0)
  on conflict (user_id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created_blinq_access on auth.users;
create trigger on_auth_user_created_blinq_access
after insert on auth.users
for each row execute function public.create_blinq_access_for_new_user();

create or replace function public.consume_blinq_credit(p_user_id uuid)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare touched integer;
begin
  update public.blinq_access
     set credits_used = credits_used + 1, updated_at = now()
   where user_id = p_user_id
     and role <> 'ADMIN'
     and plan_code in ('FREE','MANUAL')
     and access_status = 'ACTIVE'
     and (expires_at is null or expires_at > now())
     and credits_used < credits_granted;
  get diagnostics touched = row_count;
  return touched = 1;
end;
$$;

revoke all on function public.consume_blinq_credit(uuid) from public, anon, authenticated;
grant execute on function public.consume_blinq_credit(uuid) to service_role;
