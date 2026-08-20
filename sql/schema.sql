-- Esquema de base de datos para la Documentación CSS (Q10)
-- Ejecutar completo en el SQL editor de Supabase (proyecto nuevo).

create table if not exists users (
    id serial primary key,
    email text not null unique,
    name text not null,
    password_hash text not null,
    role text not null check (role in ('admin', 'editor', 'lector')),
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists modules (
    id serial primary key,
    name text not null unique,
    description text
);

create table if not exists plans (
    id serial primary key,
    name text not null unique,
    description text
);

create table if not exists types (
    id serial primary key,
    name text not null unique,
    description text
);

create table if not exists functionalities (
    id serial primary key,
    name text not null,
    description text,
    module_id integer references modules(id) on delete set null,
    type_id integer references types(id) on delete set null,
    request_type text,
    activation_notes text,
    status text not null default 'activo',
    created_by integer references users(id) on delete set null,
    updated_by integer references users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists functionality_plans (
    functionality_id integer not null references functionalities(id) on delete cascade,
    plan_id integer not null references plans(id) on delete cascade,
    primary key (functionality_id, plan_id)
);

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

create table if not exists notes (
    id serial primary key,
    functionality_id integer not null references functionalities(id) on delete cascade,
    note_text text not null,
    note_type text,
    query_id integer references queries(id) on delete set null,
    created_by integer references users(id) on delete set null,
    created_at timestamptz not null default now()
);

create table if not exists custom_developments (
    id serial primary key,
    name text not null,
    client text,
    description text,
    module_id integer references modules(id) on delete set null,
    related_functionality_id integer references functionalities(id) on delete set null,
    status text not null default 'solicitado',
    requested_by text,
    developed_by text,
    request_date date,
    delivery_date date,
    notes text,
    created_by integer references users(id) on delete set null,
    updated_by integer references users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists dimensions (
    id serial primary key,
    name text not null,
    module_id integer references modules(id) on delete set null,
    description text,
    data_type text,
    example_values text,
    created_by integer references users(id) on delete set null,
    updated_by integer references users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Mapa de dependencias entre APIs: un "recurso" agrupa varias operaciones (apis),
-- cada operación tiene una categoría (modelo/submodelo) y puede depender de otro
-- recurso a través de un parámetro (api_connections).
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

create table if not exists api_categories (
    id serial primary key,
    top_category text not null,
    sub_category text not null,
    color text not null,
    unique (top_category, sub_category)
);

create table if not exists apis (
    id serial primary key,
    name text not null,
    method text,
    endpoint text,
    module_id integer references modules(id) on delete set null,
    description text,
    auth_type text,
    version text,
    status text not null default 'activo',
    resource_id integer references api_resources(id) on delete cascade,
    category_id integer references api_categories(id) on delete set null,
    requires_list_of_id integer references apis(id) on delete set null,
    created_by integer references users(id) on delete set null,
    updated_by integer references users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists api_connections (
    id serial primary key,
    api_id integer not null references apis(id) on delete cascade,
    connected_api_id integer references apis(id) on delete cascade,
    target_resource_id integer references api_resources(id) on delete cascade,
    param_name text,
    relationship_description text,
    check (api_id <> connected_api_id),
    check (connected_api_id is not null or target_resource_id is not null)
);

create index if not exists idx_functionalities_module on functionalities(module_id);
create index if not exists idx_functionalities_type on functionalities(type_id);
create index if not exists idx_notes_functionality on notes(functionality_id);
create index if not exists idx_notes_query on notes(query_id);
create index if not exists idx_queries_name on queries(name);
create index if not exists idx_custom_dev_module on custom_developments(module_id);
create index if not exists idx_dimensions_module on dimensions(module_id);
create index if not exists idx_apis_module on apis(module_id);
create index if not exists idx_apis_resource on apis(resource_id);
create index if not exists idx_apis_category on apis(category_id);
create index if not exists idx_apis_requires on apis(requires_list_of_id);
create index if not exists idx_api_connections_api on api_connections(api_id);
create index if not exists idx_api_connections_connected on api_connections(connected_api_id);
create index if not exists idx_api_connections_target_resource on api_connections(target_resource_id);

-- No se sembran módulos/planes/tipos: se gestionan desde la página de Administración
-- una vez que exista el primer usuario admin (ver README para el bootstrap del admin).
