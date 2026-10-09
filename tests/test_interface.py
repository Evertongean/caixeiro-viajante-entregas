"""Testes básicos da interface em modo offscreen."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from ui.janela_principal import JanelaPrincipal

    PYSIDE6_DISPONIVEL = True
except ModuleNotFoundError:
    PYSIDE6_DISPONIVEL = False


@unittest.skipUnless(PYSIDE6_DISPONIVEL, "PySide6 não está instalado")
class TestInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.aplicacao = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.janela = JanelaPrincipal()
        self.aplicacao.processEvents()

    def tearDown(self) -> None:
        self.janela.close()
        self.janela.deleteLater()
        self.aplicacao.processEvents()

    def test_inicializa_com_cenario_de_exemplo(self) -> None:
        self.assertEqual(len(self.janela.grafo.listar_vertices()), 5)
        self.assertEqual(len(self.janela.grafo.listar_arestas()), 7)
        self.assertEqual(self.janela.lista_locais.count(), 5)
        self.assertEqual(self.janela.lista_clientes_rota.count(), 3)

    def test_carrega_nova_instancia_do_cenario_de_exemplo(self) -> None:
        grafo_anterior = self.janela.grafo
        self.janela.carregar_cenario_exemplo()
        self.assertIsNot(self.janela.grafo, grafo_anterior)
        self.assertIs(self.janela.mapa_cidade.grafo, self.janela.grafo)
        self.assertIs(self.janela.visualizador_grafo.grafo, self.janela.grafo)

    def test_alterna_entre_cidade_e_grafo(self) -> None:
        self.assertEqual(self.janela.modo_atual, "cidade")
        self.janela.definir_modo("grafo")
        self.assertEqual(self.janela.modo_atual, "grafo")
        self.assertIs(
            self.janela.pilha_visualizacoes.currentWidget(),
            self.janela.visualizador_grafo,
        )
        self.janela.definir_modo("cidade")
        self.assertIs(
            self.janela.pilha_visualizacoes.currentWidget(),
            self.janela.mapa_cidade,
        )

    def test_alternancia_preserva_grafo_e_selecao(self) -> None:
        grafo = self.janela.grafo
        arestas = self.janela.grafo.listar_arestas()
        self.janela.selecionar_vertice("A")
        self.janela.definir_modo("grafo")

        self.assertIs(self.janela.grafo, grafo)
        self.assertEqual(self.janela.grafo.listar_arestas(), arestas)
        self.assertEqual(self.janela.vertice_selecionado, "A")
        self.assertEqual(self.janela.mapa_cidade.selecionado_id, "A")
        self.assertEqual(self.janela.visualizador_grafo.selecionado_id, "A")

    def test_selecao_atualiza_painel_de_detalhes(self) -> None:
        self.janela.selecionar_vertice("D")
        detalhes = self.janela.rotulo_detalhes.text()
        self.assertIn("Depósito Central", detalhes)
        self.assertIn("Identificador: D", detalhes)
        self.assertIn("Cruzamento", detalhes)
        self.assertIn("2 km", detalhes)

    def test_clique_em_vertice_dispara_selecao(self) -> None:
        visualizacao = self.janela.mapa_cidade
        item = visualizacao._itens_vertices["A"]
        posicao = visualizacao.mapFromScene(item.scenePos())

        QTest.mouseClick(
            visualizacao.viewport(),
            Qt.MouseButton.LeftButton,
            pos=posicao,
        )
        self.aplicacao.processEvents()

        self.assertEqual(self.janela.vertice_selecionado, "A")
        self.assertIn("Cliente A", self.janela.rotulo_detalhes.text())


if __name__ == "__main__":
    unittest.main()
