# Documentación CSS · Q10

Plataforma interna en Streamlit para consultar y mantener actualizada la documentación del área de CSS:

- Anuncios: notas de proceso a tener en cuenta al ejecutar ciertas tareas, con módulo, prioridad (normal/importante/crítico) y vigencia (se pueden archivar sin perder el histórico). Si hay credenciales SMTP configuradas, cada anuncio nuevo notifica por correo a todos los usuarios activos automáticamente.
- Parámetros, funciones y funcionalidades a habilitar según cada tipo de petición.
- Consideraciones y notas posteriores a una habilitación.
- Desarrollos personalizados.
- Dimensiones en las distintas partes de Q10.
- Funcionalidades filtrables por plan y por tipo.
- Catálogo de APIs, con un mapa interactivo de dependencias entre recursos.
- Catálogo de queries de soporte, enlazadas a las funcionalidades que habilitan.
- Biblioteca de desarrollos reutilizables (recetas de habilitación, cambios estándar y procedimientos ante eventualidades) y catálogo de personalizaciones por institución.
- Asistente en formato chat: una burbuja flotante 🤖 en la esquina inferior izquierda, disponible en cualquier página de la app, que responde preguntas sobre toda la documentación (qué habilitar, qué hace un query, qué trae una API, etc.). Cuando identifica con confianza qué funcionalidad se debe activar (al menos 2 palabras clave de la pregunta coinciden, o la única disponible si la pregunta es muy corta), muestra una "receta" de habilitación exacta y determinística — funciones, parámetros y funcionalidades a activar con sus códigos reales, sin depender de que la IA los transcriba bien — enlazada a la meta-query correspondiente (Asignar Permisos Roles / Actualizar parámetros institucionales / Activar-Inactivar Funcionalidades). Si no hay una coincidencia lo bastante segura, en vez de arriesgarse a mostrar una receta equivocada lista los resultados relacionados (queries, APIs, dimensiones, desarrollos, etc.) como enlaces de texto en negrita, buscando tanto en la documentación propia como en el catálogo maestro real de Q10 (funciones/parámetros/funcionalidades exportados del sistema). Si hay una API key de Gemini configurada, además redacta una respuesta en lenguaje natural citando el contenido real (SQL, endpoints, descripciones) — si no, muestra igual los resultados encontrados sin IA.

Login propio con tres roles (`admin`, `editor`, `lector`). Los catálogos de **Módulos**, **Planes** y **Tipos** son administrables desde la propia app, para poder adaptar el alcance del proyecto sin tocar código.

## Stack

