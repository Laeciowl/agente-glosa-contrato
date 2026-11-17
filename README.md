# Agente de glosa por contrato: Hospital São Rafael

Lê o extrato do sinistro de um prestador, aplica as regras do contrato com a operadora e devolve os itens a glosar, com a cláusula infringida e o valor.

**Resumo de 2 páginas (regras, métricas, quantificação e deploy): [RESUMO_PARTE1.md](RESUMO_PARTE1.md)**

A análise da Parte 2 (funil de economia) está em `parte2/analise_funil.py`, e o resultado em `parte2/resultado_funil.txt`.

## Como rodar

Precisa só de Python 3.9 ou mais novo. Não há nada para instalar.

```bash
python3 rodar.py
```

No Windows, use `python rodar.py` ou `py rodar.py`.

O comando faz cinco passos e para se algum falhar:

1. Confere a tabela de preços e os pacotes do arquivo de parâmetros contra o texto do contrato.
2. Roda 20 testes de casos de borda. Exemplo: taxa de sala sem pacote na conta não é glosada.
3. Roda o agente sobre os 1.696 itens do extrato.
4. Roda as mesmas regras em SQL e confere se o resultado bate com o Python, item a item e centavo a centavo.
5. Compara com o gabarito do auditor: precisão, recall e cada divergência explicada.

O resultado esperado é R$ 121.948,93 glosados em 369 itens, 10,21% do faturado. Os arquivos de `saida/` já estão no repositório, então dá para ver os resultados sem rodar nada.

## Resultados

| Arquivo | O que tem |
|---|---|
| `saida/apontamentos.csv` | Cada item glosado: id_item, conta, código, regra, cláusula, valor cobrado, valor de contrato, valor glosado, motivo e alerta de recurso |
| `saida/resumo_glosa.txt` | Totais por regra |
| `saida/metricas_validacao.txt` | Precisão e recall contra o gabarito |
| `saida/divergencias_gabarito.csv` | Cada divergência com o auditor e o diagnóstico |
| `saida/revisao_humana.csv` | Itens que o agente não decide sozinho. Vazio neste extrato |

## As regras

| Regra | Cláusula | O que detecta | Valor glosado |
|---|---|---|---|
| R1_PRECO | 2.2 | Valor unitário acima do Anexo I | (cobrado menos tabela) x quantidade |
| R1_PRECO_PACOTE | 3.1 e 2.2 | Procedimento de pacote cobrado acima do valor de tabela | (cobrado menos tabela) x quantidade |
| R2_PACOTE | 3.2 e 3.3 | Taxa de sala do porte do pacote, fio de sutura ou compressa cobrados à parte numa conta com procedimento de pacote | Valor total do item |
| R3_URGENCIA_ELETIVO | 4.1 e 4.2 | Taxa de urgência em atendimento de caráter eletivo | Valor total do item |

Cada item recebe no máximo uma glosa. Se o item não podia ser cobrado (pacote ou urgência em eletivo), a glosa é integral e não se soma o excedente de preço.

O agente **não** glosa, e manda para revisão humana:
- item fora do Anexo I, porque a cláusula 2.3 exige negociação específica;
- taxa de sala de porte diferente do pacote da conta, porque o contrato não define esse caso;
- atendimento fora da vigência;
- caráter de atendimento desconhecido.

## Como trocar de prestador

Tudo o que vem do contrato está em `parametros/hospital_sao_rafael.json`: tabela de preços, pacotes, taxa de sala inclusa, materiais de rotina, código da taxa de urgência, vigência e tolerância de preço. Para outro hospital, copie o arquivo, troque os valores e rode:

```bash
python3 agente.py --sinistro outro_sinistro.csv --parametros parametros/outro_hospital.json --saida saida_outro/
```

O motor (`agente.py`) não muda.

## Arquivos

| Arquivo | Função |
|---|---|
| `rodar.py` | Roda tudo na ordem |
| `agente.py` | O motor de regras |
| `parametros/hospital_sao_rafael.json` | Os números do contrato |
| `regras.sql` e `cruzar_sql.py` | As mesmas regras em SQL (SQLite) e a conferência contra o Python |
| `testes.py` | Casos de borda |
| `validar.py` | Comparação com o gabarito |
| `conferir_parametros.py` | Confere o JSON contra o contrato |
| `extrair_texto_contrato.py` | Opcional. Extraiu o texto do PDF uma vez (precisa de `pdfplumber`) |
| `dados/` | Contrato, extrato do sinistro, gabarito e texto extraído do contrato |
