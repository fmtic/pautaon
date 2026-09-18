"""
================================================================================
ALUNO_PERFIL.PY - Centraliza leitura/escrita dos dados de perfil do aluno
================================================================================

Criado na Onda 3B. Durante a transição entre JSONs legados e tabelas
estruturadas, este módulo é o ÚNICO lugar que decide se lê da tabela nova
ou do JSON antigo. Nenhum outro módulo (rotas, relatórios, templates)
deve acessar `aluno.*_json` diretamente — use `get_perfil_completo()`
ou as funções de leitura individuais.

CONVENÇÕES
----------
- Funções `upsert_*` criam ou atualizam o registro correspondente a partir
  do `request.form` (ou de um dict equivalente). NÃO commitam — quem chama
  é responsável pelo `db.session.commit()`.
- Funções `get_*` leem da tabela nova; se o registro ainda não existir,
  caem no JSON antigo (`aluno.*_json`). Isso é o fallback de transição.
- `s()` normaliza string: '' -> None. `i()` normaliza int. `b()` normaliza bool.

QUANDO REMOVER O FALLBACK
-------------------------
Quando a Onda 3C dropar os JSONs, remova o bloco `FALLBACK` de cada função
`get_*` e simplifique para ler direto da tabela nova.
================================================================================
"""

from typing import Any, Optional

from app.database import db
from app.models import (
    Aluno,
    EnderecoAluno,
    PerfilDiversidade,
    PerfilSocioeconomico,
    ResponsavelAluno,
)


# =============================================================================
# NORMALIZADORES
# =============================================================================

def s(value: Any) -> Optional[str]:
    """String limpa: '' -> None, strip em volta, tolerante a None."""
    if value is None:
        return None
    t = str(value).strip()
    return t if t else None


def i(value: Any) -> Optional[int]:
    """Int tolerante: '' -> None, valor inválido -> None."""
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def b(value: Any) -> bool:
    """Bool tolerante: aceita True/False, 'on', '1', 'true', 'sim'."""
    if isinstance(value, bool):
        return value
    if value is None or value == '':
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in ('1', 'true', 'on', 'sim', 'yes', 's')


def _campo(form, nome):
    """Extrai um campo do form, tolerando ausência e MultiDict."""
    try:
        return form.get(nome)
    except Exception:
        return None


# =============================================================================
# ESCRITA (upsert a partir do form)
# =============================================================================

def upsert_endereco(aluno: Aluno, form) -> Optional[EnderecoAluno]:
    """
    Cria ou atualiza o EnderecoAluno do aluno a partir do form.

    Campos lidos: cep, rua, numero, bairro, cidade, uf, zona,
    nao_possui_acesso_internet (checkbox invertido do form).
    """
    campos = {
        'cep': s(_campo(form, 'cep')),
        'rua': s(_campo(form, 'rua')),
        'numero': s(_campo(form, 'numero')),
        'bairro': s(_campo(form, 'bairro')),
        'cidade': s(_campo(form, 'cidade')),
        'uf': s(_campo(form, 'uf')),
        'zona': s(_campo(form, 'zona')) or 'Urbana',
        'possui_acesso_internet': not b(_campo(form, 'nao_possui_acesso_internet')),
    }

    # Se todos os campos relevantes estão vazios e internet é True (default),
    # não cria/atualiza.
    relevantes = [v for k, v in campos.items() if k != 'possui_acesso_internet']
    if not any(relevantes) and campos['possui_acesso_internet'] is True:
        return None

    end = aluno.endereco
    if end is None:
        end = EnderecoAluno(aluno=aluno, unidade_id=aluno.unidade_id)
        db.session.add(end)

    for k, v in campos.items():
        setattr(end, k, v)

    return end


def upsert_responsavel(aluno: Aluno, form) -> Optional[ResponsavelAluno]:
    """
    Cria ou atualiza o responsável principal do aluno a partir do form.

    Campos lidos: responsavel_tipo, responsavel_nome, responsavel_cpf,
    telefone_resp.
    """
    tipo = s(_campo(form, 'responsavel_tipo'))
    nome = s(_campo(form, 'responsavel_nome'))
    cpf = s(_campo(form, 'responsavel_cpf'))
    telefone = s(_campo(form, 'telefone_resp'))

    if not any([tipo, nome, cpf, telefone]):
        return None

    resp = None
    if aluno.responsaveis:
        resp = aluno.responsaveis[0]
    if resp is None:
        resp = ResponsavelAluno(aluno=aluno, unidade_id=aluno.unidade_id)
        db.session.add(resp)

    resp.tipo = tipo
    resp.nome = nome
    resp.cpf = cpf
    resp.telefone = telefone

    return resp


