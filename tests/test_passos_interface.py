"""Testes offscreen dos controles e destaques passo a passo."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from ui.janela_principal import JanelaPrincipal

    PYSIDE6_DISPONIVEL = True
except ModuleNotFoundError:
    PYSIDE6_DISPONIVEL = False


@unittest.skipUnless(PYSIDE6_DISPONIVEL, "PySide6 não está instalado")
class TestPassosInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.aplicacao = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.janela = JanelaPrincipal()
        self.janela.show()
        self.aplicacao.processEvents()
        self.janela.combo_origem.setCurrentIndex(
            self.janela.combo_origem.findData("D")
        )
        self.janela.combo_destino.setCurrentIndex(
            self.janela.combo_destino.findData("B")
        )

    def tearDown(self) -> None:
        self.janela._grafo_modificado = False
        self.janela.close()
        self.janela.deleteLater()
        self.aplicacao.processEvents()

    def test_dijkstra_avanca_regride_sincroniza_views_e_conclui(self) -> None:
        self.janela.iniciar_passo_a_passo()
        sessao = self.janela.sessao_passos
        self.assertIsNotNone(sessao)
        self.assertEqual(self.janela.painel_passos.rotulo_progresso.text(), "Etapa 1 de 6")
        self.assertEqual(
            self.janela.mapa_cidade.arestas_passo_destacadas,
            self.janela.visualizador_grafo.arestas_passo_destacadas,
        )

        self.janela.avancar_passo()
        self.assertEqual(sessao.indice_atual, 1)
        self.assertTrue(self.janela.mapa_cidade.vertices_passo_processados)
        self.janela.retroceder_passo()
        self.assertEqual(sessao.indice_atual, 0)
        self.janela.ir_para_ultimo_passo()
        self.assertEqual(self.janela.resultado_atual.caminho, ["D", "X", "A", "B"])
        self.assertTrue(self.janela.mapa_cidade.arestas_passo_destacadas)

    def test_tsp_mostra_avaliacoes_e_resultado_final(self) -> None:
        self.janela.combo_algoritmo.setCurrentIndex(
            self.janela.combo_algoritmo.findData("tsp")
        )
        self.janela.iniciar_passo_a_passo()
        sessao = self.janela.sessao_passos
        self.assertEqual(sessao.total, 8)
        self.janela.ir_para_ultimo_passo()
        self.assertEqual(self.janela.resultado_atual.distancia_total, 15)
        self.assertIn("Conclusão", self.janela.painel_passos.rotulo_descricao.text())

    def test_encerrar_limpa_destaques_e_bloqueia_edicao_durante_sessao(self) -> None:
        self.janela.iniciar_passo_a_passo()
        self.assertFalse(self.janela.botao_adicionar_vertice.isEnabled())
        with self.assertRaisesRegex(RuntimeError, "passo a passo"):
            self.janela.adicionar_aresta("D", "B", 1)
        self.janela.encerrar_passo_a_passo(preservar_resultado=False)
        self.assertFalse(self.janela.passo_a_passo_ativo)
        self.assertFalse(self.janela.mapa_cidade.arestas_passo_destacadas)
        self.assertFalse(self.janela.visualizador_grafo.arestas_passo_destacadas)
        self.assertTrue(self.janela.botao_adicionar_vertice.isEnabled() is False)

    def test_sessao_bloqueia_editor_ja_ativo(self) -> None:
        self.janela.definir_modo_interface("edicao")
        self.assertTrue(self.janela.botao_adicionar_vertice.isEnabled())
        self.janela.definir_modo_interface("visualizacao")
        self.janela.iniciar_passo_a_passo()
        self.janela.definir_modo_interface("edicao")
        self.assertEqual(self.janela.modo_interface, "visualizacao")
        self.assertFalse(self.janela.botao_adicionar_vertice.isEnabled())

    def test_carregar_novo_grafo_encerra_sessao(self) -> None:
        self.janela.iniciar_passo_a_passo()
        self.janela.carregar_cenario_exemplo()
        self.assertFalse(self.janela.passo_a_passo_ativo)
        self.assertEqual(self.janela.painel_passos.rotulo_progresso.text(), "Nenhuma sessão ativa")


if __name__ == "__main__":
    unittest.main()
