# Documentación técnica integral

## Plataforma RAG, chatbot y agenda transaccional con PostgreSQL/pgvector

**Proyecto:** `pgvector-rag`  
**Versión documentada:** 1.0  
**Backend:** Python 3.12, FastAPI y Uvicorn  
**Base de datos:** PostgreSQL 17 con pgvector  
**Embeddings:** `sentence-transformers/all-MiniLM-L6-v2`  
**LLM:** OpenRouter, configurable y con `openrouter/free` como valor predeterminado  
**Frontend:** HTML, CSS y JavaScript independientes del servidor web de FastAPI

---

## 1. Propósito del sistema

Este proyecto implementa una plataforma completa de recuperación aumentada por generación, conocida como RAG (*Retrieval-Augmented Generation*), acompañada por un módulo transaccional para administrar citas.

El sistema permite:

- cargar documentos PDF, TXT y Markdown;
- extraer y normalizar su contenido;
- dividir el texto en fragmentos solapados;
- generar embeddings normalizados de 384 dimensiones;
- almacenar documentos, fragmentos y vectores en PostgreSQL;
- recuperar contenido mediante similitud coseno con pgvector;
- generar respuestas con un LLM gratuito disponible en OpenRouter;
- responder sin entregar al usuario los fragmentos internos completos;
- rechazar solicitudes para revelar prompts, credenciales o instrucciones internas;
- crear, consultar, cancelar y reprogramar citas;
- impedir reservas simultáneas sobre el mismo horario mediante transacciones;
- ejecutar el frontend como archivos HTML, CSS y JavaScript independientes;
- ejecutar FastAPI únicamente como backend y API.

RAG se utiliza para responder preguntas basadas en documentos. Las citas no se gestionan mediante RAG ni mediante SQL generado por el LLM: se gestionan con servicios deterministas, consultas parametrizadas y transacciones de PostgreSQL.

---

## 2. Arquitectura general

```mermaid
flowchart LR
    U["Usuario"] --> F["Frontend HTML/CSS/JS"]
    F -->|"HTTP/JSON"| API["FastAPI"]
    API --> INTENT{"Tipo de solicitud"}
    INTENT -->|"Pregunta documental"| RAG["RagService"]
    INTENT -->|"Operación de citas"| AC["AppointmentChatService"]
    RAG --> EMB["Sentence Transformers"]
    EMB --> PG["PostgreSQL + pgvector"]
    PG --> RAG
    RAG --> OR["OpenRouter / LLM gratuito"]
    OR --> API
    AC --> AR["AppointmentRepository"]
    AR --> PG
    API --> F
```

### 2.1 Separación de responsabilidades

- El **frontend** captura mensajes, conserva un historial corto en el navegador y presenta respuestas.
- **FastAPI** valida solicitudes, aplica dependencias y expone los endpoints.
- Los **servicios** contienen los casos de uso y las reglas de negocio.
- Los **repositorios** contienen las consultas SQL y el acceso transaccional.
- PostgreSQL almacena tanto información relacional como embeddings.
- `sentence-transformers` genera embeddings localmente.
- OpenRouter genera la respuesta final utilizando el contexto recuperado.
- El motor conversacional de citas interpreta pasos predefinidos sin permitir que el LLM modifique la agenda.

---

## 3. Estructura del proyecto

