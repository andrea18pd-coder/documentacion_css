-- Migración: búsqueda por similitud (tolerante a tildes y errores de tipeo) en el buscador global.
-- Ejecutar en el SQL editor de Supabase. No requiere cambios de tablas, solo habilita extensiones.
create extension if not exists pg_trgm;
create extension if not exists unaccent;
