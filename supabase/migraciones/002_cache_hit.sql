-- ============================================================
--  002 - Marca de cache en las etapas
--
--  Sin esta columna, una etapa servida por cache y una etapa que llamo al
--  modelo se distinguen solo por 'tokens = 0', que es una inferencia, no un
--  dato. P02 pide demostrar que el segundo run identico no llamo al LLM: con
--  la marca es una consulta, sin ella es una interpretacion.
--
--  Las 94 filas migradas en T2.2 quedan en false: se escribieron antes de que
--  el ejecutor auditara los cache hits, asi que no se sabe. false es la
--  lectura conservadora (asumir que llamaron al modelo).
-- ============================================================

alter table public.etapas_ejecucion
  add column if not exists cache_hit boolean not null default false;