```text
pgvector-rag/
├── .env
├── .env.example
├── .gitignore
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
├── README.md
├── DOCUMENTACION_TECNICA.md
├── data/
│   ├── manual_empresa_demo.txt
│   ├── faq_servicios.txt
│   ├── politica_citas.txt
│   └── privacidad_seguridad.txt
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── sql/
│   ├── 001_init.sql
│   ├── 002_appointments.sql
│   └── examples.sql
├── scripts/
│   ├── init_db.py
│   ├── ingest.py
│   ├── search.py
│   ├── seed.py
│   ├── rebuild_embeddings.py
│   ├── reindex.py
│   └── benchmark.py
├── src/
│   ├── api/
│   │   ├── main.py
│   │   ├── dependencies.py
│   │   ├── security.py
│   │   └── static/            # interfaz anterior; redirige al frontend actual
│   ├── config/
│   │   ├── settings.py
│   │   └── logging.py
│   ├── database/
│   │   ├── connection.py
│   │   └── init_db.py
│   ├── embeddings/
│   │   ├── provider.py
│   │   └── sentence_transformer.py
│   ├── models/
│   │   ├── domain.py
│   │   └── schemas.py
│   ├── repositories/
│   │   ├── document_repository.py
│   │   └── appointment_repository.py
│   └── services/
│       ├── loaders.py
│       ├── chunking.py
│       ├── document_service.py
│       ├── rag_service.py
│       ├── openrouter.py
│       ├── appointment_service.py
│       └── appointment_chat_service.py
└── tests/
    ├── unit/
    └── integration/
```

### 3.1 Archivos raíz

- `.env`: configuración privada del entorno local. No debe subirse al repositorio.
- `.env.example`: plantilla sin credenciales válidas.
- `docker-compose.yml`: definición de PostgreSQL 17 con pgvector.
- `requirements.txt`: dependencias de ejecución y pruebas.
- `pyproject.toml`: configuración de pytest.
- `README.md`: guía rápida.
- `DOCUMENTACION_TECNICA.md`: referencia técnica completa.

### 3.2 Directorio `src`

`src` contiene el código de aplicación. Las capas están separadas para impedir que la API contenga SQL o que los repositorios contengan lógica conversacional.

### 3.3 Directorio `frontend`

El frontend no es servido por Uvicorn. `index.html` se abre directamente desde el sistema de archivos. `app.js` se comunica con `http://127.0.0.1:8000`, por lo que FastAPI debe permanecer activo.

### 3.4 Directorio `data`

Contiene documentos de demostración. Agregar un archivo a esta carpeta no lo carga automáticamente; se debe ejecutar el script de ingesta.

---

## 4. Configuración mediante variables de entorno

Las variables son validadas por `pydantic-settings`.

| Variable | Propósito | Valor de desarrollo |
|---|---|---|
| `POSTGRES_USER` | Usuario de PostgreSQL | `vector_user` |
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL | debe modificarse |
| `POSTGRES_DB` | Base de datos | `vector_db` |
| `POSTGRES_HOST` | Host visto por Python | `localhost` |
| `POSTGRES_PORT` | Puerto publicado | `5433` en este entorno |
| `EMBEDDING_MODEL` | Modelo local de embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| `CHUNK_SIZE` | Tamaño aproximado del fragmento | `800` caracteres |
| `CHUNK_OVERLAP` | Solapamiento entre fragmentos | `120` caracteres |
| `OPENROUTER_API_KEY` | Credencial del LLM | privada |
| `OPENROUTER_MODEL` | Modelo generativo | `openrouter/free` |
| `OPENROUTER_BASE_URL` | API de OpenRouter | `https://openrouter.ai/api/v1` |
| `RAG_TOP_K` | Cantidad predeterminada de resultados | `5` |
| `RAG_MAX_CONTEXT_CHARS` | Límite del contexto enviado al LLM | `12000` |
| `ADMIN_API_KEY` | Protección de endpoints administrativos | secreto aleatorio |
| `PRIVACY_MODE` | Indica operación privada | `true` |
| `EXPOSE_SOURCE_TEXT` | Permite exponer fragmentos al cliente | `false` |
| `LOG_LEVEL` | Nivel de logging | `INFO` |

### Reglas para `.env`

1. Nunca confirmar `.env` en Git.
2. Nunca copiar `OPENROUTER_API_KEY`, `POSTGRES_PASSWORD` o `ADMIN_API_KEY` a JavaScript.
3. Usar secretos diferentes para desarrollo, pruebas y producción.
4. Reiniciar Uvicorn después de modificar variables de entorno.
5. Utilizar un gestor de secretos en producción.

