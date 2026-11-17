"""
Opcional. Extrai o texto do PDF do contrato para dados/contrato_texto.txt.
Ja rodei uma vez e o resultado esta no repositorio. So precisa rodar de novo
se o PDF mudar. Requer: pip install pdfplumber
"""

from pathlib import Path

import pdfplumber

PASTA = Path(__file__).resolve().parent

with pdfplumber.open(PASTA / "dados" / "Contrato-parthenon-x-hospital-sao-rafael.pdf") as pdf:
    texto = "\n\n=== PAGINA ===\n".join((pg.extract_text() or "") for pg in pdf.pages)
(PASTA / "dados" / "contrato_texto.txt").write_text(texto, encoding="utf-8")
print("Texto extraído para dados/contrato_texto.txt")
