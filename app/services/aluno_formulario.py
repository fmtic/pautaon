"""AJ5-C — Contrato único de valores e catálogos do formulário de aluno.

`valores_form_aluno()` devolve UM dicionário com um valor por nome de campo,
na ordem de precedência `form` (dados digitados, no re-render de falha) >
banco (editar) > padrões do cadastro novo. O parcial `alunos/_form_aluno.html`
só lê `v` — nada de `ident.get(...)`/`aluno.x` espalhado pelo template.

Os catálogos de opções (tuples abaixo) são a fonte única dos `<select>`:
os templates renderizam com `{% for %}` e não com `<option>` digitado à mão.
É a correção da causa raiz dos bugs de valores divergentes do AJ5-A.

Campos que só o modo editar conhece (estado de documentos, foto atual,
matrícula, escopo de quem pode ver/excluir) também saem daqui, para o
template não consultar o banco nem `current_user` para decidir valor.
"""

import re

from app.services.aluno_perfil import TIPOS_DEFICIENCIA  # catálogo canônico

# =============================================================================
# CATÁLOGOS DE OPÇÕES (fonte única dos selects do formulário)
# =============================================================================

GENERO_OPCOES = ('Masculino', 'Feminino', 'Outro')

RACA_COR_OPCOES = ('Branca', 'Preta', 'Parda', 'Amarela', 'Indígena', 'Não declarada')

RESPONSAVEL_TIPO_OPCOES = ('Mãe', 'Pai', 'Avô/Avó', 'Irmão/Tio', 'Outro')

# O "Outro" do acompanhante salva texto livre (ver `_aplicar_campos_civis`);
# valor fora desta lista volta como Outro selecionado + campo pré-preenchido.
ACOMPANHANTE_OPCOES = ('Mãe', 'Pai', 'Avô/Avó', 'Irmão/Tio', 'Outro', 'Vai sozinho')

ZONA_OPCOES = ('Urbana', 'Rural')

ESCOLARIDADE_OPCOES = (
    'Ensino fundamental', 'Ensino médio', 'Ensino médio técnico',
    'Ensino superior', 'EJA', 'Outros',
)

STATUS_ESCOLAR_OPCOES = ('Cursando', 'Concluinte', 'Trancado', 'Outros')

TIPO_INSTITUICAO_OPCOES = ('Pública', 'Privada', 'Outro')

TURNO_ESCOLAR_OPCOES = ('Manhã', 'Tarde', 'Noite', 'EAD', 'Outros')

RESIDENTE_RENDA_OPCOES = ('Aluno', 'Pai', 'Mãe', 'Irmão(ã)', 'Avô/Avó', 'Outro')

OCUPACAO_OPCOES = (
    'Estudante', 'Desempregado', 'Autônomo', 'CLT', 'Jovem Aprendiz', 'Estagiário',
)

BENEFICIO_STATUS_OPCOES = ('Não', 'Sim')

MEIO_TRANSPORTE_OPCOES = ('Ônibus', 'Carro/Moto', 'Bicicleta', 'A pé', 'Outro')

SAUDE_MEDICACAO_OPCOES = ('Não', 'Sim')

#: Sugestões do datalist de programas sociais (o campo aceita texto livre).
PROGRAMAS_SOCIAIS_OPCOES = (
    'Bolsa Família', 'Cadastro Único', 'Auxílio Gás',
    'BPC (Benefício de Prestação Continuada)', 'Minha Casa Minha Vida', 'Outros',
)

#: Períodos do ensino superior (1 a 10), como no `range(1, 11)` do template.
PERIODOS_SUPERIOR = tuple(range(1, 11))

#: Documentos com box de upload no passo V (ordem de exibição) + laudo do VI.
DOC_IDS_FORM = (
    'doc_aluno', 'doc_residencia', 'doc_declaracao',
    'doc_atestado', 'doc_termo', 'doc_responsavel',
)
DOC_LAUDO_ID = 'doc_laudo'

DOC_LABELS_FORM = {
    'doc_aluno': 'RG/CPF Aluno',
    'doc_residencia': 'Comprovante Residência',
    'doc_declaracao': 'Declaração Escolar',
    'doc_atestado': 'Atestado Médico',
    'doc_termo': 'Termo Imagem/Som',
    'doc_responsavel': 'RG/CPF Responsável',
    'doc_laudo': 'Laudo Médico',
}

