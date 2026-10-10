"""Regressões dos contratos entre os QComboBox e as enums do domínio."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from models.grafo import TipoVertice
    from models.projeto_cidade import ClassificacaoSuperficie
    from ui.dialogos_editor import DialogoSuperficie, DialogoVertice

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


if __name__ == "__main__":
    unittest.main()
