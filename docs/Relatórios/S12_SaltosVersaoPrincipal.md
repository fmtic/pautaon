# S12 - Saltos de Versao Principal (Prompt H)

Data: 31/10/2026 - Branch: nova_feature - Sem push

## E0 - Levantamento

### cryptography 46.0.7
- Required-by: google-auth 2.49.2 (>=38.0.3).
- pipdeptree: google-auth -> google-api-core, google-api-python-client, google-auth-httplib2, google-auth-oauthlib.
- Uso direto no app/scripts: nenhum.
- Vulnerabilidades: 7 (PYSEC-2026-3552/3553/3554, GHSA-537c-gmf6-5ccf). Correcao minima 48.0.1+.
- Alcance: PKCS7 decrypt (nao aplicavel), validacao de cadeia com wildcard (improvavel), OpenSSL estatico na wheel (improvavel).

### oauthlib 3.3.1
- Required-by: requests-oauthlib 2.0.0 (oauthlib>=3.0.0).
- Uso direto no app: app/auth.py importa google_auth_oauthlib.flow.Flow (nao oauthlib diretamente).
- requests-oauthlib aceita oauthlib>=3.0.0; google-auth-oauthlib 1.3.1 aceita requests-oauthlib>=0.7.0. Ou seja, oauthlib 4.x e aceito pela cadeia atual.
- Vulnerabilidades: 3 (PYSEC-2026-4114 PKCE timing side-channel, CVE-2026-49272 device_code bearer token). Correcao minima 4.0.0.
- Alcance: device_code grant nao usado (improvavel); PKCE timing side-channel (improvavel).

## Pacotes atualizados

### Pillow 12.3.0 -> 13.0.0 (commit fff264a)
- Wheel disponivel para Python 3.14 (sem build).
- app/utils/fotos.py: usa Image.open, verify, checagem de megapixels; captura Exception ampla. Nenhuma API removida afetou o codigo.
- Testes: test_s1_foto_upload.py 15 passed; prova funcional .tmp/pillow13_prova.py: PNG valido OK, JPEG valido OK, acima do limite OK, corpo invalido OK.
- Suite: 1218 passed, 693 warnings em 350.09s.
- pip-audit: Pillow sem vulnerabilidades restantes.

### pytest 8.3.4 -> 9.2.0 (commit 7b85950)
- Criado requirements-dev.txt com -r requirements.txt e pytest==9.0.3 (9.2.0 instalado); removido pytest de requirements.txt.
- Documentado em docs/manual_deploy.md.
- Suite: 1218 passed, 693 warnings em 323.53s (mesma contagem de testes coletados: 1218).
- pip-audit: pytest sem vulnerabilidades restantes.

## Pendencias (nao instaladas - exigem salto MAJOR)

| Pacote | Versao atual | Correcao | Quem exige | Alcance | Recomendacao |
|--------|--------------|----------|------------|---------|--------------|
| cryptography | 46.0.7 | 48.0.1+ | google-auth (>=38.0.3) | improvavel/nao se aplica | Atualizar depois, validar login Google e TLS em homologacao |
| oauthlib | 3.3.1 | 4.0.0 | requests-oauthlib (>=3.0.0) | improvavel | Atualizar depois, testar login Google |

## Compatibilidade de producao (Python 3.14, IIS + wfastcgi)

- wfastcgi 3.0.0: Version 3.0.0, Requires-Python None, classifiers ate Python 3.6. Nao ha evidencia de suporte a Python 3.14 na metadata; execucao real no IIS nao foi testada. Teste manual necessario no servidor.
- Nenhuma versao nova exige Python acima de 3.14.

## Passo a passo para producao

1. Backup: pip freeze da producao.
2. Instalar do requirements.txt (e requirements-dev.txt para testes).
3. pip check.
4. Reiniciar o app no IIS.
5. Testar login, login Google, upload de foto, exportacao XLSX e impressao de pauta.
6. Plano de volta: reinstalar do freeze anterior.

## Fechamento

- Suite final: 1218 passed, 693 warnings em 323.53s.
- pip check: No broken requirements found.
- Ruff: All checks passed.
- pip-audit final: 10 vulnerabilidades restantes (cryptography 7, oauthlib 3), todas exigem salto MAJOR.
