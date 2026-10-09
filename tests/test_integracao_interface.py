"""Testes de integração entre os controles Qt e os algoritmos de rotas."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from algorithms.dijkstra import dijkstra
    from models.grafo import TipoVertice, Vertice, criar_cenario_exemplo
    from ui.janela_principal import JanelaPrincipal

    PYSIDE6_DISPONIVEL = True
except ModuleNotFoundError:
    PYSIDE6_DISPONIVEL = False


@unittest.skipUnless(PYSIDE6_DISPONIVEL, "PySide6 não está instalado")
class TestIntegracaoInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.aplicacao = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.janela = JanelaPrincipal()
        self.janela.show()
        self.aplicacao.processEvents()

    def tearDown(self) -> None:
        self.janela.close()
        self.janela.deleteLater()
        self.aplicacao.processEvents()

    def _configurar_dijkstra(self, origem: str, destino: str) -> None:
        self.janela.combo_algoritmo.setCurrentIndex(
            self.janela.combo_algoritmo.findData("dijkstra")
        )
        self.janela.combo_origem.setCurrentIndex(
            self.janela.combo_origem.findData(origem)
        )
        self.janela.combo_destino.setCurrentIndex(
            self.janela.combo_destino.findData(destino)
        )

    def _configurar_tsp(self) -> None:
        self.janela.combo_algoritmo.setCurrentIndex(
            self.janela.combo_algoritmo.findData("tsp")
        )

    def test_seletor_dijkstra_e_campos_reais_do_grafo(self) -> None:
        self._configurar_dijkstra("D", "B")
        self.assertEqual(self.janela.combo_origem.currentData(), "D")
        self.assertEqual(self.janela.combo_destino.currentData(), "B")
        self.assertEqual(self.janela.pilha_configuracao.currentIndex(), 0)
        self.assertIn("menor caminho", self.janela.botao_calcular.text())

    def test_executa_dijkstra_e_destaca_as_arestas(self) -> None:
        self._configurar_dijkstra("D", "B")
        self.janela.calcular_rota()

        resultado = self.janela.resultado_atual
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado.caminho, ["D", "X", "A", "B"])
        self.assertEqual(resultado.distancia_total, 6)
        esperadas = {
            frozenset(("D", "X")),
            frozenset(("X", "A")),
            frozenset(("A", "B")),
        }
        self.assertEqual(self.janela.mapa_cidade.arestas_destacadas, esperadas)
        self.assertEqual(self.janela.visualizador_grafo.arestas_destacadas, esperadas)
        self.assertIn("6 km", self.janela.painel_resultados.rotulo_metricas.text())

    def test_dijkstra_preserva_resultado_ao_alternar_visualizacao(self) -> None:
        self._configurar_dijkstra("D", "B")
        self.janela.calcular_rota()
        resultado = self.janela.resultado_atual
        rota = self.janela.mapa_cidade.rota_destacada

        self.janela.definir_modo("grafo")
        self.assertIs(self.janela.resultado_atual, resultado)
        self.assertEqual(self.janela.visualizador_grafo.rota_destacada, rota)
        self.janela.definir_modo("cidade")
        self.assertEqual(self.janela.mapa_cidade.rota_destacada, rota)

    def test_origem_igual_ao_destino_apresenta_caminho_trivial(self) -> None:
        self._configurar_dijkstra("D", "D")
        self.janela.calcular_rota()
        resultado = self.janela.resultado_atual
        self.assertEqual(resultado.caminho, ["D"])
        self.assertEqual(resultado.distancia_total, 0)
        self.assertFalse(self.janela.mapa_cidade.arestas_destacadas)

    def test_dijkstra_inalcancavel_limpa_destaques(self) -> None:
        grafo = criar_cenario_exemplo()
        grafo.adicionar_vertice(
            Vertice("I", "Cliente isolado", TipoVertice.CLIENTE, 10, 10)
        )
        self.janela.carregar_grafo(grafo)
        self._configurar_dijkstra("D", "I")
        self.janela.calcular_rota()

        resultado = self.janela.resultado_atual
        self.assertFalse(resultado.encontrado)
        self.assertFalse(self.janela.mapa_cidade.arestas_destacadas)
        self.assertIn("inalcançável", self.janela.rotulo_aviso.text())

    def test_seletor_tsp_lista_clientes_e_execucao_completa(self) -> None:
        self._configurar_tsp()
        self.assertEqual(self.janela.pilha_configuracao.currentIndex(), 1)
        self.assertEqual(self.janela.lista_clientes_rota.count(), 3)
        self.assertEqual(self.janela.clientes_selecionados(), ["A", "B", "C"])
        self.janela.calcular_rota()

        resultado = self.janela.resultado_atual
        self.assertEqual(resultado.distancia_total, 15)
        self.assertEqual(resultado.quantidade_clientes_atendidos, 3)
        self.assertEqual(resultado.sequencias_avaliadas, 6)
        self.assertEqual(resultado.ordem_entregas, ["D", "A", "B", "C", "D"])
        self.assertEqual(resultado.percurso_completo, ["D", "X", "A", "B", "C", "D"])
        self.assertIn("15 km", self.janela.painel_resultados.rotulo_metricas.text())

    def test_tsp_selecao_parcial_e_percurso_completo(self) -> None:
        self._configurar_tsp()
        self.janela.lista_clientes_rota.item(2).setCheckState(Qt.CheckState.Unchecked)
        self.janela.calcular_rota()

        resultado = self.janela.resultado_atual
        self.assertEqual(resultado.quantidade_clientes_atendidos, 2)
        self.assertEqual(resultado.sequencias_avaliadas, 2)
        self.assertNotIn("C", resultado.ordem_entregas)
        self.assertEqual(resultado.percurso_completo[0], "D")
        self.assertEqual(resultado.percurso_completo[-1], "D")

    def test_tsp_sem_clientes_retorna_rota_trivial_e_limpa_destaques(self) -> None:
        self._configurar_tsp()
        for indice in range(self.janela.lista_clientes_rota.count()):
            self.janela.lista_clientes_rota.item(indice).setCheckState(
                Qt.CheckState.Unchecked
            )
        self.janela.calcular_rota()

        resultado = self.janela.resultado_atual
        self.assertTrue(resultado.encontrada)
        self.assertEqual(resultado.ordem_entregas, ["D"])
        self.assertEqual(resultado.distancia_total, 0)
        self.assertFalse(self.janela.mapa_cidade.arestas_destacadas)

    def test_tsp_inacessivel_informa_cliente_e_remove_destaques(self) -> None:
        grafo = criar_cenario_exemplo()
        grafo.adicionar_vertice(
            Vertice("I", "Cliente isolado", TipoVertice.CLIENTE, 10, 10)
        )
        self.janela.carregar_grafo(grafo)
        self._configurar_tsp()
        self.janela.calcular_rota()

        resultado = self.janela.resultado_atual
        self.assertFalse(resultado.encontrada)
        self.assertIn("I", self.janela.rotulo_aviso.text())
        self.assertFalse(self.janela.mapa_cidade.arestas_destacadas)

    def test_limpar_rota_remove_destaques_mas_preserva_grafo(self) -> None:
        vertices = self.janela.grafo.listar_vertices()
        arestas = self.janela.grafo.listar_arestas()
        self._configurar_dijkstra("D", "B")
        self.janela.calcular_rota()
        self.janela.limpar_rota()

        self.assertIsNone(self.janela.resultado_atual)
        self.assertFalse(self.janela.mapa_cidade.arestas_destacadas)
        self.assertFalse(self.janela.visualizador_grafo.arestas_destacadas)
        self.assertEqual(self.janela.grafo.listar_vertices(), vertices)
        self.assertEqual(self.janela.grafo.listar_arestas(), arestas)

    def test_execucoes_duplicadas_sao_ignoradas_durante_calculo(self) -> None:
        self._configurar_dijkstra("D", "B")
        chamadas = 0

        def executar_e_tentar_reentrar(grafo, origem, destino):
            nonlocal chamadas
            chamadas += 1
            self.janela.calcular_rota()
            return dijkstra(grafo, origem, destino)

        with patch("ui.janela_principal.dijkstra", executar_e_tentar_reentrar):
            self.janela.calcular_rota()
        self.assertEqual(chamadas, 1)
        self.assertFalse(self.janela.calculando)

    def test_grafo_original_e_preservado_apos_tsp(self) -> None:
        vertices = self.janela.grafo.listar_vertices()
        arestas = self.janela.grafo.listar_arestas()
        deposito = self.janela.grafo.obter_deposito()
        self._configurar_tsp()
        self.janela.calcular_rota()
        self.assertEqual(self.janela.grafo.listar_vertices(), vertices)
        self.assertEqual(self.janela.grafo.listar_arestas(), arestas)
        self.assertEqual(self.janela.grafo.obter_deposito(), deposito)


if __name__ == "__main__":
    unittest.main()
