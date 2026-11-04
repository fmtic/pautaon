# AJ5-D — Assinatura técnica dos uploads

Data: 04/11/2026  
Branch: `nova_feature`

## Escopo e salvaguardas

- Nenhuma migration foi criada ou aplicada.
- Nenhum banco real recebeu escrita. As contagens de `pautaon` e `pautaon_ensaio` foram consultadas em transações PostgreSQL somente leitura, antes e depois.
- Os testes usam SQLite e dados sintéticos; não foram usados nomes, documentos, e-mails ou ids reais.
- O primeiro `git status` mostrou um relatório AJ9-B anterior não rastreado. Ele foi preservado e não entrou em nenhum commit AJ5-D.
- Nenhum push foi feito.

## 1. Inventário dos pontos de upload

Busca de `request.files`, `FileStorage` e campos `type=file` não encontrou outros pontos de upload no servidor além dos listados abaixo. A webcam cria um `File` JPEG no navegador e usa o mesmo campo e a mesma rota da foto manual.

| Ponto (arquivo:linha) | Tipos, validação e limite | Nome gravado e destino | Quem envia; quem recebe/visualiza |
|---|---|---|---|
| Documentos do aluno — `app/templates/alunos/_form_aluno.html:428,575`; rotas `app/registros/alunos.py:513,677`; validação/gravação `app/registros/shared.py:90,128` | PDF; extensão `.pdf`, `%PDF-` nos primeiros 1024 bytes; vazio e acima de 2 MB recusados. MIME de entrada não é confiado. | Nome lógico gerado pelo servidor `<doc_id>.pdf` (não usa o nome do cliente); `UPLOAD_FOLDER/documentos/<matrícula-normalizada>` ou `aluno_<id>`. | Envio em cadastro/edição por admin, pedagógico e secretaria. Leitura em `app/registros/alunos.py:1428`: admin, pedagógico, secretaria, gerência e serviço social, com unidade validada. Inline, `application/pdf`, `nosniff` e `private, no-store`. |
| Foto do aluno — campo `app/templates/alunos/_form_aluno.html:80`; webcam `app/static/js/alunos/aluno_utils.js:227`; validação/gravação `app/utils/fotos.py:26,90`, `app/registros/shared.py:63` | JPG/JPEG, PNG e WEBP; magic bytes conferidos, extensão tem que estar na whitelist, vazio e acima de 2 MB recusados. Se Pillow estiver instalado, também verifica a imagem e o limite de megapixels. | `aluno_<id>_<UUID>.<extensão-detectada>`; `UPLOAD_FOLDER/fotos`. | Envio em cadastro/edição por admin, pedagógico e secretaria. Leitura em `app/registros/alunos.py:1551`: admin, pedagógico, secretaria, gerência e serviço social; professor somente com inscrição ativa em oferta ativa e mesma unidade. MIME fixo e `nosniff`; a resposta autenticada recebe `no-store` pelo handler global. |
| Anexo de atendimento — campos `app/templates/alunos/atendimento_pedagogico.html:346` e `app/templates/alunos/gerenciar.html:422`; validação/gravação `app/registros/atendimentos.py:62,120` | PDF, DOC, DOCX, ODT, RTF, TXT, PNG, JPG/JPEG; até 2 MB. PDF segue `validar_pdf` do AJ5-B; demais formatos conferem assinatura/estrutura adequada à extensão. Vazio e conteúdo divergente são recusados. TXT não tem magic bytes: são rejeitados controles binários. | `<UUID>.<extensão-validada>`; `UPLOAD_FOLDER/documentos/atendimentos`. O nome original fica somente como metadado de exibição. | Envio por admin, pedagógico, gerência, secretaria e serviço social (`app/registros/atendimentos.py:29,361,453`), sujeito à unidade do aluno. Leitura em `app/registros/atendimentos.py:524`: mesmos papéis e guarda de unidade; inline, MIME fixo, `nosniff`, `private, no-store`. |
| Modelo de certificado — campo `app/templates/periodos/certificado.html:82`; serviço `app/services/certificado_modelo.py:150`; rotas `app/registros/periodos.py:629,660,711` | PNG/JPG/JPEG; extensão e magic bytes precisam corresponder; vazio e acima de 5 MB recusados. | `<UUID>.<extensão-validada>`; `UPLOAD_FOLDER/certificados/<período>`. O nome original permanece como metadado para o download. | Envio e leitura por admin, pedagógico, secretaria e gerência; não-admin limitado à unidade do período e o centro precisa pertencer à mesma unidade. Pré-visualização inline; `?download=1` usa attachment. MIME fixo, `nosniff`, `private, no-store`. |
| Imagens de configuração — `app/templates/admin/informacao_padrao.html:68,76,84,93`; rota `app/informacao_padrao.py:28`; serviço `app/services/informacao_padrao.py:27,106,115` | Logo principal/secundária/foto padrão: PNG/JPG/JPEG/WEBP; favicon também ICO. Limite de 3 MB e extensão verificada; **não** verifica assinatura nem rejeita arquivo vazio. | `informacao_padrao_<timestamp>.<extensão>`; `static/uploads/informacao_padrao`. Nome gerado pelo servidor. | Envio somente por admin; leitura via `/static/`, pública, sem guarda de papel. |

O limite global de corpo é 20 MB (`config.py:212`). As outras validações individuais já existentes (PDF de aluno e foto) foram preservadas. As imagens de configuração ficam públicas e ainda não validam assinatura; não foram alteradas porque isso requer cobrir também ICO e o fluxo de substituição/serviço estático com testes próprios.

## 2. Correções de anexo e certificado