#: Campos de texto/select que v expõe, um por name= do formulário.
_TEXTO_CAMPOS = (
    'nome', 'nome_social', 'data_nascimento', 'cpf', 'rg', 'orgao_rg',
    'nacionalidade', 'natural_uf', 'natural_cidade',
    'genero', 'raca_cor',
    'nome_mae', 'cpf_mae', 'nome_pai', 'cpf_pai',
    'responsavel_tipo', 'responsavel_nome', 'responsavel_cpf',
    'acompanhante_aulas', 'acompanhante_aulas_outro',
    'cep', 'rua', 'numero', 'bairro', 'cidade', 'uf', 'zona',
    'whatsapp', 'telefone_resp', 'email',
    'escolaridade', 'status_escolar', 'status_escolar_outro',
    'ensino_superior_periodo', 'escolaridade_outro', 'nome_instituicao',
    'tipo_instituicao', 'tipo_instituicao_outro',
    'turno_escolar', 'turno_escolar_outro',
    'renda_familiar', 'pessoas_residencia', 'residente_maior_renda',
    'ocupacao', 'beneficio_social_status', 'meio_transporte',
    'tipo_deficiencia', 'saude_medicacao', 'saude_medicamento_nome',
    'saude_observacoes', 'informacoes_para_professor',
    'unidade_id',
)

#: Checkboxes (presença no form == marcado).
_CHECK_CAMPOS = (
    'vai_acompanhado_aulas', 'nao_possui_acesso_internet', 'bolsista',
    'vulnerabilidade_social', 'saude_laudo', 'autorizacao_imagem',
)

#: Padrões do cadastro novo (documentados no MER): nacionalidade Brasileira,
#: UF SP, zona Urbana, 1 pessoa na residência; nos selects sem placeholder o
#: padrão é a primeira opção — hoje o navegador já pré-seleciona essa, o
#: contrato apenas a torna explícita (atributo `selected`).
_PADROES = {
    'nacionalidade': 'Brasileira',
    'uf': 'SP',
    'zona': 'Urbana',
    'pessoas_residencia': '1',
    'residente_maior_renda': 'Aluno',
    'ocupacao': 'Estudante',
    'beneficio_social_status': 'Não',
    'meio_transporte': 'Ônibus',
    'saude_medicacao': 'Não',
}


#: Ordem de EXIBIÇÃO do select de deficiência (validação continua sendo
#: `TIPOS_DEFICIENCIA`, em `aluno_perfil.py`). O teste de paridade abaixo
#: garante que ninguém amplia um catálogo sem ampliar o outro.
TIPOS_DEFICIENCIA_EXIBICAO = (
    'Não se aplica', 'Motora/Física', 'Auditiva', 'Psicossocial',
    'Intelectual/Mental', 'Visual', 'TEA', 'Outro',
)
assert set(TIPOS_DEFICIENCIA_EXIBICAO) == set(TIPOS_DEFICIENCIA), (
    'catálogo de exibição divergiu do catálogo de validação'
)


def _cpf_formatado(cpf) -> str:
    """Mesma regra do filtro `format_cpf` (app/__init__.py), reutilizada no
    contrato para o template não precisar escolher quem formata."""
    digitos = re.sub(r"\D", "", cpf or "")
    if not digitos:
        return ""
    if len(digitos) == 11:
        return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
    return digitos


def _texto(valor) -> str:
    if valor is None:
        return ""
    return str(valor)


