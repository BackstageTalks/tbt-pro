-- Run in Supabase SQL Editor
create table if not exists public.blinq_access (
 user_id uuid primary key references auth.users(id) on delete cascade,
 email text not null,
 role text not null default 'USER' check (role in ('USER','ADMIN')),
 access_status text not null default 'FREE_ACTIVE' check (access_status in ('FREE_ACTIVE','PRO_ACTIVE','PRO_PLUS_ACTIVE','PAYMENT_PENDING','INACTIVE','BLOCKED','ADMIN')),
 plan_code text not null default 'FREE_10',
 credits_granted integer not null default 10 check (credits_granted>=0),
 credits_used integer not null default 0 check (credits_used>=0),
 paid_at timestamptz, paid_until timestamptz, payment_reference text,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
alter table public.blinq_access enable row level security;
revoke all on public.blinq_access from anon, authenticated;
create or replace function public.handle_new_blinq_user() returns trigger language plpgsql security definer set search_path=public as $$
begin
 insert into public.blinq_access(user_id,email,role,access_status,plan_code,credits_granted,credits_used)
 values(new.id,lower(coalesce(new.email,'')),'USER','FREE_ACTIVE','FREE_10',10,0)
 on conflict(user_id) do nothing;
 return new;
end; $$;
drop trigger if exists on_auth_user_created_blinq on auth.users;
create trigger on_auth_user_created_blinq after insert on auth.users for each row execute procedure public.handle_new_blinq_user();
create or replace function public.consume_blinq_credit(p_user_id uuid) returns boolean language plpgsql security definer set search_path=public as $$
declare changed integer;
begin
 update public.blinq_access set credits_used=credits_used+1,updated_at=now()
 where user_id=p_user_id and access_status='FREE_ACTIVE' and credits_used<credits_granted;
 get diagnostics changed=row_count; return changed=1;
end; $$;
revoke all on function public.consume_blinq_credit(uuid) from public,anon,authenticated;
grant execute on function public.consume_blinq_credit(uuid) to service_role;
