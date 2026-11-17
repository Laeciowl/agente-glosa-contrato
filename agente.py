"""
Agente de glosa por contrato.

O que faz, em uma frase: le o extrato do sinistro de um prestador, aplica as
regras do contrato desse prestador e grava a lista de itens a glosar, com a
clausula e o valor.

Como esta organizado:
- As regras (a logica) ficam aqui, e sao as mesmas para qualquer prestador.
- Os numeros do contrato (tabela, pacotes, codigos) ficam no arquivo JSON em
  parametros/. Trocar de hospital = trocar o JSON.
- So usa o que ja vem com o Python 3.9+. Nao precisa instalar nada.
- Valores em reais usam Decimal (aritmetica exata), para nao haver erro de centavo.

Uso:
    python3 agente.py                       (usa os caminhos padrao)
    python3 agente.py --sinistro X.csv --parametros Y.json --saida pasta/
"""

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

PASTA = Path(__file__).resolve().parent
CENTAVO = Decimal("0.01")

MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}


# ---------------------------------------------------------------------------
# Leitura dos arquivos
# ---------------------------------------------------------------------------

def reais(texto):
    """Converte '1.234,56' ou '132,93' ou '45' em Decimal('1234.56')."""
    t = str(texto).strip().replace("R$", "").replace(" ", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    return Decimal(t)


def data_pt(texto):
    """Converte '14 de junho de 2025' (ou '2025-06-14') em date."""
    t = texto.strip().lower()
    m = re.match(r"(\d{1,2}) de (\w+) de (\d{4})", t)
    if m:
        return date(int(m.group(3)), MESES[m.group(2)], int(m.group(1)))
    return date.fromisoformat(t)


def carregar_parametros(caminho):
    p = json.loads(Path(caminho).read_text(encoding="utf-8"))
    return {
        "prestador": p["prestador"],
        "contrato": p["contrato"],
        "vigencia": (date.fromisoformat(p["contrato"]["vigencia_inicio"]),
                     date.fromisoformat(p["contrato"]["vigencia_fim"])),
        "tolerancia": Decimal(p.get("tolerancia_preco_reais", "0")),
        "tabela": {i["cod_tuss"]: Decimal(i["valor"]) for i in p["tabela_precos"]["itens"]},
        "pacotes": {i["cod_procedimento"]: i for i in p["pacotes"]["itens"]},
        "codigos_taxa_sala": set(p["pacotes"]["codigos_taxa_sala"]),
        "urgencia_cod": p["taxa_urgencia"]["cod_tuss"],
        "urgencia_carateres": set(p["taxa_urgencia"]["carateres_permitidos"]),
    }


def carregar_sinistro(caminho):
    """Le o CSV do sinistro. Aceita valores com virgula decimal e BOM no inicio."""
    itens = []
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        for linha in csv.DictReader(f):
            linha["qtd"] = Decimal(linha["qtd"])
            linha["vl_unitario"] = reais(linha["vl_unitario"])
            linha["vl_total"] = reais(linha["vl_total"])
            linha["data"] = data_pt(linha["dt_atendimento"])
            itens.append(linha)
    return itens


# ---------------------------------------------------------------------------
# Regras
# ---------------------------------------------------------------------------
# Cada item recebe no maximo UMA glosa. Ordem de prioridade:
#   1. Pacote (clausula 3.3): item incluso no pacote cobrado a parte -> glosa total.
#   2. Urgencia (clausula 4.2): taxa de urgencia em atendimento eletivo -> glosa total.
#   3. Preco (clausula 2.2, ou 3.1 se for o proprio procedimento de pacote):
#      valor unitario acima da tabela -> glosa do excedente x quantidade.
# Glosa total vence glosa de excedente: se o item nao podia ser cobrado, nao faz
# sentido glosar so a diferenca de preco. Assim nenhum real e contado duas vezes.
#
# O que NAO vira glosa automatica e vai para revisao humana:
#   - item fora do Anexo I (clausula 2.3: depende de negociacao especifica);
#   - taxa de sala de porte diferente do pacote da conta (o contrato nao cobre);
#   - atendimento fora da vigencia do contrato;
#   - caráter de atendimento vazio ou desconhecido na taxa de urgencia.

def auditar(itens, par):
    """Recebe a lista de itens e os parametros. Devolve (apontamentos, revisao)."""

    # Passo 1: descobrir, para cada conta, quais procedimentos de pacote ela tem.
    pacotes_da_conta = defaultdict(list)
    for it in itens:
        if it["cod_tuss"] in par["pacotes"]:
            pacotes_da_conta[it["id_conta"]].append(par["pacotes"][it["cod_tuss"]])

    apontamentos, revisao = [], []
    ini, fim = par["vigencia"]

    # Passo 2: olhar item por item.
    for it in itens:
        cod = it["cod_tuss"]
        pacotes = pacotes_da_conta.get(it["id_conta"], [])
        taxas_inclusas = {p["taxa_sala_inclusa"] for p in pacotes}
        materiais_inclusos = {m for p in pacotes for m in p["materiais_inclusos"]}
        nomes_pacotes = ", ".join(f'{p["cod_procedimento"]} ({p["descricao"]})' for p in pacotes)

        if not (ini <= it["data"] <= fim):
            revisao.append(_rev(it, "Atendimento fora da vigência do contrato"))
            continue

        # Regra 1: pacote
        if pacotes and (cod in taxas_inclusas or cod in materiais_inclusos):
            apontamentos.append(_glosa(
                it, "R2_PACOTE", "3.2 e 3.3", it["vl_total"],
                f"Item incluso no pacote do procedimento {nomes_pacotes}, "
                f"cobrado em separado na mesma conta."))
            continue

        if pacotes and cod in par["codigos_taxa_sala"] and cod not in taxas_inclusas:
            revisao.append(_rev(
                it, f"Taxa de sala de porte diferente do pacote da conta ({nomes_pacotes}). "
                    f"O contrato não define este caso."))
            continue

        # Regra 2: taxa de urgencia em atendimento eletivo
        if cod == par["urgencia_cod"]:
            carater = it["carater_atendimento"].strip()
            if carater == "Eletivo":
                alerta = ""
                if it["tipo_conta"] == "Pronto Socorro":
                    alerta = ("Conta de Pronto Socorro registrada como eletiva: "
                              "o prestador pode alegar erro de registro no recurso.")
                apontamentos.append(_glosa(
                    it, "R3_URGENCIA_ELETIVO", "4.1 e 4.2", it["vl_total"],
                    "Taxa de urgência/emergência cobrada em atendimento de caráter eletivo.",
                    alerta))
                continue
            if carater not in par["urgencia_carateres"]:
                revisao.append(_rev(it, f"Caráter de atendimento não reconhecido: '{carater}'"))
                continue

        # Regra 3: preco acima da tabela
        if cod not in par["tabela"]:
            revisao.append(_rev(it, "Item fora do Anexo I (cláusula 2.3): depende de negociação específica"))
            continue

        teto = par["tabela"][cod]
        if it["vl_unitario"] > teto + par["tolerancia"]:
            glosa = ((it["vl_unitario"] - teto) * it["qtd"]).quantize(CENTAVO, ROUND_HALF_UP)
            if cod in par["pacotes"]:
                regra, clausula = "R1_PRECO_PACOTE", "3.1 e 2.2"
                motivo = "Procedimento de pacote cobrado acima do valor de tabela do pacote."
            else:
                regra, clausula = "R1_PRECO", "2.2"
                motivo = "Valor unitário acima do pactuado no Anexo I."
            apontamentos.append(_glosa(
                it, regra, clausula, glosa,
                f"{motivo} Cobrado R$ {it['vl_unitario']}, tabela R$ {teto}, "
                f"excedente R$ {it['vl_unitario'] - teto} x {it['qtd']}.",
                vl_contrato=teto))

    return apontamentos, revisao


def _glosa(it, regra, clausula, valor, motivo, alerta="", vl_contrato=None):
    return {
        "id_item": it["id_item"], "id_conta": it["id_conta"], "cod_tuss": it["cod_tuss"],
        "desc_item": it["desc_item"], "regra": regra, "clausula": clausula,
        "qtd": it["qtd"], "vl_unitario_cobrado": it["vl_unitario"],
        "vl_unitario_contrato": "" if vl_contrato is None else vl_contrato,
        "vl_total_cobrado": it["vl_total"], "vl_glosado": valor,
        "motivo": motivo, "alerta_recurso": alerta,
    }


def _rev(it, motivo):
    return {
        "id_item": it["id_item"], "id_conta": it["id_conta"], "cod_tuss": it["cod_tuss"],
        "desc_item": it["desc_item"], "vl_total_cobrado": it["vl_total"], "motivo": motivo,
    }


# ---------------------------------------------------------------------------
# Saida
# ---------------------------------------------------------------------------

def gravar_csv(caminho, linhas, colunas):
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colunas)
        w.writeheader()
        for l in sorted(linhas, key=lambda x: x["id_item"]):
            w.writerow(l)


