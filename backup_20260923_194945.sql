--
-- PostgreSQL database dump
--

-- Dumped from database version 17.2
-- Dumped by pg_dump version 17.2

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER TABLE IF EXISTS ONLY public."user" DROP CONSTRAINT IF EXISTS user_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.turma DROP CONSTRAINT IF EXISTS turma_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.turma DROP CONSTRAINT IF EXISTS turma_professor_id_fkey;
ALTER TABLE IF EXISTS ONLY public.turma DROP CONSTRAINT IF EXISTS turma_periodo_letivo_id_fkey;
ALTER TABLE IF EXISTS ONLY public.turma DROP CONSTRAINT IF EXISTS turma_curso_id_fkey;
ALTER TABLE IF EXISTS ONLY public.transferencia DROP CONSTRAINT IF EXISTS transferencia_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.transferencia DROP CONSTRAINT IF EXISTS transferencia_turma_origem_id_fkey;
ALTER TABLE IF EXISTS ONLY public.transferencia DROP CONSTRAINT IF EXISTS transferencia_turma_destino_id_fkey;
ALTER TABLE IF EXISTS ONLY public.transferencia DROP CONSTRAINT IF EXISTS transferencia_aluno_id_fkey;
ALTER TABLE IF EXISTS ONLY public.tema_aula DROP CONSTRAINT IF EXISTS tema_aula_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.tema_aula DROP CONSTRAINT IF EXISTS tema_aula_turma_id_fkey;
ALTER TABLE IF EXISTS ONLY public.tema_aula DROP CONSTRAINT IF EXISTS tema_aula_curso_id_fkey;
ALTER TABLE IF EXISTS ONLY public.situacao_escolar DROP CONSTRAINT IF EXISTS situacao_escolar_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.situacao_escolar DROP CONSTRAINT IF EXISTS situacao_escolar_aluno_id_fkey;
ALTER TABLE IF EXISTS ONLY public.respostas_formulario DROP CONSTRAINT IF EXISTS respostas_formulario_usuario_id_fkey;
ALTER TABLE IF EXISTS ONLY public.respostas_formulario DROP CONSTRAINT IF EXISTS respostas_formulario_aluno_id_fkey;
ALTER TABLE IF EXISTS ONLY public.registro DROP CONSTRAINT IF EXISTS registro_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.registro DROP CONSTRAINT IF EXISTS registro_educador_id_fkey;
ALTER TABLE IF EXISTS ONLY public.registro_aula DROP CONSTRAINT IF EXISTS registro_aula_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.registro_aula DROP CONSTRAINT IF EXISTS registro_aula_turma_id_fkey;
ALTER TABLE IF EXISTS ONLY public.registro_aula DROP CONSTRAINT IF EXISTS registro_aula_tema_id_fkey;
ALTER TABLE IF EXISTS ONLY public.registro_aula DROP CONSTRAINT IF EXISTS registro_aula_instrutor_id_fkey;
ALTER TABLE IF EXISTS ONLY public.periodo_letivo DROP CONSTRAINT IF EXISTS periodo_letivo_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.periodo_conselho DROP CONSTRAINT IF EXISTS periodo_conselho_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.periodo_conselho DROP CONSTRAINT IF EXISTS periodo_conselho_periodo_letivo_id_fkey;
ALTER TABLE IF EXISTS ONLY public.nivel DROP CONSTRAINT IF EXISTS nivel_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.log_acao DROP CONSTRAINT IF EXISTS log_acao_usuario_id_fkey;
ALTER TABLE IF EXISTS ONLY public.log_acao DROP CONSTRAINT IF EXISTS log_acao_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.inscricoes DROP CONSTRAINT IF EXISTS inscricoes_turma_id_fkey;
ALTER TABLE IF EXISTS ONLY public.inscricoes DROP CONSTRAINT IF EXISTS inscricoes_aluno_id_fkey;
ALTER TABLE IF EXISTS ONLY public.frequencia DROP CONSTRAINT IF EXISTS frequencia_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.frequencia DROP CONSTRAINT IF EXISTS frequencia_turma_id_fkey;
ALTER TABLE IF EXISTS ONLY public.frequencia DROP CONSTRAINT IF EXISTS frequencia_aluno_id_fkey;
ALTER TABLE IF EXISTS ONLY public.dia_bloqueado DROP CONSTRAINT IF EXISTS dia_bloqueado_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.dia_bloqueado_turma DROP CONSTRAINT IF EXISTS dia_bloqueado_turma_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.dia_bloqueado_turma DROP CONSTRAINT IF EXISTS dia_bloqueado_turma_turma_id_fkey;
ALTER TABLE IF EXISTS ONLY public.dia_bloqueado_turma DROP CONSTRAINT IF EXISTS dia_bloqueado_turma_criado_por_id_fkey;
ALTER TABLE IF EXISTS ONLY public.dia_bloqueado DROP CONSTRAINT IF EXISTS dia_bloqueado_periodo_letivo_id_fkey;
ALTER TABLE IF EXISTS ONLY public.dia_bloqueado DROP CONSTRAINT IF EXISTS dia_bloqueado_criado_por_id_fkey;
ALTER TABLE IF EXISTS ONLY public.curso DROP CONSTRAINT IF EXISTS curso_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.conselho_resposta DROP CONSTRAINT IF EXISTS conselho_resposta_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.conselho_resposta DROP CONSTRAINT IF EXISTS conselho_resposta_pergunta_id_fkey;
ALTER TABLE IF EXISTS ONLY public.conselho_resposta DROP CONSTRAINT IF EXISTS conselho_resposta_conselho_id_fkey;
ALTER TABLE IF EXISTS ONLY public.conselho_resposta DROP CONSTRAINT IF EXISTS conselho_resposta_aluno_id_fkey;
ALTER TABLE IF EXISTS ONLY public.conselho_classe DROP CONSTRAINT IF EXISTS conselho_classe_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.conselho_classe DROP CONSTRAINT IF EXISTS conselho_classe_turma_id_fkey;
ALTER TABLE IF EXISTS ONLY public.conselho_classe DROP CONSTRAINT IF EXISTS conselho_classe_proxima_turma_id_fkey;
ALTER TABLE IF EXISTS ONLY public.conselho_classe DROP CONSTRAINT IF EXISTS conselho_classe_instrutor_id_fkey;
ALTER TABLE IF EXISTS ONLY public.conselho_classe DROP CONSTRAINT IF EXISTS conselho_classe_aluno_id_fkey;
ALTER TABLE IF EXISTS ONLY public.configuracao_sistema DROP CONSTRAINT IF EXISTS configuracao_sistema_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.atendimento DROP CONSTRAINT IF EXISTS atendimento_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.atendimento DROP CONSTRAINT IF EXISTS atendimento_atendido_por_id_fkey;
ALTER TABLE IF EXISTS ONLY public.atendimento DROP CONSTRAINT IF EXISTS atendimento_aluno_id_fkey;
ALTER TABLE IF EXISTS ONLY public.aluno DROP CONSTRAINT IF EXISTS aluno_unidade_id_fkey;
ALTER TABLE IF EXISTS ONLY public.aluno DROP CONSTRAINT IF EXISTS aluno_created_by_id_fkey;
ALTER TABLE IF EXISTS ONLY public.agenda_servico_social DROP CONSTRAINT IF EXISTS agenda_servico_social_user_id_fkey;
DROP INDEX IF EXISTS public.ix_user_google_id;
DROP INDEX IF EXISTS public.ix_situacao_escolar_unidade_nome;
ALTER TABLE IF EXISTS ONLY public."user" DROP CONSTRAINT IF EXISTS user_pkey;
ALTER TABLE IF EXISTS ONLY public."user" DROP CONSTRAINT IF EXISTS user_email_key;
ALTER TABLE IF EXISTS ONLY public.unidade DROP CONSTRAINT IF EXISTS unidade_pkey;
ALTER TABLE IF EXISTS ONLY public.dia_bloqueado_turma DROP CONSTRAINT IF EXISTS uix_dia_bloqueado_turma;
ALTER TABLE IF EXISTS ONLY public.turma DROP CONSTRAINT IF EXISTS turma_pkey;
ALTER TABLE IF EXISTS ONLY public.transferencia DROP CONSTRAINT IF EXISTS transferencia_pkey;
ALTER TABLE IF EXISTS ONLY public.tema_aula DROP CONSTRAINT IF EXISTS tema_aula_pkey;
ALTER TABLE IF EXISTS ONLY public.situacao_escolar DROP CONSTRAINT IF EXISTS situacao_escolar_pkey;
ALTER TABLE IF EXISTS ONLY public.situacao_escolar DROP CONSTRAINT IF EXISTS situacao_escolar_aluno_id_key;
ALTER TABLE IF EXISTS ONLY public.respostas_formulario DROP CONSTRAINT IF EXISTS respostas_formulario_pkey;
ALTER TABLE IF EXISTS ONLY public.registro DROP CONSTRAINT IF EXISTS registro_pkey;
ALTER TABLE IF EXISTS ONLY public.registro_aula DROP CONSTRAINT IF EXISTS registro_aula_pkey;
ALTER TABLE IF EXISTS ONLY public.periodo_letivo DROP CONSTRAINT IF EXISTS periodo_letivo_pkey;
ALTER TABLE IF EXISTS ONLY public.periodo_conselho DROP CONSTRAINT IF EXISTS periodo_conselho_pkey;
ALTER TABLE IF EXISTS ONLY public.opcao_proxima_turma DROP CONSTRAINT IF EXISTS opcao_proxima_turma_pkey;
ALTER TABLE IF EXISTS ONLY public.nivel DROP CONSTRAINT IF EXISTS nivel_pkey;
ALTER TABLE IF EXISTS ONLY public.nivel DROP CONSTRAINT IF EXISTS nivel_nome_key;
ALTER TABLE IF EXISTS ONLY public.log_acao DROP CONSTRAINT IF EXISTS log_acao_pkey;
ALTER TABLE IF EXISTS ONLY public.inscricoes DROP CONSTRAINT IF EXISTS inscricoes_pkey;
ALTER TABLE IF EXISTS ONLY public.frequencia DROP CONSTRAINT IF EXISTS frequencia_pkey;
ALTER TABLE IF EXISTS ONLY public.dia_bloqueado_turma DROP CONSTRAINT IF EXISTS dia_bloqueado_turma_pkey;
ALTER TABLE IF EXISTS ONLY public.dia_bloqueado DROP CONSTRAINT IF EXISTS dia_bloqueado_pkey;
ALTER TABLE IF EXISTS ONLY public.curso DROP CONSTRAINT IF EXISTS curso_pkey;
ALTER TABLE IF EXISTS ONLY public.conselho_resposta DROP CONSTRAINT IF EXISTS conselho_resposta_pkey;
ALTER TABLE IF EXISTS ONLY public.conselho_pergunta DROP CONSTRAINT IF EXISTS conselho_pergunta_pkey;
ALTER TABLE IF EXISTS ONLY public.conselho_classe DROP CONSTRAINT IF EXISTS conselho_classe_pkey;
ALTER TABLE IF EXISTS ONLY public.configuracao_sistema DROP CONSTRAINT IF EXISTS configuracao_sistema_pkey;
ALTER TABLE IF EXISTS ONLY public.configuracao_sistema DROP CONSTRAINT IF EXISTS configuracao_sistema_chave_key;
ALTER TABLE IF EXISTS ONLY public.atendimento DROP CONSTRAINT IF EXISTS atendimento_pkey;
ALTER TABLE IF EXISTS ONLY public.aluno DROP CONSTRAINT IF EXISTS aluno_pkey;
ALTER TABLE IF EXISTS ONLY public.alembic_version DROP CONSTRAINT IF EXISTS alembic_version_pkc;
ALTER TABLE IF EXISTS ONLY public.agenda_servico_social DROP CONSTRAINT IF EXISTS agenda_servico_social_pkey;
ALTER TABLE IF EXISTS public."user" ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.unidade ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.turma ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.transferencia ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.tema_aula ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.situacao_escolar ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.respostas_formulario ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.registro_aula ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.registro ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.periodo_letivo ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.periodo_conselho ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.opcao_proxima_turma ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.nivel ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.log_acao ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.frequencia ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.dia_bloqueado_turma ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.dia_bloqueado ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.curso ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.conselho_resposta ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.conselho_pergunta ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.conselho_classe ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.configuracao_sistema ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.atendimento ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.aluno ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS public.agenda_servico_social ALTER COLUMN id DROP DEFAULT;
DROP SEQUENCE IF EXISTS public.user_id_seq;
DROP TABLE IF EXISTS public."user";
DROP SEQUENCE IF EXISTS public.unidade_id_seq;
DROP TABLE IF EXISTS public.unidade;
DROP SEQUENCE IF EXISTS public.turma_id_seq;
DROP TABLE IF EXISTS public.turma;
DROP SEQUENCE IF EXISTS public.transferencia_id_seq;
DROP TABLE IF EXISTS public.transferencia;
DROP SEQUENCE IF EXISTS public.tema_aula_id_seq;
DROP TABLE IF EXISTS public.tema_aula;
DROP SEQUENCE IF EXISTS public.situacao_escolar_id_seq;
DROP TABLE IF EXISTS public.situacao_escolar;
DROP SEQUENCE IF EXISTS public.respostas_formulario_id_seq;
DROP TABLE IF EXISTS public.respostas_formulario;
DROP SEQUENCE IF EXISTS public.registro_id_seq;
DROP SEQUENCE IF EXISTS public.registro_aula_id_seq;
DROP TABLE IF EXISTS public.registro_aula;
DROP TABLE IF EXISTS public.registro;
DROP SEQUENCE IF EXISTS public.periodo_letivo_id_seq;
DROP TABLE IF EXISTS public.periodo_letivo;
DROP SEQUENCE IF EXISTS public.periodo_conselho_id_seq;
DROP TABLE IF EXISTS public.periodo_conselho;
DROP SEQUENCE IF EXISTS public.opcao_proxima_turma_id_seq;
DROP TABLE IF EXISTS public.opcao_proxima_turma;
DROP SEQUENCE IF EXISTS public.nivel_id_seq;
DROP TABLE IF EXISTS public.nivel;
DROP SEQUENCE IF EXISTS public.log_acao_id_seq;
DROP TABLE IF EXISTS public.log_acao;
DROP TABLE IF EXISTS public.inscricoes;
DROP SEQUENCE IF EXISTS public.frequencia_id_seq;
DROP TABLE IF EXISTS public.frequencia;
DROP SEQUENCE IF EXISTS public.dia_bloqueado_turma_id_seq;
DROP TABLE IF EXISTS public.dia_bloqueado_turma;
DROP SEQUENCE IF EXISTS public.dia_bloqueado_id_seq;
DROP TABLE IF EXISTS public.dia_bloqueado;
DROP SEQUENCE IF EXISTS public.curso_id_seq;
DROP TABLE IF EXISTS public.curso;
DROP SEQUENCE IF EXISTS public.conselho_resposta_id_seq;
DROP TABLE IF EXISTS public.conselho_resposta;
DROP SEQUENCE IF EXISTS public.conselho_pergunta_id_seq;
DROP TABLE IF EXISTS public.conselho_pergunta;
DROP SEQUENCE IF EXISTS public.conselho_classe_id_seq;
DROP TABLE IF EXISTS public.conselho_classe;
DROP SEQUENCE IF EXISTS public.configuracao_sistema_id_seq;
DROP TABLE IF EXISTS public.configuracao_sistema;
DROP SEQUENCE IF EXISTS public.atendimento_id_seq;
DROP TABLE IF EXISTS public.atendimento;
DROP SEQUENCE IF EXISTS public.aluno_id_seq;
DROP TABLE IF EXISTS public.aluno;
DROP TABLE IF EXISTS public.alembic_version;
DROP SEQUENCE IF EXISTS public.agenda_servico_social_id_seq;
DROP TABLE IF EXISTS public.agenda_servico_social;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: agenda_servico_social; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.agenda_servico_social (
    id integer NOT NULL,
    titulo character varying(200) NOT NULL,
    categoria character varying(100) NOT NULL,
    data date NOT NULL,
    hora character varying(5) NOT NULL,
    localizacao character varying(255),
    descricao text,
    google_event_id character varying(255),
    participantes_emails text,
    user_id integer NOT NULL,
    data_criacao timestamp without time zone
);


--
-- Name: agenda_servico_social_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.agenda_servico_social_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: agenda_servico_social_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.agenda_servico_social_id_seq OWNED BY public.agenda_servico_social.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: aluno; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.aluno (
    id integer NOT NULL,
    nome character varying(100) NOT NULL,
    nome_social character varying(100),
    ativo boolean NOT NULL,
    data_nascimento date,
    foto_path character varying(255),
    escolaridade_json text,
    identificacao_json text,
    socioeconomico_json text,
    diversidade_json text,
    cpf character varying(20),
    rg character varying(50),
    whatsapp character varying(30),
    email character varying(120),
    nivel character varying(20),
    created_by_id integer,
    created_by_name character varying(100),
    created_at timestamp without time zone,
    unidade_id integer
);


--
-- Name: aluno_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.aluno_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: aluno_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.aluno_id_seq OWNED BY public.aluno.id;