def _banco_de(aluno, perfil) -> dict:
    """Achata banco + perfil num dict `{name: valor_cru}`, na mesma ordem de
    leitura que os templates old (`ident.get`, `end.get`, `sit.*`, ...)."""
    if aluno is None:
        return {}
    ident = (perfil or {}).get('identificacao', {})
    end = (perfil or {}).get('endereco', {})
    resp = (perfil or {}).get('responsavel', {})
    socio = (perfil or {}).get('socioeconomico', {})
    div = (perfil or {}).get('diversidade', {})
    sit = aluno.situacao_escolar

    banco = {
        'nome': aluno.nome or '',
        'nome_social': aluno.nome_social or ident.get('nome_social', ''),
        'data_nascimento': (
            aluno.data_nascimento.strftime('%Y-%m-%d') if aluno.data_nascimento else ''
        ),
        'cpf': _cpf_formatado(aluno.cpf),
        'rg': aluno.rg or '',
        'orgao_rg': ident.get('orgao_rg', ''),
        'nacionalidade': ident.get('nacionalidade', ''),
        'natural_uf': ident.get('natural_uf', ''),
        'natural_cidade': ident.get('natural_cidade', ''),
        'nome_mae': ident.get('nome_mae', ''),
        'cpf_mae': ident.get('cpf_mae', ''),
        'nome_pai': ident.get('nome_pai', ''),
        'cpf_pai': ident.get('cpf_pai', ''),
        'responsavel_tipo': resp.get('tipo', ''),
        'responsavel_nome': resp.get('nome', ''),
        'responsavel_cpf': resp.get('cpf', ''),
        'vai_acompanhado_aulas': bool(ident.get('vai_acompanhado_aulas')),
        'acompanhante_aulas': ident.get('acompanhante_aulas', ''),
        'cep': end.get('cep', ''),
        'rua': end.get('rua', ''),
        'numero': end.get('numero', ''),
        'bairro': end.get('bairro', ''),
        'cidade': end.get('cidade', ''),
        'uf': end.get('uf', 'SP'),
        'zona': end.get('zona', 'Urbana'),
        # O checkbox lê do endereço (o old editar lia um `ident` que nunca
        # teve a chave — diferença listada no relatório AJ5-C).
        'nao_possui_acesso_internet': not end.get('possui_acesso_internet', True),
        'whatsapp': aluno.whatsapp or '',
        'telefone_resp': resp.get('telefone', ''),
        'email': aluno.email or '',
        'escolaridade': (sit.escolaridade if sit else '') or '',
        'status_escolar': (sit.status if sit else '') or '',
        'status_escolar_outro': (sit.status_outro if sit else '') or '',
        'ensino_superior_periodo': (
            str(sit.ensino_superior_periodo)
            if sit and sit.ensino_superior_periodo else ''
        ),
        'escolaridade_outro': (sit.escolaridade_outro if sit else '') or '',
        'nome_instituicao': (sit.nome_instituicao if sit else '') or '',
        'tipo_instituicao': (sit.tipo_instituicao if sit else '') or '',
        'tipo_instituicao_outro': (sit.tipo_instituicao_outro if sit else '') or '',
        'turno_escolar': (sit.turno if sit else '') or '',
        'turno_escolar_outro': (sit.turno_outro if sit else '') or '',
        'bolsista': bool(sit and sit.bolsista),
        'renda_familiar': _texto(socio.get('renda_familiar', '') or ''),
        'pessoas_residencia': _texto(socio.get('pessoas_residencia', 1) or 1),
        'residente_maior_renda': socio.get('residente_maior_renda', '') or 'Aluno',
        'ocupacao': socio.get('ocupacao', '') or 'Estudante',
        'beneficio_social_status': socio.get('beneficio_social_status', '') or 'Não',
        'meio_transporte': socio.get('meio_transporte', '') or 'Ônibus',
        'vulnerabilidade_social': bool(socio.get('vulnerabilidade_social')),
        'genero': div.get('genero', ''),
        'raca_cor': div.get('raca_cor', ''),
        'saude_laudo': bool(div.get('saude_laudo')),
        'tipo_deficiencia': div.get('tipo_deficiencia', '') or '',
        'saude_medicacao': div.get('saude_medicacao', '') or 'Não',
        'saude_medicamento_nome': div.get('saude_medicamento_nome', ''),
        'saude_observacoes': div.get('saude_observacoes', ''),
        'informacoes_para_professor': div.get('informacoes_para_professor', ''),
        'autorizacao_imagem': bool(div.get('autorizacao_imagem')),
    }
    return banco


