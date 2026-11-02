-- ============================================================================
-- AJ6-C (rodada 2) — Limpeza cirúrgica do banco `pautaon` (unidades de teste)
-- ============================================================================
-- ALVO   : unidades 3, 6, 7, 8; alunos 1452–1456; cursos 15–18;
--          período letivo 3; usuários 105 e 107.
-- NUNCA  : tocar NIT (id 1) e MGB (id 2) — protegidas por asserts e cláusulas.
-- LEITURA: este script foi validado apenas com SELECT na rodada 2;
--          a primeira execução DEVE terminar em ROLLBACK (etapa 0).
--
-- Etapa 0 (obrigatória antes de qualquer COMMIT):
--   psql "<DSN do pautaon>" -f scripts/limpar_unidades_teste_pautaon.sql
--   → confira os NOTICEs da varredura catálogo e os RETURNING de cada DELETE.
--   Só altere o ROLLBACK final para COMMIT depois de conferir tudo, e só
--   depois de backup: pg_dump -Fc -f backup_pautaon_<data>.dump pautaon
-- ============================================================================

\set ON_ERROR_STOP on
BEGIN;

-- ----------------------------------------------------------------------------
-- 1. ÂNCORAS — alvo materializado numa temp table (evita duplicar listas)
-- ----------------------------------------------------------------------------
CREATE TEMP TABLE _alvo (
    tipo   text NOT NULL,   -- unidade | aluno | curso | periodo | user
    id     int  NOT NULL,   -- ids se repetem entre tipos → chave composta
    unico  text,            -- nome/identificador para conferência visual
    PRIMARY KEY (tipo, id)
) ON COMMIT DROP;

INSERT INTO _alvo (tipo, id, unico) VALUES
    ('unidade', 3, NULL), ('unidade', 6, NULL), ('unidade', 7, NULL), ('unidade', 8, NULL),
    ('aluno', 1452, NULL), ('aluno', 1453, NULL), ('aluno', 1454, NULL),
    ('aluno', 1455, NULL), ('aluno', 1456, NULL),
    ('curso', 15, NULL), ('curso', 16, NULL), ('curso', 17, NULL), ('curso', 18, NULL),
    ('periodo', 3, NULL),
    ('user', 105, NULL), ('user', 107, NULL);

-- Proteção absoluta: NIT/MGB jamais entram no alvo
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM _alvo WHERE tipo = 'unidade' AND id IN (1, 2)) THEN
        RAISE EXCEPTION 'TRAVA: alvo contém NIT (1) ou MGB (2)';
    END IF;
    -- As 4 unidades de teste têm de existir agora; se não existirem,
    -- alguém já limpou ou o banco é outro → aborta.
    IF (SELECT count(*) FROM _alvo a JOIN unidade u ON u.id = a.id AND a.tipo = 'unidade') <> 4 THEN
        RAISE EXCEPTION 'TRAVA: esperava encontrar as unidades 3, 6, 7, 8 em unidade';
    END IF;
    -- NIT e MGB têm de continuar vivas
    IF (SELECT count(*) FROM unidade WHERE id IN (1, 2)) <> 2 THEN
        RAISE EXCEPTION 'TRAVA: NIT/MGB não encontradas — banco inesperado';
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 2. VARREDURA CATÁLOGO-DRIVEN — toda FK para unidade/user/aluno que aponta
--    para o alvo, em TODAS as tabelas do esquema (nada fica invisível).
--    Referência fora das famílias conhecidas → EXCEPTION (bloqueia limpeza).
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    r    record;
    n    bigint;
    tab  text;
    total_ref bigint := 0;
    permitido text[] := ARRAY[
        -- famílias das unidades/alunos/cursos/períodos/usuários de teste
        'aluno','curso','periodo_letivo','user','unidade',
        'endereco_aluno','perfil_diversidade','perfil_socioeconomico',
        'responsavel_aluno','situacao_escolar','inscricoes','frequencia',
        'transferencia','tema_aula','registro_aula','turma','turma_curso',
        'turma_curso_horario','dia_bloqueado','dia_bloqueado_turma',
        'registro','atendimento','conselho_classe','conselho_resposta',
        'periodo_conselho','respostas_formulario','log_acao',
        'nivel','valor_esportista','instrutores'
    ];