--
-- Name: atendimento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.atendimento (
    id integer NOT NULL,
    aluno_id integer NOT NULL,
    setor character varying(50) NOT NULL,
    data_atendimento date NOT NULL,
    resumo character varying(255),
    dados json NOT NULL,
    atendido_por_id integer,
    atendido_por_nome character varying(150),
    unidade_id integer,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: atendimento_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.atendimento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: atendimento_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.atendimento_id_seq OWNED BY public.atendimento.id;


--
-- Name: configuracao_sistema; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.configuracao_sistema (
    id integer NOT NULL,
    chave character varying(50) NOT NULL,
    valor character varying(100),
    descricao character varying(255),
    unidade_id integer
);


--
-- Name: configuracao_sistema_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.configuracao_sistema_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: configuracao_sistema_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.configuracao_sistema_id_seq OWNED BY public.configuracao_sistema.id;


--
-- Name: conselho_classe; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conselho_classe (
    id integer NOT NULL,
    turma_id integer NOT NULL,
    aluno_id integer NOT NULL,
    etapa character varying(20) NOT NULL,
    data_inicio date,
    data_fim date,
    concluido boolean NOT NULL,
    instrutor_id integer,
    observacao text,
    situacao_final character varying(30),
    proxima_turma_id integer,
    unidade_id integer
);


--
-- Name: conselho_classe_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.conselho_classe_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: conselho_classe_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.conselho_classe_id_seq OWNED BY public.conselho_classe.id;


--
-- Name: conselho_pergunta; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conselho_pergunta (
    id integer NOT NULL,
    etapa character varying(20),
    tipo character varying(20),
    texto text NOT NULL,
    opcoes text,
    ativo boolean NOT NULL
);


--
-- Name: conselho_pergunta_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.conselho_pergunta_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: conselho_pergunta_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.conselho_pergunta_id_seq OWNED BY public.conselho_pergunta.id;


--
-- Name: conselho_resposta; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.conselho_resposta (
    id integer NOT NULL,
    conselho_id integer NOT NULL,
    aluno_id integer NOT NULL,
    pergunta_id integer NOT NULL,
    resposta text,
    observacao text,
    unidade_id integer
);


--
-- Name: conselho_resposta_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.conselho_resposta_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: conselho_resposta_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.conselho_resposta_id_seq OWNED BY public.conselho_resposta.id;


--
-- Name: curso; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.curso (
    id integer NOT NULL,
    nome character varying(150) NOT NULL,
    descricao character varying(300),
    carga_horaria integer,
    ativo boolean NOT NULL,
    unidade_id integer NOT NULL,
    created_at timestamp without time zone
);


--
-- Name: curso_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.curso_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: curso_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.curso_id_seq OWNED BY public.curso.id;


--
-- Name: dia_bloqueado; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dia_bloqueado (
    id integer NOT NULL,
    data date NOT NULL,
    tipo character varying(50) NOT NULL,
    descricao character varying(200),
    periodo_letivo_id integer NOT NULL,
    unidade_id integer NOT NULL,
    criado_por_id integer,
    created_at timestamp without time zone
);


--
-- Name: dia_bloqueado_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dia_bloqueado_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dia_bloqueado_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dia_bloqueado_id_seq OWNED BY public.dia_bloqueado.id;


--
-- Name: dia_bloqueado_turma; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dia_bloqueado_turma (
    id integer NOT NULL,
    turma_id integer NOT NULL,
    data character varying(10) NOT NULL,
    unidade_id integer,
    criado_por_id integer,
    created_at timestamp without time zone
);


--
-- Name: dia_bloqueado_turma_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dia_bloqueado_turma_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dia_bloqueado_turma_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dia_bloqueado_turma_id_seq OWNED BY public.dia_bloqueado_turma.id;


--
-- Name: frequencia; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.frequencia (
    id integer NOT NULL,
    aluno_id integer NOT NULL,
    turma_id integer NOT NULL,
    data character varying(20) NOT NULL,
    conceito character varying(1),
    unidade_id integer
);


--
-- Name: frequencia_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.frequencia_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: frequencia_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.frequencia_id_seq OWNED BY public.frequencia.id;


--
-- Name: inscricoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inscricoes (
    aluno_id integer NOT NULL,
    turma_id integer NOT NULL,
    nivel character varying(30),
    ativo boolean NOT NULL,
    data_inicio date NOT NULL,
    data_desativacao timestamp without time zone,
    motivo_desativacao character varying(50),
    id integer NOT NULL
);


--
-- Name: log_acao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.log_acao (
    id integer NOT NULL,
    data_hora timestamp without time zone,
    usuario_id integer,
    usuario_nome character varying(100),
    acao character varying(255),
    detalhes text,
    ip character varying(50),
    unidade_id integer
);


--
-- Name: log_acao_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.log_acao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: log_acao_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.log_acao_id_seq OWNED BY public.log_acao.id;


--
-- Name: nivel; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.nivel (
    id integer NOT NULL,
    nome character varying(100) NOT NULL,
    ativo boolean NOT NULL,
    unidade_id integer
);


--
-- Name: nivel_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.nivel_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: nivel_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.nivel_id_seq OWNED BY public.nivel.id;


--
-- Name: opcao_proxima_turma; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.opcao_proxima_turma (
    id integer NOT NULL,
    nome character varying(100) NOT NULL,
    ativo boolean NOT NULL
);


--
-- Name: opcao_proxima_turma_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.opcao_proxima_turma_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: opcao_proxima_turma_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.opcao_proxima_turma_id_seq OWNED BY public.opcao_proxima_turma.id;


--
-- Name: periodo_conselho; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.periodo_conselho (
    id integer NOT NULL,
    nome character varying(100) NOT NULL,
    data_inicio date NOT NULL,
    data_fim date NOT NULL,
    conselho_final boolean NOT NULL,
    periodo_letivo_id integer NOT NULL,
    unidade_id integer NOT NULL
);


--
-- Name: periodo_conselho_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.periodo_conselho_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: periodo_conselho_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.periodo_conselho_id_seq OWNED BY public.periodo_conselho.id;


--
-- Name: periodo_letivo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.periodo_letivo (
    id integer NOT NULL,
    nome character varying(150) NOT NULL,
    data_inicio date NOT NULL,
    data_fim date NOT NULL,
    centro_custo character varying(150),
    estimativa_alunos integer NOT NULL,
    ativo boolean NOT NULL,
    unidade_id integer NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: periodo_letivo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.periodo_letivo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: periodo_letivo_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.periodo_letivo_id_seq OWNED BY public.periodo_letivo.id;


--
-- Name: registro; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.registro (
    id integer NOT NULL,
    educador_id integer NOT NULL,
    turma character varying(100),
    mes character varying(20),
    turno character varying(20),
    dados_json text,
    criado_em timestamp without time zone,
    unidade_id integer
);


--
-- Name: registro_aula; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.registro_aula (
    id integer NOT NULL,
    turma_id integer NOT NULL,
    data character varying(20) NOT NULL,
    tema_id integer,
    observacoes text,
    instrutor_id integer,
    created_at timestamp without time zone,
    unidade_id integer
);


--
-- Name: registro_aula_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.registro_aula_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: registro_aula_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.registro_aula_id_seq OWNED BY public.registro_aula.id;


--
-- Name: registro_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.registro_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: registro_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.registro_id_seq OWNED BY public.registro.id;


--
-- Name: respostas_formulario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.respostas_formulario (
    id integer NOT NULL,
    tipo_formulario character varying(50) NOT NULL,
    aluno_id integer,
    usuario_id integer NOT NULL,
    dados json NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);


--
-- Name: respostas_formulario_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.respostas_formulario_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: respostas_formulario_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.respostas_formulario_id_seq OWNED BY public.respostas_formulario.id;


--
-- Name: situacao_escolar; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.situacao_escolar (
    id integer NOT NULL,
    aluno_id integer NOT NULL,
    unidade_id integer,
    escolaridade character varying(40),
    ensino_superior_periodo integer,
    escolaridade_outro character varying(150),
    nome_instituicao character varying(200),
    tipo_instituicao character varying(20),
    bolsista boolean NOT NULL,
    tipo_instituicao_outro character varying(150),
    turno character varying(20),
    turno_outro character varying(100),
    created_at timestamp without time zone NOT NULL,
    updated_at timestamp without time zone NOT NULL,
    status character varying(20),
    status_outro character varying(150)
);


--
-- Name: situacao_escolar_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.situacao_escolar_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: situacao_escolar_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.situacao_escolar_id_seq OWNED BY public.situacao_escolar.id;


--
-- Name: tema_aula; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tema_aula (
    id integer NOT NULL,
    curso_id integer,
    turma_id integer,
    unidade_id integer,
    titulo character varying(200),
    programa character varying(50),
    ativo boolean NOT NULL,
    data character varying(20),
    ordem integer NOT NULL
);


--
-- Name: tema_aula_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tema_aula_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tema_aula_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tema_aula_id_seq OWNED BY public.tema_aula.id;


--
-- Name: transferencia; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transferencia (
    id integer NOT NULL,
    aluno_id integer NOT NULL,
    turma_origem_id integer NOT NULL,
    turma_destino_id integer NOT NULL,
    data_transferencia timestamp without time zone NOT NULL,
    observacoes text,
    unidade_id integer NOT NULL
);


--
-- Name: transferencia_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transferencia_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transferencia_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transferencia_id_seq OWNED BY public.transferencia.id;


--
-- Name: turma; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.turma (
    id integer NOT NULL,
    nome character varying(100) NOT NULL,
    ativo boolean NOT NULL,
    data_inicio character varying(10),
    data_fim character varying(10),
    hora_inicio character varying(5),
    hora_fim character varying(5),
    dias_semana character varying(20),
    programa character varying(50),
    turno character varying(20),
    centro_custo character varying(150),
    ordenacao integer,
    unidade_id integer,
    periodo_letivo_id integer,
    curso_id integer,
    professor_id integer,
    avaliacao_inicial text,
    avaliacao_percurso text,
    avaliacao_final text,
    conselho_concluido boolean NOT NULL
);


--
-- Name: turma_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.turma_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: turma_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.turma_id_seq OWNED BY public.turma.id;


--
-- Name: unidade; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.unidade (
    id integer NOT NULL,
    nome character varying(100) NOT NULL,
    ativo boolean NOT NULL
);


--
-- Name: unidade_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.unidade_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: unidade_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.unidade_id_seq OWNED BY public.unidade.id;


--
-- Name: user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."user" (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    email character varying(120) NOT NULL,
    password character varying(200),
    role character varying(20) NOT NULL,
    is_active boolean NOT NULL,
    is_ad_user boolean NOT NULL,
    unidade_id integer,
    first_login boolean,
    google_id character varying(100),
    google_email character varying(120)
);


--
-- Name: user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_id_seq OWNED BY public."user".id;


--
-- Name: agenda_servico_social id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agenda_servico_social ALTER COLUMN id SET DEFAULT nextval('public.agenda_servico_social_id_seq'::regclass);


--
-- Name: aluno id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aluno ALTER COLUMN id SET DEFAULT nextval('public.aluno_id_seq'::regclass);


--
-- Name: atendimento id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atendimento ALTER COLUMN id SET DEFAULT nextval('public.atendimento_id_seq'::regclass);


--
-- Name: configuracao_sistema id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.configuracao_sistema ALTER COLUMN id SET DEFAULT nextval('public.configuracao_sistema_id_seq'::regclass);


--
-- Name: conselho_classe id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conselho_classe ALTER COLUMN id SET DEFAULT nextval('public.conselho_classe_id_seq'::regclass);


--
-- Name: conselho_pergunta id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conselho_pergunta ALTER COLUMN id SET DEFAULT nextval('public.conselho_pergunta_id_seq'::regclass);


--
-- Name: conselho_resposta id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conselho_resposta ALTER COLUMN id SET DEFAULT nextval('public.conselho_resposta_id_seq'::regclass);


--
-- Name: curso id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.curso ALTER COLUMN id SET DEFAULT nextval('public.curso_id_seq'::regclass);


--
-- Name: dia_bloqueado id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dia_bloqueado ALTER COLUMN id SET DEFAULT nextval('public.dia_bloqueado_id_seq'::regclass);


--
-- Name: dia_bloqueado_turma id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dia_bloqueado_turma ALTER COLUMN id SET DEFAULT nextval('public.dia_bloqueado_turma_id_seq'::regclass);


--
-- Name: frequencia id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.frequencia ALTER COLUMN id SET DEFAULT nextval('public.frequencia_id_seq'::regclass);


--
-- Name: log_acao id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_acao ALTER COLUMN id SET DEFAULT nextval('public.log_acao_id_seq'::regclass);


--
-- Name: nivel id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nivel ALTER COLUMN id SET DEFAULT nextval('public.nivel_id_seq'::regclass);


--
-- Name: opcao_proxima_turma id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opcao_proxima_turma ALTER COLUMN id SET DEFAULT nextval('public.opcao_proxima_turma_id_seq'::regclass);


--
-- Name: periodo_conselho id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodo_conselho ALTER COLUMN id SET DEFAULT nextval('public.periodo_conselho_id_seq'::regclass);


--
-- Name: periodo_letivo id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodo_letivo ALTER COLUMN id SET DEFAULT nextval('public.periodo_letivo_id_seq'::regclass);


--
-- Name: registro id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registro ALTER COLUMN id SET DEFAULT nextval('public.registro_id_seq'::regclass);


--
-- Name: registro_aula id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registro_aula ALTER COLUMN id SET DEFAULT nextval('public.registro_aula_id_seq'::regclass);


--
-- Name: respostas_formulario id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respostas_formulario ALTER COLUMN id SET DEFAULT nextval('public.respostas_formulario_id_seq'::regclass);


--
-- Name: situacao_escolar id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.situacao_escolar ALTER COLUMN id SET DEFAULT nextval('public.situacao_escolar_id_seq'::regclass);


--
-- Name: tema_aula id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tema_aula ALTER COLUMN id SET DEFAULT nextval('public.tema_aula_id_seq'::regclass);


--
-- Name: transferencia id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transferencia ALTER COLUMN id SET DEFAULT nextval('public.transferencia_id_seq'::regclass);


--
-- Name: turma id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.turma ALTER COLUMN id SET DEFAULT nextval('public.turma_id_seq'::regclass);


--
-- Name: unidade id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unidade ALTER COLUMN id SET DEFAULT nextval('public.unidade_id_seq'::regclass);


--
-- Name: user id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user" ALTER COLUMN id SET DEFAULT nextval('public.user_id_seq'::regclass);


--
-- Data for Name: agenda_servico_social; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.agenda_servico_social (id, titulo, categoria, data, hora, localizacao, descricao, google_event_id, participantes_emails, user_id, data_criacao) FROM stdin;
\.


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
b3c4d5e6f7
\.


--
-- Data for Name: aluno; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.aluno (id, nome, nome_social, ativo, data_nascimento, foto_path, escolaridade_json, identificacao_json, socioeconomico_json, diversidade_json, cpf, rg, whatsapp, email, nivel, created_by_id, created_by_name, created_at, unidade_id) FROM stdin;
1436	Gabrielle de Souza Silva	\N	t	2013-05-07	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "S\\u00e3o Jo\\u00e3o de Meriti", "nome_mae": "Andreza Damasceno de Souza", "cpf_mae": "150.398.137-16", "nome_pai": "Lu\\u00eds Alberto Souza Silva", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "(21) 98291-0680", "endereco": {"cep": "23860-000", "rua": "Rua Jos\\u00e9 Pedro", "numero": "30", "bairro": "Ru\\u00ednas", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	\N	\N	\N	andreza-g.l@hotmail.com	\N	22	Raquel Crispim	2026-09-09 13:48:00.167846	2
1432	Daniel Antenor da Silva Portugal	\N	t	2012-04-04	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Mangaratiba", "nome_mae": "Cristileine Pereira da Silva", "cpf_mae": "", "nome_pai": "Anderson Calazans Portugal", "cpf_pai": "025.052.447-31", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "(21) 98413-8477", "endereco": {"cep": "23860-000", "rua": "Rua Cel Moreira C da Silva", "numero": "S/N", "bairro": "Centro", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "5", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	\N	\N	\N	calazansanderson16@gmail.com	\N	22	Raquel Crispim	2026-09-09 13:36:25.235007	2
1364	Allan Ferreira Araújo Cabral	\N	t	2014-04-22	aluno_1364_Allan_Ferreira_Araujo_Cabral.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Monise Ferreira da Silva", "cpf_mae": "134.515.037-78", "nome_pai": "Allan Ara\\u00fajo de Oliveira Cabral", "cpf_pai": "099.358.697-09", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": true, "acompanhante_aulas": "Outro", "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Tamoio", "numero": "50", "bairro": "Vila Muriqui", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	17982361765	None	(21) 97034-4957	allanocabral@hotmail.com	\N	\N	\N	2026-08-03 12:48:14.62532	2
1348	Antonella de Oliveira Gonçalves	\N	t	2012-11-17	aluno_1348_Antonella_De_Oliveira_Goncalves.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Sem\\u00edramis de Oliveira Lima Gon\\u00e7alves", "cpf_mae": "", "nome_pai": "Rinaldo Silva Souza", "cpf_pai": "934.558.957-00", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": true, "acompanhante_aulas": "M\\u00e3e", "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua 28", "numero": "669", "bairro": "Vila Muriqui", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	93455895700	\N	21 994550060	semyramys@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625312	2
1442	Maria Luiza Pereira Chagas	\N	t	2015-02-24	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "", "natural_cidade": "", "nome_mae": "", "cpf_mae": "", "nome_pai": "", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "", "rua": "", "numero": "", "bairro": "", "cidade": "", "uf": "SP", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "Aluno", "pessoas_residencia": "1", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	\N				\N	22	Raquel Crispim	2026-09-09 14:38:15.899944	2
1437	Gael de Oliveira Sá Ucha Campos	\N	t	2015-10-23	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Paracambi", "nome_mae": "Gabriela Ribeiro de Oliveira Ucha Campos", "cpf_mae": "142.197.547-50", "nome_pai": "Guilherme S\\u00e1 Ucha Campos", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "(21) 97037-3660", "endereco": {"cep": "23860-000", "rua": "Rua Rio Branco", "numero": "127", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	\N	\N	\N	gabi_kriok@hotmail.com	\N	22	Raquel Crispim	2026-09-09 13:49:50.031014	2
1441	Lucas Brasil Pontes	\N	t	2013-02-18	aluno_1441_Lucas_Brasil_Pontes.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Andrielle de Oliveira Brasil Pontes", "cpf_mae": "114.506.717-48", "nome_pai": "Marcos Castro de Pontes", "cpf_pai": "", "responsavel_tipo": "M\\u00e3e", "responsavel_nome": "Andrielle de Oliveira Brasil Pontes", "responsavel_cpf": "114.506.717-48", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua da Lapa", "numero": " 36", "bairro": "Nova Mangaratiba", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	06551594794	\N	(21) 98416-2252	andrielle.brasil.pontes@gmail.com	\N	22	Raquel Crispim	2026-09-09 14:37:09.224297	2
1346	Alef de Oliveira Gonçalves Pereira Braga	\N	t	2008-08-26	aluno_1346_Alef_de_Oliveira_Goncalves_Pereira_Braga.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Sem\\u00edramis de Oliveira Lima Gon\\u00e7alves", "cpf_mae": "103.929.627-05", "nome_pai": "Alex Sandro Pereira Braga", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": true, "acompanhante_aulas": "M\\u00e3e", "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua 28", "numero": "669", "bairro": "Vila Muriqui", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "5", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": true, "saude_medicacao": "Sim", "saude_medicamento_nome": "Escitalopran", "saude_observacoes": "Laudo TEA, TDAH e TAG", "informacoes_para_professor": "", "autorizacao_imagem": true}	14917369762	\N	21 994550060	semyramys@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625311	2
1358	Gabriel Brandão de Barros Nobrega	\N	t	2017-04-21	aluno_1358_Gabriel_Brandao_de_Barros_Nobrega.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Ta\\u00eds Pacheco Brand\\u00e3o", "cpf_mae": "762.238.921-87", "nome_pai": "Cristiano de Barros N\\u00f3brega", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Estrada S\\u00e3o Jo\\u00e3o Marcos", "numero": "9930", "bairro": "Acampamento", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "Acima de 5", "residente_maior_renda": "Pai", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	19912747771	\N	21 992613182	brandaotp@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625317	2
1351	Manuella Siqueira Vidal	\N	t	2015-04-14	\N	\N	\N	\N	\N	18726863707	\N	21 990155953	\N	\N	\N	\N	2026-08-03 12:48:14.625314	2
1353	Miguel Ângelo Moreira Eiras	\N	t	2015-07-31	\N	\N	\N	\N	\N	19003353794	\N	21 985062044	\N	\N	\N	\N	2026-08-03 12:48:14.625315	2
1354	Thiago dos Santos de Melo	\N	t	2013-04-19	\N	\N	\N	\N	\N	07457873716	\N	21 993227632	\N	\N	\N	\N	2026-08-03 12:48:14.625315	2
1355	Raphaela Ferreira Gimenes	\N	t	2011-12-21	\N	\N	\N	\N	\N	21500284769	\N	21 969477034	\N	\N	\N	\N	2026-08-03 12:48:14.625316	2
1359	Marcos Antônio da Costa de Oliveira	\N	t	2014-04-14	\N	\N	\N	\N	\N	18871788729	\N	21 966031746	\N	\N	\N	\N	2026-08-03 12:48:14.625318	2
1362	Miguel Lucas Gonçalves Marins	\N	t	2015-03-13	\N	\N	\N	\N	\N	18618851728	\N	21 981038017	\N	\N	\N	\N	2026-08-03 12:48:14.625319	2
1365	Maria Clara Ferreira Barbosa	\N	t	2013-07-01	\N	\N	\N	\N	\N	21551755742	\N	21 998702044	\N	\N	\N	\N	2026-08-03 12:48:14.625321	2
1367	Miguel Silva Alves	\N	t	2014-05-15	\N	\N	\N	\N	\N	18384281785	\N	21 991430375	\N	\N	\N	\N	2026-08-03 12:48:14.625321	2
1368	Pedro Afonso de Moraes Menezes	\N	t	2013-11-04	\N	\N	\N	\N	\N	17335852730	\N	21 988596200	\N	\N	\N	\N	2026-08-03 12:48:14.625322	2
1369	Pedro Almeida Lima	\N	t	2013-09-17	\N	\N	\N	\N	\N	19264170707	\N	21 971402052	\N	\N	\N	\N	2026-08-03 12:48:14.625322	2
1371	Sofia de Souza Cardoso da Slva	\N	t	2015-03-26	\N	\N	\N	\N	\N	18794538786	\N	21 986754991	\N	\N	\N	\N	2026-08-03 12:48:14.625323	2
1372	Murillo de Almeida dos Santos	\N	t	2017-01-12	\N	\N	\N	\N	\N	19701109708	\N	22 974028051 (mae0 22 99800178	\N	\N	\N	\N	2026-08-03 12:48:14.625324	2
1374	Pedro Guedes Braga Viggiano	\N	t	2014-12-19	\N	\N	\N	\N	\N	18431698780	\N	21 988363089 (Pai)/21 99810308	\N	\N	\N	\N	2026-08-03 12:48:14.625325	2
1377	Pyetro Braga Vitorino	\N	t	2014-11-10	\N	\N	\N	\N	\N	06631546770	\N	21995825168	\N	\N	\N	\N	2026-08-03 12:48:14.625326	2
1373	Guilherme da Silva Nicola Ceia	\N	t	2012-06-29	aluno_1373_Guilherme_da_Silva_Nicola_Ceia.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Mangaratiba", "nome_mae": "Barbara da Silva Nicola", "cpf_mae": "127.423.537-55", "nome_pai": "Frederico da Silva Ceia", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Estrada S\\u00e3o Jo\\u00e3o Marcos", "numero": "173", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	17184542797	\N	21 968633915	barbarasilva73547@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625324	2
1340	Marcos Brasil Pontes Filho	\N	t	2010-06-21	\N	\N	\N	\N	\N	06551591779	\N	21 984162252	\N	\N	\N	\N	2026-08-03 12:48:14.625301	2
1341	Samuel da Silva Ribeiro	\N	t	2015-03-16	\N	\N	\N	\N	\N	22536615707	\N	21 966298551	\N	\N	\N	\N	2026-08-03 12:48:14.625308	2
1343	Arthur Alves de Souza	\N	t	2013-02-24	aluno_1343_Arthur_Alves_de_Souza.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Michelle da Concei\\u00e7ao Alves", "cpf_mae": "113.955.607-06", "nome_pai": "Carlos Vitor Costa de Souza", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Par\\u00e1", "numero": "38", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "Acima de 5", "residente_maior_renda": "Pai", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	21573068705	\N	21 975156550	michelleconceicaoalves84@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625309	2
1347	Arthur de Oliveira Gonçalves Silva	\N	t	2010-08-31	aluno_1347_Arthur_de_Oliveira_Goncalves_Silva.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Sem\\u00edramis de Oliveira Lima Gon\\u00e7alves", "cpf_mae": "103.929.627-05", "nome_pai": "Rinaldo Silva Souza", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua 28", "numero": "669", "bairro": "Vila Muriqui", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "5", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	15957126748	\N	21 994550060	semyramys@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625312	2
1349	Mariana de Freitas Cabral	\N	t	2016-07-13	\N	\N	\N	\N	\N	19396425745	\N	21 972424137 (Mae) 21 99759982	\N	\N	\N	\N	2026-08-03 12:48:14.625313	2
1386	Ana Luiza Leite Albano do Prado	\N	t	2016-02-12	aluno_1386_Ana_Luiza_Leite_Albano_do_Prado.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "CE", "natural_cidade": "Fortaleza", "nome_mae": "Marina Leite Albano do Prado", "cpf_mae": "912.903.923-15", "nome_pai": "Luiz Carlos do Prado J\\u00fanior", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": true, "acompanhante_aulas": "Pai", "telefone_resp": "(85) 99996-7874", "endereco": {"cep": "23860-000", "rua": "Rua das Conhas", "numero": "07", "bairro": "Vale do Sahy", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "Acima de 5", "residente_maior_renda": "Pai", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	08741703383	\N	\N	juniorprado1206@gmail.com	\N	\N	\N	2026-08-03 12:48:14.62533	2
1342	André Carvalho da Costa Júnior	\N	t	2014-07-09	aluno_1342_Andre_Carvalho_da_Costa_Junior.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Mangaratiba", "nome_mae": "Silvia Cabral Pereira", "cpf_mae": "086.616.227-51", "nome_pai": "Andr\\u00e9 Carvalho da Costa", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Itagua\\u00ed", "numero": "11", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "Pai", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	18095694789	\N	21 985045389	silvia.andrejr@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625309	2
1382	Artur Barbosa dos Santos	\N	t	2013-11-04	aluno_1382_Artur_Barbosa_dos_Santos.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Mangaratiba", "nome_mae": "Patr\\u00edcia Barbosa da Costa", "cpf_mae": "303.775.768-08", "nome_pai": "Juarez dos Santos", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Rita de C\\u00e1ssia", "numero": "01", "bairro": "Nova Mangaratiba", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Preta", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	18936403702	\N	22 976798570	msndapatricia329@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625328	2
1405	Théo Azevedo Campos	\N	t	2014-01-28	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "", "natural_cidade": "", "nome_mae": "", "cpf_mae": "", "nome_pai": "", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "", "rua": "", "numero": "", "bairro": "", "cidade": "", "uf": "SP", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "Aluno", "pessoas_residencia": "1", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "", "raca_cor": "", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": false}	\N	\N	21 964654094	\N	\N	\N	\N	2026-08-03 12:48:14.625338	2
1412	Ana Carolina dos Santos Athanazio da Cruz	\N	t	2009-03-25	aluno_1412_Ana_Carolina_dos_Santos_Athanazio_da_Cruz.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Nil\\u00f3polis", "nome_mae": "Michele dos Santos Athanazio da Cruz", "cpf_mae": "085.115.937-05", "nome_pai": "", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua S\\u00e3o Luiz", "numero": "22", "bairro": "", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	15586859793	None	21 964722147	dra.micheleathanazio@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625342	2
1380	Murilo Crispim de Melo	\N	t	2016-09-01	\N	\N	\N	\N	\N	22219486702	\N	21 982356086	\N	\N	\N	\N	2026-08-03 12:48:14.625327	2
1383	Rafael Oliveira Rodrigues	\N	t	2017-04-11	\N	\N	\N	\N	\N	19895273703	\N	21 985364623	\N	\N	\N	\N	2026-08-03 12:48:14.625328	2
1387	Matheus Ferreira Flach	\N	t	2013-01-31	\N	\N	\N	\N	\N	18174403736	\N	21 964763337	\N	\N	\N	\N	2026-08-03 12:48:14.62533	2
1419	Nathan Brito Gutierrez	\N	t	\N	\N	\N	\N	\N	\N	15840887706	\N	21 975754997	\N	\N	\N	\N	2026-08-03 12:48:14.625345	2
1379	Bernardo Crispim de Melo	\N	t	2014-10-19	aluno_1379_Bernardo_Crispim_de_Melo.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Raquel Cristina Co\\u00ealho da Silva Crispim", "cpf_mae": "148.702.217-48", "nome_pai": "Thiago da Concei\\u00e7\\u00e3o de Melo Crispim", "cpf_pai": "110.351.867-48", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": true, "acompanhante_aulas": "Pai", "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Edgar Bertino", "numero": "508", "bairro": "Vila Muriqui", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "Carro/Moto", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	18347252750	\N	21 982356086	thiagomelo.conceicao@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625327	2
1370	Abner Nunes de Oliveira Lopes	\N	t	2015-05-01	aluno_1370_Abner_Nunes_de_Oliveira_Lopes.jpeg	{"doc_entregue": {"doc_aluno": true}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Gilmara Silva Nunes Lopes", "cpf_mae": "141.167.617-37", "nome_pai": "Marlon Vinicius de Oliveira Lopes", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": true, "acompanhante_aulas": "Pai", "telefone_resp": "(21) 99957-2232", "endereco": {"cep": "23860-000", "rua": "Rua Crist\\u00f3v\\u00e3o Vieira de Vasconcelos", "numero": "257", "bairro": "Ibicu\\u00ed", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "0", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	18993163707	\N	\N	gilmara1922@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625323	2
1390	Yuri Anderson Correia Macedo	\N	t	2012-06-10	\N	\N	\N	\N	\N	20145378799	\N	21 979241072	\N	\N	\N	\N	2026-08-03 12:48:14.625331	2
1391	Ryan Riquelme Cruz de Oliveira	\N	t	2010-11-30	\N	\N	\N	\N	\N	20001237756	\N	21986671543	\N	\N	\N	\N	2026-08-03 12:48:14.625332	2
1392	Marcelo Luiz Paes de Andrade Cardoso Junior	\N	t	2015-02-14	\N	\N	\N	\N	\N	19653577760	\N	21 989839681	\N	\N	\N	\N	2026-08-03 12:48:14.625332	2
1393	Marinna Fernanda de Mattos Subtil	\N	t	2012-12-23	\N	\N	\N	\N	\N	23203029723	\N	21981502607 (mãe)	\N	\N	\N	\N	2026-08-03 12:48:14.625333	2
1396	Milton Bessa de Almeida Filho	\N	t	2015-02-17	\N	\N	\N	\N	\N	20712370722	\N	21 988536269	\N	\N	\N	\N	2026-08-03 12:48:14.625334	2
1397	Sofia Oliveira Machado	\N	t	2014-10-06	\N	\N	\N	\N	\N	18432531782	\N	21 975120613	\N	\N	\N	\N	2026-08-03 12:48:14.625335	2
1398	Nikolas Machado Martins da Silva	\N	t	2014-03-27	\N	\N	\N	\N	\N	17942532704	\N	21 991996869	\N	\N	\N	\N	2026-08-03 12:48:14.625335	2
1400	Natan Fernandes dos Santos	\N	t	2012-11-24	\N	\N	\N	\N	\N	17457837760	\N	21 970248408	\N	\N	\N	\N	2026-08-03 12:48:14.625336	2
1403	Alexia dos Santos Athanazio	\N	t	2017-03-17	aluno_1403_Alexia_dos_Santos_Athanazio.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Michele dos Santos Athanazio da Cruz", "cpf_mae": "085.115.937-05", "nome_pai": "", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": true, "acompanhante_aulas": "Irm\\u00e3o/Tio", "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua S\\u00e3o Luiz", "numero": "22", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	23322715701	None	21 964722147	dra.micheleathanazio@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625337	2
1408	Maiara Reis Oliveira	\N	t	1996-10-29	\N	\N	\N	\N	\N	16707855727	\N	21 985364623	\N	\N	\N	\N	2026-08-03 12:48:14.62534	2
1410	Vladmyr Pietro dos Santos Martins Leão	\N	t	2015-06-23	\N	\N	\N	\N	\N	18701723707	\N	21 988982648	\N	\N	\N	\N	2026-08-03 12:48:14.625341	2
1416	Yasmin de Melo Matias	\N	t	2015-07-13	\N	\N	\N	\N	\N	18732162707	\N	21 988017401	\N	\N	\N	\N	2026-08-03 12:48:14.625343	2
1417	Maria Isis Vidal Fontella	\N	t	2017-01-02	\N	\N	\N	\N	\N	19686240748	\N	21 991941518	\N	\N	\N	\N	2026-08-03 12:48:14.625344	2
1402	Anna Manuela Sampaio Carvalho de Azevedo	\N	t	2015-04-06	aluno_1402_Anna_Manuela_Sampaio_Carvalho_de_Azevedo.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Leandra Sampaio dos Santos Castro Gomes", "cpf_mae": "", "nome_pai": "Deyvid Carvalho de Azevedo", "cpf_pai": "", "responsavel_tipo": "Av\\u00f4/Av\\u00f3", "responsavel_nome": "Viviane Ribeiro Carvalho", "responsavel_cpf": "025.040.277-70", "vai_acompanhado_aulas": true, "acompanhante_aulas": "Av\\u00f4/Av\\u00f3", "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Joaquim Tito", "numero": "21", "bairro": "Inga\\u00edba", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Av\\u00f4/Av\\u00f3", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	22015851720	\N	21 970311838	vivianecarvalho212@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625337	2
1425	Ana Clara de Jesus Soares	\N	t	2017-05-27	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Ang\\u00e9lica de Jesus Domingos Soares", "cpf_mae": "116.027.777-05", "nome_pai": "Leandro Concei\\u00e7\\u00e3o Soares", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "(21) 97543-6957", "endereco": {"cep": "23860-000", "rua": "Rua do Atalho", "numero": "103", "bairro": "Ranchito", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Aluno", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	19989692742	\N	\N	angelicadejesusdomingos@hotmail.com	\N	22	Raquel Crispim	2026-09-09 13:26:33.842754	2
1426	Bernardo da Fonseca Cipriano	\N	t	2015-09-10	aluno_1426_Bernardo_da_Fonseca_Cipriano.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Angra dos Reis", "nome_mae": "Carla Alexandre da Fonseca Silva", "cpf_mae": "108.413.137-41", "nome_pai": "Marcos J\\u00fanior Domingos Cipriano", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "(21) 98666-2413", "endereco": {"cep": "23860-000", "rua": "Jos\\u00e9 Francisco Magalhaes", "numero": "12", "bairro": "Acampamento", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "5", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Branca", "saude_laudo": true, "saude_medicacao": "Sim", "saude_medicamento_nome": "Respriridona, Flisdina", "saude_observacoes": "Laudo TEA", "informacoes_para_professor": "", "autorizacao_imagem": true}	21624817742	\N	\N	carlacipriano997@gmail.com	\N	22	Raquel Crispim	2026-09-09 13:27:55.59553	2
1418	Maria Eduarda dos Santos Conceição	\N	t	2015-01-02	\N	\N	\N	\N	\N	22025171706	\N	21 969809733	\N	\N	\N	\N	2026-08-03 12:48:14.625344	2
1420	Miguel Gilberto Barboza da Rocha	\N	t	2011-02-08	\N	\N	\N	\N	\N	15949472799	\N	21 966471762	\N	\N	\N	\N	2026-08-03 12:48:14.625345	2
1350	Daniel Fernandes Rangel Pinto	\N	t	2011-07-22	aluno_1350_Daniel_Fernandes_Rangel_Pinto.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Luiza Helena Alves Fernandes", "cpf_mae": "", "nome_pai": "Giovanni Rangel Pinto", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Estrada do Rubi\\u00e3o", "numero": "7", "bairro": "Serra do Piloto", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	16282444705	None	21 966646580	luizafernandes.83@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625313	2
1427	Brayan Pedro Ferreira da Silva	\N	t	2014-12-19	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Joana Darck Ferreira da Silva", "cpf_mae": "", "nome_pai": "Luan Pedro da Silva", "cpf_pai": "176.890.897-47", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "(21) 99918-5374", "endereco": {"cep": "23860-000", "rua": "Rua S\\u00e3o Paulo", "numero": "55", "bairro": "Centro", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "5", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Preta", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	\N	\N	\N	luanpedro@gmail.com	\N	22	Raquel Crispim	2026-09-09 13:29:40.588789	2
1428	Brayan Vinicios da Silva Rodrigues	\N	t	2015-12-08	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Itagua\\u00ed", "nome_mae": "Priscila Vidal da Silva", "cpf_mae": "142.274.007-24", "nome_pai": "Bruno Duarte Rodrigues", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "(21) 9659-1851", "endereco": {"cep": "23860-000", "rua": "Av S\\u00e3o Jo\\u00e3o Marcos", "numero": "123", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "6", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	04129701711	\N	\N	vidaldasilvapriscila@gmail.com	\N	22	Raquel Crispim	2026-09-09 13:30:46.211638	2
1433	Davi Antenor da Silva Portugal	\N	t	2016-06-10	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Mangaratiba", "nome_mae": "Cristileine Pereira da Silva", "cpf_mae": "", "nome_pai": "Anderson Calazans Portugal", "cpf_pai": "025.052.447-31", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "(21) 98413-8477", "endereco": {"cep": "23860-000", "rua": "Rua Cel Moreira C da Silva", "numero": "S/N", "bairro": "Centro", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "5", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	19341218780	\N	\N	calazansanderson16@gmail.com	\N	22	Raquel Crispim	2026-09-09 13:43:39.813975	2
1429	Brian Guerra Brito	\N	t	2002-11-17	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "", "cpf_mae": "", "nome_pai": "", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Av. Litor\\u00e2nea", "numero": "23", "bairro": "Ribeira", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "Aluno", "pessoas_residencia": "1", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	17146425770	\N	(21) 97244-2945	brianguerra@icloud.com	\N	22	Raquel Crispim	2026-09-09 13:32:16.222355	2
1361	Alice Barbosa Braga	\N	t	2014-02-25	aluno_1361_Alice_Barbosa_Braga.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Nova Igua\\u00e7u", "nome_mae": "Thalyta Barbosa Gon\\u00e7alves", "cpf_mae": "", "nome_pai": "Vitor Henrique da Silva Braga", "cpf_pai": "", "responsavel_tipo": "Av\\u00f4/Av\\u00f3", "responsavel_nome": "Fatima das Gra\\u00e7as de Azeredo Braga", "responsavel_cpf": "009.379.907-10", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Santa Catarina", "numero": "319", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "Acima de 5", "residente_maior_renda": "Av\\u00f4/Av\\u00f3", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Preta", "saude_laudo": true, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "Altera\\u00e7\\u00f5es morfoestruturais em algumas v\\u00e9rtebras dorsais - Escoliose", "informacoes_para_professor": "Aluno n\\u00e3o avan\\u00e7a para outras modalidades pois o laudo m\\u00e9dico a impede de fazer esportes com muito esfor\\u00e7o f\\u00edsico.", "autorizacao_imagem": true}	\N	None	21 964272595	vyvafatima@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625319	2
1439	Kayky Barreto Monteiro	\N	t	2012-11-21	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Isabel Cristina Monteiro da Silva", "cpf_mae": "112.697.947-36", "nome_pai": "Leandro Barreto da Silva", "cpf_pai": "", "responsavel_tipo": "M\\u00e3e", "responsavel_nome": "Isabel Cristina Monteiro da Silva", "responsavel_cpf": "112.697.947-36", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Minas Gerais", "numero": " 580", "bairro": "Vila Muriqui", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "2", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Preta", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	20544280784	\N	(21) 98302-4411	bebelgal@hotmail.com	\N	22	Raquel Crispim	2026-09-09 13:54:27.970002	2
1156	Riana Rosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321265	1
1430	Brian Lucas Dias Domingos	\N	t	2012-11-26	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Tatiana Dias da Silva", "cpf_mae": "", "nome_pai": "Iago Alexandre Silva Domingos", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "(21) 99216-9541", "endereco": {"cep": "23860-000", "rua": "Rua Projetada ", "numero": "12", "bairro": "Acampamento", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "Pai", "pessoas_residencia": "2", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	21709728701	\N	\N	\N	\N	22	Raquel Crispim	2026-09-09 13:33:33.239994	2
1431	Bruno Godinho de Oliveira Silva	\N	t	2008-05-08	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Paracambi", "nome_mae": "Patricia Godinho de Oliveira", "cpf_mae": "", "nome_pai": "Igor Cardoso Silva", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Itagua\\u00ed", "numero": "08", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Preta", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	21708626760	\N	(21) 98848-9421	brunospot901@gmail.com	\N	22	Raquel Crispim	2026-09-09 13:34:52.128321	2
1404	Alice de Andrade Braz	\N	t	2015-09-14	aluno_1404_Alice_de_Andrade_Braz.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Beatriz La\\u00eds Lopes Braz", "cpf_mae": "", "nome_pai": "Lucas Braz Teixeira", "cpf_pai": "175.892.467-51", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": true, "acompanhante_aulas": "Pai", "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Tv Andrade Borges", "numero": "42", "bairro": "Cerrado ", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	18843399721	None	(21) 96461-3964	beatrzlandrade86@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625338	2
1184	Sara Silva Barbosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321278	1
1444	Nycolas Cabral Sant'anna	\N	t	2017-07-17	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "", "natural_cidade": "", "nome_mae": "", "cpf_mae": "", "nome_pai": "", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "", "rua": "", "numero": "", "bairro": "", "cidade": "", "uf": "SP", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "Aluno", "pessoas_residencia": "1", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	\N				\N	22	Raquel Crispim	2026-09-09 14:41:24.001246	2
270	Adriel Ribeiro Machado Montezzano	\N	t	2012-01-02	aluno_270_20251205_203425_0000.png	{"doc_entregue": {"doc_aluno": true, "doc_laudo": true}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "", "natural_cidade": "", "nome_mae": "", "cpf_mae": "", "nome_pai": "", "cpf_pai": "", "responsavel_tipo": "M\\u00e3e", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "", "rua": "", "numero": "", "bairro": "", "cidade": "", "uf": "", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "Aluno", "pessoas_residencia": "1", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "", "raca_cor": "", "saude_laudo": true, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320656	1
271	Adriely da Conceição Nunes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320666	1
272	Adryan de Alcantara Sacramento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320668	1
273	Adryelle Cruz Lopes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320668	1
274	Adryellen Victoria da Silva Muniz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320669	1
275	Agatha Castro da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32067	1
276	Agatha Cristal Costa Ribeiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320671	1
277	Agatha da Silva Gonçalves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320672	1
278	Ágatha Victória Siqueira de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320673	1
279	Alan Alves de Moura Filho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320674	1
280	Alan da Silva Filho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320675	1
281	Alana da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320676	1
282	Alana Neves dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320676	1
283	Alejandro Falco Torres	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320677	1
284	Alessandra Santos Gomes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320678	1
285	Alessandra Silva Martins Figueiredo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320679	1
286	Alessandra Vitoria da Silva Assis	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32068	1
287	Alex Ribeiro da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32068	1
288	Alexandra da Silva Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320681	1
289	Alexandra Domenica Dumet Mejia	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320682	1
290	Alexandre Buonomo Cintra	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320683	1
291	Alexandre de Abreu da Conceição	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320683	1
292	Alexandre Vieira dos Santos Junior	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320684	1
293	Alexia Paschoal Buonomo Cintra	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320685	1
294	Alice Alves da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320686	1
295	Alice Alves dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320686	1
296	Alice Ferreira Café	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320687	1
297	Alice Martins de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320688	1
298	Alice Paschoal Buonomo Cintra	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320689	1
299	Alice Soares de Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32069	1
300	Alice Vitória Rismo de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32069	1
301	Alice Vitoria Santos Gonçalves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320691	1
302	Alicia Maria de Souza dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320692	1
303	Alicia Oliveira de Queiroz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320693	1
304	Alicia Sousa Castro Falck	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320693	1
305	Aline de Souza Oliveira Azeredo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320694	1
306	Aline Lima de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320695	1
307	Allacy Davi Lima Miranda	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320695	1
308	Allan castro Menezes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320696	1
309	Alliny da Silva Lourenço	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320697	1
310	Allyce Ferreira de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320697	1
311	Álvaro José Rodrigues Pinto dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320698	1
312	Alyson das Neves de Moraes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320699	1
313	Amanda Gabriella Ribeiro Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.3207	1
314	Amora Marinho Marins Miranda	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.3207	1
315	Ana Alice Pereira Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320701	1
316	Ana Beatriz Araujo Frota	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320702	1
317	Ana Beatriz Correa Britto	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320702	1
318	Ana Beatriz de Almeida da Silva Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320703	1
319	Ana Beatriz Ernesto de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320704	1
320	Ana Beatriz Fontes Souza Gabi Barreto	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320705	1
321	Ana Beatriz Gonçalves Neves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320705	1
322	Ana Beatriz Miguel Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320706	1
323	Ana Carolina Andrade de Andrade	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320707	1
324	Ana Carolina Coutinho Amaral	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320708	1
325	Ana Carolina da Silva Lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320708	1
326	Ana Carolina Ferreira de Paula	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320709	1
327	Ana Clara Correa da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32071	1
328	Ana Clara Menezes Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320711	1
329	Ana Clara Rodrigues Monteiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320711	1
330	Ana Clara Silva da Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320712	1
331	Ana Eliza de Almeida	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320713	1
332	Ana Júlia da Silva Izidoro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320714	1
333	Ana Júlia de Abreu Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320714	1
334	Ana Julia de Oliveira Freitas	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320715	1
335	Ana Júlia do Nascimento Figueiredo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320716	1
336	Ana Julia Figueiredo Neves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320717	1
337	Ana Júlia Souza de Menezes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320717	1
338	Ana Jullya da Silva Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320718	1
339	Ana Livia Elias Caldas	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320719	1
340	Ana Luísa Vieira de Oliveira Miranda	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320719	1
341	Ana Luiza Barros Siqueira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32072	1
342	Ana Luiza Carlos da Cruz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320721	1
343	Ana luiza de paula Ramos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320722	1
344	Ana Luiza Pereira Moreira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320722	1
345	Ana Micaely de Oliveira Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320723	1
346	Ana Sophia Gomes de Lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320724	1
347	Anabelly Carvalho Caetano	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320725	1
348	Anderson Nepomuceno Firmino	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320725	1
349	Anderson Paulino de Araujo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320726	1
350	Andreza Mayara Silva Pinheiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320727	1
351	Anna Beatriz dos Santos de Jesus	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320734	1
352	Anna Carolina Verçosa da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320735	1
353	Anna Eduarda Costa da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320736	1
354	Anna Júlia Carvalho da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320741	1
355	Anna Julia Guimarães Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320741	1
356	Anna Julia Lima Figueiredo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320742	1
357	Anna Laura Lisboa da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320743	1
358	Anny Victoria Melo dos Santos Figueiredo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320743	1
359	Anthony de Souza Galdino	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320744	1
360	Antônio Cardoso Vilar	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320745	1
361	Antonny Inácio Ferreira Soares	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320746	1
362	Aramis da Rosa Muniz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320746	1
363	Arthur Antunes de Oliveira Corrêa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320747	1
364	Arthur Antunes Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320748	1
365	Arthur Bernardes Prates	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320749	1
366	Arthur Braga de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32075	1
367	Arthur Calegari de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32075	1
368	Arthur da Rosa Muniz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320751	1
369	Arthur de Almeida Farias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320752	1
370	Arthur de Oliveira Fernandes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320753	1
371	Arthur do Carmo dos Santos Lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320753	1
372	Arthur dos Santos Brandão	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320754	1
373	Arthur Duque da Paixão	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320755	1
374	Arthur Felipe Gonçalves Braga	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320756	1
375	Arthur Ferreira Batista	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320757	1
376	Arthur Hermann Keller Paes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320757	1
377	Arthur Inácio Silva Nogueira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320758	1
378	Arthur Lopes Simões	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320759	1
379	Arthur Marques Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32076	1
380	Arthur Miguel dos Santos Veiga Cruz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320761	1
381	Arthur Miguel Gonçalves Evangelista	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320761	1
382	Arthur Reis Portugal	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320762	1
383	Arthur Rodrigues Gomes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320763	1
384	Arthur Santana Tolentino	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320763	1
385	Arthur Santos Gomes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320764	1
386	Arthur Sebastião Antunes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320765	1
387	Artur Castro Rebeque	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320765	1
388	Aryan José Ecard Souza Melo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320766	1
389	Asafe Chaves dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320767	1
390	Atahualpa Omar Cardozo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320768	1
391	Aurélio Miguel de Souza Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320769	1
392	Aylla Sophia Bernardes da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320769	1
393	Ayrton Alencar Abreu	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32077	1
394	Aysha Tavares Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320771	1
395	Beatriz Antunes de Lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320771	1
396	Beatriz Moraes de Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320772	1
397	Beatriz Pereira Barbosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320773	1
398	Beatriz Soares dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320774	1
399	Beatriz Thomaz Petti Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320774	1
400	Benjamin Peres Faustino	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320775	1
401	Bernardo Bonifácio Lemos Ribeiro Coelho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320776	1
402	Bernardo Coutinho Castelar	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320777	1
403	Bernardo de Alcantara Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320777	1
404	Bernardo de Souza Dias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320778	1
405	Bernardo do Nascimento Bernardes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320779	1
406	Bernardo do Nascimento Vinhas	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320779	1
407	Bernardo Ferreira Andrade	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32078	1
408	Bernardo Halfeld Campos Rocha	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320781	1
409	Bernardo Lopes Montanha	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320781	1
410	Bernardo Mello Medeiros da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320782	1
411	Bernardo Miguel da Silva Miranda	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320783	1
412	Bernardo Monteiro Ferreira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320784	1
413	Bernardo Nunes Rangel	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320784	1
414	Bernardo Primo Gabino Mendes Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320785	1
415	Bernardo Silva Feitosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320835	1
416	Bernardo Thomaz Petti da conceição	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320837	1
417	Bianca dos Santos Pereira Lyra	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320838	1
418	Bianca Rocha de oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320839	1
419	Brayan Dias de Almeida Guerra	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320839	1
420	Brayan Farias dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32084	1
421	Brenda Estrela Velloso da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320841	1
422	Brenda Fernandes Martins	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320842	1
423	Brenno Brito Ramirez	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320842	1
424	Brenno Figueiredo Cortez	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320843	1
425	Brenno Gouvea Mota	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320844	1
426	Breno Barcelos Almeida	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320845	1
427	Breno de Souza Dias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320846	1
428	Breno de Souza Pincano	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320846	1
429	Breno Roberto Dias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320847	1
430	Bruna dos Santos Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320848	1
431	Brunna Ramos Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320848	1
432	Brunno Luiz Santos da Fonseca	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320849	1
433	Brunno Miguel Silva Fernandes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32085	1
434	Bruno Oliveira Barbosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320851	1
435	Bryan Cordeiro Dias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320851	1
436	Bryan da Silva Martins	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320854	1
437	Bryan dos Santos Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320854	1
438	Bryan Ferreira de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320855	1
439	Bryan Gabriel da Silva de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320856	1
440	Bryan Guilherme do Nascimento da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320856	1
441	Bryan Henrique Silva Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320857	1
442	Bryan Teixeira Soares	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320858	1
443	Caick da Silva Martins	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320859	1
444	Cailane Silva Corrêa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320859	1
445	Caio Andrade Carvalho de Faria	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32086	1
446	Caio Bernardo de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320861	1
447	Caio dos Santos de Araujo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320862	1
448	Caio dos Santos Simões	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320862	1
449	Caio Felipe da Silva Braz Junior	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320863	1
450	Caio Lucas Barbosa Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320864	1
451	Caio William Marins Caetano	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320865	1
452	Caleb Bernardino Coelho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320865	1
453	Caleb Canella Ferreira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320866	1
454	Calebe da Silva Soares Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320867	1
455	Camila Lima da Silva Campos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320867	1
456	Carlos Augusto Monteiro de Macena	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320868	1
457	Carlos Eduardo Alves Fagundes Cordeiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320869	1
458	Carlos Eduardo de Aquino Graça da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32087	1
459	Carlos Eduardo de Oliveira Correa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32087	1
460	Carlos Eduardo Manhães dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320871	1
461	Carlos Eduardo Noronha Duarte	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320872	1
462	Carlos Eduardo Pereira dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320872	1
463	Carlos Eduardo Raposo de Souza da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320873	1
464	Carlos Gabriel de Andrade Menezes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320874	1
465	Carlos Yuri da Conceição de Amorim	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320875	1
466	Carol Oliveira Moraes de Alencar	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320875	1
467	Cauã Prata Bibiano de Lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320876	1
468	Cauã Ribeiro Gomes da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320877	1
469	Cauã Rosa da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320878	1
470	Cauã Soares de Abreu	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320878	1
471	Cauê Isaques Marins Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320879	1
472	Cecília Arantes Peixoto	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32088	1
473	Cecilia Zanardo Meirelles	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32088	1
474	Cintia de Oliveira Alves Bastos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320881	1
475	Cintia Vitoria da Conceição Calegari	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320882	1
476	Claudio Augusto Azevedo de Freitas	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320882	1
477	Claudio Pereira Ramos Neto	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320883	1
478	Clayton da Rocha Lima Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320884	1
479	Cristian Vilas mariano	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320884	1
480	Cristiano Botelho Neves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320885	1
481	Crystian Ramos Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320886	1
482	Daniel Camêlo Ribeiro Andrade	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320887	1
483	Daniel de Castro Uchoa Machado	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320887	1
484	Daniel de Oliveira Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320888	1
485	Daniel do Amparo Paz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320889	1
486	Daniel dos Santos Queiroz Filho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32089	1
487	Daniel Henrique Gomes da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32089	1
488	Daniel Henrique Silva Cabral	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320891	1
489	Daniel Lactargil de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320892	1
490	Daniel Lopes de Araújo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320892	1
491	Daniel Luiz Moura Reis	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320893	1
492	Daniel Pritchard da Cunha Lima de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320894	1
493	Danilo Felix Vidal	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320895	1
494	Danyel Edson Gomes Ribeiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320895	1
495	Darlan da Conceição Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320896	1
496	Davi Carvalho do Nascimento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320897	1
497	Davi Costa Corrêa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320898	1
498	Davi de Oliveira Andrade	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320898	1
499	Davi de Oliveira Mendes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320899	1
500	Davi de Souza Vianna	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.3209	1
501	Davi Lucas da Conceição Alves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.3209	1
502	Davi Luccas Ribeiro de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320901	1
503	Davi Luis de Araujo da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320902	1
504	Davi Luis de Souza Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320902	1
505	Davi Luiz Rismo de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320903	1
506	Davi Luiz Silva Moreira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320904	1
507	Davi Magalhães Sodré da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320905	1
508	Davi Pritchard da Cunha Lima de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320905	1
509	Davi Ramos Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320906	1
510	Davi Ribeiro de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320907	1
511	Davi Rocha Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320907	1
512	Davi Velloso Batista Leite	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320908	1
513	David Carvalho Roza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320909	1
514	David Gabriel Martins Figueiredo dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32091	1
515	David Peçanha do Nascimento Tavares de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32091	1
516	David Sant'Anna de Mello	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320911	1
517	Davidson de Queiroz Soares	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320913	1
518	Davy Lopes Fagundes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320913	1
519	Dayana de Oliveira Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320914	1
520	Débora Ramos de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320915	1
521	Denner Rodrigues dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320916	1
522	Dereck Bragança Moreira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320918	1
523	Derick Peixoto dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320919	1
524	Deyvison Dutra da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320919	1
525	Diego Pereira Almeida	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32092	1
526	Diogo Miranda Correa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320921	1
527	Diully Novaski Figueiredo da Conceição	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320922	1
528	Douglas Campelo Araujo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320923	1
529	Douglas Conceição de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320923	1
530	Douglas Luiz Leite do Nascimento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320924	1
531	Dyanna Vitória de Oliveira Alves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320925	1
532	Eduarda Aparecida dos Reis Ribeiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320926	1
533	Eduarda Basilio dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320926	1
534	Eduarda Rocha Serrão	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320927	1
535	Eduardo Barbosa da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320928	1
536	Eduardo Bueno Barreiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320929	1
537	Eduardo de Santana Ferraz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32093	1
538	Eduardo Luiz Simas Junior	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32093	1
539	Elis Guimarães Cardoso	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320931	1
540	Eloá Guimarães do Valle	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320932	1
541	Eloá Lucas Borges	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320932	1
542	Eloah Angelo Araujo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320933	1
543	Emanuel dos Santos Barros	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320934	1
544	Emanuel Flausino Campos de lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320935	1
545	Emanuel lucas Borges	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320935	1
546	Emanuella Bastos da Hora	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320936	1
547	Emanuelly da Silva dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320937	1
548	Emanuelly da Silva Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320938	1
549	Emanuelly Mariano da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320938	1
550	Emanuely Silva Corrêa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320939	1
551	Emilly Magalhães de Araújo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32094	1
552	Emilly Nascimento de Freitas Amaral	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320941	1
553	Emilly Victória de Souza de Mello	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320941	1
554	Emilly Vitoria de Abreu Gomes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320942	1
555	Emilly Vitória Ribeiro Nascimento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320943	1
556	Emily Guilherme da Silva do Amaral	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320944	1
557	Eneke da Silva Aquino de Medeiros	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320944	1
558	Enzo Barreto da Silva Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320945	1
559	Enzo de Castro (NS Bia de Castro)	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320946	1
560	Enzo Fernandes Neves dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320947	1
561	Enzo Gabriel Oliveira Soares	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320947	1
562	Enzo Gabriel Silva Lopes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320948	1
563	Enzo Gabriel Vieira Martins	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320949	1
564	Enzo Miguel Viana Pontes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32095	1
565	Enzo Silva Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32095	1
566	Enzo Silva da Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320951	1
567	Enzo Siqueira lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320952	1
568	Eric Antunes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320952	1
569	Érick Cardoso Frejó	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320953	1
570	Erick da Silva Machado	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320954	1
571	Erick Souza Martinho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320955	1
572	Estefani Vitória Antunes Francisco	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320955	1
573	Ester da Silva Buonomo Cintra	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320956	1
574	Ester de Castro Uchôa Machado	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320957	1
575	Ester de Paula Menezes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320958	1
576	Ester dos Santos Gomes da Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320958	1
577	Esther Bastos da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320959	1
578	Esther de Castro Ricardino	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32096	1
579	Esther dos Santos Cunha	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320961	1
580	Esther Farias Soares Machado	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320962	1
581	Esther Pires Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320962	1
582	Estrela Nascimento Fontes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320963	1
583	Evellyn Vitória de Oliveira de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320964	1
584	Evelyn Dourado de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320965	1
585	Evillyn Sophia Felipe da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320965	1
586	Fábio Santana de Almeida	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320966	1
587	Fabiólla Carolina Coutinho da Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320967	1
588	Fabrício Borges dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320968	1
589	Fagner Felipe da Conceição Calegari	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320968	1
590	Felipe Araújo da Cunha	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320969	1
591	Felipe Emanuel Alves de Lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32097	1
592	Felipe Flavio Pinto de Azevedo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320971	1
593	Felipe Jonas Pereira Cardeal	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320971	1
594	Fernanda Anastacia Evangelista Rosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320972	1
595	Fernanda Arantes Baptista Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320973	1
596	Fernanda Silva Militano	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320973	1
597	Gabriel Adão dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320974	1
598	Gabriel Arantes Lopes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320975	1
599	Gabriel Brito Pimenta	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320976	1
600	Gabriel Campos dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320976	1
601	Gabriel Carvalho da Silva Rufino	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320977	1
602	Gabriel da Cruz Barros Matos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320978	1
603	Gabriel da Silva Andrade	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320979	1
604	Gabriel de Souza Caldas	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32098	1
605	Gabriel dos Santos Lima Castro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320981	1
606	Gabriel Faria Monteiro Nunes pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320983	1
607	Gabriel Hiller Cariello Dias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320983	1
608	Gabriel Jorge Silva da Veiga	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320984	1
609	Gabriel Lima de Matos Pavão	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320984	1
610	Gabriel Martins Bento dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320985	1
611	Gabriel Menezes Franco	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320985	1
612	Gabriel Oliveira da Conceição	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320986	1
613	Gabriel Prates de Queiroz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320986	1
614	Gabriel Sanches dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320987	1
615	Gabriel Silva de Freitas	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320988	1
616	Gabriel Teixeira do Carmo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320988	1
617	Gabriela Bonifacio Ferreira da Gloria	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320989	1
618	Gabriela dos Santos Veiga Dias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320989	1
619	Gabriela Pantoja Alfaia	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32099	1
620	Gabriella Vitoria Bueno Barreiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32099	1
621	Gabrielly Victoria Chagas Cunha	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320991	1
622	Gabrielly Victoria Teles Borges Gonçalves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320991	1
623	Gabryel Gomes Ribeiro da Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320992	1
624	Geovana da Silva Felizardo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320992	1
625	Geovana Sant'Anna Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320992	1
626	Geovanna de Oliveira Coutinho Rosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320993	1
627	Gerson Santana Tolentino	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320993	1
628	Giovanna Teixeira Lopes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320994	1
629	Giulia Araujo de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320994	1
630	Giulia Pereira Paiva Rodrigues da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320995	1
631	Grazielle de Souza Cruz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320995	1
632	Grazielle Lima Almeida	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320996	1
633	Guilherme Augusto Azevedo de Freitas	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320996	1
634	Guilherme Belarmino de Farias Aguiar	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320997	1
635	Guilherme Bispo de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320997	1
636	Guilherme da Silva Santos de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320998	1
637	Guilherme de Andrade Neves Medeiros	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320998	1
638	Guilherme do Nascimento Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320999	1
639	Guilherme Machado Cortez	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320999	1
640	Guilherme Nunes Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.320999	1
641	Guilherme Philippe Oliveira Ramos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321	1
642	Guilherme Santos Cardoso da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321	1
643	Gustavo da Silva Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321001	1
644	Gustavo de Araujo da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321001	1
645	Gustavo Henrique Machado Cortez	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321002	1
646	Gustavo Leite de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321002	1
647	Gustavo Nelson Carmona de Melo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321003	1
648	Gustavo Silva Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321003	1
649	Gustavo Thomaz de Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321004	1
650	Hadassa de Almeida da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321004	1
651	Hagib Thanus Domet Mejia	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321005	1
652	Hallan de Carvalho Batista	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321005	1
653	Heitor da Silva Miranda	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321006	1
654	Heitor de Castro Ricardino	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321006	1
655	Helena Lopes Santiago do Nascimento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321007	1
656	Heloisa Costa Faustino	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321007	1
657	Henrik Souza Gomes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321008	1
658	Henrique Lima da Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321008	1
659	Hevellyn Eduarda Rodrigues de Paula dos Sanyos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321009	1
660	Hiago Calisto Fernandes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321009	1
661	Higor Carvalho de Araujo da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321009	1
662	Higor Laurindo Freitas	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32101	1
663	Hislayne Machado Matos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32101	1
664	Hobert da Silva Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321011	1
665	Hyran Luciano da Conceição	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321011	1
666	Hytallo Carvalho Caetano	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321012	1
667	Igor Avelino Ferreira de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321012	1
668	Igor de Albuquerque Barbosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321013	1
669	Ikaro Ravi Fonseca Mattos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321013	1
670	Inzagui de Souza Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321014	1
671	Isaac Coutinho Castelar	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321014	1
672	Isaac Ernesto de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321015	1
673	Isaac José dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321015	1
674	Isaac Oliveira Mariano	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321016	1
675	Isabel Cristina Fafians Paes da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321016	1
676	Isabel Inah Ferreira Vita de Morais	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321017	1
677	Isabella Eyer de Freitas	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321018	1
678	Isabella Oliveira Raniel	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321018	1
679	Isack Medeiros dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321019	1
680	Isadora Cristina Rodrigues da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321019	1
681	Isadora Moura de carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32102	1
682	Isadora Vieira dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32102	1
683	Isadora Vitoriano da Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321021	1
684	Isaque Freitas de Sá	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321021	1
685	Israel Almeida de Moura	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321022	1
686	Ítalo Siqueira Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321022	1
687	Izabele Araujo de Oliviera	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321023	1
688	Jamile Vitória Martins Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321023	1
689	Jasmyn Santos Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321024	1
690	Jean Henrique Lourenço dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321025	1
691	Jean Luccas Pereira Vasconcelos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321026	1
692	Jemylli Maryli Ferreira da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321027	1
693	Jenifer Costa Feitosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321027	1
694	Jennifer Lopes Baptista	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321028	1
695	Jeny Kellen Fonseca Reis	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321029	1
696	Jessica Sabrina Ribeiro Dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321029	1
697	Jhuly Maria da Silva Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32103	1
698	João Danilo Pascoal da Cruz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32103	1
699	João Emanoel Lopes da Fonseca	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321031	1
700	João Emanuel Del Guidice Machado Tavares	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321031	1
701	João Felipe Guerra Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321032	1
702	João Fernando Martins de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321032	1
703	João Ferreira Santos Pedreiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321033	1
704	João Gabriel Andrade Lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321033	1
705	João Gabriel Carvalhães Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321034	1
706	João Gabriel Lages Milesi de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321034	1
707	João Gabriel Ramos Pereira Coutinho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321035	1
708	João Gabriel Santos Bonifatti	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321035	1
709	João Gabriel Santos Izaias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321035	1
710	João Gabriel Silva Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321036	1
711	João Gabriel Vital dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321036	1
712	João Gael Gonçalves Lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321037	1
713	João Guilherme de Jesus da Silva Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321037	1
714	João Guilherme Dias Ferreira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321038	1
715	João Guilherme Pinna Bittencourt	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321038	1
716	João Guilherme Rodrigues do Nascimento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321039	1
717	João Guilherme Silvino dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321039	1
718	João Gustavo de Souza Bernardes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32104	1
719	João Lucas Bernardes dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32104	1
720	João Lucas de Oliveira Aguiar	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321041	1
721	João Lucas Dias Bredoff	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321041	1
722	João Lucas Figueiredo Barbosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321042	1
723	João Marcelo Gonzaga Lactargil	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321042	1
724	João Marcos Nemesio de Moraes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321043	1
725	João Miguel da Silva Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321043	1
726	João Miguel dos Santos Fonseca	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321044	1
727	João Pedro de Souza Marinho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321044	1
728	João Pedro Fernandes de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321045	1
729	João Pedro Fontoura do Nascimento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321045	1
730	João Pedro Guidas da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321046	1
731	João Pedro Pêssoa Silveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321046	1
732	João Roberto Franco Torres	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321046	1
733	João Rodrigo Viana Figueira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321047	1
734	João victor Belo de Freitas	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321047	1
735	João Victor da Costa de Sousa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321048	1
736	João Victor do Amparo Paz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321049	1
737	João Victor Farias Soares	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321049	1
738	João Victor Figueiredo Rosa de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32105	1
739	João Victor Liberio Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32105	1
740	João Victor Santos da Conceição	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321051	1
741	João Victor Vieira Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321051	1
742	João Vitor Alexandre Corrêa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321052	1
743	João Vitor Andrade de Andrade	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321052	1
744	João Vitor Celestrino Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321053	1
745	João Vitor de Souza Costa Rezende	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321053	1
746	João Vitor dos Santos Araujo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321054	1
747	João Vitor Gomes de Sá	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321054	1
748	João Vitor Oliveira Ferreira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321055	1
749	João Vitor Pereira dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321055	1
750	Joelson Bispo Alves de Sousa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321056	1
751	John Gabriel Inácio Ferreira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321056	1
752	Jônatas da Silva Botelho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321057	1
753	Jonatha Taylor de Souza Angelo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321057	1
754	Jonathan de Jesus Ferreira -   30+	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321058	1
755	Jonathan dos Santos Pascoal	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321058	1
756	Jordana Maria De Jesus Lima Avellar	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321059	1
757	Jorge Luis do Nascimento Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32106	1
758	José Fernando Ribeiro de Sousa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32106	1
759	José Luiz da Silva Soares	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32106	1
760	José Weslley Silva Fragoso	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321061	1
761	Josué Feitosa Azevedo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321062	1
762	Juan Cunha da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321062	1
763	Juan Fernando Lima Frazão	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321062	1
764	Juan Victor Fabrino Garcia	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321063	1
765	Júlia Avendana Sá	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321063	1
766	Julia Cristina Assis de Sá	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321064	1
767	Julia de Almeida dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321064	1
768	Julia Gonçalves do Nascimento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321065	1
769	Julia Lages Milesi de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321065	1
770	Júlia Lavínia Alves Pinheiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321066	1
771	Julia Oliveira Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321066	1
772	Julia Santana Campos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321067	1
773	Julia Simplicio Batista	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321068	1
774	Juliana de Souza Carvalho Angelo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321068	1
775	Juliana Quinterio Reinoso	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321069	1
776	Júlio Cesar Minervino do Nascimento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32107	1
777	Julio Cesar Silva do Nascimento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321071	1
778	Julio Cezar Pinto dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321071	1
779	Jullya Gonçalves da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321072	1
780	Jussara Beatriz Santos Gonçalves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321072	1
781	Jussara Modesto Inocêncio	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321073	1
782	Kaic da Silva Torres	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321073	1
783	Kaick da Silva Batista	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321073	1
784	Kaik Wanderson Souza Bastos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321074	1
785	Kaike Willian Camara Gonçalves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321074	1
786	Kaiky França Duarte	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321075	1
787	Kaiky Nascimento de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321075	1
788	Kaio Basilio Paulo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321076	1
789	Kaio Gomes da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321076	1
790	Kaio Gonçalves Tobias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321077	1
791	Kaio Lucas do Nascimento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321077	1
792	Kaique Canellas Miranda	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321078	1
793	Kaique Vencerlau Braga	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321078	1
794	Kamilly Victória dos Reis Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321078	1
795	Kamily Victoria dos Santos de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321079	1
796	Karen Jeremias da Silva Queiroz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321079	1
797	Karina Gomes de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32108	1
798	Karolina de Lemos Dias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321081	1
799	Kassiana Isabelly Santos Gonçalves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321081	1
800	Kathlen de Miranda Andrade	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321082	1
801	Kauã Basilio Paulo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321082	1
802	Kauã Conceição de Jesus	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321083	1
803	Kauã Cruz Faustino Lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321083	1
804	Kauã de Santos Quirino - Não Matriculado	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321084	1
805	Kauã de Souza Vidal	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321084	1
806	Kauã dos Santos Militão de Freitas	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321085	1
807	Kauã Fernandes Maciel	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321085	1
808	Kauã Oliveira Aguiar	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321086	1
809	Kauã Severino Felix - Não matriculado	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321087	1
810	Kauan de Oliveira Ferreira dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321087	1
811	Kauan Moreira Barreto	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321088	1
812	Kauan Santos Avila	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321088	1
813	Kauãni Pires Herculano	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321089	1
814	Kauê Carvalho Fonseca	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321089	1
815	Kauê Gomes de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32109	1
816	Kauê Gutierre Souza Bastos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32109	1
817	Kauê Roberto Dias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321091	1
818	Kawã dos Santos Wandermurem	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321091	1
819	Kayhan Ferreira Magalhães	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321092	1
820	Kayk Wamberg da Conceição Lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321092	1
821	Kayke Ferreira Menezes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321093	1
822	KAYLLANE BAPTISTA DIAS	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321093	1
823	Kayllane Souza Silveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321094	1
824	Kayque de Souza Mariano	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321094	1
825	Kayque Gomes Pacheco	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321095	1
826	Kelvin Ramos Donato	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321095	1
827	Kemelly Cristiny Braga Rangel	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321096	1
828	Kethelen Cristina Sant'Anna de Mello	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321096	1
829	Kethellen Victória Inácio da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321097	1
830	Kethellyn Silva de Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321097	1
831	Ketlen Vitória da Silva Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321098	1
832	Keven dos Santos Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321098	1
833	Kiara Canellas Miranda	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321099	1
834	Kristian Fernandes da Conceição Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321099	1
835	Lais Lopes Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321099	1
836	Laiz Ribeiro da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.3211	1
837	Lara Azevedo Nayssinho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321101	1
838	Lara Valente Castelar Calixto	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321101	1
839	Lara Vitoria da Silva Marques	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321101	1
840	Larah Thomaz da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321102	1
841	Larissa Machado Araujo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321102	1
842	Laura Alves Pecly	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321103	1
843	Laura de Oliveira Martins	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321103	1
844	Laura de Oliveira Motta	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321104	1
845	Laura Pereira Paiva Rodrigues da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321104	1
846	Laura Primo Gabino Mendes Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321105	1
847	Lavinia Carvalho Garcia	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321105	1
848	Leandro Lasnor da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321106	1
849	Lenka Juliette Zaorski	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321106	1
850	Leonan da Conceição Ferreira da Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321106	1
851	Leonardo da Silva Barbosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321107	1
852	Leticia Correa Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321107	1
853	Leticia Farias Gama Ribeiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321108	1
854	Lidia Clara de Lima Barbosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321108	1
855	Lion Santos de Jesus	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321109	1
856	Lis Xavier Kalisnki Bayer	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321109	1
857	Livia de lima Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32111	1
858	Lívia Miranda dos Santos Vieira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32111	1
859	Lizandra Simião de Mello	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32111	1
860	Lohann de Souza da Conceição	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321111	1
861	Lohayne Carvalho da Silva Rufino	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321111	1
862	Lorena Sant'anna Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321113	1
863	Lorena Silva Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321114	1
864	Lorennzo Batista da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321114	1
865	Lorenzo Faustino Valente dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321115	1
866	Lorenzzo de Souza da Conceição	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321116	1
867	Lorhan Martins Gomes da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321116	1
868	Luan Braga Barcelos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321117	1
869	Luani Jeniffer Nascimento da Mota	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321117	1
870	Lucas Araujo da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321118	1
871	Lucas Batista de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321119	1
872	Lucas Correa Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321119	1
873	Lucas de Araujo Gonçalves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321119	1
874	Lucas de Medeiros da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32112	1
875	Lucas de Souza da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321121	1
876	Lucas Ferreira Cabral	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321121	1
877	Lucas Figueiredo Neves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321122	1
878	Lucas Figueiredo Neves (Antigo)	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321122	1
879	Lucas Gabriel da Silva Matos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321123	1
880	Lucas Gabriel Pires Horácio dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321123	1
881	Lucas Luiz Dantas da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321124	1
882	Lucas Miguel Paiva Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321124	1
883	Lucas Moura Ferreira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321125	1
884	Lucas Santos Bonifatti	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321125	1
885	Lucas Vieira de Oliveira Miranda	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321126	1
886	Lucca da Silva Baner	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321127	1
887	Lucca Ribeiro Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321127	1
888	Luciana Gomes Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321128	1
889	Luid Gabriel Gomes Freire	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321128	1
890	Luis Daniel dos Santos Nunes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321128	1
891	Luísa Tavares Oliveira de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321129	1
892	Luiz Claúdio Belizário dos santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321129	1
893	Luiz Eduardo Batista da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32113	1
894	Luiz Felipe Elias Caldas	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32113	1
895	Luiz Fellipe Moreira Dellarmelin	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321131	1
896	Luiz Fernando de Almeida Galdino	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321131	1
897	Luiz Gustavo Vicente Farias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321132	1
898	Luiz Henrique Pereira dos santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321132	1
899	Luiz Miguel da Silva do Amaral e Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321133	1
900	Luiz Miguel Oliveira Raniel	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321133	1
901	Luiz Otávio Firmino Ferreira dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321134	1
902	Luiza Carvalho Silva Rufino	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321134	1
903	Luna Trajano Corletto	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321135	1
904	Madson Nathan Gonçalves Gomes Alves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321135	1
905	Maia Boscolo Martins	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321136	1
906	Maicon Douglas Gonçalves de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321136	1
907	Maitê Gomes de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321136	1
908	Manoela Vitória Carvalhaes de Lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321137	1
909	Manoella lemos Machado	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321137	1
910	Manuela Galdino dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321138	1
911	Manuella Barbosa de Castro Vitória	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321138	1
912	Manuella Torres Pimentel	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321139	1
913	Manuelle Rocha de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321139	1
914	Marcelly Gomes Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32114	1
915	Marcelo Lasneau de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32114	1
916	Marcelo Ronny Santos da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321141	1
917	Marcio Henrique Figueiredo Ramos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321141	1
918	Marcos Alan dos Santos Bernardes Ribeiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321141	1
919	Marcos André da Silva Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321142	1
920	Marcos Antônio Pacheco da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321142	1
921	Marcos De Mello Wermeinger Bittencourt	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321143	1
922	Marcos Felipe de Lima Pinheiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321143	1
923	Marcos Iago Santos da Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321144	1
924	Marcos Paulo do Nascimento Carneiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321144	1
925	Marcos Vinicius Oliveira de Alvarenga	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321145	1
926	Marcos Vinícius Santos Teixeira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321146	1
927	Marcus de Carvalho Pinto Vellozo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321146	1
928	Maria Cecília da SIlva Ferreira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321147	1
929	Maria Clara Antunes Barbosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321147	1
930	Maria Clara Bastos da Conceição	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321148	1
931	Maria Clara Gonçalves Moura	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321148	1
932	Maria Eduarda Barbosa Emiliano	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321149	1
933	Maria Eduarda Carvalho da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321149	1
934	Maria Eduarda da Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32115	1
935	Maria Eduarda Damião Bertilac	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321151	1
936	Maria Eduarda de Sousa Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321151	1
937	Maria Eduarda dos Santos Azevedo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321152	1
938	Maria Eduarda dos Santos Silvino da Silveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321152	1
939	Maria Eduarda Duarte Nascimento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321153	1
940	Maria Eduarda Gomes da Matta	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321153	1
941	Maria Eduarda Lourenço da Conceição	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321154	1
942	Maria Eduarda Marinho Xavier	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321154	1
943	Maria Eduarda Nascimento de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321155	1
944	Maria Eduarda Quiterio do Amaral	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321155	1
945	Maria Eduarda Rodrigues Vitório	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321156	1
946	Maria Eduarda Rodrigues Vitório (Duplicidade	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321158	1
947	Maria Eduarda Sant' Anna Cordoeira Ferreira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321158	1
948	Maria Eduarda Santos da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321159	1
949	Maria Eduarda Venceslau de Lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321159	1
950	Maria Eloisa Bastos Santiago	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32116	1
951	Maria Emanuelly Teixeira Marins	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32116	1
952	Maria Fernanda Brito Falcão	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321161	1
953	Maria Fernanda Fernandes dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321162	1
954	Maria Fernanda Machado Abreu	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321162	1
955	Maria Fernanda Oliveira da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321163	1
956	Maria Fernanda Santos Monteiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321163	1
957	Maria Genyffer Ferreira da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321164	1
958	Maria Júlia Antunes da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321164	1
959	Maria Luisa Barbosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321165	1
960	Maria Luisa Holanda Dubs	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321165	1
961	Maria Luísa Raposo de Souza da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321166	1
962	Maria Luiza da Rosa dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321166	1
963	Maria Luiza dos Santos Marins	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321167	1
964	Maria Luiza Rocha Bandeira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321167	1
965	Maria Luiza Silva Rocha	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321167	1
966	Maria Luiza Soares Veloso	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321168	1
967	Maria Valentina Pereira Torres	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321168	1
968	Mariah Pereira Martins Figueiredo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321169	1
969	Mariana dos Santos Pereira Lyra	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321169	1
970	Marina Feliciano Jardim	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32117	1
971	Marina Navega de Abreu	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32117	1
972	Mário Guilherme Jorge dos Reis Ribeiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321171	1
973	Marjoriye de Oliveira Teixeira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321171	1
974	Maryá Pires da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321172	1
975	Mateus Henrique Sales dos Reis	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321172	1
976	MATEUS HENRY OLIVEIRA DIAS	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321173	1
977	Mateus Nascimento de Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321173	1
978	Matheus Alex Peixoto	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321174	1
979	Matheus Amaral de Luna	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321174	1
980	Matheus Barcelos Faeda	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321174	1
981	Matheus de Souza Ferreira dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321175	1
982	Matheus Eduardo Almeida Pinheiro Gomes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321175	1
983	Matheus Francisco de Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321176	1
984	Matheus Henrique Fernandes da Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321176	1
985	Matheus José Lopes Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321177	1
986	Matheus Nunes Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321177	1
987	Matheus Oliveira Aguiar	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321178	1
988	Matheus Pereira de Abreu	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321178	1
989	Matheus Ribeiro Ramos Pinto	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321179	1
990	Matheus Soares dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321179	1
991	Mayara Duarte Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32118	1
992	Mayara Lasnor Dias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32118	1
993	Mayara Teles Nascimento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321181	1
994	Maycon Tavares Leite	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321181	1
995	Maylla Vitória Rodrigues Romano	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321182	1
996	Maysa da Silva Santos de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321182	1
997	Maytê Briana Alves Gonçalves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321183	1
998	Melany Basilio Ribeiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321183	1
999	Melissa da Silva de Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321184	1
1000	Melissa Nazareth Elias Nunes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321184	1
1001	Mellany Victória Pereira Vasconcelos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321185	1
1002	Melquíades Lopes Vaz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321185	1
1003	Meyrlon de Souza Simplicio Pinna	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321186	1
1004	Micaele Carvalho de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321187	1
1005	Michel Santos Avila	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321187	1
1006	Michelle Moreira Mello	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321188	1
1007	Miguel Alves Ferraz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321188	1
1008	Miguel Amaro dos Santos Falcão	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321189	1
1009	Miguel Angelo Araujo dos Reis	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321189	1
1010	Miguel Araujo Figueiredo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32119	1
1011	Miguel Carvalho da Silva Rufino	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32119	1
1012	Miguel Carvalho Quintanilha	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321191	1
1013	Miguel da Silva Castro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321191	1
1014	Miguel de Carvalho Rosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321192	1
1015	Miguel dos Santos Braga	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321192	1
1016	Miguel Eduardo Basilio caetano	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321192	1
1017	Miguel Gomes dos Santos Luis	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321193	1
1018	Miguel Gomes Ribeiro da costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321193	1
1019	Miguel Hangelo Santos Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321194	1
1020	Miguel Kauã Santos da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321194	1
1021	Miguel Lasnor Dias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321195	1
1022	Miguel Leonardo dos Santos de Moraes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321195	1
1023	Miguel Lucas Braga de Jesus	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321196	1
1024	Miguel Luciano Rodrigues Netto	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321196	1
1025	Miguel Morela Edra Barros Vasconcellos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321197	1
1026	Miguel Soares da Silva da Motta	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321197	1
1027	Miguel Soares Lemos da Cunha	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321198	1
1028	Mikael Bazilio de Jesus	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321198	1
1029	Mikaelly Santos Gomes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321199	1
1030	Mirella Monsore Miranda	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321199	1
1031	Mirella Santana de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321201	1
1032	Mirian Lima de Almeida	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321201	1
1033	Moisés de Abreu Batista	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321202	1
1034	Murillo Costa Mizael	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321202	1
1035	Murillo Luiz Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321203	1
1036	Murilo José Quirino Monteiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321203	1
1037	Murilo Veríssimo Jaloto Flamini Machado	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321204	1
1038	Murilo Vieira Pena	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321204	1
1039	Myckael Laurindo Cavalcante de Mesquita	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321205	1
1040	Myllena Campos Avundano	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321205	1
1041	Myrella de Lima Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321206	1
1042	Nataly Lopes Bispo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321206	1
1043	Natan Duarte Bonfim	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321207	1
1044	Natan Silva Fernandes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321207	1
1045	Nathalli Flamini da Silva Neves Machado	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321208	1
1046	Nathaly Daniely da Silva Martins	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321208	1
1047	Nathan de Souza Araujo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321208	1
1048	Nathan de Souza de Menezes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321209	1
1049	Nathan de Souza Ribeiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321209	1
1050	Nathan Ferreira do Carmo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32121	1
1051	Nathan Lactargil de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32121	1
1052	Nathan Nascimento Menezes de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321211	1
1053	Nathan Teixeira da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321211	1
1054	Nick Silva de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321212	1
1055	Nícolas Barboza Gomes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321212	1
1056	Nicolas de Souza Ribeiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321213	1
1057	Nicolas Gabriel Pereira Junes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321213	1
1058	Nicolas Martins Lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321214	1
1059	Nicolas Veríssimo Jaloto Flamini Machado	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321214	1
1060	Nicollas Moraes da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321215	1
1061	Nicolle Pietra do Carmo Guimarães do Nascimento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321215	1
1062	Nicolly Araújo Bezerra	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321216	1
1063	Nicolly Avendana Silveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321216	1
1064	Nicolly Lopes de Araujo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321217	1
1065	Nicolly Sophia Gomes dos santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321217	1
1066	Nina Nogueira Azevedo de Sousa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321218	1
1067	Nuno Daniel Cordeiro Reis	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321218	1
1068	Nycolas de Souza Athaydes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321219	1
1069	Nycollas Miguel da Costa Gomes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321219	1
1070	Nycollas Quirino Botelho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32122	1
1071	Nycolle Quirino Botelho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321221	1
1072	Otávio dos Santos Mariano	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321221	1
1073	Pablo Lima Matheus dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321222	1
1074	Paolla Simplicio Alves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321222	1
1075	Patricia Pritchard da Cunha Lima de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321223	1
1076	Patrick Bernardes da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321223	1
1077	Patrick Erick Silva Dias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321224	1
1078	Patrick Ferreira Moreira da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321224	1
1079	Paula Agostinho da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321225	1
1080	Paulo Cesar Lucena Sampaio	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321226	1
1081	Paulo Daniel da Conceição Bonfim	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321226	1
1082	Paulo Henrique Rhadamés dos Santos Cardoso Ferreira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321227	1
1083	Paulo Henrique Silva Cabral	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321227	1
1084	Paulo Henrique Soares Braga	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321228	1
1085	Paulo henrique Viana dos Reis	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321228	1
1086	Paulo Matheus dos Santos Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321229	1
1087	Paulo Roberto Costa dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321229	1
1088	Paulo Roberto Vieira da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32123	1
1089	Paulo Vitor Cruz de Medeiros Figueiredo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32123	1
1090	Pedro Alves Almeida da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321231	1
1091	Pedro Bruno Soares de Souza Campos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321231	1
1092	Pedro da Silva Arantes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321232	1
1093	Pedro da Silva Djino	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321233	1
1094	Pedro de Jesus Ribeiro Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321233	1
1095	Pedro de Oliveira Pinto Lins da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321234	1
1096	Pedro do Nascimento de Araujo Almeida	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321234	1
1097	Pedro dos Santos Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321235	1
1098	Pedro Henrique Barros dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321235	1
1099	Pedro Henrique Campos dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321235	1
1100	Pedro Henrique Lopes Lima de Almeida	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321236	1
1101	Pedro Henrique Marques Procópio	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321237	1
1102	Pedro Henrique Rangel Martins	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321237	1
1103	Pedro Ivo Secundino Vargas da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321237	1
1104	Pedro Jeron de Souza Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321238	1
1105	Pedro Lima de Matos Pavão	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321238	1
1106	Pedro Lucas Avelar do Carmo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321239	1
1107	Pedro Lucas Coelho Fernandes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321239	1
1108	Pedro Lucas dos Santos Nascimento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32124	1
1109	Pedro Neves Araujo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32124	1
1110	Pedro Paulo da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321241	1
1111	Pedro Paulo Mauricio Lourenço da Conceição	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321241	1
1112	Pedro Pereira Gonçalves da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321242	1
1113	Pedro Ricardo de Souza Mota	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321242	1
1114	Pedro Victor Costa dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321243	1
1115	Pierry Basilio Ribeiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321243	1
1116	Pietra do Valle Freitas	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321245	1
1117	Pietro Augusto Gustavo Braga	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321245	1
1118	Pietro de Jesus Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321246	1
1119	Pietro Luís da Silva Diniz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321246	1
1120	Priscila de Souza dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321247	1
1121	Pyetro Barbosa Avendana	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321247	1
1122	Pyetro Lucas Gonçalves Dias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321248	1
1123	Quenã Monteiro Dias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321248	1
1124	Rafael Carvalho Grijó Reis	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321248	1
1125	Rafael Ferreira Café	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321249	1
1126	Rafaela Carvalho Roza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321249	1
1127	Rafaela Corrêa Neves Medeiros	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32125	1
1128	Rafaela Martins nunes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32125	1
1129	Rafaela Pereira Furtuozo da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321251	1
1130	Rafaela Silva da Conceição	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321251	1
1131	Rafaella Bastos da Hora	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321252	1
1132	Rafaella Gomes Amaral	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321252	1
1133	Rafaella Jesus	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321253	1
1134	Raissa Vitória da Conceição Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321254	1
1135	Rana de Oliveira Cardoso	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321254	1
1136	Ranna Viana Dutra da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321255	1
1137	Raquel Arlete Costa da Silva Bernardes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321255	1
1138	Ray Victor Fabrino Nunes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321256	1
1139	Rayan Kendyr Castro dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321256	1
1140	Rayane Avelino de Araujo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321257	1
1141	Rayane de Meneses Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321257	1
1142	Rayane Peres Gomes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321258	1
1143	Raylane da Silva Silvestre	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321258	1
1144	Rayssa Dantas Ribeiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321259	1
1145	Rayssa Santana Rodrigues da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321259	1
1146	Rebeca Silva Chagas	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32126	1
1147	Rebeka Sophia Martins Monteiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32126	1
1148	Reginaldo Medeiros Gonçalves Moreira de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321261	1
1149	Renan Pierre Reis de Oliveira Zacarias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321261	1
1150	Renan Veríssimo Guedes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321262	1
1151	Rennan de Carvalho Batista	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321263	1
1152	Rhillary Flávia Antunes Francisco	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321263	1
1153	Rhuan Verissimo Gauttenauer	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321263	1
1154	Rhyan Medeiros Victoriano Casanova	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321264	1
1155	Rian da Silva Goiano	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321264	1
1157	Richard Kayo Siqueira dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321265	1
1158	Richard Maximiano Jorge	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321266	1
1159	Richard Miguel Borges Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321266	1
1160	Richard Nascimento Borges	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321267	1
1161	Rikson Callegari da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321267	1
1162	Roberta Jennifer Santos da Conceição de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321268	1
1163	Roberta Jolie Oliveira da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321268	1
1164	Roberta Silva Faeda - Aluna 30+	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321269	1
1165	Roberto Vilas Mariano	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321269	1
1166	Rodrigo Brazão Silva Motta	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32127	1
1167	Rodrigo de Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32127	1
1168	Ruan Alvarenga Dias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321271	1
1169	Ryan Carlos Gomes da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321271	1
1170	Ryan do Nascimento Borges	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321271	1
1171	Ryan Matheus Santana de Almeida	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321272	1
1172	Sabrinny Lorrany Amaral Freitas Braz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321272	1
1173	Samile Louise Reis Santana	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321273	1
1174	Samuel Braz Ferreira Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321273	1
1175	Samuel Cirillo Azevedo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321274	1
1176	Samuel Da Silva Soares Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321274	1
1177	Samuel de Souza Angelo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321275	1
1178	Samuel dos Santos de Carvalho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321275	1
1179	Samuel Duarte Lobo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321276	1
1180	Samuel Henrique da Silva Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321276	1
1181	Samuel Neves de Souza Santos Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321277	1
1182	Samuel Silva de Oliviera Veloso	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321277	1
1183	Sara Caldas de Jesus	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321277	1
1185	Sarah Abreu Alves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321278	1
1186	Sarah Antunes Feitosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321279	1
1187	Sarah Fernandes Borges	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321279	1
1188	Sarom Salal Hás Baz dos Santos Monteiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32128	1
1189	Saulo Pereira Reis	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32128	1
1190	Seres Isabelly Andrade Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321281	1
1191	Sergio Igor Mello da Cruz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321281	1
1192	Silas Steven Santos de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321282	1
1193	Silvia Hiller Martins Penha	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321282	1
1194	Sofia Hiller Cariello Dias	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321282	1
1195	Sofia Loren da Cruz Lopes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321283	1
1196	Sofia Medeiros Correa Carlos Lopes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321284	1
1197	Sophia Alves Carvalhaes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321284	1
1198	Sophia Azevedo Britto	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321285	1
1199	Sophia Bezerra Lino	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321285	1
1200	Sophia da Silva Belmiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321286	1
1201	Sophia do Nascimento Rodrigues de Abreu Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321286	1
1202	Sophia Freixeiro de Jesus	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321288	1
1203	Sophia Gomes da Silva de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321289	1
1204	Sophia Gomes de Jesus	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321289	1
1205	Sophia Julião Silva Ribeiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32129	1
1206	Sophia Leite de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32129	1
1207	Sophia Martins da costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321291	1
1208	Sophia Nunes Ferreira Coco	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321291	1
1209	Sophia Thayane de Oliveira Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321292	1
1210	Sophia Vitória Estevão de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321293	1
1211	Sophia Vitória Fernandes Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321293	1
1212	Sophie Almeida Alves Rocha	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321293	1
1213	Sophie Cristina Santos de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321294	1
1214	Sophya de Almeida Galdino dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321294	1
1215	Sophya de Cassia Oliveira Araujo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321295	1
1216	Sophya Ferreira de Sousa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321295	1
1217	Stephany Ferreira de Sousa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321296	1
1218	Sthefany Nogueira de Brito	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321297	1
1219	Tadeu de Souza Abreu	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321297	1
1220	Tamires Tavares Mota	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321297	1
1221	Tarcisio de Almeida de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321298	1
1222	Téo Sant' Anna Dumans	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321299	1
1223	Thais Amaro dos Santos Falcão	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321299	1
1224	Thais Silva Marins	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321299	1
1225	Thais Tavares Mota	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.3213	1
1226	Thales Samuel Gomes Vidal	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.3213	1
1227	Thalita Marques de Abreu Rodrigues	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321301	1
1228	Thalita Rosa dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321301	1
1229	Thalles Henrique de Almeida Freura dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321302	1
1230	Thalles Neves Marques	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321302	1
1231	Thalyson Luiz Silva Alves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321303	1
1232	Thamyris de Souza Azerêdo Sampaio	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321303	1
1233	Thauã de Oliveira Angelo dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321304	1
1234	Thaylane Vitória Santana dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321304	1
1235	Thayna Barcelos Faeda	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321304	1
1236	Thaynara da Costa Azevedo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321305	1
1237	Thaynara de Almeida Marins	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321305	1
1238	Thaynara Patrocínio Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321306	1
1239	Theo Avendana Sá	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321306	1
1240	THÉO BRAGA CORREIA	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321307	1
1241	Theylon de Almeida de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321307	1
1242	Thiago Delfino Indio	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321308	1
1243	Thiago Henrique de Lacerda Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321308	1
1244	Thiago Imbiriba da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321309	1
1245	Thiago Lima de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321309	1
1246	Thiago Raphael Nunes Gomes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321309	1
1247	Thiago Roberto da Silva Pinto	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32131	1
1248	Thiago Rosembarque Dantas do Nascimento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32131	1
1249	Thiago Willian da Silva Machado	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321311	1
1250	Thiago Yuri Vieira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321311	1
1251	Tiffany Lopes de Almeida	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321312	1
1252	Tobias Rios Mello de Amorim	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321312	1
1253	Ubiratan Patrick Conceição Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321313	1
1254	Valentina Castro Santiago Buscácio	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321313	1
1255	VALENTYNA TEIXEIRA DO AMARAL	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321314	1
1256	Vicente Emidio Marins	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321314	1
1257	Victor André Rodrigues de Albuquerque Ribeiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321315	1
1258	Victor Borges Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321315	1
1259	Victor Hugo Costa Feitosa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321316	1
1260	Victor Hugo dos Santos Cabral	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321316	1
1261	Victor Hugo Lima da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321317	1
1262	Victor Hugo Maia Rodriguez	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321317	1
1263	Victor Hugo Rubio Pinto Lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321318	1
1264	Victor Kramer Novaski	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321318	1
1265	Victória Vieira Lima Adão	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321319	1
1266	Vida Brito de Carvalho Marins	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321319	1
1267	Vinícius Rocha Ferreira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32132	1
1268	Vinicius Silva Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32132	1
1269	Vinicius Terra Santana	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321321	1
1270	Vinnícius Sousa Nascimento	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321321	1
1271	Virginia da Conceição Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321322	1
1272	Vitor Bastos dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321323	1
1273	Vitor Hugo Cruz Faustino Lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321323	1
1274	Vitor Lima da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321324	1
1275	Vitor Soares de Jesus	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321324	1
1276	Vitória Beatriz Pracias Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321325	1
1277	Vitória de Oliveira de Sousa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321325	1
1278	Vitória de Oliveira Martins	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321326	1
1279	Vitória Manueli Gomes da Conceição	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321326	1
1280	Wagner de Freitas Moraes Junior	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321327	1
1281	Walber Pereira Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321327	1
1282	Wallace Martins Alcantara	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321328	1
1283	Wanderson Luiz Monteiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321328	1
1284	Washington Augusto Marinho Martins	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321329	1
1285	Washington Ferreira Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321329	1
1286	Waynne David Bredoff de Jesus	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321331	1
1287	Wemily dos Santos Guimarães	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321331	1
1288	Wendel Cristiano Silva Santos Carmo	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321332	1
1289	Wendell Monteiro de Souza	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321332	1
1290	Wendell Ribeiro dos Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321333	1
1291	Wesley Borges da Silva Júnior	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321333	1
1292	Wesley França Santana	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321334	1
1293	Wylde Moysés Alves Cavalcante	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321334	1
1294	Yago da Conceição Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321335	1
1295	Yan Marcos Nascimento Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321335	1
1296	Yara Nariel de Sousa Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321336	1
1297	Yasmim Aguiar de Oliveira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321336	1
1298	Yasmim Martins Santos	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321337	1
1299	Yasmim Rodrigues Marinho	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321337	1
1300	Yasmin Carvalho Alves	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321338	1
1301	Yasmin Lemos Lopes	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321338	1
1302	Ycaro da Silva Carneiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321338	1
1303	Ygor da Silva de Lima	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321339	1
1304	Ygor da Silva Jardim	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321339	1
1305	Youssef Olivier Madlum	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32134	1
1306	Ysaac Leandro de Oliveira Chafin Pereira	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.32134	1
1307	Ysabella de Oliveira Pinheiro Sant'Anna	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321341	1
1308	Yuri Gabriel de Souza Costa	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321341	1
1309	Yuri Gabriel Faustino Gomes da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321341	1
1310	Yuri Soares da Silva	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321342	1
1311	Yurick de Souza Cruz	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321342	1
1312	Yvison da Silva Carneiro	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	2026-07-30 15:19:33.321343	1
269	Youssef Olivier Madlum	\N	t	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
1443	Matheus Andrade Silva	\N	t	2012-02-19	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "", "natural_cidade": "", "nome_mae": "", "cpf_mae": "", "nome_pai": "", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "", "rua": "", "numero": "", "bairro": "", "cidade": "", "uf": "SP", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "Aluno", "pessoas_residencia": "1", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	\N				\N	22	Raquel Crispim	2026-09-09 14:40:14.518323	2
1445	Rafael Wanderley Figueiredo	\N	t	2004-02-23	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "", "natural_cidade": "", "nome_mae": "", "cpf_mae": "", "nome_pai": "", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "", "rua": "", "numero": "", "bairro": "", "cidade": "", "uf": "SP", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "Aluno", "pessoas_residencia": "1", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	\N				\N	22	Raquel Crispim	2026-09-09 14:43:23.456863	2
1446	Rodrigo César Nunes Bastos Filho	\N	t	2014-12-03	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "", "natural_cidade": "", "nome_mae": "", "cpf_mae": "", "nome_pai": "", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "", "rua": "", "numero": "", "bairro": "", "cidade": "", "uf": "SP", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "Aluno", "pessoas_residencia": "1", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	\N				\N	22	Raquel Crispim	2026-09-09 14:44:25.185626	2
1447	Tharcila de Oliveira Ucha Campos	\N	t	2011-09-21	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "", "natural_cidade": "", "nome_mae": "", "cpf_mae": "", "nome_pai": "", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "", "rua": "", "numero": "", "bairro": "", "cidade": "", "uf": "SP", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "Aluno", "pessoas_residencia": "1", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	\N				\N	22	Raquel Crispim	2026-09-09 14:46:01.268173	2
1448	Antonio Manoel Machado Abade	\N	t	2017-10-29	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Mangaratiba", "nome_mae": "Flavia Veronica de Almeida Machado Abade", "cpf_mae": "", "nome_pai": "", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "", "rua": "", "numero": "", "bairro": "", "cidade": "", "uf": "SP", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "Aluno", "pessoas_residencia": "1", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	20937053708				\N	22	Raquel Crispim	2026-09-10 09:06:54.209137	2
1394	Ana Júlia Barbosa Silva	\N	t	2013-03-01	aluno_1394_Ana_Julia_Barbosa_Silva.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Angra dos Reis", "nome_mae": "Juliana Cristine Gon\\u00e7alves Barbosa", "cpf_mae": "070.903.247-10", "nome_pai": "Wesley dos Santos Silva", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "(21) 97170-5845", "endereco": {"cep": "23860-000", "rua": "Rua Bom Pastor", "numero": "26", "bairro": "Vale do Sahy", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "2", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	06495236794	\N	\N	alinedonb@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625333	2
1407	Adilson Henrique de Souza Pereira	\N	t	2013-11-15	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Beatriz Silva de Souza", "cpf_mae": "166.521.987-46", "nome_pai": "Geovani Pereira da Cunha", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "(21) 96638-0964", "endereco": {"cep": "23860-000", "rua": "Av Frei Afonso", "numero": "100", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "Av\\u00f4/Av\\u00f3", "pessoas_residencia": "2", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Preta", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	18744633793	\N	21 966991894	beatrizifrj@hotmail.com	\N	\N	\N	2026-08-03 12:48:14.625339	2
1449	Anny Maryelle da Silva	\N	t	2015-05-05	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Maria dos Prazeres da Silva", "cpf_mae": "087.815.214-80", "nome_pai": "Jario da Silva", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "(21) 98089-6330", "endereco": {"cep": "23860-000", "rua": "Rua Rio Grande do Sul", "numero": "10", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "Outro", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	19113798790	\N		marysilva712@gmail.com	\N	22	Raquel Crispim	2026-09-11 14:40:43.97232	2
1399	Beatriz Abade Barros	\N	t	2011-06-16	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Elaine dos Santos Abade Barros", "cpf_mae": "111.783.237-65", "nome_pai": "Diego Gon\\u00e7alves Barros", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua da Lapa", "numero": "26", "bairro": "Nova Mangaratiba", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Preta", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	18622998703	\N	21 992015138	elainesabade@hotmail.com	\N	\N	\N	2026-08-03 12:48:14.625335	2
1352	Benjamin Pereira de Souza	\N	t	2016-03-01	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Angra dos Reis", "nome_mae": "Ana Cristina da Silva Pereira", "cpf_mae": "072.219.937-69", "nome_pai": "Francisco Carlos de Souza", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Projetada ", "numero": "07", "bairro": "Ru\\u00ednas", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	19127117707	\N	21 994738734	\N	\N	\N	\N	2026-08-03 12:48:14.625314	2
1401	Carlos Eduardo Nascimento de Carvalho Augusto	\N	t	2009-06-16	aluno_1401_Carlos_Eduardo_Nascimento_De_Carvalho_Augusto.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Mangaratiba", "nome_mae": "Priscila do Nascimento de Carvalho Augusto", "cpf_mae": "125.034.147-70", "nome_pai": "Carlos de Carvalho Augusto", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua das Flores", "numero": " 33", "bairro": "Nova Mangaratiba", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	17592580756	\N	21 992471467	priscilaaugusto312@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625336	2
1434	Daniel de Lima Ponciano	\N	t	2011-07-16	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Joycelene Rodrigues de Lima", "cpf_mae": "130.512.517-71", "nome_pai": "Rodrigo Ponciano Pereira", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "(21) 96937-5886", "endereco": {"cep": "23860-000", "rua": "Rua Meriti", "numero": "273", "bairro": "Vila Muriqui", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "5", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	\N	\N	\N	joyce19burguesinha@gmail.com	\N	22	Raquel Crispim	2026-09-09 13:45:37.004502	2
1344	Davi Alves da Silva	\N	t	2013-07-30	aluno_1344_Davi_Alves_da_Silva.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Belford Roxo", "nome_mae": "Bruna da Silva Santos", "cpf_mae": "006.736.193-54", "nome_pai": "Jeferson Alves da Silva", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Minas Gerais", "numero": "14", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	19876071718	\N	21 989821955	brunadasilvasantos2023@gmail.com	\N	\N	\N	2026-08-03 12:48:14.62531	2
1406	Davy Lucca Cipriano Ferreira	\N	t	2015-08-16	aluno_1406_Davy_Lucca_Cipriano_Ferreira.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Angra dos Reis", "nome_mae": "Hellen Cristine Domingos Cipriano", "cpf_mae": "161.954.867-44", "nome_pai": "Igor Prazeres Ferreira", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Projetada", "numero": "12", "bairro": "Acampamento", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "5", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	19821013775	\N	21 977262368	ciprianohellen06@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625339	2
1356	Emanuel Mendes Cabral Marçal	\N	t	2016-02-05	aluno_1356_Emanuel_Mendes_Cabral_Marcal.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Serop\\u00e9dica", "nome_mae": "Marcella Mendes do Sacramento", "cpf_mae": "164.144.917-99", "nome_pai": "Marcyel Cabral Mar\\u00e7al", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Joaquim Cardoso da Cruz", "numero": "295", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	19082628775	\N	21 972851810	marcellamarcyel@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625316	2
1435	Eloah Gabrielly de Lima Gomes	\N	t	2013-11-21	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "PB", "natural_cidade": "Campina Grande", "nome_mae": "Joycelene Rodrigues de Lima", "cpf_mae": "130.512.517-71", "nome_pai": "Germano Cherix Ribeiro Gomes", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "(21) 96937-5886", "endereco": {"cep": "23860-000", "rua": "Rua Meriti", "numero": "273", "bairro": "Vila Muriqui", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "5", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Aux\\u00edlio G\\u00e1s", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	71458350452	\N	\N	joyce19burguesinha@gmail.com	\N	22	Raquel Crispim	2026-09-09 13:47:01.994229	2
1384	Elisa de Moura Costa Barros	\N	t	2016-12-03	aluno_1384_Elisa_de_Moura_Costa_Barros.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Mangaratiba", "nome_mae": "Valesca de Moura Costa", "cpf_mae": "052.512.237-06", "nome_pai": "Alberto de Oliveira Barros", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Joaquim Cardoso da Cruz ", "numero": "184", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	19644597702	\N	21 964231775	valescamcosta@yahoo.com.br	\N	\N	\N	2026-08-03 12:48:14.625329	2
1388	Emilly Gabrielly Rofrigues da Silva	\N	t	2014-07-08	aluno_1388_Emilly_Gabrielly_Rodrigues_da_Silva.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Petr\\u00f3polis", "nome_mae": "Karina Rodrigues de Jesus da Silva", "cpf_mae": "156.992.407-48", "nome_pai": "Jonathan Cordeiro da Silva", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua da Cachoeira", "numero": "65", "bairro": "Santa Tereza", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Preta", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	23293945783	\N	24 981249948	kajon2filhos123@gmail.com	\N	\N	\N	2026-08-03 12:48:14.62533	2
1389	Enzo Gabriel Rodrigues da Silva	\N	t	2012-06-06	aluno_1389_Enzo_Gabriel_Rodrigues_da_Silva.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Petr\\u00f3polis", "nome_mae": "Karina Rodrigues de Jesus da Silva", "cpf_mae": "156.992.407-48", "nome_pai": "Jonathan Cordeiro da Silva", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua da Cachoeira", "numero": "65", "bairro": "Santa Tereza", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "", "raca_cor": "", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	23293917739	\N	24 981249948	kajon2filhos123@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625331	2
1411	Fael Araújo Santos	\N	t	2010-10-24	aluno_1411_Fael_Araujo_Santos.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "BA", "natural_cidade": "Salvador", "nome_mae": "Geisa da Paix\\u00e3o Ara\\u00fajo", "cpf_mae": "047.595.275-83", "nome_pai": "Andreti Carlos Souza Santos", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Av Frei Afonso Jorge Braga", "numero": "51", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Outro", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Preta", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	10691646589	\N	21 994408922	geisadapaixaoaraujo@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625341	2
1360	Hector Luiz dos Santos Borges	\N	t	2014-08-04	aluno_1360_Hector_Luiz_dos_Santos_Borges.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Mangaratiba", "nome_mae": "Elizabeth Vieira dos Santos", "cpf_mae": "", "nome_pai": "Hebert Luiz do Nascimento Borges", "cpf_pai": "542.540.437-91", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rodovia Rio-Santos Km 43,5", "numero": "S/N", "bairro": "Fazenda Santa Justina", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Preta", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	22167475721	\N	21 968078423	binho.rj2019@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625318	2
1414	Helena Santana Arruda	\N	t	2017-05-18	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Erika Braga Santana", "cpf_mae": "113.466.927-50", "nome_pai": "Adriano Guilherme de Arruda", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua do Cravo", "numero": "20", "bairro": "Nova Mangaratiba", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	19976427786	\N	21 979721547	erikabraga.malu@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625343	2
1376	João Gabriel Braga Vitorino	\N	t	2010-12-12	aluno_1376_Joao_Gabriel_Braga_Vitorino.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Barra Mansa", "nome_mae": "Sabrina Torres Braga", "cpf_mae": "111.220.557-81", "nome_pai": "Gabriel Vitorino da Silva J\\u00fanior", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Estrada Rj 14", "numero": "02", "bairro": "Vila Muriqui", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Preta", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	06631570727	\N	21995825168	sabrinatorresbraga@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625326	2
1450	Breno Davi Carvalho Lemos	\N	t	2013-05-07	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Mag\\u00e9", "nome_mae": "Carla Carvalho de Oliveira", "cpf_mae": "179.242.667-47", "nome_pai": "Andr\\u00e9 Roberto Lemos", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "(21) 96546-1770", "endereco": {"cep": "23860-000", "rua": "Estrada S\\u00e3o Jo\\u00e3o Marcos", "numero": "18", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Preta", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	04505086763	\N		carlaoliveira0721@gmail.com	\N	22	Raquel Crispim	2026-09-22 09:01:45.689289	2
1381	João Pedro Araujo dos Santos Farias	\N	t	2014-05-16	aluno_1381_Joao_Pedro_Araujo_dos_Santos_Farias.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Mesquita", "nome_mae": "Dulceneia Araujo dos Santos", "cpf_mae": "193.604.457-97", "nome_pai": "Josimar Oliveira Farias", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua S\\u00e3o Paulo", "numero": "09", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	19360445797	\N	21 989328013	dulceneiafarias123@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625328	2
1395	João Pedro Correa Alves	\N	t	2015-03-17	aluno_1395_Joao_Pedro_Correa_Alves.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Michelle Correa de S\\u00e1", "cpf_mae": "094.214.197-07", "nome_pai": "Itamar Alves Costa", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua 12 de outubro", "numero": "459", "bairro": "Vila Muriqui", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	21945493747	\N	21 966276800	\N	\N	\N	\N	2026-08-03 12:48:14.625334	2
1363	João Ricardo Santana Nascimento	\N	t	2014-01-14	aluno_1363_Joao_Ricardo_Santana_Nascimento.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Mangaratiba", "nome_mae": "Barbara de Oliveira Santana Nascimento", "cpf_mae": "", "nome_pai": "Ricardo Suzano do Nascimento", "cpf_pai": "025.050.307-74", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Jo\\u00e3o Bondim", "numero": "30", "bairro": "Vila Muriqui", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	18238476763	\N	21 994053227(Pai) 21 999988373	barbaraosantana@hotmail.com	\N	\N	\N	2026-08-03 12:48:14.62532	2
1375	Joaquim Ferreira Posso	\N	t	2014-11-13	aluno_1375_Joaquim_Ferreira_Posso.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Daniele de Souza Ferreira", "cpf_mae": "087.448.327-10", "nome_pai": "Pablo Ribeiro Posso", "cpf_pai": "", "responsavel_tipo": "", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Cel Jose Caetano ", "numero": "101", "bairro": "Vila Muriqui", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "Acima de 5", "residente_maior_renda": "Pai", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Branca", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	18702310740	\N	21983161569 (mãe)/21997048644(	pabloposso@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625325	2
1366	Jorge Jonathan Santos da Silva	\N	t	2015-03-07	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Patr\\u00edcia Santos da Silva", "cpf_mae": "117.817.587-19", "nome_pai": "Jorge Magno Brito da Silva", "cpf_pai": "", "responsavel_tipo": "M\\u00e3e", "responsavel_nome": "Patr\\u00edcia Santos da Silva", "responsavel_cpf": "117.817.587-19", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Av Frei Afonso", "numero": "1111", "bairro": "", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	20753891794	\N	21 973199069	patriciapatriciasantosdasilva@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625321	2
1438	Juan Godinho de Oliveira Silva	\N	t	2006-07-22	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Mangaratiba", "nome_mae": "Patr\\u00edcia Godinho de Oliveira", "cpf_mae": "", "nome_pai": "Igor Cardoso Silva", "cpf_pai": "", "responsavel_tipo": "Outro", "responsavel_nome": "", "responsavel_cpf": "", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Itagua\\u00ed", "numero": "8", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Av\\u00f4/Av\\u00f3", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	21708623744	\N	(21) 96686-8859	godinhopatricia33@gmail.com	\N	22	Raquel Crispim	2026-09-09 13:53:02.465655	2
1345	Júlio Cesar de Castro Martins do Nascimento Alves	\N	t	2015-09-30	aluno_1345_Julio_Cesar_de_Castro_Martins_do_Nascimento_Alves.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Nair\\u00edn De Castro Louren\\u00e7o do Nascimento Alves", "cpf_mae": "122.583.967-00", "nome_pai": "Thiago Cesar Martins de Ara\\u00fajo Alves", "cpf_pai": "", "responsavel_tipo": "M\\u00e3e", "responsavel_nome": "Nair\\u00edn De Castro Louren\\u00e7o do Nascimento Alves", "responsavel_cpf": "122.583.967-00", "vai_acompanhado_aulas": true, "acompanhante_aulas": "", "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Dib Jorge Sim\\u00f5es", "numero": "189", "bairro": "Santa Tereza", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "2", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": true, "saude_medicacao": "Sim", "saude_medicamento_nome": "Atentah 25mg - Rispiridona 1mg", "saude_observacoes": "Laudo TDAH - Alergia a picadas de inseto, frutos do mar grau moderado;", "informacoes_para_professor": "Laudo TDAH - Alergia a picadas de inseto, frutos do mar grau moderado;", "autorizacao_imagem": true}	19348620703	\N	21966940041	nairindecastro2015@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625311	2
1421	Kauã da Silva Rodrigues	\N	t	2012-04-04	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Mangaratiba", "nome_mae": "Priscila Vidal da Silva", "cpf_mae": "142.274.007-24", "nome_pai": "Bruno Duarte Rodrigues", "cpf_pai": "", "responsavel_tipo": "M\\u00e3e", "responsavel_nome": "Priscila Vidal da Silva", "responsavel_cpf": "142.274.007-24", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Estrada S\\u00e3o Jo\\u00e3o Marcos", "numero": "123", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "6", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	04129772732	\N	21 96591851	vidaldasilvapriscila@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625346	2
1422	Kauê da Silva Rodrigues	\N	t	2012-04-04	aluno_1422_Kaue_da_Silva_Rodrigues.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Mangaratiba", "nome_mae": "Priscila Vidal da Silva", "cpf_mae": "142.274.007-24", "nome_pai": "Bruno Duarte Rodrigues", "cpf_pai": "", "responsavel_tipo": "M\\u00e3e", "responsavel_nome": "Priscila Vidal da Silva", "responsavel_cpf": "142.274.007-24", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Estrada S\\u00e3o Jo\\u00e3o Marcos", "numero": "123", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "6", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	04129738712	\N	21 96591851	vidaldasilvapriscila@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625346	2
1440	Laura dos Santos Fraga	\N	t	2015-04-11	aluno_1440_Laura_dos_Santos_Fraga.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Jaqueline dos Santos Barboza", "cpf_mae": "119.516.717-24", "nome_pai": "Rafael Henrique Fraga de Souza", "cpf_pai": "", "responsavel_tipo": "M\\u00e3e", "responsavel_nome": "Jaqueline dos Santos Barboza", "responsavel_cpf": "119.516.717-24", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Manaus", "numero": "371", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "At\\u00e9 1 sal\\u00e1rio", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	18814438765	\N	(21) 96647-1762	jaquelinesantos24@gmail.com	\N	22	Raquel Crispim	2026-09-09 13:57:26.826571	2
1357	Lucas Alvarenga Correia	\N	t	2009-07-01	aluno_1357_Lucas_Alvarenga_Correia.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Duque de Caxias", "nome_mae": "Ana Paula Do Nascimento Alvarenga", "cpf_mae": "077.489.077-06", "nome_pai": "Jos\\u00e9 de Assis Correa", "cpf_pai": "", "responsavel_tipo": "M\\u00e3e", "responsavel_nome": "Ana Paula Do Nascimento Alvarenga", "responsavel_cpf": "077.489.077-06", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Estrada RJ 14", "numero": "72", "bairro": "Apara", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "M\\u00e3e", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	21999870786	\N	21 974356845	lucaspaulacorrea@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625317	2
1409	Luiz Guilherme Mariano dos Santos do Carmo	\N	t	2013-02-02	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "ES", "natural_cidade": "Vila Velha", "nome_mae": "La\\u00eds Mariano dos Santos", "cpf_mae": "", "nome_pai": "Jeferson do Carmo", "cpf_pai": "087.189.027-58", "responsavel_tipo": "Pai", "responsavel_nome": "Jeferson do Carmo", "responsavel_cpf": "087.189.027-58", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Jasmine", "numero": "82", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Preta", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	23353873759	\N	21 992037549	jefersondocarmo528@gmail.com	\N	\N	\N	2026-08-03 12:48:14.62534	2
1378	Luís Angelo Teixeira	\N	t	2012-11-12	aluno_1378_Luis_Angelo_Teixeira.jpeg	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Rafaella Angelo do Nascimenro Teixeira", "cpf_mae": "102.769.777-18", "nome_pai": "Fabrizio Fernandes Teixeira", "cpf_pai": "", "responsavel_tipo": "M\\u00e3e", "responsavel_nome": "Rafaella Angelo do Nascimenro Teixeira", "responsavel_cpf": "102.769.777-18", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Jos\\u00e9 Alves de Souza e Silva, 28", "numero": "28", "bairro": "Centro", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "Acima de 5", "residente_maior_renda": "Pai", "pessoas_residencia": "6", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": true, "saude_medicacao": "Sim", "saude_medicamento_nome": "Fluoxetina", "saude_observacoes": "Laudo TEA e Transtorno de Ansiedade", "informacoes_para_professor": "", "autorizacao_imagem": true}	20633887765	\N	21 976912860	rafaellaangelo@yahoo.com.br	\N	\N	\N	2026-08-03 12:48:14.625326	2
1385	Luiz Gustavo Carvalho de Lima Gomes Mendes	\N	t	2013-06-17	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Belford Roxo", "nome_mae": "Danielly Carvalho de Lima", "cpf_mae": "120.299.567-59", "nome_pai": "Gustavo Gomes Mendes", "cpf_pai": "", "responsavel_tipo": "M\\u00e3e", "responsavel_nome": "Danielly Carvalho de Lima", "responsavel_cpf": "120.299.567-59", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Estrada S\\u00e3o Jo\\u00e3o Marcos", "numero": "63", "bairro": "Nova Mangaratiba", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "4", "ocupacao": "Estudante", "beneficio_social_status": "Sim", "beneficio_social_nome": "Bolsa Fam\\u00edlia", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Masculino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	17432651744	\N	21 993821179	daniellylima550@gmail.com	\N	\N	\N	2026-08-03 12:48:14.625329	2
1413	Luiza Santos do Nascimento	\N	t	2014-09-11	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "Tha\\u00eds Santos do Nascimento", "cpf_mae": "150.966.327-41", "nome_pai": "F\\u00e1bio do Nascimento", "cpf_pai": "096.267.987-93", "responsavel_tipo": "M\\u00e3e", "responsavel_nome": "Tha\\u00eds Santos do Nascimento", "responsavel_cpf": "150.966.327-41", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23860-000", "rua": "Rua Fortaleza", "numero": "106", "bairro": "Praia do Saco", "cidade": "Mangaratiba", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "1 a 3 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Branca", "saude_laudo": true, "saude_medicacao": "Sim", "saude_medicamento_nome": "Escitalopran", "saude_observacoes": "Laudo TEA", "informacoes_para_professor": "", "autorizacao_imagem": true}	18308256740	\N	21 987687675	thaiss2013@outlook.com.br	\N	\N	\N	2026-08-03 12:48:14.625342	2
1415	Luna Vitória Fernandes Barrera Bahia	\N	t	2015-05-15	\N	{"doc_entregue": {}}	{"nome_social": "", "orgao_rg": "", "nacionalidade": "Brasileira", "natural_uf": "RJ", "natural_cidade": "Rio de Janeiro", "nome_mae": "D\\u00e9bora L\\u00facia Fernandes Luna Barrera Bahia", "cpf_mae": "104.441.827-30", "nome_pai": "Gean Saraiva dos Santos Bahia", "cpf_pai": "", "responsavel_tipo": "M\\u00e3e", "responsavel_nome": "D\\u00e9bora L\\u00facia Fernandes Luna Barrera Bahia", "responsavel_cpf": "104.441.827-30", "vai_acompanhado_aulas": false, "acompanhante_aulas": null, "telefone_resp": "", "endereco": {"cep": "23832-125", "rua": "Rua Sagres", "numero": "7", "bairro": "Piranema", "cidade": "Itagua\\u00ed", "uf": "RJ", "zona": "Urbana", "possui_acesso_internet": true}}	{"renda_familiar": "3 a 5 sal\\u00e1rios", "residente_maior_renda": "Pai", "pessoas_residencia": "3", "ocupacao": "Estudante", "beneficio_social_status": "N\\u00e3o", "beneficio_social_nome": "", "meio_transporte": "\\u00d4nibus", "vulnerabilidade_social": false}	{"genero": "Feminino", "raca_cor": "Parda", "saude_laudo": false, "saude_medicacao": "N\\u00e3o", "saude_medicamento_nome": "", "saude_observacoes": "", "informacoes_para_professor": "", "autorizacao_imagem": true}	18665884785	\N	21 967236317	deboralfl@yahoo.com.br	\N	\N	\N	2026-08-03 12:48:14.625343	2
\.


--
-- Data for Name: atendimento; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.atendimento (id, aluno_id, setor, data_atendimento, resumo, dados, atendido_por_id, atendido_por_nome, unidade_id, created_at, updated_at) FROM stdin;
1	272	pedagogico	2026-09-09	Teste	{"origem": "Equipe", "responsavel_nome": "", "motivo": "Teste", "apontamentos": "Teste", "acordos_educando": "Teste", "acordos_familia": "Teste", "observacoes": "Teste", "anexo": {"nome": "CNPJ - MercadoLivre.pdf", "arquivo": "atendimentos/atendimento_272_20260909221711798804_CNPJ_-_MercadoLivre.pdf", "tamanho": 129237}}	1	Administrador	1	2026-09-09 22:17:11.805532	2026-09-09 22:17:11.80554
\.


--
-- Data for Name: configuracao_sistema; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.configuracao_sistema (id, chave, valor, descricao, unidade_id) FROM stdin;
1	informacao_padrao.nome_instituicao	Instituto Rumo Náutico | Projeto Grael	Nome da instituicao	\N
2	informacao_padrao.cnpj	03.989.542/0001-27	CNPJ	\N
3	informacao_padrao.endereco	Avenida Carlos Ermelindo Marins 494, Jurujuba, Niterói - Rio de janeiro	Endereco	\N
4	informacao_padrao.telefones	21 9 7253-1909	Telefones de contato	\N
6	informacao_padrao.logo_principal_path	uploads/informacao_padrao/logo_principal_1785443375.png	Logo principal	\N
5	informacao_padrao.foto_default_aluno_path	uploads/informacao_padrao/foto_default_aluno_1789483710.png	Foto padrao do aluno	\N
\.


--
-- Data for Name: conselho_classe; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.conselho_classe (id, turma_id, aluno_id, etapa, data_inicio, data_fim, concluido, instrutor_id, observacao, situacao_final, proxima_turma_id, unidade_id) FROM stdin;
\.


--
-- Data for Name: conselho_pergunta; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.conselho_pergunta (id, etapa, tipo, texto, opcoes, ativo) FROM stdin;
1	FINAL	TURMA	1. Como você avalia o engajamento dos alunos nas atividades propostas e o progresso técnico da\r\nturma ao longo do semestre?	A maioria dos alunos demonstrou um engajamento ativo e constante em todas as atividades, apresentando grande progresso técnico, atingindo os objetivos propostos. | A maioria dos alunos participou das atividades, embora alguns precisassem de incentivo pontual, progredindo de forma satisfatória, alcançando os objetivos em grande parte das propostas apresentadas. | A participação foi variável. Ao longo do período alguns alunos mostraram-se mais ativos e outros menos envolvidos. O progresso foi moderado, tendo alguns alunos atingindo os objetivos e outros ainda apresentando dificuldades. | A maioria dos alunos mostrou pouco interesse e envolvimento nas atividades propostas, apresentando dificuldade em alcançar os objetivos traçados para o nível da modalidade.	t
2	FINAL	ALUNO	1. Como é o comportamento do educando durante as aulas?	Demonstram disciplina, foco e engajamento durante as atividades propostas, seguindo orientações e mostrando iniciativa. | Comportam-se de maneira responsável e atentos, participam das aulas com dedicação e respeito às regras. | Participam das atividades e seguem orientações, mas ocasionalmente perdem o foco ou precisam ser lembrados das regras e combinados para manter a disciplina. | O comportamento varia bastante, ora participando ativamente enquanto ora mostrando-se desatentos ou pouco engajados. | Apresentam dificuldades em manter a atenção, seguir orientações e se engajar nas atividades, necessitando de intervenções constantes para melhorar o comportamento.	t
\.


--
-- Data for Name: conselho_resposta; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.conselho_resposta (id, conselho_id, aluno_id, pergunta_id, resposta, observacao, unidade_id) FROM stdin;
\.


--
-- Data for Name: curso; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.curso (id, nome, descricao, carga_horaria, ativo, unidade_id, created_at) FROM stdin;
1	Natação	Aulas de natação dentro dos cursos de esporte	16	t	1	2026-07-30 17:20:50.006815
2	Mecânica Diesel	\N	92	t	2	2026-08-25 12:06:23.425912
\.


--
-- Data for Name: dia_bloqueado; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.dia_bloqueado (id, data, tipo, descricao, periodo_letivo_id, unidade_id, criado_por_id, created_at) FROM stdin;
1	2026-09-07	FERIADO	Independência	1	1	1	2026-07-30 16:10:24.402262
2	2026-10-12	FERIADO	Nossa Senhora Aparecida	1	1	1	2026-07-30 16:10:24.402267
3	2026-10-15	ATIVIDADE_INTERNA	Professor	1	1	1	2026-07-30 16:10:24.402268
4	2026-11-02	FERIADO	Finados	1	1	1	2026-07-30 16:10:24.402269
5	2026-11-20	FERIADO	Consciência Negra	1	1	1	2026-07-30 16:10:24.40227
6	2026-11-23	FERIADO	São Jorge	1	1	1	2026-07-30 16:10:24.40227
7	2026-09-07	FERIADO	Independência	2	2	1	2026-08-25 12:04:03.641589
\.


--
-- Data for Name: dia_bloqueado_turma; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.dia_bloqueado_turma (id, turma_id, data, unidade_id, criado_por_id, created_at) FROM stdin;
\.


--
-- Data for Name: frequencia; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.frequencia (id, aluno_id, turma_id, data, conceito, unidade_id) FROM stdin;
\.


--
-- Data for Name: inscricoes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.inscricoes (aluno_id, turma_id, nivel, ativo, data_inicio, data_desativacao, motivo_desativacao, id) FROM stdin;
\.


--
-- Data for Name: log_acao; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.log_acao (id, data_hora, usuario_id, usuario_nome, acao, detalhes, ip, unidade_id) FROM stdin;
136	2026-09-08 16:43:11.717191	1	Administrador	Logoff	Sessão encerrada voluntariamente.	100.85.249.40	\N
137	2026-09-08 16:43:23.370872	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: seso_nit@email.com	100.85.249.40	\N
140	2026-09-09 10:43:17.307245	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: raquelcrispim@projetograel.org.br	100.116.200.116	\N
141	2026-09-09 10:46:11.408549	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: raquelcrispim@projetograel.org.br	100.116.200.116	\N
142	2026-09-09 10:46:25.548	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: raquelcrispim@projetograel.org.br	100.116.200.116	\N
143	2026-09-09 10:46:48.637196	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: raquelcrispim@projetograel.org.br	100.116.200.116	\N
144	2026-09-09 10:46:57.31745	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
145	2026-09-09 10:47:48.942625	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
146	2026-09-09 10:56:45.352995	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
147	2026-09-09 10:57:46.825564	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
150	2026-09-09 11:18:32.141104	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
154	2026-09-09 13:21:54.482069	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
159	2026-09-09 19:32:12.220308	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
162	2026-09-09 21:36:10.577698	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
209	2026-09-10 09:02:58.212935	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
172	2026-09-09 22:12:19.890523	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
211	2026-09-10 11:49:39.475896	1	Administrador	Remoção Grave	O perfil de gerencia_6387c3f3@email.com foi apagado.	100.85.249.40	\N
212	2026-09-10 11:49:43.822956	1	Administrador	Remoção Grave	O perfil de gerencia_0b96ab37@email.com foi apagado.	100.85.249.40	\N
213	2026-09-10 11:49:47.785618	1	Administrador	Remoção Grave	O perfil de gerencia_c97a39e5@email.com foi apagado.	100.85.249.40	\N
174	2026-09-09 22:28:05.453366	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
214	2026-09-10 11:49:50.862244	1	Administrador	Remoção Grave	O perfil de gerencia_2cae04ef@email.com foi apagado.	100.85.249.40	\N
215	2026-09-10 11:49:54.217435	1	Administrador	Remoção Grave	O perfil de gerencia_14a2d14e@email.com foi apagado.	100.85.249.40	\N
171	2026-09-09 22:08:19.439927	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
216	2026-09-10 11:49:58.309048	1	Administrador	Remoção Grave	O perfil de gerencia_b822172a@email.com foi apagado.	100.85.249.40	\N
217	2026-09-10 11:50:01.787504	1	Administrador	Remoção Grave	O perfil de gerencia_ffb700e7@email.com foi apagado.	100.85.249.40	\N
168	2026-09-09 21:56:02.140771	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
165	2026-09-09 21:47:17.349756	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
229	2026-09-10 13:29:06.333505	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
231	2026-09-10 15:29:55.102784	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: raquelcrispim@projetograel.org.br	100.116.200.116	\N
232	2026-09-10 15:30:04.614758	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
234	2026-09-11 09:50:00.853179	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
236	2026-09-11 12:17:14.782874	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
238	2026-09-11 16:48:37.840454	22	Raquel Crispim	Logoff	Sessão encerrada voluntariamente.	100.116.200.116	\N
240	2026-09-14 10:54:17.143614	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
244	2026-09-14 15:49:11.982061	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
246	2026-09-14 16:54:31.491294	22	Raquel Crispim	Logoff	Sessão encerrada voluntariamente.	100.116.200.116	\N
247	2026-09-15 09:00:15.75222	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
249	2026-09-15 09:07:18.457114	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
250	2026-09-15 09:09:43.692676	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
251	2026-09-15 09:14:38.291085	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
254	2026-09-15 10:33:40.994817	1	Administrador	Logoff	Sessão encerrada voluntariamente.	::1	\N
256	2026-09-15 11:46:48.434504	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
258	2026-09-15 14:23:39.993034	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
260	2026-09-15 19:40:37.684847	84	Alinelopes	Acesso Aprovado	Usuário Alinelopes acessou o sistema.	192.168.1.43	\N
261	2026-09-16 07:55:28.540549	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: raquelcrispim@projetograel.org.br	100.116.200.116	\N
262	2026-09-16 07:55:38.488366	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: raquelcrispim@projetograel.org.br	100.116.200.116	\N
264	2026-09-16 08:08:36.253782	22	Raquel Crispim	Logoff	Sessão encerrada voluntariamente.	100.116.200.116	\N
265	2026-09-16 08:08:47.607404	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
267	2026-09-16 11:16:35.578853	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
268	2026-09-16 11:43:56.625658	22	Raquel Crispim	Logoff	Sessão encerrada voluntariamente.	100.116.200.116	\N
269	2026-09-16 14:24:05.332757	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
270	2026-09-16 16:37:57.025944	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
271	2026-09-17 08:27:37.028333	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
272	2026-09-17 11:03:42.952051	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
273	2026-09-18 09:52:46.330346	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: Alinelopes	100.76.72.15	\N
274	2026-09-18 09:53:05.63954	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: Alinelopes	100.76.72.15	\N
275	2026-09-21 12:02:38.016749	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
138	2026-09-08 16:54:26.421095	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
148	2026-09-09 11:10:29.992227	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: nonexistent@example.com	127.0.0.1	\N
151	2026-09-09 11:24:55.878811	1	Administrador	Logoff	Sessão encerrada voluntariamente.	100.85.249.40	\N
152	2026-09-09 11:25:05.943907	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
155	2026-09-09 14:31:45.650287	23	Cláudia Romão	Acesso Aprovado	Usuário Cláudia Romão acessou o sistema.	100.80.160.117	\N
156	2026-09-09 14:32:47.434569	23	Cláudia Romão	Troca de Senha	Cláudia Romão definiu nova senha.	100.80.160.117	\N
157	2026-09-09 14:40:42.586735	23	Cláudia Romão	Logoff	Sessão encerrada voluntariamente.	100.80.160.117	\N
92	2026-08-25 11:00:20.340345	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.114.24.108	\N
93	2026-08-25 11:00:28.043418	1	Administrador	Logoff	Sessão encerrada voluntariamente.	100.114.24.108	\N
94	2026-08-25 11:03:37.01212	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: fabianomotta	100.114.24.108	\N
95	2026-08-25 11:03:50.402548	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: fabianomotta	100.114.24.108	\N
96	2026-08-25 11:04:19.91458	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: fabianomotta	100.114.24.108	\N
97	2026-08-25 11:04:31.25973	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: fabianomotta	100.114.24.108	\N
98	2026-08-25 11:12:00.29042	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: fabianomotta	100.85.249.40	\N
99	2026-08-25 11:15:36.18348	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: fabianomotta	100.85.249.40	\N
100	2026-08-25 11:17:00.217029	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: fabianomotta	100.85.249.40	\N
101	2026-08-25 11:17:49.377051	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: fabianomotta	100.85.249.40	\N
102	2026-08-25 11:17:53.198919	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: fabianomotta	100.85.249.40	\N
103	2026-08-25 11:26:34.308172	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: fabianomotta	100.85.249.40	\N
104	2026-08-25 11:30:09.195683	5	Fabiano Motta	Acesso Aprovado	Usuário Fabiano Motta acessou o sistema.	100.85.249.40	\N
105	2026-08-25 11:30:16.646275	5	Fabiano Motta	Logoff	Sessão encerrada voluntariamente.	100.85.249.40	\N
106	2026-08-25 11:49:52.161488	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: laisdecarvalho	100.87.69.9	\N
107	2026-08-25 11:50:03.619623	30	Laiscarvalho	Acesso Aprovado	Usuário Laiscarvalho acessou o sistema.	100.87.69.9	\N
108	2026-08-25 11:50:48.876675	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
109	2026-08-25 11:52:08.984973	1	Administrador	Alteração de Cadastros	Admin alterou laiscarvalho@pgrael.local.	100.85.249.40	\N
110	2026-08-25 11:52:50.860087	30	Laiscarvalho	Acesso Aprovado	Usuário Laiscarvalho acessou o sistema.	100.87.69.9	\N
111	2026-08-25 11:53:54.541792	30	Laiscarvalho	Acesso Aprovado	Usuário Laiscarvalho acessou o sistema.	100.87.69.9	\N
112	2026-08-25 12:01:30.475281	1	Administrador	Cadastro Período Letivo	Criado período 2026.2 para unidade MGB	100.85.249.40	\N
113	2026-08-25 12:09:17.741215	1	Administrador	Logoff	Sessão encerrada voluntariamente.	100.85.249.40	\N
114	2026-08-25 12:09:26.075563	5	Fabiano Motta	Acesso Aprovado	Usuário Fabiano Motta acessou o sistema.	100.85.249.40	\N
115	2026-08-25 12:10:44.678707	5	Fabiano Motta	Logoff	Sessão encerrada voluntariamente.	100.85.249.40	\N
175	2026-09-09 22:31:35.973363	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
169	2026-09-09 21:59:28.776261	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
166	2026-09-09 21:51:52.048722	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
163	2026-09-09 21:41:31.92086	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
160	2026-09-09 21:33:23.132163	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
116	2026-08-25 12:11:11.095109	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
117	2026-08-25 16:08:12.484915	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
118	2026-08-25 16:12:10.445048	1	Administrador	Cadastro Local	Admin gerou conta manual: gerente@email.com	100.85.249.40	\N
119	2026-08-25 16:12:32.499205	31	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	::1	\N
120	2026-08-25 16:13:09.984182	31	Gerente	Troca de Senha	Gerente definiu nova senha.	::1	\N
122	2026-08-25 16:28:46.687157	1	Administrador	Logoff	Sessão encerrada voluntariamente.	100.85.249.40	\N
123	2026-08-25 16:28:56.627625	35	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	100.85.249.40	\N
124	2026-08-25 16:29:16.503861	31	Gerente	Logoff	Sessão encerrada voluntariamente.	::1	\N
125	2026-08-25 16:29:56.970742	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	::1	\N
126	2026-08-25 16:30:33.36481	1	Administrador	Alteração de Cadastros	Admin alterou gerente@pgrael.local.	::1	\N
127	2026-08-25 17:19:31.653421	35	Gerente	Logoff	Sessão encerrada voluntariamente.	100.85.249.40	\N
128	2026-08-31 16:58:09.108817	6	Maria Fabíola	Acesso Aprovado	Usuário Maria Fabíola acessou o sistema.	192.168.1.42	\N
129	2026-09-03 08:58:43.393711	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
130	2026-09-03 11:07:36.993522	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
131	2026-09-04 11:54:41.548098	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: claudiaromao@projetograel.org.br	100.80.160.117	\N
132	2026-09-04 12:01:32.931403	23	Cláudia Romão	Acesso Aprovado	Usuário Cláudia Romão acessou o sistema.	100.85.249.40	\N
133	2026-09-04 12:03:34.932193	23	Cláudia Romão	Acesso Aprovado	Usuário Cláudia Romão acessou o sistema.	100.85.249.40	\N
134	2026-09-04 12:08:17.591704	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
135	2026-09-08 15:38:49.30228	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
139	2026-09-08 18:00:51.219154	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
149	2026-09-09 11:11:29.142376	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
153	2026-09-09 11:36:48.277429	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
158	2026-09-09 16:24:47.540091	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
210	2026-09-10 10:22:02.441455	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
176	2026-09-09 22:36:23.705824	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
173	2026-09-09 22:15:17.473072	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
170	2026-09-09 22:03:04.906189	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
218	2026-09-10 11:50:04.831677	1	Administrador	Remoção Grave	O perfil de gerencia_95238b57@email.com foi apagado.	100.85.249.40	\N
219	2026-09-10 11:50:08.19543	1	Administrador	Remoção Grave	O perfil de gerencia_5d968c46@email.com foi apagado.	100.85.249.40	\N
220	2026-09-10 11:50:11.367784	1	Administrador	Remoção Grave	O perfil de gerencia_329fa6cf@email.com foi apagado.	100.85.249.40	\N
164	2026-09-09 21:44:17.54111	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
221	2026-09-10 11:50:14.243288	1	Administrador	Remoção Grave	O perfil de gerencia_12009e65@email.com foi apagado.	100.85.249.40	\N
222	2026-09-10 11:50:17.145543	1	Administrador	Remoção Grave	O perfil de gerencia_76307eac@email.com foi apagado.	100.85.249.40	\N
223	2026-09-10 11:50:20.159418	1	Administrador	Remoção Grave	O perfil de gerencia_0fe62b52@email.com foi apagado.	100.85.249.40	\N
161	2026-09-09 21:34:46.069862	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
224	2026-09-10 11:50:23.199958	1	Administrador	Remoção Grave	O perfil de gerencia_90e56594@email.com foi apagado.	100.85.249.40	\N
225	2026-09-10 11:50:26.503581	1	Administrador	Remoção Grave	O perfil de gerencia_b2ed53d8@email.com foi apagado.	100.85.249.40	\N
167	2026-09-09 21:52:36.08726	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
226	2026-09-10 11:50:29.60196	1	Administrador	Remoção Grave	O perfil de gerencia_f68e8f0d@email.com foi apagado.	100.85.249.40	\N
121	2026-08-25 16:19:14.234781	\N	Gerente	Acesso Aprovado	Usuário Gerente acessou o sistema.	127.0.0.1	\N
227	2026-09-10 11:50:35.912912	1	Administrador	Remoção Grave	O perfil de gerencia_085b43a2@email.com foi apagado.	100.85.249.40	\N
228	2026-09-10 11:50:54.964204	1	Administrador	Alteração de Cadastros	Admin alterou laiscarvalho@pgrael.local.	100.85.249.40	\N
230	2026-09-10 14:06:33.623341	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
233	2026-09-10 18:15:58.598136	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
235	2026-09-11 10:42:20.318087	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
237	2026-09-11 14:31:51.438002	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
239	2026-09-11 17:51:50.818312	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
241	2026-09-14 13:48:27.919315	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: raquelcrispim@projetograel.org.br	100.116.200.116	\N
242	2026-09-14 13:48:37.840349	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: raquelcrispim@projetograel.org.br	100.116.200.116	\N
243	2026-09-14 13:51:00.458086	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
245	2026-09-14 16:47:27.274495	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
248	2026-09-15 09:07:03.520299	1	Administrador	Logoff	Sessão encerrada voluntariamente.	100.85.249.40	\N
252	2026-09-15 10:25:44.465954	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
253	2026-09-15 10:25:55.952052	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	::1	\N
255	2026-09-15 10:34:49.518362	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	::1	\N
257	2026-09-15 11:48:30.035528	1	Administrador	Informacao Padrao	Administrador atualizou dados institucionais padrao.	100.85.249.40	\N
259	2026-09-15 17:52:37.380739	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
263	2026-09-16 07:55:51.361716	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
266	2026-09-16 10:36:47.357017	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
276	2026-09-21 12:14:36.337346	1	Administrador	Alteração de Cadastros	Admin alterou Alinelopes@pgrael.local.	100.85.249.40	\N
277	2026-09-21 17:12:55.196485	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
278	2026-09-22 07:48:44.425143	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
279	2026-09-22 08:55:09.438178	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
280	2026-09-22 10:14:41.688377	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
281	2026-09-22 11:16:42.734474	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
282	2026-09-22 15:06:44.593336	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
283	2026-09-22 17:04:02.296148	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: admin@email.com	100.85.249.40	\N
284	2026-09-22 17:04:17.894835	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: admin@email.com	100.85.249.40	\N
285	2026-09-22 17:04:53.98763	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: admin@email.com	100.85.249.40	\N
286	2026-09-22 17:05:11.069219	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: admin@email.com	100.85.249.40	\N
287	2026-09-22 17:09:03.889757	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: admin@email.com	100.85.249.40	\N
288	2026-09-22 17:10:44.030241	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
289	2026-09-22 17:10:58.239698	1	Administrador	Troca de Senha	Administrador definiu nova senha.	100.85.249.40	\N
290	2026-09-22 21:53:07.463624	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
291	2026-09-23 09:49:11.326414	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: raquelcrispim@projetograel.org.br	100.116.200.116	\N
292	2026-09-23 09:49:20.530784	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: raquelcrispim@projetograel.org.br	100.116.200.116	\N
293	2026-09-23 09:49:32.166687	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: raquelcrispim@projetograel.org.br	100.116.200.116	\N
294	2026-09-23 09:49:32.318595	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: raquelcrispim@projetograel.org.br	100.116.200.116	\N
295	2026-09-23 09:49:32.520517	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: raquelcrispim@projetograel.org.br	100.116.200.116	\N
296	2026-09-23 09:49:32.665675	\N	Anônimo/Sistema	Aviso de Invasão/Falha	Login declinado para alvo de e-mail: raquelcrispim@projetograel.org.br	100.116.200.116	\N
297	2026-09-23 09:51:50.584097	22	Raquel Crispim	Acesso Aprovado	Usuário Raquel Crispim acessou o sistema.	100.116.200.116	\N
298	2026-09-23 09:57:22.074643	1	Administrador	Acesso Aprovado	Usuário Administrador acessou o sistema.	100.85.249.40	\N
\.


--
-- Data for Name: nivel; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.nivel (id, nome, ativo, unidade_id) FROM stdin;
1	Básico	t	1
2	Intermediário I	t	1
3	Intermediário II	t	1
4	Avançado	t	1
\.


--
-- Data for Name: opcao_proxima_turma; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.opcao_proxima_turma (id, nome, ativo) FROM stdin;
\.


--
-- Data for Name: periodo_conselho; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.periodo_conselho (id, nome, data_inicio, data_fim, conselho_final, periodo_letivo_id, unidade_id) FROM stdin;
\.


--
-- Data for Name: periodo_letivo; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.periodo_letivo (id, nome, data_inicio, data_fim, centro_custo, estimativa_alunos, ativo, unidade_id, created_at, updated_at) FROM stdin;
1	NIT-2026.2	2026-08-03	2026-12-08	Petrobras, Mar de Oportunidades	518	t	1	2026-07-30 16:09:06.044447	\N
2	2026.2	2026-08-25	2026-10-30	Ventos de Cidadania	106	t	2	2026-08-25 12:01:30.469003	2026-09-09 14:39:16.373706
\.


--
-- Data for Name: registro; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.registro (id, educador_id, turma, mes, turno, dados_json, criado_em, unidade_id) FROM stdin;
\.


--
-- Data for Name: registro_aula; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.registro_aula (id, turma_id, data, tema_id, observacoes, instrutor_id, created_at, unidade_id) FROM stdin;
\.


--
-- Data for Name: respostas_formulario; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.respostas_formulario (id, tipo_formulario, aluno_id, usuario_id, dados, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: situacao_escolar; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.situacao_escolar (id, aluno_id, unidade_id, escolaridade, ensino_superior_periodo, escolaridade_outro, nome_instituicao, tipo_instituicao, bolsista, tipo_instituicao_outro, turno, turno_outro, created_at, updated_at, status, status_outro) FROM stdin;
1	1449	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Tarde	\N	2026-09-11 14:40:43.995542	2026-09-11 14:40:43.995546	Cursando	\N
2	1399	2	Ensino fundamental	\N	\N	EDC - Escola Delmiro Cabral	Pública	f	\N	Manhã	\N	2026-09-11 15:09:19.562254	2026-09-11 15:09:19.562263	Cursando	\N
3	1352	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Tarde	\N	2026-09-11 15:17:44.704215	2026-09-11 15:17:44.70422	Cursando	\N
4	1379	2	Ensino fundamental	\N	\N	EDC - Escola Delmiro Cabral	Privada	f	\N	Tarde	\N	2026-09-11 15:22:00.537316	2026-09-11 15:22:00.537323	Cursando	\N
5	1426	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Manhã	\N	2026-09-11 15:32:10.749107	2026-09-11 15:32:10.749113	Cursando	\N
6	1427	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Tarde	\N	2026-09-11 15:40:15.451409	2026-09-11 15:40:15.45142	Cursando	\N
7	1428	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Manhã	\N	2026-09-11 16:02:20.933038	2026-09-11 16:02:20.933046	Cursando	\N
8	1429	2	Ensino médio	\N	\N	CEJAM - Profª Andrea Felix de Oliveira Dias	Pública	f	\N	Noite	\N	2026-09-11 16:07:52.864157	2026-09-11 16:07:52.864162	Concluinte	\N
9	1430	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Manhã	\N	2026-09-11 16:36:56.548819	2026-09-11 16:36:56.548827	Cursando	\N
10	1431	2	Ensino médio	\N	\N	Colégio Estadual João Paulo II	Pública	f	\N	Manhã	\N	2026-09-11 16:41:31.445087	2026-09-11 16:41:31.445092	Cursando	\N
11	1401	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Manhã	\N	2026-09-14 13:54:50.224337	2026-09-14 13:54:50.224342	Cursando	\N
12	1432	2	Ensino fundamental	\N	\N	Centro Educacional Espaço Curumim	Privada	f	\N	Manhã	\N	2026-09-14 14:03:29.653367	2026-09-14 14:03:29.653374	Cursando	\N
13	1434	2	Ensino fundamental	\N	\N	Colégio Municipal Nossa Senhora das Graças	Pública	f	\N	Manhã	\N	2026-09-14 14:09:55.862678	2026-09-14 14:09:55.862683	Cursando	\N
14	1350	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Manhã	\N	2026-09-14 16:08:01.435222	2026-09-14 16:08:01.435231	Cursando	\N
15	1344	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Manhã	\N	2026-09-14 16:15:22.400355	2026-09-14 16:15:22.400366	Cursando	\N
16	1433	2	Ensino fundamental	\N	\N	Centro Educacional Espaço Curumim	Privada	f	\N	Tarde	\N	2026-09-15 14:33:49.137424	2026-09-15 14:33:49.13743	Cursando	\N
17	1406	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba		f	\N	Manhã	\N	2026-09-15 14:58:14.44066	2026-09-15 14:58:14.440667	Cursando	\N
18	1384	2	Ensino fundamental	\N	\N	Centro Educacional Espaço Curumim	Privada	f	\N	Tarde	\N	2026-09-16 08:14:30.901256	2026-09-16 08:14:30.901262	Cursando	\N
19	1435	2	Ensino fundamental	\N	\N	Colégio Municipal Nossa Senhora das Graças	Pública	f	\N	Manhã	\N	2026-09-16 08:22:46.497562	2026-09-16 08:22:46.497568	Cursando	\N
20	1356	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Manhã	\N	2026-09-16 08:40:39.881095	2026-09-16 08:40:39.8811	Cursando	\N
21	1388	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Manhã	\N	2026-09-16 08:48:04.310966	2026-09-16 08:48:04.310972	Cursando	\N
22	1389	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Manhã	\N	2026-09-16 08:57:25.981599	2026-09-16 08:57:25.981604	Cursando	\N
23	1411	2	Ensino médio	\N	\N	Colégio Estadual João Paulo II	Pública	f	\N	Manhã	\N	2026-09-16 11:34:35.952262	2026-09-16 11:34:35.95227	Cursando	\N
24	1358	2	Ensino fundamental	\N	\N	Centro Educacional Espaço Curumim	Privada	f	\N	Tarde	\N	2026-09-16 11:41:09.302527	2026-09-16 11:41:09.302532	Cursando	\N
25	1436	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Manhã	\N	2026-09-16 14:36:31.268238	2026-09-16 14:36:31.268243	Cursando	\N
26	1437	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Manhã	\N	2026-09-16 14:41:40.896495	2026-09-16 14:41:40.8965	Cursando	\N
27	1373	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Manhã	\N	2026-09-16 14:49:15.382353	2026-09-16 14:49:15.382361	Cursando	\N
28	1360	2	Ensino fundamental	\N	\N	Cemu 3 - Centro Educacional de Muriqui	Privada	f	\N	Manhã	\N	2026-09-17 08:45:04.77099	2026-09-17 08:45:04.770997	Cursando	\N
29	1414	2	Ensino fundamental	\N	\N	Escola Municipal Maria Augusta Lopes	Pública	f	\N	Manhã	\N	2026-09-17 08:53:28.782799	2026-09-17 08:53:28.782805	Cursando	\N
30	1376	2	Ensino fundamental	\N	\N	CEMU - Centro Educacional de Muriqui	Privada	f	\N	Manhã	\N	2026-09-17 09:14:53.006882	2026-09-17 09:14:53.006888	Cursando	\N
31	1450	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N		\N	2026-09-22 09:01:45.708201	2026-09-22 09:01:45.708207	Cursando	\N
32	1381	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Manhã	\N	2026-09-22 10:01:02.409646	2026-09-22 10:01:02.409657	Cursando	\N
33	1395	2	Ensino fundamental	\N	\N	CEMU 2 - Centro Educacional de Muriqui	Privada	f	\N	Manhã	\N	2026-09-22 10:20:18.650979	2026-09-22 10:20:18.650985	Cursando	\N
34	1363	2	Ensino fundamental	\N	\N	CEMU 2 - Centro Educacional de Muriqui	Privada	f	\N	Manhã	\N	2026-09-22 10:27:26.188652	2026-09-22 10:27:26.188662	Cursando	\N
35	1375	2	Ensino fundamental	\N	\N	CEMU 2 - Centro Educacional de Muriqui	Privada	f	\N	Manhã	\N	2026-09-22 10:32:47.380429	2026-09-22 10:32:47.380435	Cursando	\N
36	1366	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N		\N	2026-09-22 10:39:36.177108	2026-09-22 10:39:36.177116	Cursando	\N
37	1345	2	Ensino fundamental	\N	\N	Cemu 3 - Centro Educacional de Muriqui	Privada	f	\N	Tarde	\N	2026-09-22 10:54:22.116152	2026-09-22 10:54:22.116158	Cursando	\N
38	1421	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Tarde	\N	2026-09-22 11:25:03.08457	2026-09-22 11:25:03.084578	Cursando	\N
39	1422	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Manhã	\N	2026-09-22 11:31:02.120943	2026-09-22 11:31:02.12095	Cursando	\N
40	1439	2	Ensino fundamental	\N	\N	Colégio Municipal Nossa Senhora das Graças	Pública	f	\N	Manhã	\N	2026-09-22 11:42:08.369694	2026-09-22 11:42:08.3697	Cursando	\N
41	1440	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Manhã	\N	2026-09-22 15:21:00.210291	2026-09-22 15:21:00.210296	Cursando	\N
42	1357	2	Ensino médio	\N	\N	Colégio Estadual João Paulo II	Pública	f	\N	Manhã	\N	2026-09-23 10:08:12.384345	2026-09-23 10:08:12.384351	Cursando	\N
43	1441	2	Ensino fundamental	\N	\N	Centro Educacional Espaço Curumim	Privada	f	\N	Manhã	\N	2026-09-23 10:17:28.518634	2026-09-23 10:17:28.518643	Cursando	\N
44	1378	2	Ensino fundamental	\N	\N	Escola Municipal Coronel Moreira da Silva	Pública	f	\N	Manhã	\N	2026-09-23 10:36:50.57569	2026-09-23 10:36:50.575697	Cursando	\N
45	1409	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Tarde	\N	2026-09-23 10:49:35.615672	2026-09-23 10:49:35.615677	Cursando	\N
46	1385	2	Ensino fundamental	\N	\N	CIEP Brizolão 294 Candido Jorge Capixaba	Pública	f	\N	Manhã	\N	2026-09-23 11:12:03.654178	2026-09-23 11:12:03.654184	Cursando	\N
47	1413	2	Ensino fundamental	\N	\N	Centro Educacional Espaço Curumim	Privada	f	\N	Manhã	\N	2026-09-23 11:28:11.398432	2026-09-23 11:28:11.398438	Cursando	\N
48	1415	2	Ensino fundamental	\N	\N	Colégio Adventista de Itaguaí	Privada	f	\N	Manhã	\N	2026-09-23 11:53:10.930031	2026-09-23 11:53:10.930038	Cursando	\N
\.


--
-- Data for Name: tema_aula; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.tema_aula (id, curso_id, turma_id, unidade_id, titulo, programa, ativo, data, ordem) FROM stdin;
1	1	\N	1	Tour pelo Projeto	\N	t	\N	1
2	1	\N	1	Nadar	\N	t	\N	2
3	2	\N	2	Introdução à mecânica	\N	t	\N	1
\.


--
-- Data for Name: transferencia; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.transferencia (id, aluno_id, turma_origem_id, turma_destino_id, data_transferencia, observacoes, unidade_id) FROM stdin;
\.


--
-- Data for Name: turma; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.turma (id, nome, ativo, data_inicio, data_fim, hora_inicio, hora_fim, dias_semana, programa, turno, centro_custo, ordenacao, unidade_id, periodo_letivo_id, curso_id, professor_id, avaliacao_inicial, avaliacao_percurso, avaliacao_final, conselho_concluido) FROM stdin;
1	 Natação das 8h - 3 e 5	t	2026-08-04	2026-12-03	08:00	09:00	Terça, Quinta	Esporte	Manhã	Petrobras	1	1	1	1	\N	\N	\N	\N	f
\.


--
-- Data for Name: unidade; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.unidade (id, nome, ativo) FROM stdin;
1	NIT	t
2	MGB	t
\.


--
-- Data for Name: user; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public."user" (id, name, email, password, role, is_active, is_ad_user, unidade_id, first_login, google_id, google_email) FROM stdin;
5	Fabiano Motta	fabianomotta@pgrael.local	scrypt:32768:8:1$mYmT8QYdJ3N58AVs$26898460540400d8f06bea5023a62a74abcef5be36f1cd8d538d31999e11b750cd3b315b79a3115dc644805827fa29049803561557ad3f4bbc5fbb01eece58c4	professor	t	t	1	f	\N	\N
6	Maria Fabíola	mfabiolaraposo@pgrael.local	scrypt:32768:8:1$QuJfdZo9DuZuTlUr$72c113156206b9ec030dcc34108fa33eb5c628e213713a4dd463005f4c1a039bf37d054db8c1070c82880304a7bfb996a647991e8e265ebbaeae34b522af6662	secretaria	t	t	1	f	\N	\N
22	Raquel Crispim	raquelcrispim@projetograel.org.br	scrypt:32768:8:1$zQaakNyKEX9dvZZg$66f2f9c2aa1c0db76854878cb59cc6ca0cffae52d35cfc1104ba440bceb30231b94fcc609a3d132f47431fd1e2d86ae259f64189966c9ffb61a2cb9f4d47e8c5	secretaria	t	f	2	f	\N	\N
24	MGB	mgb@projetograel.org.br	scrypt:32768:8:1$KnFVF7ny3TKfAeb4$2e7178a93b2133fb48764953d98481d8605069550009d8e2dacc2172b3e2caefee8181252366bff1e4c6b7faa083f9f729683fbe0fd4ffad08b44987fb0c3725	pedagogico	t	f	2	f	\N	\N
31	Gerente	gerente@email.com	scrypt:32768:8:1$31BKby9PFokvRWxU$5b3a226af8d92431d4866248ccba36e02da3aa7d7ceaf94e7b051ee371c49abc310deeb07b0441074beec37013d4db09758c748c50eab790168c4ef733fa0337	gerencia	t	f	\N	f	\N	\N
35	Gerente	gerente@pgrael.local		gerencia	t	t	\N	f	\N	\N
23	Cláudia Romão	claudiaromao@projetograel.org.br	scrypt:32768:8:1$YzKLHZ9a0fLyYNIf$2500c7626ff0ec75577b83aaa2942fc4d6f7b70736e532cfb45b62881c36c49833aa3d2022091d45eb144c376684cb301388e8eb8e3a8bed3bf9da821d6e4032	pedagogico	t	f	2	f	\N	\N
30	Lais Carvalho	laiscarvalho@pgrael.local		gerencia	t	t	\N	f	\N	\N
84	Alinelopes	Alinelopes@pgrael.local		secretaria	t	t	1	f	\N	\N
1	Administrador	admin@email.com	scrypt:32768:8:1$73NGTih3klpTnrix$0b5bc099eaaf3ed156d72ed6e1b3321fe6b0224f754b90e48f563ba5bb2c83af2ad4a8d819d688ae05b8819dab8b27d4df5e66a7c3c1a372b17d549584be1bfe	admin	t	f	\N	f	\N	\N
\.


--
-- Name: agenda_servico_social_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.agenda_servico_social_id_seq', 1, false);


--
-- Name: aluno_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.aluno_id_seq', 1450, true);


--
-- Name: atendimento_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.atendimento_id_seq', 1, true);


--
-- Name: configuracao_sistema_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.configuracao_sistema_id_seq', 6, true);


--
-- Name: conselho_classe_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.conselho_classe_id_seq', 1, false);


--
-- Name: conselho_pergunta_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.conselho_pergunta_id_seq', 2, true);


--
-- Name: conselho_resposta_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.conselho_resposta_id_seq', 1, false);


--
-- Name: curso_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.curso_id_seq', 2, true);


--
-- Name: dia_bloqueado_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.dia_bloqueado_id_seq', 7, true);


--
-- Name: dia_bloqueado_turma_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.dia_bloqueado_turma_id_seq', 1, false);


--
-- Name: frequencia_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.frequencia_id_seq', 1, false);


--
-- Name: log_acao_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.log_acao_id_seq', 298, true);


--
-- Name: nivel_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.nivel_id_seq', 4, true);


--
-- Name: opcao_proxima_turma_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.opcao_proxima_turma_id_seq', 1, false);


--
-- Name: periodo_conselho_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.periodo_conselho_id_seq', 1, false);


--
-- Name: periodo_letivo_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.periodo_letivo_id_seq', 2, true);


--
-- Name: registro_aula_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.registro_aula_id_seq', 1, false);


--
-- Name: registro_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.registro_id_seq', 1, false);


--
-- Name: respostas_formulario_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.respostas_formulario_id_seq', 1, false);


--
-- Name: situacao_escolar_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.situacao_escolar_id_seq', 48, true);


--
-- Name: tema_aula_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.tema_aula_id_seq', 3, true);


--
-- Name: transferencia_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.transferencia_id_seq', 1, false);


--
-- Name: turma_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.turma_id_seq', 1, true);


--
-- Name: unidade_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.unidade_id_seq', 2, true);


--
-- Name: user_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.user_id_seq', 85, true);


--
-- Name: agenda_servico_social agenda_servico_social_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agenda_servico_social
    ADD CONSTRAINT agenda_servico_social_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: aluno aluno_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aluno
    ADD CONSTRAINT aluno_pkey PRIMARY KEY (id);


--
-- Name: atendimento atendimento_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atendimento
    ADD CONSTRAINT atendimento_pkey PRIMARY KEY (id);


--
-- Name: configuracao_sistema configuracao_sistema_chave_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.configuracao_sistema
    ADD CONSTRAINT configuracao_sistema_chave_key UNIQUE (chave);


--
-- Name: configuracao_sistema configuracao_sistema_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.configuracao_sistema
    ADD CONSTRAINT configuracao_sistema_pkey PRIMARY KEY (id);


--
-- Name: conselho_classe conselho_classe_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conselho_classe
    ADD CONSTRAINT conselho_classe_pkey PRIMARY KEY (id);


--
-- Name: conselho_pergunta conselho_pergunta_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conselho_pergunta
    ADD CONSTRAINT conselho_pergunta_pkey PRIMARY KEY (id);


--
-- Name: conselho_resposta conselho_resposta_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conselho_resposta
    ADD CONSTRAINT conselho_resposta_pkey PRIMARY KEY (id);


--
-- Name: curso curso_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.curso
    ADD CONSTRAINT curso_pkey PRIMARY KEY (id);


--
-- Name: dia_bloqueado dia_bloqueado_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dia_bloqueado
    ADD CONSTRAINT dia_bloqueado_pkey PRIMARY KEY (id);


--
-- Name: dia_bloqueado_turma dia_bloqueado_turma_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dia_bloqueado_turma
    ADD CONSTRAINT dia_bloqueado_turma_pkey PRIMARY KEY (id);


--
-- Name: frequencia frequencia_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.frequencia
    ADD CONSTRAINT frequencia_pkey PRIMARY KEY (id);


--
-- Name: inscricoes inscricoes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inscricoes
    ADD CONSTRAINT inscricoes_pkey PRIMARY KEY (aluno_id, turma_id);


--
-- Name: log_acao log_acao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_acao
    ADD CONSTRAINT log_acao_pkey PRIMARY KEY (id);


--
-- Name: nivel nivel_nome_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nivel
    ADD CONSTRAINT nivel_nome_key UNIQUE (nome);


--
-- Name: nivel nivel_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nivel
    ADD CONSTRAINT nivel_pkey PRIMARY KEY (id);


--
-- Name: opcao_proxima_turma opcao_proxima_turma_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opcao_proxima_turma
    ADD CONSTRAINT opcao_proxima_turma_pkey PRIMARY KEY (id);


--
-- Name: periodo_conselho periodo_conselho_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodo_conselho
    ADD CONSTRAINT periodo_conselho_pkey PRIMARY KEY (id);


--
-- Name: periodo_letivo periodo_letivo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodo_letivo
    ADD CONSTRAINT periodo_letivo_pkey PRIMARY KEY (id);


--
-- Name: registro_aula registro_aula_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registro_aula
    ADD CONSTRAINT registro_aula_pkey PRIMARY KEY (id);


--
-- Name: registro registro_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registro
    ADD CONSTRAINT registro_pkey PRIMARY KEY (id);


--
-- Name: respostas_formulario respostas_formulario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respostas_formulario
    ADD CONSTRAINT respostas_formulario_pkey PRIMARY KEY (id);


--
-- Name: situacao_escolar situacao_escolar_aluno_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.situacao_escolar
    ADD CONSTRAINT situacao_escolar_aluno_id_key UNIQUE (aluno_id);


--
-- Name: situacao_escolar situacao_escolar_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.situacao_escolar
    ADD CONSTRAINT situacao_escolar_pkey PRIMARY KEY (id);


--
-- Name: tema_aula tema_aula_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tema_aula
    ADD CONSTRAINT tema_aula_pkey PRIMARY KEY (id);


--
-- Name: transferencia transferencia_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transferencia
    ADD CONSTRAINT transferencia_pkey PRIMARY KEY (id);


--
-- Name: turma turma_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.turma
    ADD CONSTRAINT turma_pkey PRIMARY KEY (id);


--
-- Name: dia_bloqueado_turma uix_dia_bloqueado_turma; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dia_bloqueado_turma
    ADD CONSTRAINT uix_dia_bloqueado_turma UNIQUE (turma_id, data);


--
-- Name: unidade unidade_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.unidade
    ADD CONSTRAINT unidade_pkey PRIMARY KEY (id);


--
-- Name: user user_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_email_key UNIQUE (email);


--
-- Name: user user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (id);


--
-- Name: ix_situacao_escolar_unidade_nome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_situacao_escolar_unidade_nome ON public.situacao_escolar USING btree (unidade_id, nome_instituicao);


--
-- Name: ix_user_google_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_user_google_id ON public."user" USING btree (google_id);


--
-- Name: agenda_servico_social agenda_servico_social_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.agenda_servico_social
    ADD CONSTRAINT agenda_servico_social_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: aluno aluno_created_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aluno
    ADD CONSTRAINT aluno_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES public."user"(id);


--
-- Name: aluno aluno_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aluno
    ADD CONSTRAINT aluno_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: atendimento atendimento_aluno_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atendimento
    ADD CONSTRAINT atendimento_aluno_id_fkey FOREIGN KEY (aluno_id) REFERENCES public.aluno(id);


--
-- Name: atendimento atendimento_atendido_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atendimento
    ADD CONSTRAINT atendimento_atendido_por_id_fkey FOREIGN KEY (atendido_por_id) REFERENCES public."user"(id);


--
-- Name: atendimento atendimento_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.atendimento
    ADD CONSTRAINT atendimento_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: configuracao_sistema configuracao_sistema_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.configuracao_sistema
    ADD CONSTRAINT configuracao_sistema_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: conselho_classe conselho_classe_aluno_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conselho_classe
    ADD CONSTRAINT conselho_classe_aluno_id_fkey FOREIGN KEY (aluno_id) REFERENCES public.aluno(id);


--
-- Name: conselho_classe conselho_classe_instrutor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conselho_classe
    ADD CONSTRAINT conselho_classe_instrutor_id_fkey FOREIGN KEY (instrutor_id) REFERENCES public."user"(id);


--
-- Name: conselho_classe conselho_classe_proxima_turma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conselho_classe
    ADD CONSTRAINT conselho_classe_proxima_turma_id_fkey FOREIGN KEY (proxima_turma_id) REFERENCES public.opcao_proxima_turma(id);


--
-- Name: conselho_classe conselho_classe_turma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conselho_classe
    ADD CONSTRAINT conselho_classe_turma_id_fkey FOREIGN KEY (turma_id) REFERENCES public.turma(id);


--
-- Name: conselho_classe conselho_classe_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conselho_classe
    ADD CONSTRAINT conselho_classe_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: conselho_resposta conselho_resposta_aluno_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conselho_resposta
    ADD CONSTRAINT conselho_resposta_aluno_id_fkey FOREIGN KEY (aluno_id) REFERENCES public.aluno(id);


--
-- Name: conselho_resposta conselho_resposta_conselho_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conselho_resposta
    ADD CONSTRAINT conselho_resposta_conselho_id_fkey FOREIGN KEY (conselho_id) REFERENCES public.conselho_classe(id);


--
-- Name: conselho_resposta conselho_resposta_pergunta_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conselho_resposta
    ADD CONSTRAINT conselho_resposta_pergunta_id_fkey FOREIGN KEY (pergunta_id) REFERENCES public.conselho_pergunta(id);


--
-- Name: conselho_resposta conselho_resposta_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.conselho_resposta
    ADD CONSTRAINT conselho_resposta_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: curso curso_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.curso
    ADD CONSTRAINT curso_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: dia_bloqueado dia_bloqueado_criado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dia_bloqueado
    ADD CONSTRAINT dia_bloqueado_criado_por_id_fkey FOREIGN KEY (criado_por_id) REFERENCES public."user"(id);


--
-- Name: dia_bloqueado dia_bloqueado_periodo_letivo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dia_bloqueado
    ADD CONSTRAINT dia_bloqueado_periodo_letivo_id_fkey FOREIGN KEY (periodo_letivo_id) REFERENCES public.periodo_letivo(id);


--
-- Name: dia_bloqueado_turma dia_bloqueado_turma_criado_por_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dia_bloqueado_turma
    ADD CONSTRAINT dia_bloqueado_turma_criado_por_id_fkey FOREIGN KEY (criado_por_id) REFERENCES public."user"(id);


--
-- Name: dia_bloqueado_turma dia_bloqueado_turma_turma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dia_bloqueado_turma
    ADD CONSTRAINT dia_bloqueado_turma_turma_id_fkey FOREIGN KEY (turma_id) REFERENCES public.turma(id);


--
-- Name: dia_bloqueado_turma dia_bloqueado_turma_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dia_bloqueado_turma
    ADD CONSTRAINT dia_bloqueado_turma_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: dia_bloqueado dia_bloqueado_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dia_bloqueado
    ADD CONSTRAINT dia_bloqueado_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: frequencia frequencia_aluno_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.frequencia
    ADD CONSTRAINT frequencia_aluno_id_fkey FOREIGN KEY (aluno_id) REFERENCES public.aluno(id);


--
-- Name: frequencia frequencia_turma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.frequencia
    ADD CONSTRAINT frequencia_turma_id_fkey FOREIGN KEY (turma_id) REFERENCES public.turma(id);


--
-- Name: frequencia frequencia_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.frequencia
    ADD CONSTRAINT frequencia_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: inscricoes inscricoes_aluno_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inscricoes
    ADD CONSTRAINT inscricoes_aluno_id_fkey FOREIGN KEY (aluno_id) REFERENCES public.aluno(id);


--
-- Name: inscricoes inscricoes_turma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inscricoes
    ADD CONSTRAINT inscricoes_turma_id_fkey FOREIGN KEY (turma_id) REFERENCES public.turma(id);


--
-- Name: log_acao log_acao_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_acao
    ADD CONSTRAINT log_acao_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: log_acao log_acao_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.log_acao
    ADD CONSTRAINT log_acao_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public."user"(id);


--
-- Name: nivel nivel_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.nivel
    ADD CONSTRAINT nivel_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: periodo_conselho periodo_conselho_periodo_letivo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodo_conselho
    ADD CONSTRAINT periodo_conselho_periodo_letivo_id_fkey FOREIGN KEY (periodo_letivo_id) REFERENCES public.periodo_letivo(id);


--
-- Name: periodo_conselho periodo_conselho_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodo_conselho
    ADD CONSTRAINT periodo_conselho_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: periodo_letivo periodo_letivo_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.periodo_letivo
    ADD CONSTRAINT periodo_letivo_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: registro_aula registro_aula_instrutor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registro_aula
    ADD CONSTRAINT registro_aula_instrutor_id_fkey FOREIGN KEY (instrutor_id) REFERENCES public."user"(id);


--
-- Name: registro_aula registro_aula_tema_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registro_aula
    ADD CONSTRAINT registro_aula_tema_id_fkey FOREIGN KEY (tema_id) REFERENCES public.tema_aula(id);


--
-- Name: registro_aula registro_aula_turma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registro_aula
    ADD CONSTRAINT registro_aula_turma_id_fkey FOREIGN KEY (turma_id) REFERENCES public.turma(id);


--
-- Name: registro_aula registro_aula_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registro_aula
    ADD CONSTRAINT registro_aula_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: registro registro_educador_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registro
    ADD CONSTRAINT registro_educador_id_fkey FOREIGN KEY (educador_id) REFERENCES public."user"(id);


--
-- Name: registro registro_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registro
    ADD CONSTRAINT registro_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: respostas_formulario respostas_formulario_aluno_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respostas_formulario
    ADD CONSTRAINT respostas_formulario_aluno_id_fkey FOREIGN KEY (aluno_id) REFERENCES public.aluno(id);


--
-- Name: respostas_formulario respostas_formulario_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.respostas_formulario
    ADD CONSTRAINT respostas_formulario_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public."user"(id);


--
-- Name: situacao_escolar situacao_escolar_aluno_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.situacao_escolar
    ADD CONSTRAINT situacao_escolar_aluno_id_fkey FOREIGN KEY (aluno_id) REFERENCES public.aluno(id);


--
-- Name: situacao_escolar situacao_escolar_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.situacao_escolar
    ADD CONSTRAINT situacao_escolar_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: tema_aula tema_aula_curso_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tema_aula
    ADD CONSTRAINT tema_aula_curso_id_fkey FOREIGN KEY (curso_id) REFERENCES public.curso(id);


--
-- Name: tema_aula tema_aula_turma_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tema_aula
    ADD CONSTRAINT tema_aula_turma_id_fkey FOREIGN KEY (turma_id) REFERENCES public.turma(id);


--
-- Name: tema_aula tema_aula_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tema_aula
    ADD CONSTRAINT tema_aula_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: transferencia transferencia_aluno_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transferencia
    ADD CONSTRAINT transferencia_aluno_id_fkey FOREIGN KEY (aluno_id) REFERENCES public.aluno(id);


--
-- Name: transferencia transferencia_turma_destino_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transferencia
    ADD CONSTRAINT transferencia_turma_destino_id_fkey FOREIGN KEY (turma_destino_id) REFERENCES public.turma(id);


--
-- Name: transferencia transferencia_turma_origem_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transferencia
    ADD CONSTRAINT transferencia_turma_origem_id_fkey FOREIGN KEY (turma_origem_id) REFERENCES public.turma(id);


--
-- Name: transferencia transferencia_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transferencia
    ADD CONSTRAINT transferencia_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: turma turma_curso_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.turma
    ADD CONSTRAINT turma_curso_id_fkey FOREIGN KEY (curso_id) REFERENCES public.curso(id);


--
-- Name: turma turma_periodo_letivo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.turma
    ADD CONSTRAINT turma_periodo_letivo_id_fkey FOREIGN KEY (periodo_letivo_id) REFERENCES public.periodo_letivo(id);


--
-- Name: turma turma_professor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.turma
    ADD CONSTRAINT turma_professor_id_fkey FOREIGN KEY (professor_id) REFERENCES public."user"(id);


--
-- Name: turma turma_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.turma
    ADD CONSTRAINT turma_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- Name: user user_unidade_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_unidade_id_fkey FOREIGN KEY (unidade_id) REFERENCES public.unidade(id);


--
-- PostgreSQL database dump complete
--

