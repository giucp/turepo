# Base de datos de Tu Repo

La estructura completa de la base de datos vive en **`schema.sql`** (tablas, índices,
vistas, funciones RPC, triggers y políticas RLS). Esto permite **reconstruir el proyecto
desde cero** si Supabase se corrompe, se borra, o si quieres recrearlo.

> `schema.sql` define **estructura**, no datos. No incluye reportes/fotos/usuarios
> (esos se respaldan con los backups de Supabase, ver más abajo).

## Cómo restaurar la estructura en un proyecto Supabase nuevo

1. Crea un proyecto nuevo en Supabase.
2. Abre **SQL Editor**.
3. Pega el contenido de `schema.sql` y ejecútalo de arriba a abajo.
   - Está ordenado por dependencias (tablas → índices → funciones → triggers → vistas → RLS).
   - Es idempotente en su mayoría (`create ... if not exists`, `create or replace`,
     `drop policy if exists`), así que correrlo de nuevo no rompe nada.
4. Actualiza en `index.html` el `SUPABASE_URL` y `SUPABASE_KEY` (anon) del proyecto nuevo.

## Pasos manuales que NO están en `schema.sql` (ojo)

Estas piezas viven fuera del esquema SQL y hay que recrearlas aparte:

- **Storage (bucket `fotos`)**: crear el bucket `fotos` (lectura pública de lo aprobado) y
  sus políticas de Storage. *(No están dumpeadas aquí; recrear desde el panel de Storage o
  dumpear las policies de `storage.objects` si se quiere versionar.)*
- **Auth**: proveedor de Google OAuth y los **Redirect URLs** (`https://turepo.com`).
- **Secrets de los GitHub Actions**: `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY`
  (en el repo, Settings → Secrets → Actions). La `service_role` se saca del panel del
  proyecto nuevo. **Nunca** va en el código ni aquí.
- **Cron externo (cron-job.org)**: las 4 tareas que disparan los workflows
  (bcv/noticias/binance/moderar_fotos) y el token fino `turepo-cron`.
- **Datos semilla de tasas** (opcional): el app lee `tasa_bcv`/`tasa_binance` con `id=1`;
  si no existen filas, cae a respaldos públicos hasta que los Actions las pueblen.

## Backups (datos reales)

- La **estructura** está versionada aquí (este archivo).
- Los **datos** dependen de los backups de Supabase. En el plan gratis los backups
  automáticos son limitados; revisar en **Database → Backups** del panel. Para algo crítico,
  considerar un export manual periódico (`pg_dump`) o subir de plan para PITR.

## Mantener este archivo al día

Cada vez que cambie el esquema en producción (nueva tabla/columna/RPC/política), reflejarlo
aquí en `schema.sql` y commitearlo. Si se acumulan cambios, se puede re-dumpear corriendo en
el SQL Editor las queries de `information_schema` / `pg_*` (columns, constraints, indexes,
`pg_get_viewdef`, `pg_get_functiondef`, `pg_get_triggerdef`, `pg_policies`).
