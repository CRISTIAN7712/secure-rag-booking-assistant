-- Distancia euclídea (L2): menor es mejor.
SELECT chunk_id, embedding <-> $1::vector AS distance FROM embeddings ORDER BY embedding <-> $1::vector LIMIT 10;
-- Distancia coseno: score de similitud = 1 - distancia.
SELECT chunk_id, 1 - (embedding <=> $1::vector) AS score FROM embeddings ORDER BY embedding <=> $1::vector LIMIT 10;
-- Producto interno negativo: menor es mejor; ideal con vectores normalizados.
SELECT chunk_id, -(embedding <#> $1::vector) AS inner_product FROM embeddings ORDER BY embedding <#> $1::vector LIMIT 10;
-- Filtro JSONB/categoría combinado con búsqueda vectorial.
SELECT c.document_id, c.text, c.metadata, 1 - (e.embedding <=> $1::vector) AS score
FROM embeddings e JOIN chunks c ON c.id = e.chunk_id
WHERE c.metadata @> '{"category":"manual"}'::jsonb
ORDER BY e.embedding <=> $1::vector LIMIT 10;

