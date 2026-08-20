-- Migración: notificaciones dentro de la app para anuncios nuevos (sin correo).
-- Ejecutar solo si el proyecto ya existía antes de este cambio (ya tenía `process_notes`).

alter table users add column if not exists last_seen_announcements_at timestamptz;

-- Evita que a los usuarios existentes les aparezcan de golpe como "nuevos" todos los
-- anuncios ya publicados hasta ahora (los usuarios nuevos, sin fecha, sí ven todo como nuevo).
update users set last_seen_announcements_at = now() where last_seen_announcements_at is null;