---

## 5. Funcionamiento de la ingesta documental

```mermaid
sequenceDiagram
    participant CLI as Script ingest.py
    participant Loader as Loader
    participant Chunker as TextChunker
    participant Model as all-MiniLM-L6-v2
    participant DB as PostgreSQL
    CLI->>Loader: Lee PDF/TXT/Markdown
    Loader-->>CLI: Texto extraído
    CLI->>Chunker: Texto + metadatos
    Chunker-->>CLI: Fragmentos solapados
    CLI->>Model: Lista de textos
    Model-->>CLI: Vectores normalizados
    CLI->>DB: Documento + chunks + embeddings
```

### 5.1 Carga

`loaders.py` selecciona el mecanismo según la extensión:

- TXT y Markdown: lectura UTF-8.
- PDF: extracción mediante `pypdf`.
- Otros formatos: error de validación.

Los PDF escaneados sin capa de texto requieren OCR, que no está incluido actualmente.

### 5.2 Chunking

`TextChunker`:

- normaliza espacios consecutivos;
- intenta cortar en límites de palabras;
- aplica solapamiento para preservar contexto;
- asigna un índice secuencial;
- conserva metadatos de origen.

El solapamiento debe ser menor que el tamaño del fragmento.

### 5.3 Embeddings

`SentenceTransformerProvider` utiliza `all-MiniLM-L6-v2` y solicita normalización. El resultado es un vector `float32` de 384 dimensiones.

La dimensión debe coincidir con `VECTOR(384)`. Cambiar a un modelo de otra dimensión exige migrar la columna, reconstruir todos los embeddings y recrear los índices.

### 5.4 Persistencia

La creación de documento, chunks y embeddings se ejecuta en una misma conexión transaccional. El checksum SHA-256 evita cargar exactamente el mismo archivo dos veces.

---

## 6. Funcionamiento del RAG

### 6.1 Flujo de pregunta

1. El frontend envía `message`, historial y `session_id` a `POST /chat`.
2. El motor de citas comprueba si el mensaje corresponde a una operación transaccional.
3. Si no es una operación de citas, `RagService` aplica las reglas de privacidad.
4. Se genera el embedding normalizado de la pregunta.
5. PostgreSQL recupera los chunks más cercanos mediante `<=>`.
6. El score se calcula como `1 - distancia_coseno`.
7. Los resultados se delimitan y numeran como contexto interno.
8. OpenRouter recibe instrucciones, historial limitado, contexto y pregunta.
9. El LLM redacta una respuesta con referencias `[1]`, `[2]`, etc.
10. La API aplica una comprobación de salida.
11. El cliente recibe la respuesta y referencias mínimas, pero no los chunks completos.

### 6.2 Prompt y contexto

El contexto documental se trata como datos no confiables. Una instrucción escrita dentro de un documento no debe modificar las reglas del asistente. El prompt ordena explícitamente ignorar instrucciones incrustadas en el contexto.

El usuario no debe recibir:

- el prompt del sistema;
- instrucciones internas;
- el bloque de contexto completo;
- variables de entorno;
- credenciales;
- rutas locales;
- configuración privada.

### 6.3 OpenRouter

`openrouter/free` permite que OpenRouter seleccione un modelo gratuito disponible. Ventajas:

- costo de inferencia cero para modelos gratuitos;
- no depende de un único modelo;
- útil para demostraciones y aprendizaje.

Limitaciones:

- requiere cuenta y API key;
- disponibilidad variable;
- límites de solicitudes;
- latencia y calidad diferentes entre modelos;
- no ofrece garantías de producción.

Para producción debe seleccionarse un modelo y proveedor con requisitos de privacidad, residencia, disponibilidad y retención acordes al negocio.

---

## 7. Base de datos vectorial

### 7.1 Tablas documentales

#### `documents`

Almacena identidad del documento, nombre, tipo, JSONB, checksum y fechas.

