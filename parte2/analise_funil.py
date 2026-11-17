"""
Parte 2: funil de economia e oportunidade por alavanca.

Le dados/inteligencias_6_meses.csv (exportado da planilha) e calcula:
1. O funil do mes: identificada -> enviada a operadora -> enviada ao prestador -> efetivada.
2. A perda em cada etapa, separada por causa.
3. Quanto cada alavanca acrescenta de economia efetivada, em dois cenarios.

Premissas (todas tambem no memo):
- A planilha e a foto de um mes (junho de 2025). Sinistro processado no mes: R$ 70 milhoes.
- "Media de Efetivacao todos clientes Arvo" = efetivado / enviado ao prestador nos outros clientes.
- Cenario conservador: a perda entre operadora e prestador continua na taxa atual de cada
  inteligencia (ou na media, para as desligadas).
- Cenario potencial: essa perda e eliminada (relatorio de registro + fluxo automatico).
- Efetivacao: a taxa real de cada inteligencia ligada; para as desligadas, a media dos outros clientes.
- Inteligencia desligada, ao ser ligada, envia todo o identificado (sem filtros).

So usa a biblioteca padrao do Python. Rodar: python3 parte2/analise_funil.py
"""

import csv
from pathlib import Path

P = Path(__file__).resolve().parent.parent
SINISTRO_MES = 70_000_000
META = 0.02
CORTE_EFETIVACAO = 0.50   # inteligencia com media de efetivacao abaixo disso nao entra no plano


