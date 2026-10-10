"""Testes da integração entre algoritmos, geometria espacial e apresentação 3D."""

from __future__ import annotations

import unittest

from algorithms.caixeiro_viajante import LIMITE_PADRAO_CLIENTES
from models.grafo import Grafo, TipoVertice, Vertice, criar_cenario_exemplo
from models.projeto_cidade import GeometriaRua, ProjetoCidade
from models.rota import (
    AlgoritmoRota,
    EstadoEspacial,
    RotaInacessivel,
    calcular_dijkstra,
    calcular_tsp,
)
from ui.apresentacao_rota import (
    marcadores_rota_qml,
    pontos_para_enquadrar,
    segmentos_rota_qml,
)


class TestRotaIntegrada(unittest.TestCase):
    def setUp(self) -> None:
        self.projeto = ProjetoCidade(grafo=criar_cenario_exemplo())
        self.projeto.posicoes = {
            "D": (0.0, 0.0, 0.0),
            "X": (1.0, 0.0, 0.0),
            "A": (2.0, 0.0, 0.0),
            "B": (3.0, 0.0, 1.0),
            "C": (1.0, 0.0, 2.0),
        }

    def configurar_rua(
        self,
        origem: str,
        destino: str,
        *curvas: tuple[float, float, float],
        confirmada: bool = True,
    ) -> None:
        chave = self.projeto.chave_aresta(origem, destino)
        self.projeto.ruas[chave] = GeometriaRua(
            origem,
            destino,
            list(curvas),
            confirmada,
        )

    def configurar_percurso_demonstracao(self) -> None:
        self.configurar_rua("D", "X", (0.5, 0.0, -0.2))
        self.configurar_rua("X", "A", (1.5, 0.0, 0.2))
        self.configurar_rua("A", "B", (2.4, 0.0, 0.3))
        self.configurar_rua("B", "C", (2.2, 0.0, 1.6))
        self.configurar_rua("C", "D", (0.2, 0.0, 1.0))

    def test_dijkstra_prepara_resultado_e_segmentos_com_curvas(self) -> None:
        self.configurar_percurso_demonstracao()
        rota = calcular_dijkstra(self.projeto, "D", "B")
        self.assertEqual(rota.algoritmo, AlgoritmoRota.DIJKSTRA)
        self.assertEqual(rota.percurso_completo, ("D", "X", "A", "B"))
        self.assertEqual(rota.distancia_total, 6)
        self.assertEqual(rota.estado_espacial, EstadoEspacial.COMPLETO)
        self.assertEqual(len(rota.segmentos_espaciais), 3)
        self.assertEqual(
            rota.segmentos_espaciais[0].pontos,
            ((0.0, 0.0, 0.0), (0.5, 0.0, -0.2), (1.0, 0.0, 0.0)),
        )
        self.assertEqual(len(segmentos_rota_qml(rota)), 6)

    def test_tsp_mantem_ordem_de_atendimento_separada_do_percurso(self) -> None:
        self.configurar_percurso_demonstracao()
        rota = calcular_tsp(self.projeto, ["A", "B", "C"])
        self.assertEqual(rota.algoritmo, AlgoritmoRota.TSP)
        self.assertEqual(rota.ordem_atendimento, ("D", "A", "B", "C", "D"))
        self.assertEqual(
            rota.percurso_completo, ("D", "X", "A", "B", "C", "D")
        )
        self.assertEqual(rota.distancia_total, 15)
        self.assertEqual(rota.clientes_selecionados, ("A", "B", "C"))
        self.assertTrue(rota.calibracao_completa)

    def test_inverte_a_polilinha_quando_percorre_aresta_ao_contrario(self) -> None:
        self.configurar_rua("D", "X", (0.4, 0.0, 0.1))
        rota = calcular_dijkstra(self.projeto, "X", "D")
        self.assertEqual(
            rota.segmentos_espaciais[0].pontos,
            ((1.0, 0.0, 0.0), (0.4, 0.0, 0.1), (0.0, 0.0, 0.0)),
        )

    def test_rua_sem_geometria_fica_pendente_e_nao_vira_reta(self) -> None:
        rota = calcular_dijkstra(self.projeto, "D", "B")
        self.assertEqual(rota.estado_espacial, EstadoEspacial.INDISPONIVEL)
        self.assertEqual(
            rota.arestas_pendentes,
            (("D", "X"), ("X", "A"), ("A", "B")),
        )
        self.assertEqual(segmentos_rota_qml(rota), [])

    def test_geometria_nao_confirmada_e_laranja_e_permanece_pendente(self) -> None:
        self.configurar_rua("D", "X", (0.5, 0.0, 0.1), confirmada=False)
        rota = calcular_dijkstra(self.projeto, "D", "X")
        segmentos = segmentos_rota_qml(rota)
        self.assertEqual(rota.estado_espacial, EstadoEspacial.PARCIAL)
        self.assertTrue(all(segmento["cor"] == "#F59E0B" for segmento in segmentos))
        self.assertTrue(all(not segmento["confirmado"] for segmento in segmentos))

    def test_fita_da_rota_fica_proxima_ao_pavimento(self) -> None:
        self.configurar_rua("D", "X", (0.5, 0.0, 0.1))
        rota = calcular_dijkstra(self.projeto, "D", "X")
        segmentos = segmentos_rota_qml(rota)

        self.assertTrue(segmentos)
        self.assertTrue(
            all(segmento["ay"] == 0.004 for segmento in segmentos)
        )
        self.assertTrue(
            all(segmento["by"] == 0.004 for segmento in segmentos)
        )

    def test_tsp_preserva_repeticao_real_da_mesma_rua(self) -> None:
        grafo = Grafo()
        grafo.adicionar_vertice(Vertice("D", "Base", TipoVertice.DEPOSITO, 0, 0))
        grafo.adicionar_vertice(Vertice("C", "Cliente", TipoVertice.CLIENTE, 1, 0))
        grafo.adicionar_aresta("D", "C", 2)
        projeto = ProjetoCidade(
            grafo=grafo,
            posicoes={"D": (0, 0, 0), "C": (1, 0, 0)},
            ruas={
                ("C", "D"): GeometriaRua("D", "C", [], True),
            },
        )
        rota = calcular_tsp(projeto, ["C"])
        self.assertEqual(rota.percurso_completo, ("D", "C", "D"))
        self.assertEqual(len(rota.segmentos_espaciais), 2)
        segmentos = segmentos_rota_qml(rota)
        self.assertEqual([item["sequencia"] for item in segmentos], [0, 1])

    def test_marcadores_destacam_inicio_fim_e_clientes(self) -> None:
        self.configurar_percurso_demonstracao()
        rota = calcular_tsp(self.projeto, ["A", "B", "C"])
        marcadores = marcadores_rota_qml(rota, self.projeto)
        por_id = {item["id"]: item for item in marcadores}
        self.assertIn("INÍCIO", por_id["D"]["texto"])
        self.assertIn("FIM", por_id["D"]["texto"])
        self.assertEqual(por_id["A"]["texto"], "ENTREGA 1")
        self.assertGreaterEqual(len(pontos_para_enquadrar(rota, self.projeto)), 5)

    def test_apresentacao_da_missao_distingue_trecho_e_entrega(self) -> None:
        self.configurar_percurso_demonstracao()
        rota = calcular_tsp(self.projeto, ["A", "B", "C"])
        segmentos = segmentos_rota_qml(rota, 2)
        estados = {
            item["sequencia"]: item["estado"] for item in segmentos
        }
        self.assertEqual(estados[0], "percorrido")
        self.assertEqual(estados[2], "atual")
        self.assertEqual(estados[4], "restante")
        marcadores = marcadores_rota_qml(
            rota, self.projeto, {"A"}, "B"
        )
        por_id = {item["id"]: item for item in marcadores}
        self.assertIn("OK", por_id["A"]["texto"])
        self.assertIn("PRÓXIMA", por_id["B"]["texto"])

    def test_destino_inacessivel_e_grafo_desconectado(self) -> None:
        self.projeto.grafo.remover_aresta("B", "C")
        self.projeto.grafo.remover_aresta("C", "D")
        self.projeto.grafo.remover_aresta("A", "C")
        with self.assertRaisesRegex(RotaInacessivel, "inacessível"):
            calcular_dijkstra(self.projeto, "D", "C")
        with self.assertRaisesRegex(RotaInacessivel, "clientes inacessíveis"):
            calcular_tsp(self.projeto, ["C"])

    def test_tsp_rejeita_ausencia_deposito_e_limite(self) -> None:
        sem_deposito = ProjetoCidade(grafo=Grafo())
        sem_deposito.grafo.adicionar_vertice(
            Vertice("C", "Cliente", TipoVertice.CLIENTE, 0, 0)
        )
        with self.assertRaisesRegex(ValueError, "não possui um depósito"):
            calcular_tsp(sem_deposito, ["C"])

        grafo = Grafo()
        grafo.adicionar_vertice(Vertice("D", "Base", TipoVertice.DEPOSITO, 0, 0))
        clientes = []
        for indice in range(LIMITE_PADRAO_CLIENTES + 1):
            identificador = f"C{indice}"
            clientes.append(identificador)
            grafo.adicionar_vertice(
                Vertice(identificador, identificador, TipoVertice.CLIENTE, indice, 0)
            )
        with self.assertRaisesRegex(ValueError, "limite de 8"):
            calcular_tsp(ProjetoCidade(grafo=grafo), clientes)

    def test_selecao_vazia_do_tsp_retorna_rota_trivial(self) -> None:
        rota = calcular_tsp(self.projeto, [])
        self.assertEqual(rota.ordem_atendimento, ("D",))
        self.assertEqual(rota.percurso_completo, ("D",))
        self.assertEqual(rota.distancia_total, 0)
        self.assertEqual(rota.estado_espacial, EstadoEspacial.COMPLETO)


if __name__ == "__main__":
    unittest.main()
