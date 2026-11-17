"""Opcional. Converte a planilha da Parte 2 em CSV (dados/inteligencias_6_meses.csv).
Ja rodei uma vez e o CSV esta no repositorio. Requer: pip install openpyxl"""
import csv
from pathlib import Path
import openpyxl
P = Path(__file__).resolve().parent.parent
ws = openpyxl.load_workbook(P / "dados" / "Inteligencias_apos_6_meses.xlsx", data_only=True).active
linhas = list(ws.iter_rows(values_only=True))
print("Sinistro processado:", linhas[0][1], "| Mes:", linhas[1][1])
cab = ["inteligencia", "tipo", "status", "identificada", "enviada_operadora", "enviada_prestador", "efetivada", "media_efetivacao_clientes_arvo"]
with open(P / "dados" / "inteligencias_6_meses.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(cab)
    for l in linhas[4:]:
        if l[0] and l[0] != "Total":
            w.writerow([l[0], l[1], l[2], l[3], l[4], l[5], l[6], l[8]])
        if l[0] == "Total":
            print("Linha Total da planilha:", l[3:9])
