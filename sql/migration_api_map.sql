-- Migración: mapa de dependencias entre APIs (recursos, categorías, parámetros)
-- Ejecutar en el SQL editor de Supabase, después de sql/schema.sql.

create table if not exists api_categories (
    id serial primary key,
    top_category text not null,
    sub_category text not null,
    color text not null,
    unique (top_category, sub_category)
);

create table if not exists api_resources (
    id serial primary key,
    slug text not null unique,
    name text not null,
    description text,
    created_by integer references users(id) on delete set null,
    updated_by integer references users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table apis add column if not exists resource_id integer references api_resources(id) on delete cascade;
alter table apis add column if not exists category_id integer references api_categories(id) on delete set null;
alter table apis add column if not exists requires_list_of_id integer references apis(id) on delete set null;

alter table api_connections alter column connected_api_id drop not null;
alter table api_connections add column if not exists target_resource_id integer references api_resources(id) on delete cascade;
alter table api_connections add column if not exists param_name text;

do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'api_connections_target_present'
    ) then
        alter table api_connections
            add constraint api_connections_target_present
            check (connected_api_id is not null or target_resource_id is not null);
    end if;
end $$;

create index if not exists idx_apis_resource on apis(resource_id);
create index if not exists idx_apis_category on apis(category_id);
create index if not exists idx_apis_requires on apis(requires_list_of_id);
create index if not exists idx_api_connections_target_resource on api_connections(target_resource_id);
