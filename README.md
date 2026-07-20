# PostgreSQL + pgvector RAG

> Actualización: el proyecto ahora incluye generación con OpenRouter y una interfaz de chatbot. Configure `OPENROUTER_API_KEY` en `.env`; el modelo predeterminado es `openrouter/free`.

## Privacidad y administración

El modo privado rechaza solicitudes para revelar prompts, instrucciones internas, contexto oculto o credenciales. El endpoint de chat no entrega el texto de los fragmentos recuperados y limita las referencias al nombre del documento. Las operaciones `POST/GET/DELETE /documents` y `POST /search` requieren el encabezado administrativo `X-Admin-Key`, cuyo valor se configura únicamente en `.env` mediante `ADMIN_API_KEY`. Nunca copie esa clave al frontend.

```powershell
$headers = @{ 'X-Admin-Key' = 'su-clave-administrativa' }
Invoke-RestMethod http://127.0.0.1:8000/documents -Headers $headers
```

## Chatbot RAG con OpenRouter

Obtenga una clave en OpenRouter y configure:

```dotenv
OPENROUTER_API_KEY=sk-or-v1-su-clave
OPENROUTER_MODEL=openrouter/free
```

Después de iniciar Docker y FastAPI, abra `http://localhost:8000`. El endpoint `POST /chat` acepta:

```json
{"message":"¿Qué dicen mis documentos?","history":[],"top_k":5,"category":null}
```

La respuesta contiene `answer`, el modelo gratuito que respondió y las fuentes recuperadas. `openrouter/free` tiene inferencia sin costo, pero requiere cuenta y clave; la disponibilidad y los límites de uso pueden variar, por lo que está pensado principalmente para aprendizaje y uso de bajo volumen.

Backend listo para almacenar PDF, TXT y Markdown, fragmentarlos, generar embeddings normalizados de 384 dimensiones con `all-MiniLM-L6-v2` y recuperar contexto por similitud coseno. La API devuelve contexto; deliberadamente no llama a ningún LLM, por lo que puede integrarse después con OpenAI, Claude, Gemini, Ollama u OpenRouter.

## Inicio rápido

Requiere Docker y Python 3.12+.

```powershell
Copy-Item .env.example .env
docker compose up -d
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m scripts.init_db
uvicorn src.api.main:app --reload
```

La primera ejecución descarga el modelo desde Hugging Face. Cambie la contraseña de `.env` antes de desplegar. Swagger queda en `http://localhost:8000/docs` y el estado en `GET /health`.

## Uso

```powershell
python -m scripts.ingest .\data --metadata '{"category":"manual"}'
python -m scripts.search "¿Cómo funciona pgvector?" --top-k 5
python -m scripts.seed
python -m scripts.rebuild_embeddings
python -m scripts.benchmark "búsqueda semántica" --runs 50
```

También puede subir un archivo con `POST /documents` (`multipart/form-data`: `file` y `metadata` como JSON), listar con `GET /documents`, borrar con `DELETE /documents/{id}` y buscar con:

```json
{"query":"índices vectoriales","top_k":5,"category":"manual","metadata":{"language":"es"}}
```

## Diseño

`documents` conserva identidad y metadatos del archivo; `chunks` contiene texto, posición y JSONB; `embeddings` desacopla el vector y el modelo para permitir reconstrucciones. Las eliminaciones usan cascada. Servicios y proveedores dependen de interfaces/repositories, lo que permite sustituir el modelo o almacenamiento sin acoplar la API. La salida de búsqueda (`score`, `text`, `metadata`, `document_id`) es el contexto listo para un orquestador RAG.

## Distancias e índices

- `<->`: distancia euclídea L2.
- `<=>`: distancia coseno. El sistema devuelve `1 - distancia` como similitud.
- `<#>`: producto interno negativo; se niega para mostrar un score mayor-es-mejor.

Los ejemplos completos están en `sql/examples.sql`. HNSW ofrece alta recuperación y consultas rápidas sin fase de entrenamiento, acepta inserciones dinámicas, pero tarda más en construirse y consume más memoria. IVFFlat usa menos memoria y construye más rápido para conjuntos grandes y estables, pero requiere datos previos, `ANALYZE` y ajuste de `lists`/`ivfflat.probes`; su recall suele ser inferior. Mantenga solo el índice que use:

```powershell
python -m scripts.reindex --type hnsw
python -m scripts.reindex --type ivfflat --lists 100
```

Como regla inicial para IVFFlat use `lists ≈ filas / 1000` hasta un millón de filas y `sqrt(filas)` después; mida siempre con datos propios.

## Modelos y dimensiones

El esquema declara `VECTOR(384)`, compatible con `all-MiniLM-L6-v2`. Para otro modelo cambie `EMBEDDING_MODEL`; si su dimensión difiere, migre `VECTOR(384)`, reconstruya embeddings y recree el índice. El proveedor siempre normaliza. Para un proveedor externo implemente el protocolo `EmbeddingProvider` y inyéctelo en `DocumentService`.

## Pruebas

```powershell
pytest tests/unit
$env:RUN_INTEGRATION='1'
$env:DATABASE_URL='postgresql://vector_user:change_me@localhost:5432/vector_db'
pytest -m integration
```

## Producción y escalado

- No publique PostgreSQL; use red privada, secretos gestionados, TLS, backups y un usuario de privilegios mínimos.
- Ejecute varias réplicas stateless de FastAPI y dimensione el pool por réplica.
- Procese ingestas grandes mediante una cola; genere embeddings por lotes y aplique límites de tamaño.
- Ajuste HNSW (`hnsw.ef_search`) o IVFFlat (`ivfflat.probes`) con el benchmark; vigile latencia, recall, memoria y bloat.
- Particione por tenant o colección cuando el filtro sea selectivo, use réplicas de lectura y considere almacenamiento especializado al superar la capacidad operativa de un solo clúster.
- Fije versiones exactas y analice vulnerabilidades en CI antes de crear imágenes inmutables.

## Estructura

La configuración está en `src/config`, PostgreSQL en `src/database`, modelos en `src/models`, embeddings en `src/embeddings`, persistencia en `src/repositories`, casos de uso en `src/services`, HTTP en `src/api`, SQL en `sql`, operaciones en `scripts` y pruebas en `tests`.
