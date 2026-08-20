-- Migración: sesiones persistentes (para que la sesión sobreviva a un refresh de la página).
-- Ejecutar solo si el proyecto ya existía antes de este cambio.

create table if not exists sessions (
    token text primary key,
    user_id integer not null references users(id) on delete cascade,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null
);

create index if not exists idx_sessions_user on sessions(user_id);
create index if not exists idx_sessions_expires on sessions(expires_at);
