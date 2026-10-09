"""Testes unitários do algoritmo de Dijkstra."""

import math
import unittest

from algorithms.dijkstra import dijkstra, dijkstra_todos
from models.grafo import Grafo, TipoVertice, Vertice, criar_cenario_exemplo


class TestDijkstra(unittest.TestCase):
    def setUp(self) -> None:
        self.grafo = criar_cenario_exemplo()

    def test_menor_caminho_de_d_para_b(self) -> None:
        resultado = dijkstra(self.grafo, "D", "B")
        self.assertTrue(resultado.encontrado)
        self.assertEqual(resultado.caminho, ["D", "X", "A", "B"])
        self.assertEqual(resultado.distancia_total, 6)

    def test_menor_caminho_de_d_para_a(self) -> None:
        resultado = dijkstra(self.grafo, "D", "A")
        self.assertEqual(resultado.caminho, ["D", "X", "A"])
        self.assertEqual(resultado.distancia_total, 3)

    def test_menor_caminho_de_a_para_c(self) -> None:
        resultado = dijkstra(self.grafo, "A", "C")
        self.assertEqual(resultado.caminho, ["A", "B", "C"])
        self.assertEqual(resultado.distancia_total, 5)

    def test_menor_caminho_de_d_para_c_e_aresta_direta(self) -> None:
        resultado = dijkstra(self.grafo, "D", "C")
        self.assertEqual(resultado.caminho, ["D", "C"])
        self.assertEqual(resultado.distancia_total, 7)

    def test_origem_igual_ao_destino(self) -> None:
        resultado = dijkstra(self.grafo, "A", "A")
        self.assertTrue(resultado.encontrado)
        self.assertEqual(resultado.caminho, ["A"])
        self.assertEqual(resultado.distancia_total, 0)

    def test_rejeita_origem_ou_destino_inexistente(self) -> None:
        with self.assertRaisesRegex(KeyError, "Não existe vértice"):
            dijkstra(self.grafo, "Z", "A")
        with self.assertRaisesRegex(KeyError, "Não existe vértice"):
            dijkstra(self.grafo, "A", "Z")
        with self.assertRaisesRegex(KeyError, "Não existe vértice"):
            dijkstra_todos(self.grafo, "Z")

    def test_grafo_com_apenas_um_vertice(self) -> None:
        grafo = Grafo()
        grafo.adicionar_vertice(
            Vertice("U", "Único", TipoVertice.CRUZAMENTO, 0, 0)
        )
        resultado = dijkstra(grafo, "U", "U")
        self.assertEqual(resultado.caminho, ["U"])
        self.assertEqual(resultado.distancia_total, 0)

    def test_destino_inalcancavel_em_grafo_desconectado(self) -> None:
        isolado = Vertice("I", "Isolado", TipoVertice.CLIENTE, 10, 10)
        self.grafo.adicionar_vertice(isolado)

        resultado = dijkstra(self.grafo, "D", "I")

        self.assertFalse(resultado.encontrado)
        self.assertEqual(resultado.caminho, [])
        self.assertTrue(math.isinf(resultado.distancia_total))

    def test_escolhe_o_menor_entre_multiplos_caminhos(self) -> None:
        grafo = Grafo()
        for identificador in ("A", "B", "C", "D"):
            grafo.adicionar_vertice(
                Vertice(
                    identificador,
                    identificador,
                    TipoVertice.CRUZAMENTO,
                    0,
                    0,
                )
            )
        grafo.adicionar_aresta("A", "D", 10)
        grafo.adicionar_aresta("A", "B", 2)
        grafo.adicionar_aresta("B", "C", 2)
        grafo.adicionar_aresta("C", "D", 2)

        resultado = dijkstra(grafo, "A", "D")

        self.assertEqual(resultado.caminho, ["A", "B", "C", "D"])
        self.assertEqual(resultado.distancia_total, 6)

    def test_calcula_caminhos_para_todos_os_vertices(self) -> None:
        resultado = dijkstra_todos(self.grafo, "D")

        self.assertEqual(
            resultado.distancias,
            {"D": 0, "X": 2, "A": 3, "B": 6, "C": 7},
        )
        self.assertEqual(resultado.reconstruir_caminho("B"), ["D", "X", "A", "B"])
        self.assertEqual(resultado.resultado_para("A").distancia_total, 3)

    def test_calculo_completo_marca_inalcancaveis_com_infinito(self) -> None:
        self.grafo.adicionar_vertice(
            Vertice("I", "Isolado", TipoVertice.CLIENTE, 10, 10)
        )
        resultado = dijkstra_todos(self.grafo, "D")

        self.assertTrue(math.isinf(resultado.distancias["I"]))
        self.assertEqual(resultado.reconstruir_caminho("I"), [])
        self.assertFalse(resultado.resultado_para("I").encontrado)

    def test_registro_de_etapas_e_opcional_e_estruturado(self) -> None:
        sem_historico = dijkstra(self.grafo, "D", "B")
        com_historico = dijkstra(
            self.grafo, "D", "B", registrar_etapas=True
        )

        self.assertEqual(sem_historico.etapas, ())
        self.assertGreater(len(com_historico.etapas), 0)
        primeira = com_historico.etapas[0]
        self.assertEqual(primeira.vertice_atual, "D")
        self.assertEqual(primeira.distancias["X"], 2)
        self.assertIn("D", primeira.vertices_processados)
        self.assertEqual(primeira.predecessores["X"], "D")
        self.assertEqual(
            {(aresta.origem, aresta.destino) for aresta in primeira.arestas_analisadas},
            {("D", "X"), ("D", "C")},
        )
        self.assertEqual(
            {atualizacao.vertice for atualizacao in primeira.atualizacoes},
            {"X", "C"},
        )

    def test_historico_guarda_fotografias_independentes(self) -> None:
        resultado = dijkstra(
            self.grafo, "D", "B", registrar_etapas=True
        )
        self.assertTrue(math.isinf(resultado.etapas[0].distancias["A"]))
        self.assertEqual(resultado.etapas[-1].distancias["A"], 3)

    def test_algoritmo_nao_modifica_o_grafo(self) -> None:
        vertices_antes = self.grafo.listar_vertices()
        arestas_antes = self.grafo.listar_arestas()
        deposito_antes = self.grafo.obter_deposito()
        vizinhos_antes = {
            vertice.identificador: self.grafo.obter_vizinhos(vertice.identificador)
            for vertice in vertices_antes
        }

        dijkstra(self.grafo, "D", "B", registrar_etapas=True)
        dijkstra_todos(self.grafo, "A")

        self.assertEqual(self.grafo.listar_vertices(), vertices_antes)
        self.assertEqual(self.grafo.listar_arestas(), arestas_antes)
        self.assertEqual(self.grafo.obter_deposito(), deposito_antes)
        for identificador, vizinhos in vizinhos_antes.items():
            self.assertEqual(self.grafo.obter_vizinhos(identificador), vizinhos)

    def test_rejeita_objeto_que_nao_seja_grafo(self) -> None:
        with self.assertRaisesRegex(TypeError, "instância de Grafo"):
            dijkstra(None, "A", "B")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
