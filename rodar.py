"""
Roda tudo, na ordem, com um comando:

    python3 rodar.py

1. Confere os parametros (tabela e pacotes) contra o texto do contrato.
2. Roda os testes de casos de borda.
3. Roda o agente sobre o sinistro e grava os apontamentos.
4. Roda as mesmas regras em SQL e confere se bate com o Python.
5. Compara com o gabarito do auditor (precisao e recall).

Se qualquer conferencia falhar, para e avisa.
"""

import sys
import unittest

import agente
import conferir_parametros
import cruzar_sql
import testes
import validar


def etapa(n, titulo):
    print(f"\n{'=' * 70}\n{n}. {titulo}\n{'=' * 70}")


def main():
    etapa(1, "Conferir parâmetros contra o contrato")
    if not conferir_parametros.conferir():
        sys.exit("Parâmetros não batem com o contrato. Corrija o JSON antes de seguir.")

    etapa(2, "Testes de casos de borda")
    res = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromModule(testes))
    if not res.wasSuccessful():
        sys.exit("Algum teste falhou.")

    etapa(3, "Agente: aplicar as regras do contrato ao sinistro")
    sys.argv = sys.argv[:1]
    agente.main()

    etapa(4, "Conferência dupla: mesmas regras em SQL")
    if not cruzar_sql.cruzar():
        sys.exit("Python e SQL não batem.")

    etapa(5, "Validação contra o gabarito do auditor")
    validar.main()

    print("\nTudo conferido. Resultados em saida/:")
    print("  apontamentos.csv           itens glosados, cláusula e valor")
    print("  revisao_humana.csv         itens que o agente não decide sozinho")
    print("  resumo_glosa.txt           totais por regra")
    print("  metricas_validacao.txt     precisão e recall contra o gabarito")
    print("  divergencias_gabarito.csv  cada divergência com o diagnóstico")


if __name__ == "__main__":
    main()