#### `chunks`

Almacena texto, posición, metadatos y relación con el documento. Al eliminar un documento, sus chunks se eliminan en cascada.

#### `embeddings`

Relación uno a uno con `chunks`. Almacena nombre del modelo, vector de 384 dimensiones y fechas de mantenimiento.

### 7.2 Operadores pgvector

- `<->`: distancia euclídea.
- `<=>`: distancia coseno.
- `<#>`: producto interno negativo.

El proyecto utiliza distancia coseno porque los embeddings están normalizados.

### 7.3 HNSW

HNSW es el índice predeterminado. Ofrece buen recall, consultas rápidas e inserciones dinámicas, a cambio de mayor memoria y construcción más costosa.

### 7.4 IVFFlat

IVFFlat es una alternativa para colecciones grandes y relativamente estables. Requiere datos previos, `ANALYZE` y ajuste de `lists` y `ivfflat.probes`. No se recomienda mantener HNSW e IVFFlat simultáneamente sin una razón medida.

---

## 8. Sistema de citas

### 8.1 Tablas

- `appointment_services`: servicios, descripción y duración.
- `professionals`: profesionales asignados a un servicio.
- `appointment_slots`: fecha/hora de inicio y fin.
- `appointments`: cliente, correo, estado y relación con un slot.
- `appointment_conversations`: estado JSONB de cada conversación.

### 8.2 Datos simulados

La migración crea:

- Soporte técnico, 30 minutos.
- Demostración comercial, 60 minutos.
- Consultoría, 60 minutos.
- Tres profesionales simulados.
- Horarios a las 09:00, 11:00, 14:00 y 16:00.
- Disponibilidad de lunes a viernes durante los siguientes 45 días.
- Zona horaria `America/Bogota`.

### 8.3 Operaciones conversacionales

El usuario puede escribir:

```text
Quiero agendar una cita
Ver mis citas
Cancelar una reserva
Cambiar la fecha de mi cita
Reprogramar mi cita
```

El estado se almacena por `session_id`. Las intenciones explícitas pueden interrumpir un flujo anterior para evitar que una orden de cancelación sea interpretada como el nombre de un servicio.

### 8.4 Protección contra doble reserva

PostgreSQL mantiene un índice único parcial para permitir una sola cita activa por slot. Antes de crear o reprogramar:

1. el repositorio bloquea la fila del slot con `FOR UPDATE`;
2. comprueba que el horario sea futuro y esté activo;
3. verifica nuevamente que no exista una reserva confirmada;
4. crea o actualiza la cita;
5. confirma la transacción.

Si dos usuarios intentan reservar simultáneamente, solo una transacción puede completar la operación.

### 8.5 Reprogramación

La reprogramación conserva el UUID de la cita, verifica que el nuevo slot pertenezca al mismo servicio, libera el slot anterior y ocupa el nuevo de forma atómica.

### 8.6 Límite de seguridad actual

La agenda es una demostración funcional, no un sistema completo de identidad. La consulta conversacional utiliza correo y códigos de cita, pero no implementa registro, inicio de sesión, verificación de correo, MFA ni autorización por propietario.

Antes de producción se debe:

- implementar usuarios autenticados;
- asociar cada cita a un `user_id` inmutable;
- limitar todas las consultas por el usuario autenticado;
- verificar propiedad antes de consultar, cancelar o reprogramar;
- evitar enumeración por correo;
- auditar operaciones sensibles;
- aplicar rate limiting y protección contra abuso.

---

## 9. Seguridad y privacidad

### 9.1 Protección administrativa

Los endpoints documentales requieren `X-Admin-Key`:

- `POST /documents`;
- `GET /documents`;
- `DELETE /documents/{id}`;
- `POST /search`.

La comparación de la clave es de tiempo constante. Si `ADMIN_API_KEY` no está configurada o conserva el placeholder, la administración queda deshabilitada.

### 9.2 Protección contra extracción de prompts

