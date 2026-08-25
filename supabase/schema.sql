-- Supabase SQL Editor: run once.
create table if not exists public.blinq_access (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  access_status text not null default 'FREE_ACTIVE' check (access_status in ('FREE_ACTIVE','PAYMENT_PENDING','PRO_ACTIVE','EXPIRED','DISABLED')),
  plan_code text not null default 'FREE_20',
  credits_granted integer not null default 20 check (credits_granted >= 0),
  credits_used integer not null default 0 check (credits_used >= 0),
  trial_used boolean not null default true,
  access_requested_at timestamptz,
  paid_at timestamptz,
  paid_until timestamptz,
  payment_reference text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.blinq_access enable row level security;
revoke all on public.blinq_access from anon, authenticated;

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
     and access_status = 'FREE_ACTIVE'
     and credits_used < credits_granted;
  get diagnostics touched = row_count;
  return touched = 1;
end;
$$;
revoke all on function public.consume_blinq_credit(uuid) from public, anon, authenticated;
grant execute on function public.consume_blinq_credit(uuid) to service_role;
