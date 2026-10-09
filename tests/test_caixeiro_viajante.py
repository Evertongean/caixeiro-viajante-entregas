"""Testes unitários da solução exata do Caixeiro Viajante."""

import math
import unittest

from algorithms.caixeiro_viajante import caixeiro_viajante
from algorithms.dijkstra import dijkstra
from models.grafo import Grafo, TipoVertice, Vertice, criar_cenario_exemplo


class TestCaixeiroViajante(unittest.TestCase):
    def setUp(self) -> None:
        self.grafo = criar_cenario_exemplo()

    def test_encontra_rota_otima_do_cenario_principal(self) -> None:
        resultado = caixeiro_viajante(self.grafo)

        self.assertTrue(resultado.encontrada)
        self.assertEqual(resultado.distancia_total, 15)
        self.assertIn(
            resultado.ordem_entregas,
            (["D", "A", "B", "C", "D"], ["D", "C", "B", "A", "D"]),
        )
        self.assertEqual(resultado.ordem_entregas[0], "D")
        self.assertEqual(resultado.ordem_entregas[-1], "D")
        self.assertEqual(resultado.sequencias_avaliadas, 6)
        self.assertEqual(resultado.quantidade_clientes_atendidos, 3)

    def test_visita_todos_os_clientes_exatamente_na_ordem_de_atendimento(self) -> None:
        resultado = caixeiro_viajante(self.grafo)
        self.assertEqual(set(resultado.ordem_entregas[1:-1]), {"A", "B", "C"})
        self.assertEqual(len(resultado.ordem_entregas[1:-1]), 3)

    def test_distingue_ordem_de_entregas_do_percurso_completo(self) -> None:
        resultado = caixeiro_viajante(self.grafo)

        self.assertNotEqual(resultado.ordem_entregas, resultado.percurso_completo)
        self.assertIn("X", resultado.percurso_completo)
        self.assertNotIn("X", resultado.ordem_entregas)
        self.assertEqual(resultado.percurso_completo[0], "D")
        self.assertEqual(resultado.percurso_completo[-1], "D")

    def test_distancia_e_soma_das_arestas_do_percurso(self) -> None:
        resultado = caixeiro_viajante(self.grafo)
        soma = sum(
            self.grafo.obter_distancia(origem, destino)
            for origem, destino in zip(
                resultado.percurso_completo,
                resultado.percurso_completo[1:],
            )
        )
        self.assertEqual(soma, resultado.distancia_total)
        self.assertEqual(
            sum(segmento.distancia for segmento in resultado.segmentos),
            resultado.distancia_total,
        )

    def test_segmentos_sao_caminhos_reais_compativeis_com_dijkstra(self) -> None:
        resultado = caixeiro_viajante(self.grafo)
        for segmento in resultado.segmentos:
            esperado = dijkstra(self.grafo, segmento.origem, segmento.destino)
            self.assertEqual(segmento.caminho, esperado.caminho)
            self.assertEqual(segmento.distancia, esperado.distancia_total)

    def test_rota_com_apenas_um_cliente(self) -> None:
        resultado = caixeiro_viajante(self.grafo, ["A"])

        self.assertEqual(resultado.ordem_entregas, ["D", "A", "D"])
        self.assertEqual(resultado.percurso_completo, ["D", "X", "A", "X", "D"])
        self.assertEqual(resultado.distancia_total, 6)
        self.assertEqual(resultado.sequencias_avaliadas, 1)
        self.assertEqual(resultado.quantidade_clientes_atendidos, 1)

    def test_selecao_vazia_e_rota_trivial(self) -> None:
        resultado = caixeiro_viajante(self.grafo, [])

        self.assertTrue(resultado.encontrada)
        self.assertEqual(resultado.ordem_entregas, ["D"])
        self.assertEqual(resultado.percurso_completo, ["D"])
        self.assertEqual(resultado.distancia_total, 0)
        self.assertEqual(resultado.sequencias_avaliadas, 1)
        self.assertEqual(resultado.quantidade_clientes_atendidos, 0)

    def test_grafo_sem_clientes_tambem_gera_rota_trivial(self) -> None:
        grafo = Grafo()
        grafo.adicionar_vertice(
            Vertice("D", "Depósito", TipoVertice.DEPOSITO, 0, 0)
        )
        grafo.definir_deposito("D")
        self.assertEqual(caixeiro_viajante(grafo).percurso_completo, ["D"])

    def test_cliente_desconectado_impede_rota_viavel(self) -> None:
        self.grafo.adicionar_vertice(
            Vertice("I", "Cliente isolado", TipoVertice.CLIENTE, 10, 10)
        )
        resultado = caixeiro_viajante(self.grafo)

        self.assertFalse(resultado.encontrada)
        self.assertEqual(resultado.ordem_entregas, [])
        self.assertEqual(resultado.percurso_completo, [])
        self.assertTrue(math.isinf(resultado.distancia_total))
        self.assertEqual(resultado.clientes_inacessiveis, ("I",))
        self.assertEqual(resultado.sequencias_avaliadas, 0)

    def test_selecao_parcial_considera_so_entregas_escolhidas(self) -> None:
        resultado = caixeiro_viajante(self.grafo, ["B", "A"])

        self.assertTrue(resultado.encontrada)
        self.assertEqual(set(resultado.ordem_entregas[1:-1]), {"A", "B"})
        self.assertNotIn("C", resultado.ordem_entregas)
        self.assertEqual(resultado.quantidade_clientes_atendidos, 2)
        self.assertEqual(resultado.sequencias_avaliadas, 2)

    def test_rejeita_clientes_inexistentes_duplicados_ou_de_tipo_incorreto(self) -> None:
        with self.assertRaisesRegex(KeyError, "Não existe vértice"):
            caixeiro_viajante(self.grafo, ["Z"])
        with self.assertRaisesRegex(ValueError, "duplicados"):
            caixeiro_viajante(self.grafo, ["A", "A"])
        with self.assertRaisesRegex(ValueError, "não possui o tipo cliente"):
            caixeiro_viajante(self.grafo, ["X"])
        with self.assertRaisesRegex(TypeError, "identificadores dos clientes"):
            caixeiro_viajante(self.grafo, [1])  # type: ignore[list-item]

    def test_rejeita_excesso_de_clientes_antes_do_calculo(self) -> None:
        grafo = Grafo()
        grafo.adicionar_vertice(
            Vertice("D", "Depósito", TipoVertice.DEPOSITO, 0, 0)
        )
        grafo.definir_deposito("D")
        for numero in range(9):
            grafo.adicionar_vertice(
                Vertice(
                    f"C{numero}",
                    f"Cliente {numero}",
                    TipoVertice.CLIENTE,
                    numero,
                    numero,
                )
            )

        with self.assertRaisesRegex(ValueError, "limite de 8 clientes"):
            caixeiro_viajante(grafo)

    def test_limite_de_clientes_e_configuravel(self) -> None:
        with self.assertRaisesRegex(ValueError, "limite de 2 clientes"):
            caixeiro_viajante(self.grafo, limite_clientes=2)
        self.assertTrue(
            caixeiro_viajante(self.grafo, limite_clientes=3).encontrada
        )

    def test_empate_tem_resultado_deterministico(self) -> None:
        grafo = Grafo()
        for identificador, tipo in (
            ("D", TipoVertice.DEPOSITO),
            ("A", TipoVertice.CLIENTE),
            ("B", TipoVertice.CLIENTE),
        ):
            grafo.adicionar_vertice(Vertice(identificador, identificador, tipo, 0, 0))
        grafo.definir_deposito("D")
        grafo.adicionar_aresta("D", "A", 1)
        grafo.adicionar_aresta("D", "B", 1)
        grafo.adicionar_aresta("A", "B", 1)

        primeira = caixeiro_viajante(grafo, ["B", "A"])
        segunda = caixeiro_viajante(grafo, {"A", "B"})

        self.assertEqual(primeira.ordem_entregas, ["D", "A", "B", "D"])
        self.assertEqual(segunda.ordem_entregas, primeira.ordem_entregas)

    def test_exige_deposito_principal(self) -> None:
        grafo = Grafo()
        grafo.adicionar_vertice(
            Vertice("A", "Cliente", TipoVertice.CLIENTE, 0, 0)
        )
        with self.assertRaisesRegex(ValueError, "não possui um depósito"):
            caixeiro_viajante(grafo)

    def test_nao_modifica_o_grafo(self) -> None:
        vertices_antes = self.grafo.listar_vertices()
        arestas_antes = self.grafo.listar_arestas()
        deposito_antes = self.grafo.obter_deposito()
        vizinhos_antes = {
            vertice.identificador: self.grafo.obter_vizinhos(vertice.identificador)
            for vertice in vertices_antes
        }

        caixeiro_viajante(self.grafo)

        self.assertEqual(self.grafo.listar_vertices(), vertices_antes)
        self.assertEqual(self.grafo.listar_arestas(), arestas_antes)
        self.assertEqual(self.grafo.obter_deposito(), deposito_antes)
        for identificador, vizinhos in vizinhos_antes.items():
            self.assertEqual(self.grafo.obter_vizinhos(identificador), vizinhos)


if __name__ == "__main__":
    unittest.main()
