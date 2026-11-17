"""
Roda as regras em SQL (regras.sql, no SQLite que ja vem com o Python) e confere,
item a item e centavo a centavo, se o resultado e igual ao do agente.py.

Se as duas implementacoes, escritas de forma independente, chegam no mesmo
numero, o numero esta certo.
"""

import json
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

import agente

PASTA = Path(__file__).resolve().parent


def centavos(valor):
    return int((Decimal(valor) * 100).to_integral_value())


def carregar_banco(itens, caminho_json):
    p = json.loads(Path(caminho_json).read_text(encoding="utf-8"))
    db = sqlite3.connect(":memory:")
    c = db.cursor()
    c.execute("CREATE TABLE sinistro (id_item, id_conta, cod_tuss, carater, tipo_conta, data_iso, "
              "qtd INTEGER, vl_unitario_c INTEGER, vl_total_c INTEGER)")
    c.executemany("INSERT INTO sinistro VALUES (?,?,?,?,?,?,?,?,?)", [
        (i["id_item"], i["id_conta"], i["cod_tuss"], i["carater_atendimento"].strip(), i["tipo_conta"],
         i["data"].isoformat(), int(i["qtd"]), centavos(i["vl_unitario"]), centavos(i["vl_total"]))
        for i in itens])
    c.execute("CREATE TABLE tabela (cod_tuss, valor_c INTEGER)")
    c.executemany("INSERT INTO tabela VALUES (?,?)",
                  [(t["cod_tuss"], centavos(t["valor"])) for t in p["tabela_precos"]["itens"]])
    c.execute("CREATE TABLE pacote (cod_procedimento, taxa_sala)")
    c.execute("CREATE TABLE pacote_material (cod_procedimento, cod_material)")
    for pk in p["pacotes"]["itens"]:
        c.execute("INSERT INTO pacote VALUES (?,?)", (pk["cod_procedimento"], pk["taxa_sala_inclusa"]))
        for m in pk["materiais_inclusos"]:
            c.execute("INSERT INTO pacote_material VALUES (?,?)", (pk["cod_procedimento"], m))
    c.execute("CREATE TABLE taxa_sala (cod_tuss)")
    c.executemany("INSERT INTO taxa_sala VALUES (?)", [(x,) for x in p["pacotes"]["codigos_taxa_sala"]])
    c.execute("CREATE TABLE carater_urgencia (carater)")
    c.executemany("INSERT INTO carater_urgencia VALUES (?)",
                  [(x,) for x in p["taxa_urgencia"]["carateres_permitidos"]])
    c.execute("CREATE TABLE parametro (nome, valor)")
    c.executemany("INSERT INTO parametro VALUES (?,?)", [
        ("vigencia_inicio", p["contrato"]["vigencia_inicio"]),
        ("vigencia_fim", p["contrato"]["vigencia_fim"]),
        ("urgencia_cod", p["taxa_urgencia"]["cod_tuss"]),
        ("tolerancia_c", centavos(p.get("tolerancia_preco_reais", "0"))),
    ])
    c.executescript((PASTA / "regras.sql").read_text(encoding="utf-8"))
    return db


def cruzar():
    caminho_json = PASTA / "parametros" / "hospital_sao_rafael.json"
    par = agente.carregar_parametros(caminho_json)
    itens = agente.carregar_sinistro(PASTA / "dados" / "sinistro-hospital-saorafael.csv")
    py = {a["id_item"]: (a["regra"], centavos(a["vl_glosado"])) for a in agente.auditar(itens, par)[0]}

    db = carregar_banco(itens, caminho_json)
    sql = {r[0]: (r[1], r[2]) for r in db.execute("SELECT id_item, regra, vl_glosado_c FROM apontamentos_sql")}

    diferencas = sorted(set(py.items()) ^ set(sql.items()))
    total_py, total_sql = sum(v for _, v in py.values()), sum(v for _, v in sql.values())
    print(f"Python: {len(py)} itens, R$ {total_py / 100:,.2f}")
    print(f"SQL:    {len(sql)} itens, R$ {total_sql / 100:,.2f}")
    for regra, n, v in db.execute("SELECT regra, COUNT(*), SUM(vl_glosado_c) FROM apontamentos_sql "
                                  "GROUP BY regra ORDER BY SUM(vl_glosado_c) DESC"):
        print(f"  SQL {regra:<22} {n:>4} itens   R$ {v / 100:>12,.2f}")
    if diferencas:
        print(f"DIVERGÊNCIA entre Python e SQL em {len(diferencas)} registros: {diferencas[:10]}")
        return False
    print("Python e SQL batem item a item e centavo a centavo.")
    return True


if __name__ == "__main__":
    sys.exit(0 if cruzar() else 1)
