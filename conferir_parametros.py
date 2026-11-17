"""
Confere se cada codigo e valor do arquivo de parametros aparece no contrato.

A tabela do Anexo I foi transcrita a mao para o JSON. Este script compara a
transcricao com o texto extraido do PDF (dados/contrato_texto.txt), para pegar
erro de digitacao. O texto foi extraido uma vez com pdfplumber
(ver extrair_texto_contrato.py); a conferencia em si nao precisa de nada instalado.
"""

import json
import re
import sys
from decimal import Decimal
from pathlib import Path

PASTA = Path(__file__).resolve().parent


def brl(valor):
    """Decimal('4200.00') -> '4.200,00'"""
    inteiro, centavos = f"{Decimal(valor):.2f}".split(".")
    inteiro = f"{int(inteiro):,}".replace(",", ".")
    return f"{inteiro},{centavos}"


def conferir(caminho_json=PASTA / "parametros" / "hospital_sao_rafael.json",
             caminho_texto=PASTA / "dados" / "contrato_texto.txt"):
    p = json.loads(Path(caminho_json).read_text(encoding="utf-8"))
    texto = re.sub(r"\s+", "", Path(caminho_texto).read_text(encoding="utf-8"))
    erros = []

    anexo1 = texto[texto.find("ANEXOI-TABELA"):texto.find("ANEXOII")]
    for t in p["tabela_precos"]["itens"]:
        esperado = t["cod_tuss"] + ".{0,80}?R\\$" + re.escape(brl(t["valor"]))
        if not re.search(esperado, anexo1):
            erros.append(f"Anexo I: código {t['cod_tuss']} com valor R$ {brl(t['valor'])} não encontrado no contrato")

    anexo2 = texto[texto.find("ANEXOII"):]
    for pk in p["pacotes"]["itens"]:
        pos = anexo2.find(pk["cod_procedimento"])
        janela = anexo2[max(0, pos - 80):pos + 80] if pos >= 0 else ""
        for cod in [pk["cod_procedimento"], pk["taxa_sala_inclusa"], *pk["materiais_inclusos"]]:
            if cod not in janela:
                erros.append(f"Anexo II: código {cod} não encontrado junto ao pacote {pk['cod_procedimento']}")

    if p["taxa_urgencia"]["cod_tuss"] not in texto[texto.find("CLÁUSULAQUARTA"):texto.find("CLÁUSULAQUINTA")]:
        erros.append("Cláusula 4: código da taxa de urgência não encontrado")

    n = len(p["tabela_precos"]["itens"])
    if erros:
        print("\n".join(erros))
        return False
    print(f"Parâmetros conferidos com o contrato: {n} preços do Anexo I, "
          f"{len(p['pacotes']['itens'])} pacotes do Anexo II e o código da taxa de urgência.")
    return True


if __name__ == "__main__":
    sys.exit(0 if conferir() else 1)