- [Streamlit](https://streamlit.io/) (multipágina, con navegación según el rol del usuario).
- [Supabase](https://supabase.com/) (Postgres) como base de datos, vía `st.connection(type="sql")`.
- `bcrypt` para el hash de contraseñas.

## Puesta en marcha (local)

1. **Crear el proyecto en Supabase** y correr el script `sql/schema.sql` completo en su SQL editor. Esto crea todas las tablas (usuarios, módulos, planes, tipos, funcionalidades, notas, desarrollos personalizados, dimensiones, APIs, recursos/categorías de APIs, queries, biblioteca de desarrollos, personalizaciones, anuncios/notas de proceso y el catálogo maestro de Q10). Si el proyecto ya existía antes de que se agregara alguna de estas piezas, corre además `sql/migration_api_map.sql`, `sql/migration_queries.sql`, `sql/migration_custom_dev_library.sql`, `sql/migration_sys_catalog.sql` y/o `sql/migration_process_notes.sql` según corresponda.

2. **Generar el primer usuario admin.** Como no hay un endpoint público de registro, se crea manualmente:

   ```bash
   pip install bcrypt
   python scripts/hash_password.py "tu-contraseña-temporal"
   ```

   Copia el hash impreso y ejecútalo en el SQL editor de Supabase:

   ```sql
   insert into users (email, name, password_hash, role, active)
   values ('tu_correo@empresa.com', 'Tu Nombre', '<hash pegado aquí>', 'admin', true);
   ```

3. **Configurar la conexión a la base de datos.** Copia `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` y reemplaza la URL con la cadena de conexión real de tu proyecto Supabase (usa el *connection pooler*, puerto `6543`). Opcionalmente, agrega tu API key gratuita de [Google AI Studio](https://aistudio.google.com/apikey) en la sección `[gemini]` para que el Asistente redacte respuestas con IA (sin esto, sigue funcionando solo con el buscador), y/o una casilla de correo real con contraseña de aplicación en la sección `[smtp]` para que la página Anuncios notifique por correo a todos los usuarios activos cada vez que se publica un anuncio nuevo (sin esto, los anuncios se siguen publicando normalmente, solo que sin correo). No hace falta verificar ningún dominio: sirve una cuenta de Outlook/Office 365 o Gmail con una contraseña de aplicación.

4. **Instalar dependencias y correr la app:**

   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```

5. Inicia sesión con el usuario admin creado en el paso 2, ve a **Administración** y crea al menos un **Módulo**, un **Plan** y un **Tipo** antes de cargar contenido en las demás páginas.

## Despliegue en Streamlit Community Cloud

1. Sube este repositorio a GitHub.
2. En [share.streamlit.io](https://share.streamlit.io/), crea una nueva app apuntando a `app.py`.
3. En la sección **Secrets** de la configuración de la app, pega el mismo contenido que tienes en tu `.streamlit/secrets.toml` local.
4. Despliega. Como los datos viven en Supabase (no en el disco de Streamlit Cloud), las ediciones de los usuarios persisten aunque la app se reinicie o se redepliegue.

## Estructura del proyecto

```
app.py                          # entrypoint: login y navegación según rol
lib/
  db.py                         # conexión y helpers de lectura/escritura sobre Supabase
  auth.py                       # login, sesión y control de acceso por rol
  ui.py                         # estilo Q10, header, buscador global y componentes reutilizables
  catalog.py                    # catálogos compartidos: módulos, planes, tipos
  search.py                     # búsqueda global (funcionalidades, desarrollos, dimensiones, APIs, queries, biblioteca, personalizaciones)
  activation_items.py           # extrae funciones/parámetros/funcionalidades de las notas de activación y arma la "receta" de habilitación
  sys_catalog.py                # catálogo maestro real de Q10 (funciones/parámetros/funcionalidades exportados del sistema), respaldo de búsqueda
  llm.py                        # cliente Gemini para que el Asistente redacte respuestas (opcional, cae a solo-buscador si no hay API key)
  assistant_widget.py           # burbuja flotante del Asistente (chat), inyectada en todas las páginas vía top_bar()
  notifications.py              # notifica por correo (SMTP) a todos los usuarios activos cuando se publica un anuncio (opcional)
  api_graph.py                  # construcción y render del mapa interactivo de dependencias entre APIs
pages/
  0_Anuncios.py                 # notas de proceso a tener en cuenta al ejecutar ciertas tareas (módulo, prioridad, vigencia)
  1_Funcionalidades.py
  2_Desarrollos_Personalizados.py # seguimiento de solicitudes de desarrollo por cliente
  3_Dimensiones.py
  4_APIs.py                     # catálogo de APIs + mapa interactivo de dependencias
  5_Administracion.py           # solo admin: usuarios y catálogos
  6_Queries.py                  # catálogo de queries de soporte
  7_Biblioteca_Desarrollos.py   # biblioteca de desarrollos reutilizables (P/F/E) + personalizaciones por institución
sql/
  schema.sql                    # DDL completo para Supabase (instalación nueva)
  migration_api_map.sql         # migración para agregar el mapa de APIs a una BD existente
  migration_queries.sql         # migración para agregar el catálogo de queries a una BD existente
  migration_custom_dev_library.sql # migración para agregar la biblioteca de desarrollos y personalizaciones
  migration_sys_catalog.sql     # migración para agregar el catálogo maestro real de Q10 (funciones/parámetros/funcionalidades)
  migration_process_notes.sql   # migración para agregar los anuncios/notas de proceso
scripts/hash_password.py        # utilidad para generar el hash del primer admin
assets/
  style.css                     # paleta e identidad visual inspirada en q10.com
  api_graph.css, api_graph.js   # estilo y lógica del mapa interactivo de APIs (tema claro Q10)
  vis-network.min.js            # librería de grafos (vis-network), embebida localmente
```

## Roles

| Rol      | Puede consultar | Puede crear/editar/eliminar contenido | Gestiona usuarios y catálogos |
|----------|:---:|:---:|:---:|
| Lector   | ✅ | ❌ | ❌ |
| Editor   | ✅ | ✅ | ❌ |
| Admin    | ✅ | ✅ | ✅ |

## Próximos pasos sugeridos

- Ajustar la paleta/tipografía si la marca cambia (todo el estilo vive en `assets/style.css` y `.streamlit/config.toml`).
- Agregar más módulos de contenido: el patrón de cada página (filtros → tabla → detalle → formulario de alta/edición/borrado) está pensado para ser fácil de replicar.
