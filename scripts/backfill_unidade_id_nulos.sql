\set ON_ERROR_STOP on

-- Execute only against a disposable clone of pautaon. The expected counts
-- intentionally fail closed if the source dataset has changed.
BEGIN;

DO $$
DECLARE
    qtd_frequencia bigint;
    qtd_registro_aula bigint;
    qtd_conselho_resposta bigint;
BEGIN
    SELECT COUNT(*) INTO qtd_frequencia
    FROM public.frequencia
    WHERE unidade_id IS NULL;
    IF qtd_frequencia <> 52 THEN
        RAISE EXCEPTION 'frequencia NULL count expected 52, got %', qtd_frequencia;
    END IF;

    SELECT COUNT(*) INTO qtd_registro_aula
    FROM public.registro_aula
    WHERE unidade_id IS NULL;
    IF qtd_registro_aula <> 4 THEN
        RAISE EXCEPTION 'registro_aula NULL count expected 4, got %', qtd_registro_aula;
    END IF;

    SELECT COUNT(*) INTO qtd_conselho_resposta
    FROM public.conselho_resposta
    WHERE unidade_id IS NULL;
    IF qtd_conselho_resposta <> 78 THEN
        RAISE EXCEPTION 'conselho_resposta NULL count expected 78, got %',
            qtd_conselho_resposta;
    END IF;

    IF EXISTS (
        SELECT f.id
        FROM public.frequencia f
        LEFT JOIN public.turma t ON t.id = f.turma_id
        LEFT JOIN public.turma_curso tc ON tc.id = f.turma_curso_id
        WHERE f.unidade_id IS NULL
        GROUP BY f.id
        HAVING COUNT(DISTINCT t.unidade_id) <> 1
            OR BOOL_OR(
                tc.id IS NOT NULL
                AND (tc.turma_id <> t.id
                     OR tc.unidade_id IS DISTINCT FROM t.unidade_id)
            )
    ) THEN
        RAISE EXCEPTION 'frequencia has NULL or ambiguous parent unit';
    END IF;

    IF EXISTS (
        SELECT r.id
        FROM public.registro_aula r
        LEFT JOIN public.turma t ON t.id = r.turma_id
        LEFT JOIN public.turma_curso tc ON tc.id = r.turma_curso_id
        WHERE r.unidade_id IS NULL
        GROUP BY r.id
        HAVING COUNT(DISTINCT t.unidade_id) <> 1
            OR BOOL_OR(
                tc.id IS NOT NULL
                AND (tc.turma_id <> t.id
                     OR tc.unidade_id IS DISTINCT FROM t.unidade_id)
            )
    ) THEN
        RAISE EXCEPTION 'registro_aula has NULL or ambiguous parent unit';
    END IF;

    IF EXISTS (
        SELECT r.id
        FROM public.conselho_resposta r
        LEFT JOIN public.conselho_classe c ON c.id = r.conselho_id
        LEFT JOIN public.turma t ON t.id = c.turma_id
        LEFT JOIN public.turma_curso tc ON tc.id = c.turma_curso_id
        WHERE r.unidade_id IS NULL
        GROUP BY r.id
        HAVING COUNT(DISTINCT t.unidade_id) <> 1
            OR BOOL_OR(
                tc.id IS NOT NULL
                AND (tc.turma_id <> t.id
                     OR tc.unidade_id IS DISTINCT FROM t.unidade_id)
            )
    ) THEN
        RAISE EXCEPTION 'conselho_resposta has NULL or ambiguous parent unit';
    END IF;
END
$$;

CREATE TEMP TABLE aj10_frequencia_unidades_preenchidas AS
SELECT id, unidade_id
FROM public.frequencia
WHERE unidade_id IS NOT NULL;

CREATE TEMP TABLE aj10_registro_aula_unidades_preenchidas AS
SELECT id, unidade_id
FROM public.registro_aula
WHERE unidade_id IS NOT NULL;

CREATE TEMP TABLE aj10_conselho_resposta_unidades_preenchidas AS
SELECT id, unidade_id
FROM public.conselho_resposta
WHERE unidade_id IS NOT NULL;

UPDATE public.frequencia f
SET unidade_id = t.unidade_id
FROM public.turma t
WHERE f.unidade_id IS NULL
  AND t.id = f.turma_id
RETURNING f.id;

UPDATE public.registro_aula r
SET unidade_id = t.unidade_id
FROM public.turma t
WHERE r.unidade_id IS NULL
  AND t.id = r.turma_id
RETURNING r.id;

UPDATE public.conselho_resposta r
SET unidade_id = t.unidade_id
FROM public.conselho_classe c
JOIN public.turma t ON t.id = c.turma_id
WHERE r.unidade_id IS NULL
  AND c.id = r.conselho_id
RETURNING r.id;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.frequencia WHERE unidade_id IS NULL
    ) THEN
        RAISE EXCEPTION 'frequencia still has NULL unidade_id rows';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.registro_aula WHERE unidade_id IS NULL
    ) THEN
        RAISE EXCEPTION 'registro_aula still has NULL unidade_id rows';
    END IF;
    IF EXISTS (
        SELECT 1 FROM public.conselho_resposta WHERE unidade_id IS NULL
    ) THEN
        RAISE EXCEPTION 'conselho_resposta still has NULL unidade_id rows';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM aj10_frequencia_unidades_preenchidas before_row
        LEFT JOIN public.frequencia current_row ON current_row.id = before_row.id
        WHERE current_row.id IS NULL
           OR current_row.unidade_id IS DISTINCT FROM before_row.unidade_id
    ) THEN
        RAISE EXCEPTION 'pre-filled frequencia unidade_id changed';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM aj10_registro_aula_unidades_preenchidas before_row
        LEFT JOIN public.registro_aula current_row ON current_row.id = before_row.id
        WHERE current_row.id IS NULL
           OR current_row.unidade_id IS DISTINCT FROM before_row.unidade_id
    ) THEN
        RAISE EXCEPTION 'pre-filled registro_aula unidade_id changed';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM aj10_conselho_resposta_unidades_preenchidas before_row
        LEFT JOIN public.conselho_resposta current_row ON current_row.id = before_row.id
        WHERE current_row.id IS NULL
           OR current_row.unidade_id IS DISTINCT FROM before_row.unidade_id
    ) THEN
        RAISE EXCEPTION 'pre-filled conselho_resposta unidade_id changed';
    END IF;
END
$$;

-- The unitless student has no enrollment, so there is no unique parent unit.
-- Do not update aluno in this backfill.

-- To persist on an explicitly approved disposable database, comment ROLLBACK
-- and uncomment COMMIT after reviewing the returned IDs and assertions.
ROLLBACK;
-- COMMIT;
