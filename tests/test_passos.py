"""Testes dos históricos estruturados usados pelo modo didático."""

from __future__ import annotations

import unittest

from algorithms.caixeiro_viajante import caixeiro_viajante
from algorithms.dijkstra import dijkstra
from models.grafo import TipoVertice, Vertice, criar_cenario_exemplo
from ui.execucao_passos import SessaoPassoAPasso


class TestHistoricosPassoAPasso(unittest.TestCase):
    def test_dijkstra_mantem_resultado_e_explica_relaxamentos(self) -> None:
        grafo = criar_cenario_exemplo()
        normal = dijkstra(grafo, "D", "B")
        passo = SessaoPassoAPasso.criar_dijkstra(grafo, "D", "B")

        self.assertEqual(passo.resultado.caminho, normal.caminho)
        self.assertEqual(passo.resultado.distancia_total, normal.distancia_total)
        self.assertEqual(passo.passos[0].numero, 1)
        self.assertIn("Inicialização", passo.passos[0].descricao)
        self.assertTrue(any("Relaxamento" in estado.descricao for estado in passo.passos))
        self.assertEqual(passo.passos[-1].caminho_final, tuple(normal.caminho))

    def test_dijkstra_inacessivel_nao_inventa_caminho(self) -> None:
        grafo = criar_cenario_exemplo()
        grafo.adicionar_vertice(Vertice("I", "Isolado", TipoVertice.CLIENTE, 10, 10))
        sessao = SessaoPassoAPasso.criar_dijkstra(grafo, "D", "I")
        self.assertFalse(sessao.resultado.encontrado)
        self.assertEqual(sessao.passos[-1].caminho_final, ())
        self.assertIn("inalcançável", sessao.passos[-1].descricao)

    def test_tsp_registra_candidatas_e_melhor_solucao(self) -> None:
        grafo = criar_cenario_exemplo()
        normal = caixeiro_viajante(grafo)
        com_historico = caixeiro_viajante(grafo, registrar_etapas=True)

        avaliacoes = [etapa for etapa in com_historico.etapas if etapa.fase == "avaliacao"]
        self.assertEqual(len(avaliacoes), normal.sequencias_avaliadas)
        self.assertEqual(com_historico.ordem_entregas, normal.ordem_entregas)
        self.assertEqual(com_historico.distancia_total, normal.distancia_total)
        self.assertEqual(com_historico.etapas[-1].melhor_distancia, 15)
        self.assertTrue(any("Nova melhor" in etapa.descricao for etapa in avaliacoes))

    def test_sessao_navega_e_detecta_alteracao_externa(self) -> None:
        grafo = criar_cenario_exemplo()
        sessao = SessaoPassoAPasso.criar_dijkstra(grafo, "D", "B")
        primeiro = sessao.passo_atual
        sessao.ir_para_ultimo()
        self.assertTrue(sessao.finalizada)
        sessao.retroceder()
        self.assertIsNot(sessao.passo_atual, primeiro)
        grafo.remover_aresta("D", "X")
        self.assertTrue(sessao.grafo_foi_alterado(grafo))


if __name__ == "__main__":
    unittest.main()
