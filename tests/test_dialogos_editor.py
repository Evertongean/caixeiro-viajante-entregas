"""Regressões dos contratos entre os QComboBox e as enums do domínio."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLabel, QPushButton

    from models.grafo import TipoVertice
    from models.projeto_cidade import ClassificacaoSuperficie
    from ui.dialogos_editor import (
        DialogoRua,
        DialogoSuperficie,
        DialogoVertice,
    )

    PYSIDE6_DISPONIVEL = True
except ModuleNotFoundError:
    PYSIDE6_DISPONIVEL = False


@unittest.skipUnless(PYSIDE6_DISPONIVEL, "PySide6 não está instalado")
class TestDialogosEditor(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.aplicacao = QApplication.instance() or QApplication([])

    def test_opcoes_amigaveis_retornam_enum_de_classificacao(self) -> None:
        dialogo = DialogoSuperficie(
            "wh_plane_0|gray", ClassificacaoSuperficie.NAO_CLASSIFICADA
        )
        esperadas = (
            ("Rua trafegável", ClassificacaoSuperficie.RUA),
            ("Calçada", ClassificacaoSuperficie.CALCADA),
            ("Área bloqueada / edifício", ClassificacaoSuperficie.BLOQUEADA),
            ("Ainda não classificada", ClassificacaoSuperficie.NAO_CLASSIFICADA),
        )
        for indice, (texto, classificacao) in enumerate(esperadas):
            with self.subTest(classificacao=classificacao):
                dialogo.classificacao.setCurrentIndex(indice)
                self.assertEqual(dialogo.classificacao.currentText(), texto)
                self.assertIs(dialogo.valor(), classificacao)
                self.assertIsInstance(dialogo.valor(), ClassificacaoSuperficie)

    def test_qt_armazena_string_mas_dialogo_reconstroi_enum(self) -> None:
        dialogo = DialogoSuperficie(
            "wh_plane_0|gray", ClassificacaoSuperficie.RUA
        )
        dado_qt = dialogo.classificacao.currentData(Qt.ItemDataRole.UserRole)
        self.assertEqual(dado_qt, "rua")
        self.assertIs(type(dado_qt), str)
        self.assertIs(dialogo.valor(), ClassificacaoSuperficie.RUA)

    def test_classificacao_invalida_e_rejeitada_explicitamente(self) -> None:
        dialogo = DialogoSuperficie(
            "wh_plane_0|gray", ClassificacaoSuperficie.RUA
        )
        dialogo.classificacao.setItemData(0, "valor-invalido")
        with self.assertRaisesRegex(ValueError, "classificação selecionada"):
            dialogo.valor()

    def test_dialogo_de_vertice_tambem_reconstroi_tipo_enum(self) -> None:
        dialogo = DialogoVertice(
            tipo_sugerido=TipoVertice.CLIENTE,
            identificador_sugerido="C9",
        )
        dialogo.nome.setText("Cliente 9")
        identificador, nome, tipo = dialogo.dados()
        self.assertEqual((identificador, nome), ("C9", "Cliente 9"))
        self.assertIs(tipo, TipoVertice.CLIENTE)

    def test_dialogo_rua_mostra_apenas_conexao_distancia_e_acoes(self) -> None:
        dialogo = DialogoRua("A", "B")
        textos = [rotulo.text() for rotulo in dialogo.findChildren(QLabel)]
        botoes = [botao.text() for botao in dialogo.findChildren(QPushButton)]
        self.assertIn("A ↔ B", textos)
        self.assertIn("Distância da rua (km)", textos)
        self.assertEqual(len(dialogo.findChildren(QDoubleSpinBox)), 1)
        self.assertEqual(dialogo.peso.decimals(), 1)
        self.assertEqual(set(botoes), {"Salvar", "Cancelar"})
        conteudo = " ".join(textos + botoes).lower()
        self.assertNotIn("sugest", conteudo)
        self.assertNotIn("escala", conteudo)
        self.assertNotIn("fator", conteudo)

    def test_distancia_manual_aceita_virgula_e_salva_valor_exibido(self) -> None:
        for entrada, esperado in (("1,5", 1.5), ("2,8", 2.8)):
            with self.subTest(entrada=entrada):
                dialogo = DialogoRua("A", "B")
                campo = dialogo.peso.lineEdit()
                campo.selectAll()
                QTest.keyClicks(campo, entrada)
                dialogo.peso.interpretText()
                self.assertEqual(dialogo.dados(), esperado)
                self.assertEqual(dialogo.peso.text(), f"{entrada} km")

    def test_peso_antigo_preciso_so_muda_com_acao_explicita(self) -> None:
        dialogo = DialogoRua("A", "B", peso_atual=2.345678901)
        self.assertEqual(dialogo.peso.text(), "2,3 km")
        self.assertEqual(dialogo.dados(), 2.345678901)
        dialogo.peso.setValue(2.8)
        self.assertEqual(dialogo.dados(), 2.8)

    def test_peso_antigo_pequeno_pode_ser_preservado_sem_salvar_zero(self) -> None:
        dialogo = DialogoRua("A", "B", peso_atual=0.04)
        self.assertEqual(dialogo.peso.text(), "0,0 km")
        dialogo.botao_salvar.click()
        self.assertEqual(dialogo.result(), dialogo.DialogCode.Accepted)
        self.assertEqual(dialogo.dados(), 0.04)

    def test_distancia_invalida_nao_aceita_o_dialogo(self) -> None:
        for entrada in ("texto inválido", "0", "-1,0"):
            with self.subTest(entrada=entrada):
                dialogo = DialogoRua("A", "B")
                dialogo.peso.lineEdit().setText(entrada)
                dialogo.botao_salvar.click()
                self.assertNotEqual(dialogo.result(), dialogo.DialogCode.Accepted)
                self.assertTrue(dialogo.erro_distancia.text())

    def test_rua_nova_exige_distancia_positiva(self) -> None:
        dialogo = DialogoRua("A", "B")
        self.assertEqual(dialogo.peso.text(), "0,0 km")
        dialogo.botao_salvar.click()
        self.assertNotEqual(dialogo.result(), dialogo.DialogCode.Accepted)
        self.assertIn("0,1 km", dialogo.erro_distancia.text())


if __name__ == "__main__":
    unittest.main()