BEGIN
    FOR r IN
        SELECT c.conrelid::regclass::text AS tabela,
               a.attname                  AS coluna,
               confconf.relname           AS ref
        FROM pg_constraint c
        JOIN pg_attribute a      ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey) AND array_length(c.conkey,1) = 1
        JOIN pg_class     confconf ON confconf.oid = c.confrelid
        WHERE c.contype = 'f'
          AND confconf.relname IN ('unidade','user','aluno','curso','periodo_letivo')
        ORDER BY 1, 2
    LOOP
        -- conrelid::regclass::text pode vir citado ("user"); %I adiciona as aspas
        tab := trim(both '"' FROM r.tabela);
        -- tipo do alvo: período_letivo está gravado como 'periodo' na temp table
        n := 0;
        IF NOT EXISTS (SELECT 1 FROM _alvo WHERE tipo = CASE r.ref WHEN 'periodo_letivo' THEN 'periodo' ELSE r.ref END)
        THEN
            CONTINUE;
        END IF;
        EXECUTE format(
            'SELECT count(*) FROM %I t WHERE t.%I IN (SELECT id FROM _alvo a WHERE a.tipo = %L AND a.id = t.%I)'
            , tab, r.coluna,
              CASE r.ref WHEN 'periodo_letivo' THEN 'periodo' ELSE r.ref END, r.coluna
        ) INTO n;

        IF n > 0 THEN
            total_ref := total_ref + n;
            IF NOT (tab = ANY (permitido)) THEN
                RAISE EXCEPTION 'BLOQUEIO: %.% aponta para o alvo (% linhas) e não está na lista conhecida — revisar antes de limpar',
                    tab, r.coluna, n;
            END IF;
            RAISE NOTICE 'catálogo: %.% -> % : % linha(s) no alvo', tab, r.coluna, r.ref, n;
        END IF;
    END LOOP;
    RAISE NOTICE 'catálogo: total de referências ao alvo = %', total_ref;
END $$;

-- ----------------------------------------------------------------------------
-- 3. ASSERTS DE CONTAGEM — valores congelados na sondagem SELECT-only da
--    rodada 2 (docs/Relatórios/AJ6C_UnidadesDeTeste.md). Qualquer divergência
--    aborta antes do primeiro DELETE.
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    real     int;
BEGIN
    -- (unidades, esperado, id-alvo)
    SELECT count(*) INTO real FROM unidade WHERE id IN (SELECT id FROM _alvo WHERE tipo='unidade');
    IF real <> 4 THEN RAISE EXCEPTION 'unidade no alvo: esperado 4, encontrado %', real; END IF;

    SELECT count(*) INTO real FROM aluno WHERE id IN (SELECT id FROM _alvo WHERE tipo='aluno');
    IF real <> 5 THEN RAISE EXCEPTION 'aluno no alvo: esperado 5, encontrado %', real; END IF;

    -- nenhum aluno do alvo tem frequência lançada
    SELECT count(*) INTO real FROM frequencia WHERE aluno_id IN (SELECT id FROM _alvo WHERE tipo='aluno');
    IF real <> 0 THEN RAISE EXCEPTION 'BLOQUEIO: % linha(s) de frequencia penduradas nos alunos alvo', real; END IF;

    -- nenhum aluno do alvo tem inscrição
    SELECT count(*) INTO real FROM inscricoes WHERE aluno_id IN (SELECT id FROM _alvo WHERE tipo='aluno');
    IF real <> 0 THEN RAISE EXCEPTION 'BLOQUEIO: % inscrição(ões) pendurada(s) nos alunos alvo', real; END IF;

    -- cursos: só os 4 do alvo, e nenhum com turma
    SELECT count(*) INTO real FROM curso WHERE id IN (SELECT id FROM _alvo WHERE tipo='curso');
    IF real <> 4 THEN RAISE EXCEPTION 'curso no alvo: esperado 4, encontrado %', real; END IF;
    SELECT count(*) INTO real FROM turma_curso WHERE curso_id IN (SELECT id FROM _alvo WHERE tipo='curso');
    IF real <> 0 THEN RAISE EXCEPTION 'BLOQUEIO: % oferta(s) pendurada(s) nos cursos alvo', real; END IF;
    SELECT count(*) INTO real FROM tema_aula WHERE curso_id IN (SELECT id FROM _alvo WHERE tipo='curso');
    IF real <> 0 THEN RAISE EXCEPTION 'BLOQUEIO: % tema(s) de aula pendurado(s) nos cursos alvo', real; END IF;

    -- período letivo 3: sem turma
    SELECT count(*) INTO real FROM turma WHERE periodo_letivo_id = 3;
    IF real <> 0 THEN RAISE EXCEPTION 'BLOQUEIO: % turma(s) usando o período alvo', real; END IF;
    SELECT count(*) INTO real FROM dia_bloqueado WHERE periodo_letivo_id = 3;
    IF real <> 0 THEN RAISE EXCEPTION 'BLOQUEIO: % dia(s) bloqueado(s) no período alvo', real; END IF;

    -- usuários 105/107: sem linhas em tabelas de operação
    SELECT count(*) INTO real FROM frequencia WHERE autor_id IN (SELECT id FROM _alvo WHERE tipo='user');
    IF real <> 0 THEN RAISE EXCEPTION 'BLOQUEIO: % frequencia(s) autoras dos usuários alvo', real; END IF;
    SELECT count(*) INTO real FROM registro_aula WHERE instrutor_id IN (SELECT id FROM _alvo WHERE tipo='user');
    IF real <> 0 THEN RAISE EXCEPTION 'BLOQUEIO: % registro(s) de aula dos usuários alvo', real; END IF;
    SELECT count(*) INTO real FROM turma WHERE professor_id IN (SELECT id FROM _alvo WHERE tipo='user');
    IF real <> 0 THEN RAISE EXCEPTION 'BLOQUEIO: % turma(s) com professor dos usuários alvo', real; END IF;
    -- log_acao.usuario_id é histórico: preservado (não se limpa auditoria)