COLUNAS_APONT = ["id_item", "id_conta", "cod_tuss", "desc_item", "regra", "clausula", "qtd",
                 "vl_unitario_cobrado", "vl_unitario_contrato", "vl_total_cobrado",
                 "vl_glosado", "motivo", "alerta_recurso"]
COLUNAS_REV = ["id_item", "id_conta", "cod_tuss", "desc_item", "vl_total_cobrado", "motivo"]


def resumo(itens, apontamentos, revisao):
    faturado = sum(i["vl_total"] for i in itens)
    glosado = sum(a["vl_glosado"] for a in apontamentos)
    por_regra = defaultdict(lambda: [0, Decimal("0")])
    for a in apontamentos:
        por_regra[(a["regra"], a["clausula"])][0] += 1
        por_regra[(a["regra"], a["clausula"])][1] += a["vl_glosado"]
    linhas = [
        f"Itens no extrato:          {len(itens)}",
        f"Contas no extrato:         {len({i['id_conta'] for i in itens})}",
        f"Faturado:                  R$ {faturado:,.2f}",
        f"Itens glosados:            {len(apontamentos)}",
        f"Contas com glosa:          {len({a['id_conta'] for a in apontamentos})}",
        f"Valor glosado:             R$ {glosado:,.2f}",
        f"Glosa / faturado:          {(glosado / faturado * 100).quantize(CENTAVO)}%",
        f"Itens em revisão humana:   {len(revisao)}",
        "",
        "Por regra:",
    ]
    for (regra, cl), (n, v) in sorted(por_regra.items(), key=lambda x: -x[1][1]):
        linhas.append(f"  {regra:<22} cláusula {cl:<10} {n:>4} itens   R$ {v:>12,.2f}"
                      f"   {(v / glosado * 100).quantize(CENTAVO):>6}% da glosa")
    alertas = [a for a in apontamentos if a["alerta_recurso"]]
    if alertas:
        linhas.append("")
        linhas.append(f"Glosas com alerta de recurso: {len(alertas)} itens, "
                      f"R$ {sum(a['vl_glosado'] for a in alertas):,.2f}")
    return "\n".join(linhas)


def main():
    ap = argparse.ArgumentParser(description="Agente de glosa por contrato")
    ap.add_argument("--sinistro", default=PASTA / "dados" / "sinistro-hospital-saorafael.csv")
    ap.add_argument("--parametros", default=PASTA / "parametros" / "hospital_sao_rafael.json")
    ap.add_argument("--saida", default=PASTA / "saida")
    a = ap.parse_args()

    par = carregar_parametros(a.parametros)
    itens = carregar_sinistro(a.sinistro)
    apontamentos, revisao = auditar(itens, par)

    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    gravar_csv(saida / "apontamentos.csv", apontamentos, COLUNAS_APONT)
    gravar_csv(saida / "revisao_humana.csv", revisao, COLUNAS_REV)
    texto = resumo(itens, apontamentos, revisao)
    (saida / "resumo_glosa.txt").write_text(texto + "\n", encoding="utf-8")
    print(texto)
    return apontamentos, revisao


if __name__ == "__main__":
    main()