Antes de generar embeddings o llamar a OpenRouter, `RagService` detecta solicitudes relacionadas con prompts, instrucciones ocultas, credenciales y variables de entorno. Estas solicitudes reciben una respuesta de política local.

También se examina la respuesta del LLM para detectar marcadores de configuración privada conocidos.

Estas medidas reducen el riesgo, pero ningún filtro basado únicamente en texto garantiza seguridad absoluta. Deben combinarse con aislamiento de datos, mínimo privilegio, auditoría y pruebas de red team.

### 9.3 Exposición de fuentes

Con `EXPOSE_SOURCE_TEXT=false`, la API devuelve texto vacío en cada fuente. Solo se expone:

- número de referencia;
- UUID del documento;
- score;
- nombre de origen.

### 9.4 CORS

FastAPI permite solicitudes procedentes de archivos locales (`Origin: null`) y servidores de desarrollo en `localhost` o `127.0.0.1`. En producción esta política debe restringirse al dominio exacto del frontend; no se debe permitir `null`.

### 9.5 Amenazas pendientes para producción

- No existe autenticación de usuarios finales.
- Los endpoints de citas no están asociados a una identidad verificada.
- No existe rate limiting.
- No existe protección CSRF porque el sistema no usa cookies, pero deberá revisarse si se agregan sesiones web.
- No existe cifrado TLS local.
- Los documentos enviados a un LLM externo abandonan el perímetro local.
- Los logs deben revisarse para evitar información sensible.
- No existe escaneo antivirus de archivos cargados.
- Los PDF no se ejecutan, pero deben limitarse tamaño y complejidad para evitar agotamiento de recursos.

---

## 10. API REST

### 10.1 Salud

```http
GET /health
```

Comprueba la conexión con PostgreSQL.

### 10.2 Chat

```http
POST /chat
Content-Type: application/json
```

```json
{
  "message": "¿Qué datos no debo enviar?",
  "history": [],
  "session_id": "UUID",
  "top_k": 5,
  "category": null
}
```

Devuelve `answer`, `model`, referencias y, cuando corresponde, una cita estructurada.

### 10.3 Documentos

Requieren `X-Admin-Key`.

```text
POST   /documents
GET    /documents
DELETE /documents/{document_id}
POST   /search
```

### 10.4 Citas

```text
GET    /appointments/services
GET    /appointments/availability
POST   /appointments
GET    /appointments?customer_email=...
PUT    /appointments/{appointment_id}?slot_id=...
DELETE /appointments/{appointment_id}
```

Los endpoints directos de consulta y modificación deben protegerse con autenticación antes de un despliegue real.

### 10.5 Swagger

En desarrollo:

```text
http://127.0.0.1:8000/docs
```

Swagger no debe publicarse sin autenticación en producción.

---

## 11. Ejecución en Windows

### 11.1 Requisitos

- Windows 10 u 11.
- Docker Desktop iniciado.
- Python 3.12 o superior.
- PowerShell.
- Acceso a Internet para descargar dependencias, el modelo y llamar a OpenRouter.

### 11.2 Preparación

```powershell
cd "C:\Users\crist\OneDrive\Documentos\pgvector-rag"
Copy-Item .env.example .env
notepad .env
```

No se debe reemplazar el `.env` actual si ya contiene las credenciales configuradas.

### 11.3 PostgreSQL

```powershell
docker compose up -d
docker compose ps
```

Este entorno publica PostgreSQL en `5433` porque `5432` estaba ocupado. La asignación es:

```text
localhost:5433 -> contenedor:5432
```

### 11.4 Entorno virtual

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 11.5 Inicialización

```powershell
python -m scripts.init_db
```

El inicializador ejecuta únicamente migraciones con nombre `NNN_*.sql`. `examples.sql` no se ejecuta.

### 11.6 Ingesta

```powershell
python -m scripts.ingest .\data\manual_empresa_demo.txt
python -m scripts.ingest .\data\faq_servicios.txt
```

