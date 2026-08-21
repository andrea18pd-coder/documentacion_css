-- Migración: catálogo de sentencias SQL sueltas de uso frecuente, importadas en bloque desde
-- archivos .sql de trabajo diario (separados por comentarios tipo '-------- Título --------').
-- Ejecutar en el SQL editor de Supabase, después de sql/schema.sql.

create table if not exists sql_statements (
    id serial primary key,
    title text not null,
    sql_text text not null,
    source_file text,
    tags text,
    created_by integer references users(id) on delete set null,
    updated_by integer references users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_sql_statements_title on sql_statements(title);
create index if not exists idx_sql_statements_source_file on sql_statements(source_file);
