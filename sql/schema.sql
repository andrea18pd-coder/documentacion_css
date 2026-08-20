-- Esquema de base de datos para la Documentación CSS (Q10)
-- Ejecutar completo en el SQL editor de Supabase (proyecto nuevo).

-- Extensiones para el buscador global (similitud tolerante a tildes y errores de tipeo).
create extension if not exists pg_trgm;
create extension if not exists unaccent;

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

-- Biblioteca interna de desarrollos reutilizables (no confundir con `custom_developments`,
-- que es el seguimiento de solicitudes por cliente). Cada artículo trae una receta de
-- "cómo habilitar" una funcionalidad, o un procedimiento ante una eventualidad.
-- kind: 'Personalización' | 'Funcionalidad' | 'Eventualidad'
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

-- Catálogo de códigos de "Personalización: NNN" por institución, referenciados desde
-- notas de funcionalidades y desde los artículos de custom_development_articles.
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
create index if not exists idx_custom_development_articles_name on custom_development_articles(name);
create index if not exists idx_custom_development_articles_kind on custom_development_articles(kind);
create index if not exists idx_personalizations_name on personalizations(name);
create index if not exists idx_personalizations_institution on personalizations(institution);
create index if not exists idx_personalizations_external_id on personalizations(external_id);

-- Catálogo maestro real de Q10 (funciones, parámetros y funcionalidades de aplicación),
-- exportado directo del sistema. De solo lectura: respalda la búsqueda del Asistente cuando
-- algo existe en el sistema real pero no está documentado manualmente en activation_notes.
create table if not exists sys_functions (
    fun_codigo integer primary key,
    fun_nombre text not null,
    fun_controlador text,
    fun_accion text,
    fun_area text,
    fun_grupo text,
    fun_valores_ruta text,
    fun_menu boolean,
    fun_codigo_padre integer,
    fun_orden integer,
    fun_modal text,
    fun_descripcion text
);

create table if not exists sys_parameters (
    par_codigo integer primary key,
    par_nombre text not null,
    par_observaciones text,
    par_tipo_dato text,
    par_valor text,
    par_visible boolean,
    par_prerrequisito_par_codigo integer,
    par_prerrequisito_valor text,
    par_valores_lista text,
    par_valores_multiple text
);

create table if not exists sys_app_functionalities (
    funapl_codigo integer primary key,
    funapl_seccion text,
    funapl_categoria text,
    funapl_funcionalidad text not null,
    funapl_descripcion text,
    funapl_estado boolean,
    funapl_orden integer,
    funapl_padre integer,
    funcion_relacionada integer,
    orden integer
);

create index if not exists idx_sys_functions_nombre on sys_functions(fun_nombre);
create index if not exists idx_sys_parameters_nombre on sys_parameters(par_nombre);
create index if not exists idx_sys_app_functionalities_nombre on sys_app_functionalities(funapl_funcionalidad);

-- Anuncios / notas de proceso a tener en cuenta al ejecutar ciertos procesos (no confundir
-- con `notes`, que son consideraciones ligadas a una funcionalidad puntual).
create table if not exists process_notes (
    id serial primary key,
    title text not null,
    description text not null,
    module_id integer references modules(id) on delete set null,
    priority text not null default 'normal' check (priority in ('normal', 'importante', 'critico')),
    active boolean not null default true,
    created_by integer references users(id) on delete set null,
    updated_by integer references users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_process_notes_module on process_notes(module_id);
create index if not exists idx_process_notes_active on process_notes(active);
create index if not exists idx_process_notes_priority on process_notes(priority);

-- No se sembran módulos/planes/tipos: se gestionan desde la página de Administración
-- una vez que exista el primer usuario admin (ver README para el bootstrap del admin).