### 11.7 Backend

```powershell
uvicorn src.api.main:app --reload
```

### 11.8 Frontend

Abrir directamente:

```text
C:\Users\crist\OneDrive\Documentos\pgvector-rag\frontend\index.html
```

El indicador debe mostrar `Backend conectado`.

### 11.9 Detener

```powershell
# En la terminal de Uvicorn
Ctrl+C

# Para detener PostgreSQL
docker compose down
```

`docker compose down` conserva el volumen. `docker compose down -v` elimina la base de datos y es destructivo.

---

## 12. Ejecución en Linux

### 12.1 Requisitos

- Distribución Linux moderna.
- Docker Engine con plugin Compose.
- Python 3.12 o superior.
- Shell Bash compatible.

En Debian/Ubuntu se debe instalar Docker siguiendo la documentación oficial. El usuario puede requerir pertenecer al grupo `docker` o utilizar `sudo`.

### 12.2 Preparación

```bash
cd /ruta/al/proyecto/pgvector-rag
cp .env.example .env
nano .env
```

Configure contraseñas y claves antes de continuar.

### 12.3 PostgreSQL

```bash
docker compose up -d
docker compose ps
```

Si `5432` está ocupado:

```dotenv
POSTGRES_PORT=5433
```

### 12.4 Entorno virtual

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Si el módulo `venv` no está instalado en Debian/Ubuntu:

```bash
sudo apt install python3.12-venv
```

### 12.5 Inicialización e ingesta

```bash
python -m scripts.init_db
python -m scripts.ingest ./data/manual_empresa_demo.txt
python -m scripts.ingest ./data/faq_servicios.txt
```

### 12.6 Backend

```bash
uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000
```

### 12.7 Frontend

Abrir `frontend/index.html` con el navegador. También puede utilizarse un servidor estático separado:

```bash
python -m http.server 5500 --directory frontend
```

En ese caso, abrir:

```text
http://127.0.0.1:5500
```

FastAPI continuará funcionando de forma independiente en el puerto 8000.

### 12.8 Servicio de producción en Linux

Para producción no se debe utilizar `--reload`. Una opción es systemd con un proxy inverso:

```ini
[Unit]
Description=pgvector RAG API
After=network.target docker.service

[Service]
Type=simple
WorkingDirectory=/opt/pgvector-rag
EnvironmentFile=/opt/pgvector-rag/.env
ExecStart=/opt/pgvector-rag/.venv/bin/uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
User=ragapp
Group=ragapp

[Install]
WantedBy=multi-user.target
```

El frontend puede servirse con Nginx y `/api` puede enviarse al backend. Deben habilitarse HTTPS, cabeceras seguras y límites de tamaño.

---

## 13. Scripts operativos

### Inicializar migraciones

```bash
python -m scripts.init_db
```

### Ingestar archivos o directorios

```bash
python -m scripts.ingest ./data
```

Los archivos duplicados por checksum son rechazados.

### Búsqueda desde CLI

```bash
python -m scripts.search "política de cancelación" --top-k 5
```

Este script es administrativo y muestra texto recuperado en la terminal; no debe exponerse a usuarios finales.

### Reconstruir embeddings

```bash
python -m scripts.rebuild_embeddings
python -m scripts.rebuild_embeddings --document-id UUID
```

### Cambiar índice

```bash
python -m scripts.reindex --type hnsw
python -m scripts.reindex --type ivfflat --lists 100
```

### Benchmark

```bash
python -m scripts.benchmark "búsqueda semántica" --runs 50
```

El resultado se guarda en `benchmark-results.json`.

---

## 14. Pruebas y validación

### Unitarias

```bash
pytest tests/unit -q
```

Cubren chunking, loaders y construcción del contexto RAG con dependencias simuladas.

### Integración

Windows PowerShell:

```powershell
$env:RUN_INTEGRATION='1'
$env:DATABASE_URL='postgresql://vector_user:contraseña@localhost:5433/vector_db'
pytest -m integration
```