def upsert_perfil_socioeconomico(aluno: Aluno, form) -> Optional[PerfilSocioeconomico]:
    """
    Cria ou atualiza o PerfilSocioeconomico do aluno.

    Campos lidos: renda_familiar, residente_maior_renda, pessoas_residencia,
    ocupacao, beneficio_social_status, beneficio_social_nome, meio_transporte,
    vulnerabilidade_social.
    """
    campos = {
        'renda_familiar': s(_campo(form, 'renda_familiar')),
        'residente_maior_renda': s(_campo(form, 'residente_maior_renda')),
        'pessoas_residencia': i(_campo(form, 'pessoas_residencia')),
        'ocupacao': s(_campo(form, 'ocupacao')),
        'beneficio_social_status': s(_campo(form, 'beneficio_social_status')),
        'beneficio_social_nome': s(_campo(form, 'beneficio_social_nome')),
        'meio_transporte': s(_campo(form, 'meio_transporte')),
        'vulnerabilidade_social': b(_campo(form, 'vulnerabilidade_social')),
    }

    if not any(v not in (None, False) for v in campos.values()):
        return None

    perfil = aluno.perfil_socioeconomico
    if perfil is None:
        perfil = PerfilSocioeconomico(aluno=aluno, unidade_id=aluno.unidade_id)
        db.session.add(perfil)

    for k, v in campos.items():
        setattr(perfil, k, v)

    return perfil


def upsert_perfil_diversidade(aluno: Aluno, form) -> Optional[PerfilDiversidade]:
    """
    Cria ou atualiza o PerfilDiversidade do aluno.

    Campos lidos: genero, raca_cor, saude_laudo, saude_medicacao,
    saude_medicamento_nome, saude_observacoes, informacoes_para_professor,
    autorizacao_imagem.
    """
    campos = {
        'genero': s(_campo(form, 'genero')),
        'raca_cor': s(_campo(form, 'raca_cor')),
        'saude_laudo': b(_campo(form, 'saude_laudo')),
        'saude_medicacao': s(_campo(form, 'saude_medicacao')),
        'saude_medicamento_nome': s(_campo(form, 'saude_medicamento_nome')),
        'saude_observacoes': s(_campo(form, 'saude_observacoes')),
        'informacoes_para_professor': s(_campo(form, 'informacoes_para_professor')),
        'autorizacao_imagem': b(_campo(form, 'autorizacao_imagem')),
    }

    if not any(v not in (None, False) for v in campos.values()):
        return None

    perfil = aluno.perfil_diversidade
    if perfil is None:
        perfil = PerfilDiversidade(aluno=aluno, unidade_id=aluno.unidade_id)
        db.session.add(perfil)

    for k, v in campos.items():
        setattr(perfil, k, v)

    return perfil


# =============================================================================
# LEITURA (com fallback para JSON antigo)
# =============================================================================

def get_endereco(aluno: Aluno) -> dict:
    """Retorna endereço do aluno, preferindo tabela nova; cai no JSON se vazio."""
    e = aluno.endereco
    if e is not None:
        return {
            'cep': e.cep or '',
            'rua': e.rua or '',
            'numero': e.numero or '',
            'bairro': e.bairro or '',
            'cidade': e.cidade or '',
            'uf': e.uf or '',
            'zona': e.zona or 'Urbana',
            'possui_acesso_internet': e.possui_acesso_internet,
        }
    # FALLBACK (Onda 3B)
    return aluno.identificacao_json.get('endereco', {}) or {}


def get_responsavel_principal(aluno: Aluno) -> dict:
    """Retorna o primeiro responsável do aluno, com fallback para o JSON."""
    if aluno.responsaveis:
        r = aluno.responsaveis[0]
        return {
            'tipo': r.tipo or '',
            'nome': r.nome or '',
            'cpf': r.cpf or '',
            'telefone': r.telefone or '',
        }
    # FALLBACK (Onda 3B)
    ident = aluno.identificacao_json
    return {
        'tipo': ident.get('responsavel_tipo', '') or '',
        'nome': ident.get('responsavel_nome', '') or '',
        'cpf': ident.get('responsavel_cpf', '') or '',
        'telefone': ident.get('telefone_resp', '') or '',
    }


