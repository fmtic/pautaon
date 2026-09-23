# Programas sociais no cadastro do aluno

O campo **Qual programa?** aceita vários benefícios sem que o usuário precise
separá-los por vírgulas. Cada nome é adicionado como uma etiqueta individual.

## Uso no cadastro e na edição

1. Marque **Sim** em **Beneficiário de Programa Social?**.
2. Selecione um nome sugerido ou digite um nome próprio.
3. Pressione `Enter` ou clique em **Adicionar**.
4. Repita os passos para cada benefício.
5. Para corrigir um item, remova a etiqueta pelo botão de fechar e adicione o
   nome corrigido.

Os nomes são enviados como valores separados e o backend remove duplicidades.
Internamente, a compatibilidade é mantida usando `\|` entre os nomes salvos.
Registros antigos com um único nome continuam funcionando normalmente.

## Adicionar ou editar nomes sugeridos

A lista de sugestões é mantida nos dois templates abaixo e deve ser atualizada
nos dois arquivos para que cadastro e edição ofereçam as mesmas opções:

- `app/templates/alunos/novo.html`
- `app/templates/alunos/editar.html`

Dentro de cada arquivo, localize o bloco `<datalist id="programas_sociais">`.
Para adicionar um benefício, inclua uma nova opção:

```html
<option value="Nome oficial do benefício">
```

Para editar um nome, altere o conteúdo do atributo `value` e mantenha o mesmo
texto visível. Como o usuário também pode digitar nomes próprios, atualizar a
lista não exige migration nem altera registros já salvos.

Se um benefício deixar de ser oferecido, remova-o dos dois `datalist`; isso
retira apenas a sugestão e não apaga nomes já registrados nos alunos.

## Banco de dados

O campo `perfil_socioeconomico.beneficio_social_nome` é `TEXT`, pois vários
benefícios podem ultrapassar o limite anterior de 100 caracteres. A migration
`4c8e2f7a1b30_amplia_programas_sociais` faz essa alteração.