Linux:

```bash
export RUN_INTEGRATION=1
export DATABASE_URL='postgresql://vector_user:contraseña@localhost:5433/vector_db'
pytest -m integration
```

### Validaciones recomendadas

- `docker compose config --quiet`;
- `python -m compileall -q src scripts tests`;
- prueba de `/health`;
- prueba de búsqueda semántica;
- prueba de reserva concurrente;
- prueba de cancelación y reprogramación;
- prueba de acceso administrativo con y sin clave;
- pruebas de extracción de prompts;
- prueba de que `sources[].text` permanezca vacío.

---

## 15. Logging y errores

El sistema configura logging centralizado con fecha, nivel, logger y mensaje. Las excepciones de validación se convierten en respuestas HTTP apropiadas.

Estados importantes:

- `401`: credencial administrativa inválida;
- `404`: recurso inexistente;
- `409`: slot ocupado o conflicto transaccional;
- `422`: datos inválidos;
- `502`: OpenRouter no respondió correctamente;
- `503`: base de datos o configuración administrativa no disponible.

Nunca se deben registrar claves, contraseñas, tokens, documentos completos ni cuerpos que contengan datos personales.

---

## 16. Reglas de ingeniería del proyecto

### 16.1 Arquitectura

1. La API no debe contener SQL.
2. Los repositorios no deben llamar al LLM.
3. El LLM no debe ejecutar SQL ni decidir directamente una transacción.
4. Los servicios deben representar casos de uso independientes.
5. Las dependencias deben construirse en `api/dependencies.py`.
6. Los modelos de entrada y salida deben validarse con Pydantic.
7. Todas las consultas deben ser parametrizadas.

### 16.2 RAG

1. Usar el mismo modelo para indexar documentos y preguntas.
2. Normalizar embeddings si se usa similitud coseno.
3. Mantener la dimensión del modelo alineada con el esquema.
4. No enviar contexto ilimitado al LLM.
5. No utilizar un score como garantía de veracidad.
6. Responder que la información no está disponible cuando el contexto no respalde la respuesta.
7. No mostrar fragmentos completos a usuarios en modo privado.

### 16.3 Citas

1. Consultar disponibilidad en tiempo real.
2. Volver a verificar el slot dentro de la transacción.
3. Solicitar confirmación antes de cancelar o reprogramar.
4. Mantener historial y auditoría de cambios.
5. No permitir que un LLM construya consultas de escritura.
6. En producción, verificar la identidad y propiedad de cada cita.

### 16.4 Seguridad

1. Aplicar mínimo privilegio.
2. No incluir secretos en el repositorio o frontend.
3. Rotar claves comprometidas.
4. No confiar en instrucciones provenientes de documentos.
5. Limitar tamaño, tipo y frecuencia de archivos.
6. Ocultar Swagger y detalles de error en producción.
7. Restringir CORS al origen real.
8. Usar HTTPS.
9. Realizar backups y pruebas de restauración.
10. Mantener dependencias e imágenes actualizadas.

### 16.5 Calidad

1. Todo cambio de comportamiento debe incluir una prueba.
2. Las migraciones deben ser idempotentes cuando sea posible.
3. No modificar una migración ya desplegada en producción; crear una nueva.
4. Mantener tipado completo y docstrings donde aporten claridad.
5. Evitar comentarios que repitan el código.
6. Medir rendimiento con datos representativos.

---

## 17. Copias de seguridad y recuperación

### Exportar

Windows:

```powershell
docker exec pgvector-rag-db pg_dump -U vector_user -d vector_db -Fc -f /tmp/vector_db.dump
docker cp pgvector-rag-db:/tmp/vector_db.dump .\vector_db.dump
```

Linux:

```bash
docker exec pgvector-rag-db pg_dump -U vector_user -d vector_db -Fc -f /tmp/vector_db.dump
docker cp pgvector-rag-db:/tmp/vector_db.dump ./vector_db.dump
```

