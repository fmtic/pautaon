# Relatório de alterações: fluxo de atendimentos

Data: 2026-09-09

## Objetivo

Foi ajustado o fluxo de atendimentos de alunos para:

- Exibir uma tela de transição entre os módulos de atendimento.
- Separar o atendimento pedagógico do módulo de Serviço Social conforme o perfil do usuário.
- Renomear o template pedagógico para `atendimento_pedagogico.html`.
- Permitir o registro de dados detalhados do atendimento pedagógico.
- Preservar o aluno selecionado ao iniciar um atendimento a partir da listagem de alunos.

## Arquivos alterados

### `app/routes/registros/atendimentos.py`

- Adicionada a rota protegida:
  - `GET /alunos/atendimentos/transicao`
  - Endpoint: `registros.transicao_atendimentos`
- A rota verifica os perfis já usados no módulo:
  - `admin`
  - `pedagogico`
  - `gerencia`
  - `secretaria`
  - `servico_social`
- A listagem passou a renderizar `alunos/atendimento_pedagogico.html`.
- A consulta da listagem recupera, para cada aluno, o atendimento mais recente e o campo `atendido_por_nome`.
- A listagem continua filtrando por unidade, nome, matrícula, setor e período.
- O cadastro e a edição aceitam tanto JSON legado quanto `multipart/form-data`.
- Foram adicionadas validações server-side para:
  - data do atendimento;
  - origem do atendimento;
  - motivo obrigatório;
  - extensão do anexo;
  - tamanho máximo de 2 MB.
- Extensões atualmente permitidas:
  - `.pdf`
  - `.doc`
  - `.docx`
  - `.odt`
  - `.rtf`
  - `.txt`
  - `.png`
  - `.jpg`
  - `.jpeg`
- Anexos são salvos em:
  - `app/static/uploads/documentos/atendimentos/`
- O nome do arquivo é sanitizado com `secure_filename`.
- O JSON do atendimento guarda os metadados do anexo, incluindo nome original, caminho relativo e tamanho.

### `app/templates/alunos/atendimento_pedagogico.html`

- Template renomeado a partir de `atendimentos.html`.
- A tabela exibe:
  - matrícula;
  - foto;
  - nome completo;
  - usuário que registrou o atendimento mais recente;
  - data do último atendimento;
  - ações.
- O formulário de registro inclui:
  - nome, matrícula e foto do aluno;
  - turma atual;
  - curso;
  - horário;
  - instrutor;
  - origem: Educando, Família ou Equipe;
  - responsável presente;
  - campo para novo responsável;
  - motivo;
  - data do atendimento;
  - apontamentos;
  - acordos com o educando;
  - acordos com a família;
  - observações;
  - anexo com limite de 2 MB.
- O histórico exibe os campos novos quando disponíveis.
- Registros antigos continuam com fallback para campos legados, como `descricao` e `resumo`.

### `app/templates/alunos/gerenciar.html`

- O botão de ação `Registrar Atendimento` deixou de abrir o modal local.
- O botão agora aponta para:
  - `/alunos/atendimentos/transicao?aluno_id=<id>`
- O aluno selecionado é preservado no fluxo.
- O modal antigo ainda existe no arquivo, mas não é mais acionado por esse botão. Ele pode ser removido em uma limpeza posterior, desde que nenhum outro fluxo ainda o utilize.

### `app/templates/alunos/transicao_atendimentos.html`

- Atendimento Pedagógico aponta para a listagem pedagógica filtrada pela matrícula do aluno selecionado.
- Serviço Social recebe o `aluno_id` como parâmetro de consulta.
- As opções são exibidas conforme o `role` do usuário:
  - Pedagógico: `pedagogico` e `admin`.
  - Serviço Social: `servico_social` e `admin`.
- Existe uma mensagem de fallback para usuários sem essas permissões específicas.

### `app/templates/base.html`

- O submenu `Alunos > Atendimentos` aponta para a tela de transição, em vez de apontar diretamente para a listagem pedagógica.

## Persistência e banco de dados

### O que foi preservado

A tabela `atendimento` já possui a estrutura adequada para esta alteração:

- `aluno_id`
- `setor`
- `data_atendimento`
- `resumo`
- `dados` como JSON
- `atendido_por_id`
- `atendido_por_nome`
- `unidade_id`
- campos de auditoria

Os novos campos foram armazenados dentro de `Atendimento.dados`, por exemplo:

