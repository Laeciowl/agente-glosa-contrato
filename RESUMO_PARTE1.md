# Resumo: agente de glosa por contrato, Hospital São Rafael

## A resposta

Em junho de 2025, o Hospital São Rafael cobrou **R$ 121.948,93 em desacordo com o contrato**: 10,21% dos R$ 1.194.396,92 faturados, em 369 itens de 208 das 320 contas.

O agente encontra essas cobranças sozinho, com **94,4% de precisão e 90,0% de recall** contra o gabarito do auditor. As 23 divergências não seguem nenhum padrão do extrato, e por isso não justificam mudar as regras. A recomendação é levar essas divergências para uma calibragem com a auditoria médica e depois ligar o agente em sombra, regra por regra.

## As regras extraídas do contrato

| Regra | Cláusula | O que detecta | Valor glosado | Itens | R$ | % da glosa |
|---|---|---|---|---|---|---|
| Item de pacote cobrado à parte | 3.2 e 3.3 | Taxa de sala do porte do pacote, fio de sutura (70520020) ou compressa (70402600) cobrados numa conta com colecistectomia, herniorrafia ou artroscopia | Valor total do item | 117 | 55.484,17 | 45,5% |
| Procedimento de pacote acima da tabela | 3.1 e 2.2 | Cirurgia de pacote cobrada acima do valor do Anexo I | Excedente x quantidade | 29 | 27.899,15 | 22,9% |
| Taxa de urgência em eletivo | 4.1 e 4.2 | Taxa 99999001 em atendimento de caráter eletivo | Valor total do item | 77 | 26.589,35 | 21,8% |
| Preço acima da tabela | 2.2 | Valor unitário acima do Anexo I | Excedente x quantidade | 146 | 11.976,26 | 9,8% |

**68% da glosa vem dos pacotes:** o hospital cobra a cirurgia acima do preço do pacote e ainda cobra à parte o que já está dentro dele.

**O que o agente sabe não glosar:**
- Taxa de sala, fio e compressa em contas sem procedimento de pacote: 51 itens, R$ 23.208,88.
- Taxa de urgência em atendimento de urgência: 33 itens, R$ 11.381,28.

Uma regra ingênua teria glosado esses R$ 34.590,16, e perderia tudo no recurso. Item fora do Anexo I, taxa de sala de porte diferente do pacote e atendimento fora da vigência vão para revisão humana. Neste extrato, a fila ficou vazia.

## Métricas

| | Agente glosou | Agente não glosou |
|---|---|---|
| Auditor disse Sim | 135 | 15 |
| Auditor disse Não | 8 | 105 |

- **Precisão (94,4%):** quanto das glosas enviadas se sustenta. Cada erro vira recurso, efetivado zero e desgaste com o hospital.
- **Recall (90,0%):** quanto do indevido o agente encontra. Cada erro é pagamento desnecessário.
- **Priorizo a precisão.** A glosa vai ao prestador sem revisão humana, e a economia só conta depois do recurso.

**As 23 divergências:**
- **15 falsos negativos:** itens que o auditor reprovou, mas que estão abaixo da tabela, fora de pacote e não são urgência em eletivo. Não se distinguem dos 105 itens aprovados em preço, caráter, tipo de conta ou quantidade. Nenhuma cláusula sustenta glosá-los.
- **8 falsos positivos:** todos infringem uma cláusula de forma objetiva. Em 2 contas, o próprio auditor reprovou outro item do mesmo pacote.

Ajustar o agente ao gabarito obrigaria a glosar sem contrato. Cada divergência, com o diagnóstico, está em `saida/divergencias_gabarito.csv`.

**Conferência:** o mesmo resultado sai por três implementações independentes, item a item e centavo a centavo: o agente em Python, as regras em SQL (`regras.sql`) e uma reimplementação em pandas que lê a tabela direto do PDF.

## Recurso: a regra mais defensável e a mais frágil

- **Mais defensável: preço acima da tabela (2.2).** É aritmética contra um valor assinado no Anexo I, e a cláusula traz a fórmula da glosa.
- **Mais frágil: taxa de urgência em Pronto Socorro registrado como eletivo.** São 9 itens e R$ 3.087,98. A regra depende de um campo que o próprio hospital preenche, e um PS eletivo é incoerente: o hospital pode provar urgência pelo prontuário. Essas glosas saem marcadas com alerta e devem ir para revisão humana, não para envio automático.
- **Pacote:** a cláusula 3.3 é forte ("integralmente glosada"). O ponto de ataque seria alegar que o item era de outro procedimento. Por isso cada glosa cita a conta e o procedimento de pacote que a sustenta.

## Deploy

**Parâmetros que mudam de prestador para prestador.** Ficam em `parametros/hospital_sao_rafael.json`; o motor não muda:
- tabela de preços;
- pacotes, com a taxa de sala inclusa e os materiais de rotina;
- unidade do pacote (conta ou internação);
- taxas condicionadas ao caráter;
- vigência e reajustes, ou seja, qual tabela vale em cada data;
- tolerância de preço;
- regras ligadas e numeração das cláusulas.

Para outro hospital, troca o arquivo. O gargalo de escala é preencher esse arquivo. Aí entra IA: um modelo lê o contrato e propõe o JSON, `conferir_parametros.py` confere contra o texto e um humano aprova.

**Produção.** Não ligaria enviando glosas direto, porque o gabarito tem 263 itens escolhidos de forma não aleatória.
1. **Sombra, de 2 a 4 semanas:** o agente roda nas contas reais sem enviar. A operadora revisa uma amostra aleatória de 200 glosas e 200 itens não glosados.
2. **Pronto, regra por regra:** pelo menos 190 de 200 glosas corretas (limite inferior de 91% com 95% de confiança), zero erro de parâmetro e aprovação de Contas Médicas e da Auditoria Médica.
3. **Ordem de ligar:** preço, depois pacote, depois urgência fora do PS. Cada regra tem um interruptor próprio.

**Monitoramento depois de ligar:**
- taxa de reversão em recurso por regra (alerta acima de 5%);
- taxa de recurso;
- economia efetivada sobre enviada;
- volume semanal por regra contra o período de sombra;
- itens fora do Anexo I;
- fila de revisão humana;
- fim da vigência em 31/12/2026, com alerta 60 dias antes para atualizar a tabela.

No longo prazo, sucesso é a cobrança indevida do hospital caindo mês a mês: ele aprende a cobrar certo.

## Como rodar

```bash
python3 rodar.py
```

Precisa só de Python 3.9 ou mais novo, sem nada para instalar. Detalhes no [README](README.md).