def valores_form_aluno(aluno=None, perfil=None, form=None, foto_url=None):
    """Contrato único do formulário de aluno.

    Args:
        aluno:  instância em edição (None no cadastro novo)
        perfil: resultado de `get_perfil_completo(aluno)` (edição)
        form:   MultiDict digitado (re-render na falha); tem precedência
        foto_url: URL da foto atual (a rota calcula com `url_for`)

    Returns:
        dict `v` com um valor por `name=` do formulário + chaves derivadas
        de exibição (`beneficios`, `doc_estado`, `matricula_badge`, ...).
    """
    banco = _banco_de(aluno, perfil)
    v = {}

    def _origem(chave):
        """form > banco > padrão — um ponto único de precedência."""
        if form is not None:
            return form.get(chave, '')
        if chave in banco:
            return banco[chave]
        return _PADROES.get(chave, '')

    for chave in _TEXTO_CAMPOS:
        v[chave] = _texto(_origem(chave))
    for chave in _CHECK_CAMPOS:
        if form is not None:
            v[chave] = bool(form.get(chave))
        else:
            v[chave] = bool(_origem(chave))

    # -- acompanhante: "Outro" com texto livre (mesma regra do AJ5-A) ---------
    if form is not None:
        sel = _texto(form.get('acompanhante_aulas', ''))
        livre = _texto(form.get('acompanhante_aulas_outro', ''))
        v['acompanhante_aulas'] = sel
        v['acompanhante_outro_texto'] = livre if sel == 'Outro' else ''
    else:
        salva = _texto(banco.get('acompanhante_aulas', ''))
        livre = bool(salva) and salva not in ACOMPANHANTE_OPCOES
        v['acompanhante_aulas'] = 'Outro' if livre else salva
        v['acompanhante_outro_texto'] = salva if livre else ''
    v['acompanhante_mostra_outro'] = v['acompanhante_aulas'] == 'Outro'

    # -- benefícios sociais (tags reidratadas) --------------------------------
    if form is not None:
        try:
            brutos = form.getlist('beneficio_social_nome')
        except AttributeError:
            brutos = [form.get('beneficio_social_nome', '')]
        v['beneficios'] = [b.strip() for b in map(_texto, brutos) if b.strip()]
    else:
        salvos = (perfil or {}).get('socioeconomico', {}).get('beneficio_social_nome', '')
        v['beneficios'] = [b.strip() for b in _texto(salvos).split('|') if b.strip()]

    # -- renda per capita (exibição; o JS recalcula ao digitar) ---------------
    v['renda_per_capita'] = ''
    if form is None and aluno is not None:
        from app.services.aluno_perfil import renda_per_capita
        per_capita = renda_per_capita(
            (perfil or {}).get('socioeconomico', {}).get('renda_familiar'),
            (perfil or {}).get('socioeconomico', {}).get('pessoas_residencia'),
        )
        v['renda_per_capita'] = _texto(per_capita or '')

    # -- estado por documento (só edição tem flags; novo = tudo não enviado) --
    estado = {}
    if aluno is not None:
        entregue = (aluno.documentos_dict() or {}).get('doc_entregue', {})
        for doc_id in DOC_IDS_FORM + (DOC_LAUDO_ID,):
            estado[doc_id] = bool(entregue.get(doc_id))
    v['doc_estado'] = estado
    v['uploads'] = [(doc_id, DOC_LABELS_FORM[doc_id]) for doc_id in DOC_IDS_FORM]
    v['upload_laudo'] = (DOC_LAUDO_ID, DOC_LABELS_FORM[DOC_LAUDO_ID])

    # -- coisas do modo que o template não decide sozinho ---------------------
    v['aluno_id'] = aluno.id if aluno is not None else None
    v['matricula_badge'] = (aluno.matricula if aluno is not None else '00000.2026') or ''
    v['foto_url'] = foto_url or ''

    return v


def catalogos_formulario() -> dict:
    """Todos os catálogos de opções num dict único, para o parcial ler via `cat`."""
    return {
        'genero': GENERO_OPCOES,
        'raca_cor': RACA_COR_OPCOES,
        'responsavel_tipo': RESPONSAVEL_TIPO_OPCOES,
        'acompanhante_aulas': ACOMPANHANTE_OPCOES,
        'zona': ZONA_OPCOES,
        'escolaridade': ESCOLARIDADE_OPCOES,
        'status_escolar': STATUS_ESCOLAR_OPCOES,
        'tipo_instituicao': TIPO_INSTITUICAO_OPCOES,
        'turno_escolar': TURNO_ESCOLAR_OPCOES,
        'residente_maior_renda': RESIDENTE_RENDA_OPCOES,
        'ocupacao': OCUPACAO_OPCOES,
        'beneficio_social_status': BENEFICIO_STATUS_OPCOES,
        'meio_transporte': MEIO_TRANSPORTE_OPCOES,
        'saude_medicacao': SAUDE_MEDICACAO_OPCOES,
        'tipo_deficiencia': TIPOS_DEFICIENCIA_EXIBICAO,
        'programas_sociais': PROGRAMAS_SOCIAIS_OPCOES,
        'periodos': PERIODOS_SUPERIOR,
    }


__all__ = [
    'valores_form_aluno',
    'catalogos_formulario',
    'TIPOS_DEFICIENCIA',
    'GENERO_OPCOES', 'RACA_COR_OPCOES', 'RESPONSAVEL_TIPO_OPCOES',
    'ACOMPANHANTE_OPCOES', 'ZONA_OPCOES', 'ESCOLARIDADE_OPCOES',
    'STATUS_ESCOLAR_OPCOES', 'TIPO_INSTITUICAO_OPCOES', 'TURNO_ESCOLAR_OPCOES',
    'RESIDENTE_RENDA_OPCOES', 'OCUPACAO_OPCOES', 'BENEFICIO_STATUS_OPCOES',
    'MEIO_TRANSPORTE_OPCOES', 'SAUDE_MEDICACAO_OPCOES', 'PROGRAMAS_SOCIAIS_OPCOES',
    'PERIODOS_SUPERIOR',
    'DOC_IDS_FORM', 'DOC_LAUDO_ID', 'DOC_LABELS_FORM',
]
