-- Migración: catálogo de queries de soporte para habilitar funciones/funcionalidades,
-- y vínculo desde las notas de tipo 'Query' de una funcionalidad hacia el query exacto.
-- Ejecutar en el SQL editor de Supabase, después de sql/schema.sql.

create table if not exists queries (
    id serial primary key,
    external_id integer,
    name text not null,
    description text,
    tags text,
    sql_text text not null,
    active boolean not null default true,
    created_by integer references users(id) on delete set null,
    updated_by integer references users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_queries_name on queries(name);

alter table notes add column if not exists query_id integer references queries(id) on delete set null;
create index if not exists idx_notes_query on notes(query_id);
