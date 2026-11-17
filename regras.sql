-- As mesmas regras do agente.py, escritas em SQL.
-- Serve para conferir os numeros por um caminho independente.
--
-- Tabelas de entrada (carregadas por cruzar_sql.py, a partir do CSV e do JSON):
--   sinistro(id_item, id_conta, cod_tuss, carater, tipo_conta, data_iso, qtd,
--            vl_unitario_c, vl_total_c)            valores em CENTAVOS (inteiros)
--   tabela(cod_tuss, valor_c)                       Anexo I, em centavos
--   pacote(cod_procedimento, taxa_sala)             Anexo II
--   pacote_material(cod_procedimento, cod_material) Anexo II, materiais de rotina
--   taxa_sala(cod_tuss)                             codigos de taxa de sala
--   carater_urgencia(carater)                       carateres em que a taxa de urgencia e devida
--   parametro(nome, valor)                          vigencia, codigo da taxa de urgencia, tolerancia

DROP VIEW IF EXISTS apontamentos_sql;

CREATE VIEW apontamentos_sql AS
WITH
p AS (
    SELECT
        (SELECT valor FROM parametro WHERE nome = 'vigencia_inicio')         AS vig_ini,
        (SELECT valor FROM parametro WHERE nome = 'vigencia_fim')            AS vig_fim,
        (SELECT valor FROM parametro WHERE nome = 'urgencia_cod')            AS urg_cod,
        CAST((SELECT valor FROM parametro WHERE nome = 'tolerancia_c') AS INTEGER) AS tol_c
),
-- Contas que tem procedimento de pacote
conta_pacote AS (
    SELECT DISTINCT s.id_conta, pk.cod_procedimento, pk.taxa_sala
    FROM sinistro s
    JOIN pacote pk ON pk.cod_procedimento = s.cod_tuss
),
-- Itens inclusos no pacote de cada conta: a taxa de sala do porte e os materiais de rotina
inclusos AS (
    SELECT id_conta, taxa_sala AS cod FROM conta_pacote
    UNION
    SELECT cp.id_conta, pm.cod_material
    FROM conta_pacote cp
    JOIN pacote_material pm ON pm.cod_procedimento = cp.cod_procedimento
),
classificado AS (
    SELECT
        s.*,
        t.valor_c AS teto_c,
        CASE
            WHEN s.data_iso NOT BETWEEN p.vig_ini AND p.vig_fim THEN 'REVISAO'
            -- Regra 1: item incluso no pacote cobrado a parte
            WHEN EXISTS (SELECT 1 FROM inclusos i WHERE i.id_conta = s.id_conta AND i.cod = s.cod_tuss)
                THEN 'R2_PACOTE'
            -- Taxa de sala de outro porte numa conta de pacote: contrato nao define
            WHEN s.cod_tuss IN (SELECT cod_tuss FROM taxa_sala)
                 AND EXISTS (SELECT 1 FROM conta_pacote cp WHERE cp.id_conta = s.id_conta)
                THEN 'REVISAO'
            -- Regra 2: taxa de urgencia em atendimento eletivo
            WHEN s.cod_tuss = p.urg_cod AND s.carater = 'Eletivo' THEN 'R3_URGENCIA_ELETIVO'
            WHEN s.cod_tuss = p.urg_cod AND s.carater NOT IN (SELECT carater FROM carater_urgencia)
                THEN 'REVISAO'
            -- Item fora do Anexo I
            WHEN t.cod_tuss IS NULL THEN 'REVISAO'
            -- Regra 3: preco acima da tabela
            WHEN s.vl_unitario_c > t.valor_c + p.tol_c THEN
                CASE WHEN s.cod_tuss IN (SELECT cod_procedimento FROM pacote)
                     THEN 'R1_PRECO_PACOTE' ELSE 'R1_PRECO' END
            ELSE 'OK'
        END AS regra
    FROM sinistro s
    CROSS JOIN p
    LEFT JOIN tabela t ON t.cod_tuss = s.cod_tuss
)
SELECT
    id_item,
    id_conta,
    cod_tuss,
    regra,
    CASE
        WHEN regra IN ('R2_PACOTE', 'R3_URGENCIA_ELETIVO') THEN vl_total_c
        ELSE (vl_unitario_c - teto_c) * qtd
    END AS vl_glosado_c
FROM classificado
WHERE regra LIKE 'R%';
