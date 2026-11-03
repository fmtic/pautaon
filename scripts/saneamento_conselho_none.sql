-- ============================================================================
-- AJ7-B — Saneamento do texto literal "None" nos campos do conselho
-- ============================================================================
-- ORIGEM  : bug de renderização (fix `fix(conselho): ...` da série AJ7-B) que
--           mostrava "None" nos textareas e, se re-salvo sem edição, gravava a
--           string literal 'None' em `conselho_resposta.observacao`/`resposta`.
-- AUDITORIA (2026-11-03, SELECT-only, .tmp/aj7b_auditoria.py):
--   pautaon        — exatamente 'None': 0 em todos os campos (78 respostas,
--                    45 conselhos, 4 ofertas; 78 respostas com observacao NULL)
--   pautaon_ensaio — exatamente 'None': 0 (6 respostas, 5 conselhos, 12 ofertas;
--                    6 respostas com observacao NULL)
--   Nenhum dado real está contaminado HOJE; o script é preventivo e fica
--   pronto caso algum lançamento salvo antes do fix tenha gravado 'None'.
--
-- COMO USAR (somente o responsável, após backup):
--   1. pg_dump -Fc -f backup_pautaon_<data>.dump pautaon  (idem pautaon_ensaio)
--   2. psql "<DSN>" -f scripts/saneamento_conselho_none.sql
--      → a execução termina em ROLLBACK por padrão; leia os RETURNING.
--   3. Se as contagens conferirem, troque o ROLLBACK final por COMMIT.
--
-- CONTAGENS ESPERADAS: congeladas nos DO $$ de assertion abaixo (0 = nada
-- contaminado; os UPDATEs simplesmente não encontram linhas). Qualquer
-- divergência entre o esperado e o encontrado aborta antes do primeiro UPDATE.
-- ============================================================================

\set ON_ERROR_STOP on
BEGIN;

-- ----------------------------------------------------------------------------
-- 1. ASSERTS DE CONTAGEM — valores congelados na sondagem SELECT-only.
--    `exatamente 'None'` = btrim(campo) = 'None' (conteúdo só "None", com ou
--    sem espaços). JSON de parecer ('{"...": "None"}') é varrido à parte.
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    n int;
    esperado int := 0;  -- auditoria 2026-11-03: nada contaminado
BEGIN
    SELECT count(*) INTO n FROM conselho_resposta WHERE btrim(resposta) = 'None';
    IF n <> esperado THEN RAISE EXCEPTION 'conselho_resposta.resposta = None: esperado %, encontrado %', esperado, n; END IF;

    SELECT count(*) INTO n FROM conselho_resposta WHERE btrim(observacao) = 'None';
    IF n <> esperado THEN RAISE EXCEPTION 'conselho_resposta.observacao = None: esperado %, encontrado %', esperado, n; END IF;

    SELECT count(*) INTO n FROM conselho_classe WHERE btrim(observacao) = 'None';
    IF n <> esperado THEN RAISE EXCEPTION 'conselho_classe.observacao = None: esperado %, encontrado %', esperado, n; END IF;

    SELECT count(*) INTO n FROM turma_curso
      WHERE btrim(avaliacao_inicial) = 'None'
         OR btrim(avaliacao_percurso) = 'None'
         OR btrim(avaliacao_final) = 'None';
    IF n <> esperado THEN RAISE EXCEPTION 'turma_curso.avaliacao_* = None: esperado %, encontrado %', esperado, n; END IF;

    SELECT count(*) INTO n FROM turma_curso
      WHERE avaliacao_inicial  LIKE '%"None"%'
         OR avaliacao_percurso LIKE '%"None"%'
         OR avaliacao_final    LIKE '%"None"%';
    IF n <> esperado THEN RAISE EXCEPTION 'turma_curso.avaliacao_* JSON com valor "None": esperado %, encontrado %', esperado, n; END IF;

    SELECT count(*) INTO n FROM turma
      WHERE btrim(avaliacao_inicial) = 'None'
         OR btrim(avaliacao_percurso) = 'None'
         OR btrim(avaliacao_final) = 'None';
    IF n <> esperado THEN RAISE EXCEPTION 'turma.avaliacao_* = None: esperado %, encontrado %', esperado, n; END IF;

    SELECT count(*) INTO n FROM turma
      WHERE avaliacao_inicial  LIKE '%"None"%'
         OR avaliacao_percurso LIKE '%"None"%'
         OR avaliacao_final    LIKE '%"None"%';
    IF n <> esperado THEN RAISE EXCEPTION 'turma.avaliacao_* JSON com valor "None": esperado %, encontrado %', esperado, n; END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 2. SANEAMENTO — campo de texto que é apenas "None" volta a NULL (o estado
--    "sem observação" anterior ao bug); nunca '' mágico, nunca outro valor.
-- ----------------------------------------------------------------------------
UPDATE conselho_resposta
   SET resposta = NULL
 WHERE btrim(resposta) = 'None'
RETURNING id, aluno_id, pergunta_id;

UPDATE conselho_resposta
   SET observacao = NULL
 WHERE btrim(observacao) = 'None'
RETURNING id, aluno_id, pergunta_id;

UPDATE conselho_classe
   SET observacao = NULL
 WHERE btrim(observacao) = 'None'
RETURNING id, aluno_id, etapa;

UPDATE turma
   SET avaliacao_inicial = NULL
 WHERE btrim(avaliacao_inicial) = 'None'
RETURNING id, unidade_id;

UPDATE turma
   SET avaliacao_percurso = NULL
 WHERE btrim(avaliacao_percurso) = 'None'
RETURNING id, unidade_id;

UPDATE turma
   SET avaliacao_final = NULL
 WHERE btrim(avaliacao_final) = 'None'
RETURNING id, unidade_id;

-- ----------------------------------------------------------------------------
-- 3. CONFERÊNCIA PÓS-SANEAMENTO — nenhum texto de conselho pode rester 'None'.
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    n int;
BEGIN
    SELECT count(*) INTO n FROM conselho_resposta
      WHERE btrim(resposta) = 'None' OR btrim(observacao) = 'None';
    IF n <> 0 THEN RAISE EXCEPTION 'pós: restaram % resposta(s) com None', n; END IF;

    SELECT count(*) INTO n FROM conselho_classe WHERE btrim(observacao) = 'None';
    IF n <> 0 THEN RAISE EXCEPTION 'pós: restaram % conselho(s) classe com observacao None', n; END IF;

    SELECT count(*) INTO n FROM turma
      WHERE btrim(avaliacao_inicial) = 'None'
         OR btrim(avaliacao_percurso) = 'None'
         OR btrim(avaliacao_final) = 'None';
    IF n <> 0 THEN RAISE EXCEPTION 'pós: restaram % turma(s) com avaliacao_* None', n; END IF;
    RAISE NOTICE 'pós: nenhum campo de conselho com None (dentro da transação)';
END $$;

-- ============================================================================
-- FINALIZAÇÃO — manter ROLLBACK na primeira execução; trocar para COMMIT
-- somente após conferir os RETURNING contra as contagens do relatório
-- docs/Relatórios/AJ7B_NoneConselho.md.
-- ============================================================================
ROLLBACK;
-- COMMIT;
