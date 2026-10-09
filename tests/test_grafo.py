"""Testes unitários da estrutura de grafo."""

import unittest

from models.grafo import Aresta, Grafo, TipoVertice, Vertice, criar_cenario_exemplo


class TestGrafo(unittest.TestCase):
    def setUp(self) -> None:
        self.grafo = criar_cenario_exemplo()

    def test_cadastra_vertices(self) -> None:
        self.assertEqual(len(self.grafo.listar_vertices()), 5)
        self.assertEqual(self.grafo.obter_vertice("A").nome, "Cliente A")

    def test_cria_conexoes_sem_duplica_las_na_listagem(self) -> None:
        self.assertEqual(len(self.grafo.listar_arestas()), 7)
        self.assertTrue(self.grafo.existe_aresta("D", "X"))
        self.assertFalse(self.grafo.existe_aresta("D", "A"))

    def test_arestas_sao_simetricas(self) -> None:
        self.assertEqual(self.grafo.obter_vizinhos("D")["X"], 2)
        self.assertEqual(self.grafo.obter_vizinhos("X")["D"], 2)

    def test_consulta_pesos(self) -> None:
        self.assertEqual(self.grafo.obter_distancia("A", "B"), 3)
        self.assertEqual(self.grafo.obter_distancia("B", "A"), 3)
        with self.assertRaisesRegex(ValueError, "Não existe aresta"):
            self.grafo.obter_distancia("D", "A")

    def test_remove_aresta_nos_dois_sentidos(self) -> None:
        self.grafo.remover_aresta("A", "B")
        self.assertFalse(self.grafo.existe_aresta("A", "B"))
        self.assertFalse(self.grafo.existe_aresta("B", "A"))

    def test_remove_vertice_e_suas_conexoes(self) -> None:
        removido = self.grafo.remover_vertice("X")
        self.assertEqual(removido.identificador, "X")
        self.assertNotIn("X", self.grafo.obter_vizinhos("D"))
        self.assertNotIn("X", self.grafo.obter_vizinhos("A"))
        self.assertNotIn("X", self.grafo.obter_vizinhos("B"))
        with self.assertRaises(KeyError):
            self.grafo.obter_vertice("X")

    def test_remover_deposito_limpa_definicao(self) -> None:
        self.grafo.remover_vertice("D")
        self.assertIsNone(self.grafo.obter_deposito())

    def test_atualiza_peso_simetricamente(self) -> None:
        self.grafo.atualizar_peso_aresta("X", "B", 4.5)
        self.assertEqual(self.grafo.obter_distancia("X", "B"), 4.5)
        self.assertEqual(self.grafo.obter_distancia("B", "X"), 4.5)

    def test_rejeita_identificador_duplicado(self) -> None:
        duplicado = Vertice("A", "Outro", TipoVertice.CLIENTE, 0, 0)
        with self.assertRaisesRegex(ValueError, "Já existe um vértice"):
            self.grafo.adicionar_vertice(duplicado)

    def test_atualiza_vertice_preservando_suas_conexoes(self) -> None:
        atualizado = self.grafo.atualizar_vertice(
            "X",
            nome="Novo cruzamento",
            tipo=TipoVertice.CRUZAMENTO,
            x=8,
            y=9,
        )
        self.assertEqual(atualizado.nome, "Novo cruzamento")
        self.assertEqual(self.grafo.obter_vizinhos("D")["X"], 2)
        self.assertEqual(self.grafo.obter_vertice("X").x, 8)

    def test_rejeita_nomes_duplicados_e_segundo_deposito(self) -> None:
        with self.assertRaisesRegex(ValueError, "nome"):
            self.grafo.adicionar_vertice(
                Vertice("Z", "Cliente A", TipoVertice.CLIENTE, 1, 1)
            )
        with self.assertRaisesRegex(ValueError, "no máximo um depósito"):
            self.grafo.adicionar_vertice(
                Vertice("D2", "Outro depósito", TipoVertice.DEPOSITO, 1, 1)
            )

    def test_rejeita_pesos_invalidos(self) -> None:
        for peso in (0, -1, float("inf"), float("nan"), True):
            with self.subTest(peso=peso):
                with self.assertRaisesRegex(ValueError, "peso da aresta"):
                    self.grafo.adicionar_aresta("D", "A", peso)

        with self.assertRaisesRegex(ValueError, "peso da aresta"):
            self.grafo.atualizar_peso_aresta("D", "X", 0)

    def test_aresta_tambem_protege_suas_invariantes(self) -> None:
        origem = self.grafo.obter_vertice("A")
        destino = self.grafo.obter_vertice("B")
        with self.assertRaisesRegex(ValueError, "peso da aresta"):
            Aresta(origem, destino, -1)
        with self.assertRaisesRegex(ValueError, "a ele mesmo"):
            Aresta(origem, origem, 1)

    def test_rejeita_laco(self) -> None:
        with self.assertRaisesRegex(ValueError, "a ele mesmo"):
            self.grafo.adicionar_aresta("A", "A", 1)

    def test_rejeita_aresta_duplicada_inclusive_invertida(self) -> None:
        with self.assertRaisesRegex(ValueError, "já existe"):
            self.grafo.adicionar_aresta("X", "D", 2)

    def test_rejeita_operacoes_com_vertice_inexistente(self) -> None:
        with self.assertRaisesRegex(KeyError, "Não existe vértice"):
            self.grafo.adicionar_aresta("A", "Z", 1)
        with self.assertRaisesRegex(KeyError, "Não existe vértice"):
            self.grafo.remover_vertice("Z")

    def test_rejeita_remocao_e_atualizacao_de_aresta_inexistente(self) -> None:
        with self.assertRaisesRegex(ValueError, "Não existe aresta"):
            self.grafo.remover_aresta("D", "A")
        with self.assertRaisesRegex(ValueError, "Não existe aresta"):
            self.grafo.atualizar_peso_aresta("D", "A", 2)

    def test_identifica_clientes_e_deposito(self) -> None:
        deposito = self.grafo.obter_deposito()
        self.assertIsNotNone(deposito)
        self.assertEqual(deposito.identificador, "D")  # type: ignore[union-attr]
        self.assertEqual(
            {cliente.identificador for cliente in self.grafo.listar_clientes()},
            {"A", "B", "C"},
        )

    def test_grafo_vazio_nao_tem_deposito(self) -> None:
        self.assertIsNone(Grafo().obter_deposito())

    def test_deposito_precisa_ter_tipo_correto(self) -> None:
        with self.assertRaisesRegex(ValueError, "não possui o tipo depósito"):
            self.grafo.definir_deposito("A")

    def test_nao_permite_dois_depositos_principais(self) -> None:
        outro = Vertice("D2", "Depósito 2", TipoVertice.DEPOSITO, 9, 9)
        with self.assertRaisesRegex(ValueError, "no máximo um depósito"):
            self.grafo.adicionar_vertice(outro)


if __name__ == "__main__":
    unittest.main()