END $$;

-- ----------------------------------------------------------------------------
-- 4. EXCLUSÕES — ordem inversa das dependências; cada DELETE devolve linhas
-- ----------------------------------------------------------------------------
-- 4.1 filhos diretos de aluno
DELETE FROM endereco_aluno        WHERE aluno_id IN (SELECT id FROM _alvo WHERE tipo='aluno') RETURNING id, aluno_id;
DELETE FROM perfil_diversidade    WHERE aluno_id IN (SELECT id FROM _alvo WHERE tipo='aluno') RETURNING id, aluno_id;
DELETE FROM perfil_socioeconomico WHERE aluno_id IN (SELECT id FROM _alvo WHERE tipo='aluno') RETURNING id, aluno_id;
DELETE FROM responsavel_aluno     WHERE aluno_id IN (SELECT id FROM _alvo WHERE tipo='aluno') RETURNING id, aluno_id;
DELETE FROM situacao_escolar      WHERE aluno_id IN (SELECT id FROM _alvo WHERE tipo='aluno') RETURNING id, aluno_id;

-- 4.2 alunos (cruzam FK dupla: unidade alvo E lista congelada)
DELETE FROM aluno
WHERE id IN (SELECT id FROM _alvo WHERE tipo='aluno')
  AND unidade_id IN (3, 6, 7, 8)
  AND unidade_id NOT IN (1, 2)
RETURNING id, unidade_id;

-- 4.3 usuários (preserva auditoria; nome não revelado aqui por privacidade)
DELETE FROM "user"
WHERE id IN (SELECT id FROM _alvo WHERE tipo='user')
  AND unidade_id IN (3, 6, 7, 8)
  AND unidade_id NOT IN (1, 2)
RETURNING id, role, unidade_id;

-- 4.4 cursos e período letivo das unidades de teste
DELETE FROM curso
WHERE id IN (SELECT id FROM _alvo WHERE tipo='curso')
  AND unidade_id IN (3, 6, 7, 8) AND unidade_id NOT IN (1, 2)
RETURNING id, unidade_id;

DELETE FROM periodo_letivo
WHERE id = 3
  AND unidade_id IN (3, 6, 7, 8) AND unidade_id NOT IN (1, 2)
RETURNING id, unidade_id;

-- 4.5 unidades de teste (proteção dupla de NIT/MGB: id e nome)
DELETE FROM unidade
WHERE id IN (3, 6, 7, 8)
  AND id NOT IN (1, 2)
RETURNING id;  -- nome propositalmente fora: privacidade nos logs

-- ----------------------------------------------------------------------------
-- 5. CONFERÊNCIA PÓS-LIMPEZA
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    real int;
BEGIN
    SELECT count(*) INTO real FROM unidade WHERE id IN (3, 6, 7, 8);
    IF real <> 0 THEN RAISE EXCEPTION 'pós: restaram % unidade(s) alvo', real; END IF;
    SELECT count(*) INTO real FROM unidade WHERE id IN (1, 2);
    IF real <> 2 THEN RAISE EXCEPTION 'pós: NIT/MGB não preservadas: %', real; END IF;
    SELECT count(*) INTO real FROM aluno WHERE id IN (1452,1453,1454,1455,1456);
    IF real <> 0 THEN RAISE EXCEPTION 'pós: restaram % aluno(s) alvo', real; END IF;
    RAISE NOTICE 'pós: limpeza consistente (dentro da transação)';
END $$;

-- SELECT id, nome FROM unidade ORDER BY id;  -- visual: esperado só NIT e MGB

-- ============================================================================
-- FINALIZAÇÃO — manter ROLLBACK na primeira execução; trocar para COMMIT
-- somente após conferir NOTICEs + RETURNING contra a tabela do relatório.
-- ============================================================================
ROLLBACK;
-- COMMIT;
