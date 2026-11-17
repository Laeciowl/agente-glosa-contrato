"""
Testes com casos pequenos e inventados. Cada teste prova que o agente sabe a
diferenca entre o que o contrato manda glosar e o que ele permite cobrar.

Rodar: python3 testes.py
"""

import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

import agente

PAR = agente.carregar_parametros(Path(__file__).resolve().parent / "parametros" / "hospital_sao_rafael.json")


def item(id_item, conta, cod, valor, qtd=1, carater="Eletivo", tipo_conta="Internação", data=date(2025, 6, 10)):
    v, q = Decimal(str(valor)), Decimal(qtd)
    return {"id_item": id_item, "id_conta": conta, "cod_tuss": cod, "desc_item": cod,
            "carater_atendimento": carater, "tipo_conta": tipo_conta, "qtd": q,
            "vl_unitario": v, "vl_total": v * q, "data": data}


def rodar(*itens):
    apont, rev = agente.auditar(list(itens), PAR)
    return {a["id_item"]: a for a in apont}, {r["id_item"]: r for r in rev}


class TaxaDeSala(unittest.TestCase):
    def test_taxa_de_sala_sem_pacote_na_conta_nao_e_glosada(self):
        g, r = rodar(item("A", "C1", "20103050", 600))
        self.assertEqual(g, {})
        self.assertEqual(r, {})

    def test_taxa_de_sala_do_porte_do_pacote_e_glosada_inteira(self):
        g, _ = rodar(item("P", "C1", "31309062", 3000), item("A", "C1", "20103050", 600))
        self.assertEqual(g["A"]["regra"], "R2_PACOTE")
        self.assertEqual(g["A"]["vl_glosado"], Decimal("600"))

    def test_taxa_de_sala_de_outro_porte_vai_para_revisao(self):
        # Herniorrafia inclui porte 2. Porte 4 na mesma conta: o contrato nao define.
        g, r = rodar(item("P", "C1", "31309062", 3000), item("A", "C1", "20103077", 1200))
        self.assertNotIn("A", g)
        self.assertIn("A", r)

    def test_pacote_em_outra_conta_nao_contamina(self):
        g, _ = rodar(item("P", "C1", "31001012", 4000), item("A", "C2", "20103077", 1200))
        self.assertNotIn("A", g)

    def test_conta_com_dois_pacotes_glosa_as_duas_taxas(self):
        g, _ = rodar(item("P1", "C1", "31001012", 4000), item("P2", "C1", "31309062", 3000),
                     item("A", "C1", "20103077", 1200), item("B", "C1", "20103050", 600))
        self.assertEqual({g["A"]["regra"], g["B"]["regra"]}, {"R2_PACOTE"})


class MateriaisDeRotina(unittest.TestCase):
    def test_fio_sem_pacote_na_conta_nao_e_glosado(self):
        g, _ = rodar(item("A", "C1", "70520020", 44, qtd=3))
        self.assertEqual(g, {})

    def test_fio_e_compressa_com_pacote_sao_glosados_inteiros(self):
        g, _ = rodar(item("P", "C1", "30715016", 3700), item("A", "C1", "70520020", 44, qtd=3),
                     item("B", "C1", "70402600", 8.5, qtd=4))
        self.assertEqual(g["A"]["vl_glosado"], Decimal("132"))
        self.assertEqual(g["B"]["vl_glosado"], Decimal("34.0"))

    def test_glosa_integral_vence_excedente_sem_contar_duas_vezes(self):
        g, _ = rodar(item("P", "C1", "30715016", 3700), item("A", "C1", "70520020", 50, qtd=2))
        self.assertEqual(g["A"]["regra"], "R2_PACOTE")
        self.assertEqual(g["A"]["vl_glosado"], Decimal("100"))

    def test_cateter_em_conta_de_pacote_nao_e_glosado(self):
        # Clausula 3.4: materiais especiais nao integram o pacote.
        g, _ = rodar(item("P", "C1", "30715016", 3700), item("A", "C1", "70451938", 270))
        self.assertNotIn("A", g)


class TaxaDeUrgencia(unittest.TestCase):
    def test_urgencia_em_atendimento_de_urgencia_nao_e_glosada(self):
        g, _ = rodar(item("A", "C1", "99999001", 350, carater="Urgência"))
        self.assertEqual(g, {})

    def test_urgencia_em_urgencia_acima_da_tabela_glosa_so_o_excedente(self):
        g, _ = rodar(item("A", "C1", "99999001", 360, carater="Urgência"))
        self.assertEqual(g["A"]["regra"], "R1_PRECO")
        self.assertEqual(g["A"]["vl_glosado"], Decimal("10.00"))

    def test_urgencia_em_eletivo_e_glosada_inteira(self):
        g, _ = rodar(item("A", "C1", "99999001", 340))
        self.assertEqual(g["A"]["regra"], "R3_URGENCIA_ELETIVO")
        self.assertEqual(g["A"]["vl_glosado"], Decimal("340"))
        self.assertEqual(g["A"]["alerta_recurso"], "")

    def test_urgencia_em_eletivo_no_pronto_socorro_sai_com_alerta(self):
        g, _ = rodar(item("A", "C1", "99999001", 340, tipo_conta="Pronto Socorro"))
        self.assertEqual(g["A"]["regra"], "R3_URGENCIA_ELETIVO")
        self.assertNotEqual(g["A"]["alerta_recurso"], "")

    def test_carater_desconhecido_vai_para_revisao(self):
        g, r = rodar(item("A", "C1", "99999001", 340, carater=""))
        self.assertNotIn("A", g)
        self.assertIn("A", r)


class Preco(unittest.TestCase):
    def test_preco_abaixo_ou_igual_a_tabela_nao_e_glosado(self):
        g, _ = rodar(item("A", "C1", "60012010", 480), item("B", "C1", "60012010", 470))
        self.assertEqual(g, {})

    def test_preco_acima_glosa_excedente_vezes_quantidade(self):
        g, _ = rodar(item("A", "C1", "40304361", 20.50, qtd=3))
        self.assertEqual(g["A"]["regra"], "R1_PRECO")
        self.assertEqual(g["A"]["vl_glosado"], Decimal("7.50"))

    def test_procedimento_de_pacote_acima_da_tabela(self):
        g, _ = rodar(item("A", "C1", "31001012", 5000))
        self.assertEqual(g["A"]["regra"], "R1_PRECO_PACOTE")
        self.assertEqual(g["A"]["vl_glosado"], Decimal("800.00"))

    def test_item_fora_do_anexo_i_vai_para_revisao(self):
        g, r = rodar(item("A", "C1", "12345678", 999))
        self.assertNotIn("A", g)
        self.assertIn("A", r)

    def test_tolerancia_configuravel(self):
        par = dict(PAR, tolerancia=Decimal("1.00"))
        apont, _ = agente.auditar([item("A", "C1", "40304361", 18.50)], par)
        self.assertEqual(apont, [])


class Vigencia(unittest.TestCase):
    def test_fora_da_vigencia_vai_para_revisao(self):
        g, r = rodar(item("A", "C1", "40304361", 30, data=date(2024, 12, 31)))
        self.assertNotIn("A", g)
        self.assertIn("A", r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
