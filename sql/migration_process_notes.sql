-- Migración: apartado de Anuncios / notas de proceso a tener en cuenta al ejecutar
-- ciertos procesos (no confundir con `notes`, que son consideraciones ligadas a una
-- funcionalidad puntual). Ejecutar solo si el proyecto ya existía antes de este cambio.

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
