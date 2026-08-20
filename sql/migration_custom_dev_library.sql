-- Migración: biblioteca interna de desarrollos personalizados reutilizables (P/F/E)
-- y catálogo de personalizaciones numeradas por institución.
-- Ejecutar en el SQL editor de Supabase, después de sql/schema.sql.
-- No tiene relación con la tabla `custom_developments` (seguimiento de solicitudes por cliente).

create table if not exists custom_development_articles (
    id serial primary key,
    external_id integer,
    name text not null,
    description_html text not null,
    kind text not null,
    created_by integer references users(id) on delete set null,
    updated_by integer references users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_custom_development_articles_name on custom_development_articles(name);
create index if not exists idx_custom_development_articles_kind on custom_development_articles(kind);

create table if not exists personalizations (
    id serial primary key,
    external_id integer,
    name text not null,
    description text,
    institution text,
    created_by integer references users(id) on delete set null,
    updated_by integer references users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_personalizations_name on personalizations(name);
create index if not exists idx_personalizations_institution on personalizations(institution);
create index if not exists idx_personalizations_external_id on personalizations(external_id);