def get_perfil_socioeconomico(aluno: Aluno) -> dict:
    """Retorna o perfil socioeconômico, com fallback para o JSON."""
    p = aluno.perfil_socioeconomico
    if p is not None:
        return {
            'renda_familiar': p.renda_familiar or '',
            'residente_maior_renda': p.residente_maior_renda or '',
            'pessoas_residencia': p.pessoas_residencia,
            'ocupacao': p.ocupacao or '',
            'beneficio_social_status': p.beneficio_social_status or '',
            'beneficio_social_nome': p.beneficio_social_nome or '',
            'meio_transporte': p.meio_transporte or '',
            'vulnerabilidade_social': p.vulnerabilidade_social,
        }
    # FALLBACK (Onda 3B)
    return aluno.socioeconomico_json or {}


def get_perfil_diversidade(aluno: Aluno) -> dict:
    """Retorna o perfil de diversidade, com fallback para o JSON."""
    p = aluno.perfil_diversidade
    if p is not None:
        return {
            'genero': p.genero or '',
            'raca_cor': p.raca_cor or '',
            'saude_laudo': p.saude_laudo,
            'saude_medicacao': p.saude_medicacao or '',
            'saude_medicamento_nome': p.saude_medicamento_nome or '',
            'saude_observacoes': p.saude_observacoes or '',
            'informacoes_para_professor': p.informacoes_para_professor or '',
            'autorizacao_imagem': p.autorizacao_imagem,
        }
    # FALLBACK (Onda 3B)
    return aluno.diversidade_json or {}


def get_identificacao(aluno: Aluno) -> dict:
    """
    Retorna dados civis do aluno (colunas novas + fallback no JSON por campo).
    """
    ident = aluno.identificacao_json or {}

    def _prefere_coluna(coluna_valor, chave_json):
        v = coluna_valor
        if v is None or (isinstance(v, str) and not v.strip()):
            return ident.get(chave_json, '') or ''
        return v

    return {
        'orgao_rg': _prefere_coluna(aluno.orgao_rg, 'orgao_rg'),
        'nacionalidade': _prefere_coluna(aluno.nacionalidade, 'nacionalidade'),
        'natural_uf': _prefere_coluna(aluno.natural_uf, 'natural_uf'),
        'natural_cidade': _prefere_coluna(aluno.natural_cidade, 'natural_cidade'),
        'nome_mae': _prefere_coluna(aluno.nome_mae, 'nome_mae'),
        'cpf_mae': _prefere_coluna(aluno.cpf_mae, 'cpf_mae'),
        'nome_pai': _prefere_coluna(aluno.nome_pai, 'nome_pai'),
        'cpf_pai': _prefere_coluna(aluno.cpf_pai, 'cpf_pai'),
        'vai_acompanhado_aulas': (
            aluno.vai_acompanhado_aulas or bool(ident.get('vai_acompanhado_aulas'))
        ),
        'acompanhante_aulas': _prefere_coluna(
            aluno.acompanhante_aulas, 'acompanhante_aulas'
        ),
    }


def get_perfil_completo(aluno: Aluno) -> dict:
    """
    Retorna um dicionário com TODOS os dados de perfil do aluno já resolvidos
    (tabela nova ou fallback JSON). Ideal para passar ao template de uma vez.

    Uso:
        perfil = get_perfil_completo(aluno)
        render_template('alunos/editar.html', aluno=aluno, perfil=perfil)
    """
    return {
        'identificacao': get_identificacao(aluno),
        'endereco': get_endereco(aluno),
        'responsavel': get_responsavel_principal(aluno),
        'socioeconomico': get_perfil_socioeconomico(aluno),
        'diversidade': get_perfil_diversidade(aluno),
    }


__all__ = [
    # normalizadores
    's', 'i', 'b',
    # escritas
    'upsert_endereco',
    'upsert_responsavel',
    'upsert_perfil_socioeconomico',
    'upsert_perfil_diversidade',
    # leituras
    'get_endereco',
    'get_responsavel_principal',
    'get_perfil_socioeconomico',
    'get_perfil_diversidade',
    'get_identificacao',
    'get_perfil_completo',
]