### Restaurar

La restauración debe probarse primero en una base separada. No sobrescribir producción sin un procedimiento aprobado.

```bash
docker cp ./vector_db.dump pgvector-rag-db:/tmp/vector_db.dump
docker exec pgvector-rag-db pg_restore -U vector_user -d vector_db --clean --if-exists /tmp/vector_db.dump
```

`--clean` es destructivo para los objetos restaurados. Requiere respaldo verificado y autorización.

---

## 18. Escalado y producción

Para evolucionar el proyecto:

1. Crear autenticación y autorización por usuario/tenant.
2. Separar ingesta en workers y cola de tareas.
3. Generar embeddings por lotes.
4. Añadir límites de tamaño y antivirus.
5. Implementar rate limiting.
6. Añadir métricas de latencia, errores, recall y uso de tokens.
7. Utilizar un proxy inverso y TLS.
8. Desplegar varias réplicas de FastAPI con pools dimensionados.
9. Usar migraciones versionadas con una herramienta como Alembic.
10. Añadir evaluación RAG con conjuntos de preguntas y respuestas esperadas.
11. Auditar el proveedor LLM y su política de retención.
12. Implementar backups automáticos y recuperación ante desastres.

---

## 19. Solución de problemas

### Puerto 5432 ocupado

```text
Bind for 0.0.0.0:5432 failed: port is already allocated
```

Cambiar `POSTGRES_PORT` a `5433` y recrear el contenedor.

### Backend desconectado en el frontend

- comprobar que Uvicorn esté activo;
- abrir `http://127.0.0.1:8000/health`;
- verificar que `frontend/app.js` apunte al puerto correcto;
- revisar CORS y firewall.

### Error de OpenRouter

- verificar `OPENROUTER_API_KEY`;
- reiniciar Uvicorn después de modificar `.env`;
- revisar rate limits del modelo gratuito;
- probar otro modelo o `openrouter/free`.

### Modelo de embeddings tarda al iniciar

La primera ejecución descarga el modelo. En Windows pueden aparecer advertencias sobre symlinks; afectan eficiencia de caché, no la generación de embeddings.

### Documento duplicado

El checksum ya existe. Eliminar o actualizar el documento de forma controlada antes de reingestar.

### Cambios de código no visibles

- usar Uvicorn con `--reload` en desarrollo;
- recargar el navegador con `Ctrl+F5`;
- reiniciar Uvicorn cuando cambia `.env`.

---

## 20. Lista de verificación antes de producción

- [ ] Cambiar todas las contraseñas y claves.
- [ ] Implementar autenticación de usuarios.
- [ ] Asociar documentos y citas a propietarios o tenants.
- [ ] Eliminar acceso CORS `null`.
- [ ] Servir frontend y API mediante HTTPS.
- [ ] Deshabilitar `--reload`.
- [ ] Proteger o deshabilitar Swagger.
- [ ] Configurar rate limiting.
- [ ] Limitar cargas de archivos.
- [ ] Configurar backups automáticos.
- [ ] Verificar restauración.
- [ ] Añadir monitoreo y alertas.
- [ ] Revisar logs y datos personales.
- [ ] Evaluar retención del proveedor LLM.
- [ ] Ejecutar pruebas de seguridad y prompt injection.
- [ ] Ejecutar pruebas de concurrencia de citas.
- [ ] Fijar versiones exactas en una imagen reproducible.

---

## 21. Resumen operacional

El proyecto combina dos tipos de capacidades:

1. **RAG documental:** recupera información autorizada desde pgvector y utiliza OpenRouter para redactar una respuesta.
2. **Operaciones transaccionales:** administra citas mediante reglas deterministas y transacciones PostgreSQL.

La separación es intencional: el LLM ayuda a conversar y responder, pero la base de datos y los servicios controlan las acciones que modifican estado. Esta regla debe conservarse durante toda evolución del proyecto.