- A validação acontece antes da criação da pasta e da gravação do arquivo. Falha de extensão, assinatura, vazio ou tamanho não deixa arquivo no storage e retorna mensagem ao usuário.
- Anexos: PDF via AJ5-B; PNG/JPEG via magic bytes; DOC exige assinatura OLE e stream `WordDocument`; DOCX exige ZIP, content type Word e `word/document.xml`; ODT exige ZIP e mimetype ODT; RTF exige `{\\rtf`; TXT rejeita controles binários.
- Em ambos os pontos o caminho no disco contém UUID hexadecimal completo e extensão validada, nunca o nome recebido do navegador. Os nomes originais permanecem somente para exibição/download.
- Rotas de entrega mantêm as guards existentes de papel e unidade. `Content-Type` é selecionado por mapa fixo, e as respostas agora incluem `X-Content-Type-Options: nosniff` e `Cache-Control: private, no-store`.
- Anexo continua inline, como antes; modelo mantém preview inline e download como attachment quando solicitado.

## 3. Testes e verificações

- Testes novos cobrem arquivos falsos `.pdf`/`.png`, extensão/conteúdo divergentes, vazio, acima dos limites (2 MB/5 MB), formatos permitidos, nomes com traversal, ausência de gravação em disco, MIME/headers, `403` por papel/unidade e upload/download válido.
- Reversão isolada dos testes: worktree absoluto `D:\\pautaon-aj5d-test-red`, no commit somente de testes `4f421affc5b67c4ee44d3ab2e547d1a9af6c152b`; antes do fix, **11 falharam e 13 passaram**, como esperado. Worktree removido e confirmado ausente.
- Regressões direcionadas finais: `tests/test_aj5d_upload_signature.py` + `tests/test_certificado_modelo.py`: **48 passed**.
- Matrizes `tests/test_aj6b6_matriz_rotas_professor.py` e `tests/test_aj6b7_complemento.py`: executadas na validação direcionada, sem falhas nesses arquivos.
- Ruff (`F821,F811,F841,F401`) em todos os arquivos Python tocados: **All checks passed**.
- Suíte completa (`python -m pytest -q`), uma execução: **1.638 passed, 0 failed, 0 skipped**, 956 warnings, em 25m27s.

## 4. Contagens dos bancos reais

As contagens foram obtidas por `SELECT COUNT(*)` em transações somente leitura. Os 38 nomes de tabela e suas contagens ficaram idênticos antes/depois em ambos os bancos:

| Tabela | `pautaon` antes → depois | `pautaon_ensaio` antes → depois |
|---|---:|---:|
| agenda_servico_social | 0 → 0 | 0 → 0 |
| alembic_version | 1 → 1 | 1 → 1 |
| aluno | 1.155 → 1.155 | 1.166 → 1.166 |
| atendimento | 1 → 1 | 1 → 1 |
| centro_custo | 6 → 6 | 7 → 7 |
| configuracao_sistema | 7 → 7 | 7 → 7 |
| conselho_classe | 45 → 45 | 5 → 5 |
| conselho_pergunta | 12 → 12 | 10 → 10 |
| conselho_resposta | 78 → 78 | 6 → 6 |
| curso | 9 → 9 | 12 → 12 |
| dia_bloqueado | 11 → 11 | 11 → 11 |
| dia_bloqueado_turma | 0 → 0 | 0 → 0 |
| endereco_aluno | 112 → 112 | 112 → 112 |
| frequencia | 64 → 64 | 20 → 20 |
| inscricoes | 32 → 32 | 41 → 41 |
| log_acao | 1.204 → 1.204 | 1.747 → 1.747 |
| login_controle | 0 → 0 | 0 → 0 |
| modelo_certificado | 0 → 0 | 0 → 0 |
| nivel | 6 → 6 | 6 → 6 |
| opcao_proxima_turma | 0 → 0 | 2 → 2 |
| perfil_diversidade | 112 → 112 | 111 → 111 |
| perfil_socioeconomico | 112 → 112 | 112 → 112 |
| periodo_conselho | 1 → 1 | 0 → 0 |
| periodo_letivo | 2 → 2 | 5 → 5 |
| registro | 0 → 0 | 0 → 0 |
| registro_aula | 6 → 6 | 4 → 4 |
| registro_aula_tema | 7 → 7 | 4 → 4 |
| responsavel_aluno | 83 → 83 | 82 → 82 |
| respostas_formulario | 0 → 0 | 0 → 0 |
| situacao_escolar | 104 → 104 | 103 → 103 |
| tema_aula | 54 → 54 | 55 → 55 |
| transferencia | 0 → 0 | 1 → 1 |
| turma | 3 → 3 | 8 → 8 |
| turma_curso | 4 → 4 | 12 → 12 |
| turma_curso_horario | 8 → 8 | 20 → 20 |
| unidade | 2 → 2 | 4 → 4 |
| user | 22 → 22 | 25 → 25 |
| valor_esportista | 8 → 8 | 0 → 0 |

## 5. Commits AJ5-D

Commits com paths explícitos; testes, correções e documentação estão separados:

| Tipo | Hash | Escopo |
|---|---|---|
| test | `42761c5fb5216257bdc89d07f3f9f93c157480fd` | Casos de assinatura, tamanho, nome, permissão e headers |
| test | `1eefd92ad69a48fc3642fed42ff7e0cb1cf834bc` | Formatos permitidos e fixture JPEG coerente |
| test | `4f421affc5b67c4ee44d3ab2e547d1a9af6c152b` | Containers DOC/DOCX/ODT e rejeições adicionais |
| fix | `657374cf7d1ab0a37e1a480b6d279d1bbbce0ec2` | Validação de assinatura, UUIDs e headers |
| fix | `f242a24be194ad2a85b93837b15fd48088e4a97b` | Checagem estrutural e remoção do argumento obsoleto |
