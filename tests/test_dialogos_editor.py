"""Regressões dos contratos entre os QComboBox e as enums do domínio."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLabel

    from models.grafo import TipoVertice
    from models.projeto_cidade import ClassificacaoSuperficie
    from ui.dialogos_editor import (
        DialogoEscalaCenario,
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

    def test_dialogo_rua_mostra_sugestao_em_km_e_um_unico_campo(self) -> None:
        dialogo = DialogoRua("A", "B", 0.875, escala_validada=True)
        textos = [rotulo.text() for rotulo in dialogo.findChildren(QLabel)]
        self.assertIn("A ↔ B", textos)
        self.assertEqual(dialogo.sugestao.text(), "0,875000 km")
        self.assertAlmostEqual(dialogo.dados(), 0.875)
        self.assertEqual(len(dialogo.findChildren(QDoubleSpinBox)), 1)
        self.assertFalse(any("Fator" in texto for texto in textos))
        self.assertFalse(any("Peso oficial" in texto for texto in textos))

    def test_usar_sugestao_substitui_valor_manual(self) -> None:
        dialogo = DialogoRua("A", "B", 0.5, peso_atual=3.75)
        self.assertAlmostEqual(dialogo.dados(), 3.75)
        dialogo.botao_usar_sugestao.click()
        self.assertAlmostEqual(dialogo.dados(), 0.5)

    def test_distancia_manual_aceita_decimal_com_precisao(self) -> None:
        dialogo = DialogoRua("A", "B", 1.0)
        dialogo.peso.setValue(0.123456789)
        self.assertAlmostEqual(dialogo.dados(), 0.123456789, places=9)
        self.assertIn(",", dialogo.peso.text())

    def test_distancia_invalida_nao_aceita_o_dialogo(self) -> None:
        dialogo = DialogoRua("A", "B", 1.0)
        dialogo.peso.lineEdit().setText("texto inválido")
        dialogo.botao_salvar.click()
        self.assertNotEqual(dialogo.result(), dialogo.DialogCode.Accepted)
        self.assertIn("numérica válida", dialogo.erro_distancia.text())

        dialogo.peso.lineEdit().setText("0")
        dialogo.botao_salvar.click()
        self.assertNotEqual(dialogo.result(), dialogo.DialogCode.Accepted)

    def test_escala_nao_validada_identifica_sugestao_como_estimativa(self) -> None:
        dialogo = DialogoRua("A", "B", 1.0, escala_validada=False)
        textos = " ".join(
            rotulo.text() for rotulo in dialogo.findChildren(QLabel)
        )
        self.assertIn("Estimativa baseada na escala geral", textos)

    def test_configuracao_geral_da_escala_e_separada(self) -> None:
        dialogo = DialogoEscalaCenario(0.25, False)
        dialogo.escala.setValue(0.5)
        dialogo.validada.setChecked(True)
        self.assertEqual(dialogo.dados(), (0.5, True))


if __name__ == "__main__":
    unittest.main()
