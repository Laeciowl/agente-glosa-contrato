"""
Compara os apontamentos do agente com o gabarito do auditor.

Precisao: dos itens que o agente glosou, quantos o auditor tambem marcou como indevidos.
          Cada erro aqui e uma glosa que o prestador vai contestar no recurso.
Recall:   dos itens que o auditor marcou como indevidos, quantos o agente pegou.
          Cada erro aqui e dinheiro que a operadora paga sem precisar.

Tambem grava cada divergencia com um diagnostico, para ser revisada uma a uma.
"""

import csv
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import agente

PASTA = Path(__file__).resolve().parent


def ler_gabarito(caminho):
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        return {l["id_item"]: l["indevido"].strip().lower() == "sim" for l in csv.DictReader(f)}


def pct(a, b):
    return f"{Decimal(a) / Decimal(b) * 100:.1f}%" if b else "n/a"


def validar(itens, apontamentos, gabarito):
    por_id = {i["id_item"]: i for i in itens}
    glosa = {a["id_item"]: a for a in apontamentos}

    vp = [i for i, sim in gabarito.items() if sim and i in glosa]        # verdadeiro positivo
    fp = [i for i, sim in gabarito.items() if not sim and i in glosa]    # falso positivo
    fn = [i for i, sim in gabarito.items() if sim and i not in glosa]    # falso negativo
    vn = [i for i, sim in gabarito.items() if not sim and i not in glosa]

    # Rotulos do auditor por (conta, regra), para achar incoerencias dentro da mesma conta
    rotulos_conta_regra = defaultdict(set)
    for i, sim in gabarito.items():
        if i in glosa:
            rotulos_conta_regra[(glosa[i]["id_conta"], glosa[i]["regra"])].add(sim)

    divergencias = []
    for i in fp:
        a = glosa[i]
        diag = (f"Auditor marcou Não, mas o item infringe a cláusula {a['clausula']}: {a['motivo']}")
        if True in rotulos_conta_regra[(a["id_conta"], a["regra"])]:
            diag += " O auditor marcou Sim em outro item da mesma conta pela mesma regra."
        divergencias.append({"id_item": i, "tipo": "falso positivo (agente glosou, auditor disse Não)",
                             "id_conta": a["id_conta"], "cod_tuss": a["cod_tuss"],
                             "desc_item": a["desc_item"], "valor_em_jogo": a["vl_glosado"],
                             "diagnostico": diag})
    for i in fn:
        it = por_id[i]
        diag = ("Auditor marcou Sim, mas o item está dentro do valor de tabela, não é item de pacote "
                "e não é taxa de urgência em eletivo. Nenhuma cláusula do contrato sustenta a glosa.")
        divergencias.append({"id_item": i, "tipo": "falso negativo (auditor disse Sim, agente não glosou)",
                             "id_conta": it["id_conta"], "cod_tuss": it["cod_tuss"],
                             "desc_item": it["desc_item"], "valor_em_jogo": it["vl_total"],
                             "diagnostico": diag})

    por_regra = defaultdict(lambda: [0, 0])
    for i in vp:
        por_regra[glosa[i]["regra"]][0] += 1
    for i in fp:
        por_regra[glosa[i]["regra"]][1] += 1

    linhas = [
        f"Itens no gabarito: {len(gabarito)} ({sum(gabarito.values())} Sim, "
        f"{len(gabarito) - sum(gabarito.values())} Não)",
        "",
        "Matriz de confusão (linhas = auditor, colunas = agente)",
        f"                    agente glosou   agente não glosou",
        f"  auditor Sim       {len(vp):>8}         {len(fn):>8}",
        f"  auditor Não       {len(fp):>8}         {len(vn):>8}",
        "",
        f"Precisão: {pct(len(vp), len(vp) + len(fp))}   ({len(vp)} de {len(vp) + len(fp)} glosas confirmadas pelo auditor)",
        f"Recall:   {pct(len(vp), len(vp) + len(fn))}   ({len(vp)} de {len(vp) + len(fn)} indevidos encontrados)",
        f"Acurácia: {pct(len(vp) + len(vn), len(gabarito))}",
        "",
        "Valor em jogo nas divergências:",
        f"  falsos positivos: R$ {sum(glosa[i]['vl_glosado'] for i in fp):,.2f} glosados em itens que o auditor aprovou",
        f"  falsos negativos: R$ {sum(por_id[i]['vl_total'] for i in fn):,.2f} cobrados em itens que o auditor reprovou (valor total do item)",
        "",
        "Precisão por regra (no gabarito):",
    ]
    for r, (v, f) in sorted(por_regra.items()):
        linhas.append(f"  {r:<22} {v:>3} confirmadas, {f:>2} contestadas pelo auditor   precisão {pct(v, v + f)}")

    ps = [i for i in gabarito if i in glosa and glosa[i]["alerta_recurso"]]
    linhas += ["", f"Glosas com alerta de recurso (PS registrado como eletivo) presentes no gabarito: {len(ps)}"
               f" ({sum(gabarito[i] for i in ps)} Sim)"]
    return "\n".join(linhas), divergencias


def main():
    par = agente.carregar_parametros(PASTA / "parametros" / "hospital_sao_rafael.json")
    itens = agente.carregar_sinistro(PASTA / "dados" / "sinistro-hospital-saorafael.csv")
    apontamentos, _ = agente.auditar(itens, par)
    gabarito = ler_gabarito(PASTA / "dados" / "gabarito-auditoria.csv")
    texto, divergencias = validar(itens, apontamentos, gabarito)

    saida = PASTA / "saida"
    saida.mkdir(exist_ok=True)
    (saida / "metricas_validacao.txt").write_text(texto + "\n", encoding="utf-8")
    with open(saida / "divergencias_gabarito.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id_item", "tipo", "id_conta", "cod_tuss", "desc_item",
                                          "valor_em_jogo", "diagnostico"])
        w.writeheader()
        w.writerows(sorted(divergencias, key=lambda d: (d["tipo"], d["id_item"])))
    print(texto)


if __name__ == "__main__":
    main()
