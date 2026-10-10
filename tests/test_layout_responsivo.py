"""Verificações geométricas do layout em resoluções de demonstração."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtWidgets import QApplication, QScrollArea

    from ui.estilos import ESTILO_APLICACAO
    from ui.janela_principal import JanelaPrincipal

    PYSIDE6_DISPONIVEL = True
except ModuleNotFoundError:
    PYSIDE6_DISPONIVEL = False


@unittest.skipUnless(PYSIDE6_DISPONIVEL, "PySide6 não está instalado")
class TestLayoutResponsivo(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.aplicacao = QApplication.instance() or QApplication([])
        cls.aplicacao.setStyleSheet(ESTILO_APLICACAO)

    def setUp(self) -> None:
        self.janela = JanelaPrincipal()
        self.janela.show()
        self.aplicacao.processEvents()

    def tearDown(self) -> None:
        self.janela.close()
        self.janela.deleteLater()
        self.aplicacao.processEvents()

    def _componentes_layout(self):
        raiz = self.janela.centralWidget()
        conteudo = raiz.layout().itemAt(2).widget()
        divisor = conteudo.layout().itemAt(0).widget()
        resultados = conteudo.layout().itemAt(1).widget()
        return divisor, resultados

    def _verificar_resolucao(self, largura: int, altura: int) -> None:
        self.janela.resize(largura, altura)
        self.aplicacao.processEvents()
        self.assertEqual(self.janela.size().width(), largura)
        self.assertEqual(self.janela.size().height(), altura)

        divisor, resultados = self._componentes_layout()
        esquerdo, central, direito = (divisor.widget(indice) for indice in range(3))
        self.assertGreater(esquerdo.width(), 0)
        self.assertGreater(central.width(), 0)
        self.assertGreater(direito.width(), 0)

        # O QSplitter reserva os pequenos intervalos dos próprios handles;
        # nenhum painel pode atravessar o handle seguinte.
        handle_esquerdo = divisor.handle(1).geometry()
        handle_direito = divisor.handle(2).geometry()
        self.assertLessEqual(
            esquerdo.x() + esquerdo.width(),
            handle_esquerdo.x() + handle_esquerdo.width(),
        )
        self.assertGreaterEqual(central.x(), handle_esquerdo.x())
        self.assertLessEqual(
            central.x() + central.width(),
            handle_direito.x() + handle_direito.width(),
        )
        self.assertGreaterEqual(direito.x(), handle_direito.x())

        self.assertGreater(resultados.width(), 0)
        self.assertTrue(self.janela.botao_calcular.isVisible())
        self.assertTrue(self.janela.painel_passos.isVisible())

        rolagem = direito.findChild(QScrollArea)
        self.assertIsNotNone(rolagem)
        self.assertFalse(rolagem.horizontalScrollBar().isVisible())
        self.assertEqual(rolagem.widget().width(), rolagem.viewport().width())

        # O conteúdo vertical pode exceder a altura, mas o painel de passos
        # continua alcançável pela rolagem.
        rolagem.ensureWidgetVisible(self.janela.painel_passos)
        self.aplicacao.processEvents()
        viewport_global = QRect(
            rolagem.viewport().mapToGlobal(QPoint(0, 0)),
            rolagem.viewport().size(),
        )
        botao_global = QRect(
            self.janela.painel_passos.botao_iniciar.mapToGlobal(QPoint(0, 0)),
            self.janela.painel_passos.botao_iniciar.size(),
        )
        self.assertTrue(viewport_global.intersects(botao_global))

    def test_resolucoes_de_demonstracao(self) -> None:
        for resolucao in ((1300, 800), (960, 640), (800, 600)):
            with self.subTest(resolucao=resolucao):
                self._verificar_resolucao(*resolucao)

    def test_alternar_visualizacao_preserva_as_larguras(self) -> None:
        self.janela.resize(800, 600)
        self.janela.show()
        self.aplicacao.processEvents()
        divisor, _ = self._componentes_layout()
        larguras = [divisor.widget(indice).width() for indice in range(3)]

        self.janela.definir_modo("grafo")
        self.aplicacao.processEvents()
        self.assertEqual(
            [divisor.widget(indice).width() for indice in range(3)], larguras
        )
        self.janela.definir_modo("cidade")
        self.aplicacao.processEvents()
        self.assertEqual(
            [divisor.widget(indice).width() for indice in range(3)], larguras
        )


if __name__ == "__main__":
    unittest.main()