```json
{
  "origem": "Família",
  "responsavel_nome": "Nome do responsável",
  "motivo": "Motivo do atendimento",
  "apontamentos": "Apontamentos",
  "acordos_educando": "Acordos com o educando",
  "acordos_familia": "Acordos com a família",
  "observacoes": "Observações",
  "anexo": {
    "nome": "documento.pdf",
    "arquivo": "atendimentos/atendimento_1_20260909120000000000_documento.pdf",
    "tamanho": 12345
  }
}
```

### O que não foi alterado no banco

- Nenhuma coluna nova foi criada.
- Nenhuma tabela nova foi criada.
- Nenhuma migration Alembic foi criada.
- Nenhum registro existente foi migrado ou reescrito.
- Não houve alteração no modelo `Atendimento`.
- Os anexos não são armazenados como BLOB no banco; somente seus metadados e caminho relativo ficam no JSON.

### Motivo de não alterar o schema

O projeto já usa `Atendimento.dados` como JSON flexível para campos específicos dos formulários. Usar esse campo evita migration e mantém compatibilidade com registros antigos e com outros setores que podem possuir campos próprios.

## Ajustes que não foram possíveis ou não foram realizados

1. **Não foi criada uma tabela própria para anexos.**
   - O anexo fica no filesystem e seus metadados ficam no JSON.
   - Uma evolução futura poderia criar uma tabela `atendimento_anexo` para múltiplos anexos, auditoria, exclusão e controle de integridade.

2. **Não há exclusão automática do arquivo físico ao excluir ou substituir um atendimento.**
   - A exclusão atual remove o registro do banco, mas o arquivo físico pode permanecer.
   - Deve ser tratado em uma futura rotina de limpeza ou no endpoint de exclusão.

3. **O campo de responsável usa os nomes disponíveis na ficha do aluno.**
   - Foram considerados `nome_mae`, `nome_pai` e `responsavel_nome` do JSON de identificação.
   - Não foi criada uma tabela relacional de responsáveis.
   - Caso a ficha passe a possuir múltiplos responsáveis estruturados, o formulário deverá ser adaptado.

4. **O botão de Serviço Social preserva `aluno_id` na URL, mas o destino existente pode ainda não usar esse parâmetro para abrir automaticamente o aluno.**
   - O próximo agente deve verificar o fluxo do endpoint `servico_social.listar_entrevistas` e, se necessário, implementar o pré-carregamento do aluno.

5. **O modal antigo de atendimento em `gerenciar.html` não foi removido.**
   - Ele deixou de ser acionado pelo botão principal.
   - Deve ser removido somente após confirmar que não há outro JavaScript ou fluxo dependente dele.

6. **A consulta usa `atendido_por_nome` armazenado no momento do registro.**
   - Se o usuário mudar de nome depois, registros antigos continuarão mostrando o nome histórico salvo.
   - Isso é desejável para auditoria, mas deve ser considerado caso o próximo agente queira exibir sempre o nome atual do usuário via relacionamento.

7. **Não foi implementada uma política avançada de segurança de conteúdo para documentos.**
   - A validação atual é por extensão e tamanho.
   - Para produção, considerar validação MIME, antivírus, armazenamento privado e download protegido por autorização.

## Compatibilidade com dados existentes

- Registros antigos sem os novos campos continuam sendo exibidos.
- O histórico usa fallback para `resumo` e `descricao` quando os campos novos não existem.
- A API de cadastro continua aceitando JSON, além do novo envio multipart com anexo.
- A estrutura da tabela `atendimento` não foi alterada.

## Validações executadas

Foram executadas com sucesso:

- `python -m py_compile app/routes/registros/atendimentos.py`
- carregamento dos templates pelo Jinja;
- confirmação das rotas Flask;
- geração das URLs com `aluno_id`;
- validação de extensão de upload inválida;
- `git diff --check`.

O Ruff não foi executado porque não está instalado no ambiente Python utilizado.

## Pontos recomendados para o próximo agente

1. Testar manualmente o fluxo com um usuário `pedagogico`.
2. Testar com um usuário `admin` e confirmar a exibição das duas opções.
3. Testar com um usuário `servico_social` e confirmar que somente o módulo social aparece.
4. Testar cadastro com arquivo de até 2 MB.
5. Testar rejeição de arquivo acima de 2 MB.
6. Testar rejeição de extensão não permitida.
7. Confirmar que o aluno selecionado em `gerenciar.html` permanece selecionado na listagem pedagógica.
8. Decidir se o módulo de Serviço Social deve abrir diretamente o formulário do aluno recebido em `aluno_id`.
9. Avaliar a remoção do modal antigo em `gerenciar.html`.
10. Avaliar uma futura tabela relacional para anexos caso seja necessário suportar vários arquivos por atendimento.
