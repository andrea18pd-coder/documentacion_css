-- Migración: catálogo maestro real de Q10 (funciones, parámetros y funcionalidades de
-- aplicación), exportado directo del sistema. Es de solo lectura — se usa para enriquecer y
-- respaldar la búsqueda del Asistente cuando algo no está documentado manualmente en
-- activation_notes, pero sí existe en el sistema real.
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