def ler():
    with open(P / "dados" / "inteligencias_6_meses.csv", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    for l in linhas:
        for c in ["identificada", "enviada_operadora", "enviada_prestador", "efetivada",
                  "media_efetivacao_clientes_arvo"]:
            l[c] = float(l[c])
        l["ligada"] = l["status"].strip().lower() == "ligada"
    return linhas


def reais(v):
    return f"R$ {v:>12,.0f}".replace(",", ".")


def pct(v):
    return f"{v / SINISTRO_MES * 100:5.2f}%"


def main():
    d = ler()
    lig = [x for x in d if x["ligada"]]
    des = [x for x in d if not x["ligada"]]
    soma = lambda lst, c: sum(x[c] for x in lst)

    ident, op, pr, ef = (soma(d, c) for c in ["identificada", "enviada_operadora", "enviada_prestador", "efetivada"])
    ident_lig = soma(lig, "identificada")
    passagem_media = soma(lig, "enviada_prestador") / soma(lig, "enviada_operadora")
    efet_media = soma(lig, "efetivada") / soma(lig, "enviada_prestador")

    out = []
    w = out.append
    w("FUNIL DO MÊS (junho de 2025, sinistro processado R$ 70.000.000)")
    w(f"  Identificada (26 inteligências)        {reais(ident)}  {pct(ident)}")
    w(f"   - perda: 12 inteligências desligadas  {reais(soma(des, 'identificada'))}")
    w(f"   - perda: filtros nas 14 ligadas       {reais(ident_lig - op)}")
    w(f"  Enviada à operadora                    {reais(op)}  {pct(op)}")
    w(f"   - perda: registro + análise interna   {reais(op - pr)}  ({(1 - pr / op) * 100:.1f}% do enviado)")
    w(f"  Enviada ao prestador                   {reais(pr)}  {pct(pr)}")
    w(f"   - perda: recursos de glosa            {reais(pr - ef)}  ({(1 - ef / pr) * 100:.1f}% do enviado)")
    w(f"  Efetivada                              {reais(ef)}  {pct(ef)}")
    w(f"  Meta do Paulo (2% do sinistro)         {reais(SINISTRO_MES * META)}  {pct(SINISTRO_MES * META)}")
    w(f"  Distância até a meta                   {reais(SINISTRO_MES * META - ef)}")
    w("")
    w(f"Efetivado / identificado: {ef / ident * 100:.1f}%. De cada R$ 100 que a Arvo identifica, R$ {ef / ident * 100:.0f} viram economia.")
    w("")

    # Diagnostico por inteligencia ligada
    w("INTELIGÊNCIAS LIGADAS: onde está cada perda")
    w(f"  {'inteligência':<44}{'tipo':<15}{'filtro':>7}{'op→prest':>10}{'efetiv.':>9}{'média Arvo':>11}")
    for x in sorted(lig, key=lambda x: -x["identificada"]):
        x["filtro"] = 1 - x["enviada_operadora"] / x["identificada"]
        x["passagem"] = x["enviada_prestador"] / x["enviada_operadora"]
        x["efet"] = x["efetivada"] / x["enviada_prestador"]
        w(f"  {x['inteligencia'][:43]:<44}{x['tipo']:<15}{x['filtro'] * 100:6.0f}%{x['passagem'] * 100:9.0f}%"
          f"{x['efet'] * 100:8.0f}%{x['media_efetivacao_clientes_arvo'] * 100:10.0f}%")
    pas = [x["passagem"] for x in lig]
    w(f"  Passagem operadora→prestador varia só de {min(pas) * 100:.0f}% a {max(pas) * 100:.0f}% entre as 14 inteligências.")
    w(f"  Correlação entre passagem e efetivação da inteligência: {corr(pas, [x['efet'] for x in lig]):+.2f}")
    w(f"  Correlação entre passagem e média Arvo da inteligência: {corr(pas, [x['media_efetivacao_clientes_arvo'] for x in lig]):+.2f}")
    acima = sum(1 for x in lig if x["efet"] >= x["media_efetivacao_clientes_arvo"] - 0.005)
    w(f"  Inteligências com efetivação igual ou acima da média Arvo: {acima} de {len(lig)}")
    for tipo in ["Técnica", "Administrativa"]:
        g = [x for x in lig if x["tipo"] == tipo]
        w(f"  Retido por filtro nas {tipo.lower()}s: {reais(soma(g, 'identificada') - soma(g, 'enviada_operadora'))}")
    w("")

    # Alavancas
    def alavancas(potencial):
        res = []
        # A. eliminar perda entre operadora e prestador nas ligadas
        a = sum(x["enviada_operadora"] * (1 - x["passagem"]) * x["efet"] for x in lig) if potencial else 0.0
        res.append(("A. Fechar a perda de registro e análise nas 14 ligadas", a, "Parthenon (TI) + Arvo"))
        # B. liberar filtros nas ligadas
        for tipo, dono in [("Técnica", "Dr. Ary + Arvo"), ("Administrativa", "Alana + Arvo")]:
            v = sum((x["identificada"] - x["enviada_operadora"]) * (1 if potencial else x["passagem"]) * x["efet"]
                    for x in lig if x["tipo"] == tipo)
            res.append((f"B. Liberar códigos retidos nas ligadas ({tipo.lower()}s)", v, dono))
        # C. ligar desligadas com boa efetivacao nos outros clientes
        for tipo, dono in [("Técnica", "Dr. Ary + Arvo"), ("Administrativa", "Alana + Arvo")]:
            v = sum(x["identificada"] * (1 if potencial else passagem_media) * x["media_efetivacao_clientes_arvo"]
                    for x in des if x["tipo"] == tipo and x["media_efetivacao_clientes_arvo"] >= CORTE_EFETIVACAO)
            res.append((f"C. Ligar desligadas ({tipo.lower()}s, média Arvo ≥ 50%)", v, dono))
        v = sum(x["identificada"] * (1 if potencial else passagem_media) * x["media_efetivacao_clientes_arvo"]
                for x in des if x["media_efetivacao_clientes_arvo"] < CORTE_EFETIVACAO)
        res.append(("D. Ligar as 2 de baixa efetivação (Alto Markup, terapia internação)", v, "não recomendado agora"))
        return res

    for nome, potencial in [("CONSERVADOR (perda de registro continua)", False),
                            ("POTENCIAL (perda de registro eliminada)", True)]:
        w(f"CENÁRIO {nome}: efetivado incremental por mês")
        acum = ef
        w(f"  {'Hoje':<70}{'':>16}{reais(acum)}  {pct(acum)}")
        for desc, v, dono in alavancas(potencial):
            if desc.startswith("D."):
                w(f"  {desc:<70}+{reais(v)}   (fora da soma: {dono})")
                continue
            acum += v
            w(f"  {desc:<70}+{reais(v)}  {reais(acum)}  {pct(acum)}   [{dono}]")
        w(f"  Atinge a meta de 2%? {'sim' if acum >= SINISTRO_MES * META else 'não'}. "
          f"Falta: {reais(max(0, SINISTRO_MES * META - acum))} por mês.")
        w(f"  Anualizado (x12, premissa): incremental de {reais((acum - ef) * 12)} por ano.")
        w("")

    # Ranking por inteligencia (alavancas B e C), para priorizar
    ops = []
    for x in lig:
        r = x["identificada"] - x["enviada_operadora"]
        if r > 0:
            ops.append((x["inteligencia"], x["tipo"], "retida (ligada)", r,
                        r * x["passagem"] * x["efet"], r * x["efet"], x["efet"], "real na Parthenon"))
    for x in des:
        m = x["media_efetivacao_clientes_arvo"]
        ops.append((x["inteligencia"], x["tipo"], "desligada", x["identificada"],
                    x["identificada"] * passagem_media * m, x["identificada"] * m, m, "média Arvo"))
    ops.sort(key=lambda o: -o[4])
    w("RANKING DE OPORTUNIDADE POR INTELIGÊNCIA (efetivado incremental por mês)")
    w(f"  {'inteligência':<44}{'tipo':<15}{'situação':<17}{'valor parado':>15}{'conservador':>15}{'potencial':>15}{'efetiv.':>8}")
    acum_c = 0
    for nome, tipo, sit, parado, cons, pot, efet, fonte in ops:
        acum_c += cons
        w(f"  {nome[:43]:<44}{tipo:<15}{sit:<17}{reais(parado):>17}{reais(cons):>17}{reais(pot):>17}{efet * 100:7.0f}%")
    w("")
    with open(P / "parte2" / "ranking_oportunidades.csv", "w", newline="", encoding="utf-8") as f:
        cw = csv.writer(f)
        cw.writerow(["inteligencia", "tipo", "situacao", "valor_parado_mes", "efetivado_conservador_mes",
                     "efetivado_potencial_mes", "taxa_efetivacao_usada", "fonte_da_taxa"])
        for o in ops:
            cw.writerow([o[0], o[1], o[2], round(o[3], 2), round(o[4], 2), round(o[5], 2), round(o[6], 4), o[7]])

    teto = sum(x["identificada"] * x["efet"] for x in lig) + sum(
        x["identificada"] * x["media_efetivacao_clientes_arvo"] for x in des)
    w(f"TETO TEÓRICO (todas as 26 ligadas, sem filtro, sem perda de registro): {reais(teto)}  {pct(teto)}")
    w(f"Média de efetivação usada como referência das ligadas hoje: {efet_media * 100:.1f}%;"
      f" passagem média operadora→prestador: {passagem_media * 100:.1f}%.")

    texto = "\n".join(out)
    (P / "parte2" / "resultado_funil.txt").write_text(texto + "\n", encoding="utf-8")
    print(texto)


def corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a) ** 0.5
    vb = sum((y - mb) ** 2 for y in b) ** 0.5
    return cov / (va * vb)


if __name__ == "__main__":
    main()
