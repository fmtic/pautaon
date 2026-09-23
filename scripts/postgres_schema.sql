-- SQL de criação de schema para PostgreSQL gerado a partir dos modelos do app
-- Execute no psql ou no cliente SQL do seu servidor PostgreSQL.


CREATE TABLE conselho_pergunta (
	id SERIAL NOT NULL, 
	etapa etapa_conselho_enum, 
	tipo tipo_pergunta_enum, 
	texto TEXT NOT NULL, 
	opcoes TEXT, 
	ativo BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);


CREATE TABLE opcao_proxima_turma (
	id SERIAL NOT NULL, 
	nome VARCHAR(100) NOT NULL, 
	ativo BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);


CREATE TABLE unidade (
	id SERIAL NOT NULL, 
	nome VARCHAR(100) NOT NULL, 
	ativo BOOLEAN NOT NULL, 
	PRIMARY KEY (id)
);


CREATE TABLE configuracao_sistema (
	id SERIAL NOT NULL, 
	chave VARCHAR(50) NOT NULL, 
	valor VARCHAR(100), 
	descricao VARCHAR(255), 
	unidade_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE curso (
	id SERIAL NOT NULL, 
	nome VARCHAR(150) NOT NULL, 
	descricao VARCHAR(300), 
	carga_horaria INTEGER, 
	ativo BOOLEAN NOT NULL, 
	unidade_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE nivel (
	id SERIAL NOT NULL, 
	nome VARCHAR(100) NOT NULL, 
	ativo BOOLEAN NOT NULL, 
	unidade_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (nome), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE periodo_letivo (
	id SERIAL NOT NULL, 
	nome VARCHAR(150) NOT NULL, 
	data_inicio DATE NOT NULL, 
	data_fim DATE NOT NULL, 
	centro_custo VARCHAR(150), 
	estimativa_alunos INTEGER NOT NULL, 
	ativo BOOLEAN NOT NULL, 
	unidade_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE "user" (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	password VARCHAR(200), 
	role VARCHAR(20) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	is_ad_user BOOLEAN NOT NULL, 
	unidade_id INTEGER, 
	first_login BOOLEAN, 
	google_id VARCHAR(100), 
	google_email VARCHAR(120), 
	PRIMARY KEY (id), 
	CONSTRAINT ck_user_role CHECK (role IN ('admin', 'pedagogico', 'professor', 'secretaria', 'servico_social', 'gerencia', 'pendente')), 
	UNIQUE (email), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE agenda_servico_social (
	id SERIAL NOT NULL, 
	titulo VARCHAR(200) NOT NULL, 
	categoria VARCHAR(100) NOT NULL, 
	data DATE NOT NULL, 
	hora VARCHAR(5) NOT NULL, 
	localizacao VARCHAR(255), 
	descricao TEXT, 
	google_event_id VARCHAR(255), 
	participantes_emails TEXT, 
	user_id INTEGER NOT NULL, 
	data_criacao TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES "user" (id)
);


CREATE TABLE aluno (
	id SERIAL NOT NULL, 
	nome VARCHAR(100) NOT NULL, 
	nome_social VARCHAR(100), 
	ativo BOOLEAN NOT NULL, 
	data_nascimento DATE, 
	foto_path VARCHAR(255), 
	documentos_entregues JSONB, 
	escolaridade_json TEXT, 
	identificacao_json TEXT, 
	socioeconomico_json TEXT, 
	diversidade_json TEXT, 
	cpf VARCHAR(20), 
	rg VARCHAR(50), 
	whatsapp VARCHAR(30), 
	email VARCHAR(120), 
	nivel VARCHAR(20), 
	orgao_rg VARCHAR(20), 
	nacionalidade VARCHAR(50), 
	natural_uf VARCHAR(2), 
	natural_cidade VARCHAR(100), 
	nome_mae VARCHAR(150), 
	cpf_mae VARCHAR(20), 
	nome_pai VARCHAR(150), 
	cpf_pai VARCHAR(20), 
	vai_acompanhado_aulas BOOLEAN NOT NULL, 
	acompanhante_aulas VARCHAR(150), 
	created_by_id INTEGER, 
	created_by_name VARCHAR(100), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	unidade_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_id) REFERENCES "user" (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE dia_bloqueado (
	id SERIAL NOT NULL, 
	data DATE NOT NULL, 
	tipo tipo_dia_bloqueado_enum NOT NULL, 
	descricao VARCHAR(200), 
	periodo_letivo_id INTEGER NOT NULL, 
	unidade_id INTEGER NOT NULL, 
	criado_por_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(periodo_letivo_id) REFERENCES periodo_letivo (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id), 
	FOREIGN KEY(criado_por_id) REFERENCES "user" (id)
);


CREATE TABLE log_acao (
	id SERIAL NOT NULL, 
	data_hora TIMESTAMP WITHOUT TIME ZONE, 
	usuario_id INTEGER, 
	usuario_nome VARCHAR(100), 
	acao VARCHAR(255), 
	detalhes TEXT, 
	ip VARCHAR(50), 
	unidade_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(usuario_id) REFERENCES "user" (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE periodo_conselho (
	id SERIAL NOT NULL, 
	nome VARCHAR(100) NOT NULL, 
	data_inicio DATE NOT NULL, 
	data_fim DATE NOT NULL, 
	conselho_final BOOLEAN NOT NULL, 
	periodo_letivo_id INTEGER NOT NULL, 
	unidade_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(periodo_letivo_id) REFERENCES periodo_letivo (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE registro (
	id SERIAL NOT NULL, 
	educador_id INTEGER NOT NULL, 
	turma VARCHAR(100), 
	mes VARCHAR(20), 
	turno VARCHAR(20), 
	dados_json TEXT, 
	criado_em TIMESTAMP WITHOUT TIME ZONE, 
	unidade_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(educador_id) REFERENCES "user" (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE turma (
	id SERIAL NOT NULL, 
	nome VARCHAR(100) NOT NULL, 
	ativo BOOLEAN NOT NULL, 
	data_inicio DATE, 
	data_fim DATE, 
	hora_inicio TIME WITHOUT TIME ZONE, 
	hora_fim TIME WITHOUT TIME ZONE, 
	dias_semana VARCHAR(20), 
	programa VARCHAR(50), 
	turno VARCHAR(20), 
	centro_custo VARCHAR(150), 
	ordenacao INTEGER, 
	unidade_id INTEGER, 
	periodo_letivo_id INTEGER, 
	curso_id INTEGER, 
	professor_id INTEGER, 
	avaliacao_inicial TEXT, 
	avaliacao_percurso TEXT, 
	avaliacao_final TEXT, 
	conselho_concluido BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id), 
	FOREIGN KEY(periodo_letivo_id) REFERENCES periodo_letivo (id), 
	FOREIGN KEY(curso_id) REFERENCES curso (id), 
	FOREIGN KEY(professor_id) REFERENCES "user" (id)
);


CREATE TABLE atendimento (
	id SERIAL NOT NULL, 
	aluno_id INTEGER NOT NULL, 
	setor VARCHAR(50) NOT NULL, 
	data_atendimento DATE NOT NULL, 
	resumo VARCHAR(255), 
	dados JSONB NOT NULL, 
	atendido_por_id INTEGER, 
	atendido_por_nome VARCHAR(150), 
	unidade_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(aluno_id) REFERENCES aluno (id), 
	FOREIGN KEY(atendido_por_id) REFERENCES "user" (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE conselho_classe (
	id SERIAL NOT NULL, 
	turma_id INTEGER NOT NULL, 
	aluno_id INTEGER NOT NULL, 
	etapa etapa_conselho_enum NOT NULL, 
	data_inicio DATE, 
	data_fim DATE, 
	concluido BOOLEAN NOT NULL, 
	instrutor_id INTEGER, 
	observacao TEXT, 
	situacao_final VARCHAR(30), 
	proxima_turma_id INTEGER, 
	unidade_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT uix_conselho_turma_aluno_etapa UNIQUE (turma_id, aluno_id, etapa), 
	CONSTRAINT ck_conselho_situacao_final CHECK (situacao_final IS NULL OR situacao_final IN ('Aprovado', 'Reprovado por Falta', 'Desistente', 'Evadido', 'Participação', 'Concluído')), 
	FOREIGN KEY(turma_id) REFERENCES turma (id), 
	FOREIGN KEY(aluno_id) REFERENCES aluno (id), 
	FOREIGN KEY(instrutor_id) REFERENCES "user" (id), 
	FOREIGN KEY(proxima_turma_id) REFERENCES opcao_proxima_turma (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE dia_bloqueado_turma (
	id SERIAL NOT NULL, 
	turma_id INTEGER NOT NULL, 
	data DATE NOT NULL, 
	unidade_id INTEGER, 
	criado_por_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uix_dia_bloqueado_turma UNIQUE (turma_id, data), 
	FOREIGN KEY(turma_id) REFERENCES turma (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id), 
	FOREIGN KEY(criado_por_id) REFERENCES "user" (id)
);


CREATE TABLE endereco_aluno (
	id SERIAL NOT NULL, 
	aluno_id INTEGER NOT NULL, 
	unidade_id INTEGER, 
	cep VARCHAR(10), 
	rua VARCHAR(200), 
	numero VARCHAR(20), 
	bairro VARCHAR(100), 
	cidade VARCHAR(100), 
	uf VARCHAR(2), 
	zona VARCHAR(20), 
	possui_acesso_internet BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (aluno_id), 
	FOREIGN KEY(aluno_id) REFERENCES aluno (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE frequencia (
	id SERIAL NOT NULL, 
	aluno_id INTEGER NOT NULL, 
	turma_id INTEGER NOT NULL, 
	data DATE NOT NULL, 
	conceito conceito_frequencia_enum, 
	unidade_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT uix_frequencia_aluno_turma_data UNIQUE (aluno_id, turma_id, data), 
	FOREIGN KEY(aluno_id) REFERENCES aluno (id), 
	FOREIGN KEY(turma_id) REFERENCES turma (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE inscricoes (
	id SERIAL NOT NULL, 
	aluno_id INTEGER NOT NULL, 
	turma_id INTEGER NOT NULL, 
	nivel VARCHAR(30), 
	ativo BOOLEAN NOT NULL, 
	data_inicio DATE NOT NULL, 
	data_desativacao TIMESTAMP WITHOUT TIME ZONE, 
	motivo_desativacao VARCHAR(50), 
	PRIMARY KEY (id), 
	FOREIGN KEY(aluno_id) REFERENCES aluno (id), 
	FOREIGN KEY(turma_id) REFERENCES turma (id)
);


CREATE TABLE perfil_diversidade (
	id SERIAL NOT NULL, 
	aluno_id INTEGER NOT NULL, 
	unidade_id INTEGER, 
	genero VARCHAR(30), 
	raca_cor VARCHAR(30), 
	saude_laudo BOOLEAN NOT NULL, 
	tipo_deficiencia VARCHAR(30), 
	saude_medicacao VARCHAR(5), 
	saude_medicamento_nome VARCHAR(150), 
	saude_observacoes TEXT, 
	informacoes_para_professor TEXT, 
	autorizacao_imagem BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (aluno_id), 
	FOREIGN KEY(aluno_id) REFERENCES aluno (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE perfil_socioeconomico (
	id SERIAL NOT NULL, 
	aluno_id INTEGER NOT NULL, 
	unidade_id INTEGER, 
	renda_familiar NUMERIC(12, 2), 
	residente_maior_renda VARCHAR(50), 
	pessoas_residencia INTEGER, 
	ocupacao VARCHAR(50), 
	beneficio_social_status VARCHAR(20), 
	beneficio_social_nome VARCHAR(100), 
	meio_transporte VARCHAR(30), 
	vulnerabilidade_social BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (aluno_id), 
	FOREIGN KEY(aluno_id) REFERENCES aluno (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE responsavel_aluno (
	id SERIAL NOT NULL, 
	aluno_id INTEGER NOT NULL, 
	unidade_id INTEGER, 
	tipo VARCHAR(30), 
	nome VARCHAR(150), 
	cpf VARCHAR(20), 
	telefone VARCHAR(30), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(aluno_id) REFERENCES aluno (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE respostas_formulario (
	id SERIAL NOT NULL, 
	tipo_formulario VARCHAR(50) NOT NULL, 
	aluno_id INTEGER, 
	usuario_id INTEGER NOT NULL, 
	dados JSONB NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(aluno_id) REFERENCES aluno (id), 
	FOREIGN KEY(usuario_id) REFERENCES "user" (id)
);


CREATE TABLE situacao_escolar (
	id SERIAL NOT NULL, 
	aluno_id INTEGER NOT NULL, 
	unidade_id INTEGER, 
	escolaridade VARCHAR(40), 
	ensino_superior_periodo INTEGER, 
	escolaridade_outro VARCHAR(150), 
	status VARCHAR(20), 
	status_outro VARCHAR(150), 
	nome_instituicao VARCHAR(200), 
	tipo_instituicao VARCHAR(20), 
	bolsista BOOLEAN NOT NULL, 
	tipo_instituicao_outro VARCHAR(150), 
	turno VARCHAR(20), 
	turno_outro VARCHAR(100), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (aluno_id), 
	FOREIGN KEY(aluno_id) REFERENCES aluno (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE tema_aula (
	id SERIAL NOT NULL, 
	curso_id INTEGER, 
	turma_id INTEGER, 
	unidade_id INTEGER, 
	titulo VARCHAR(200), 
	programa VARCHAR(50), 
	ativo BOOLEAN NOT NULL, 
	data DATE, 
	ordem INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(curso_id) REFERENCES curso (id), 
	FOREIGN KEY(turma_id) REFERENCES turma (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE transferencia (
	id SERIAL NOT NULL, 
	aluno_id INTEGER NOT NULL, 
	turma_origem_id INTEGER NOT NULL, 
	turma_destino_id INTEGER NOT NULL, 
	data_transferencia TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	observacoes TEXT, 
	unidade_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(aluno_id) REFERENCES aluno (id), 
	FOREIGN KEY(turma_origem_id) REFERENCES turma (id), 
	FOREIGN KEY(turma_destino_id) REFERENCES turma (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE conselho_resposta (
	id SERIAL NOT NULL, 
	conselho_id INTEGER NOT NULL, 
	aluno_id INTEGER NOT NULL, 
	pergunta_id INTEGER NOT NULL, 
	resposta TEXT, 
	observacao TEXT, 
	unidade_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(conselho_id) REFERENCES conselho_classe (id), 
	FOREIGN KEY(aluno_id) REFERENCES aluno (id), 
	FOREIGN KEY(pergunta_id) REFERENCES conselho_pergunta (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);


CREATE TABLE registro_aula (
	id SERIAL NOT NULL, 
	turma_id INTEGER NOT NULL, 
	data DATE NOT NULL, 
	tema_id INTEGER, 
	observacoes TEXT, 
	instrutor_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	unidade_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(turma_id) REFERENCES turma (id), 
	FOREIGN KEY(tema_id) REFERENCES tema_aula (id), 
	FOREIGN KEY(instrutor_id) REFERENCES "user" (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidade (id)
);

