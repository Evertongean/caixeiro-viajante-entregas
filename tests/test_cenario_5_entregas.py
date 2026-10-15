"""Regressão do cenário acadêmico com depósito e cinco entregas."""

from __future__ import annotations

import unittest
from pathlib import Path

from models.missao import ControladorMissao, EstadoMissao
from models.projeto_cidade import carregar_projeto_cidade, projeto_para_dados
from models.rota import calcular_dijkstra, calcular_tsp
from scripts.criar_cenario_5_entregas import criar_cenario
from scripts.validar_cenario_5_entregas import CLIENTES, validar


RAIZ = Path(__file__).parents[1]
CENARIO = RAIZ / "delivery-route-5-entregas.json"
ORIGEM = RAIZ / "delivery-route1.json"


class TestCenarioCincoEntregas(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.projeto = carregar_projeto_cidade(CENARIO)

    def test_arquivo_e_reproducivel_exclusivamente_a_partir_da_origem(self) -> None:
        gerado = criar_cenario(ORIGEM)
        self.assertEqual(projeto_para_dados(gerado), projeto_para_dados(self.projeto))

    def test_validacao_completa_do_cenario(self) -> None:
        relatorio = validar(CENARIO, ORIGEM)
        self.assertEqual(relatorio["depositos"], 1)
        self.assertEqual(relatorio["clientes"], 5)
        self.assertEqual(relatorio["cruzamentos"], 19)
        self.assertEqual(relatorio["ruas"], 32)
        self.assertEqual(relatorio["ruas_confirmadas"], 32)
        self.assertEqual(relatorio["ruas_pendentes"], 0)
        self.assertTrue(relatorio["persistencia_sem_perda"])
        self.assertTrue(relatorio["proveniencia_integral"])

    def test_dijkstra_alcanca_os_cinco_clientes_com_geometria_confirmada(self) -> None:
        for cliente in CLIENTES:
            with self.subTest(cliente=cliente):
                rota = calcular_dijkstra(self.projeto, "D", cliente)
                self.assertEqual(rota.percurso_completo[0], "D")
                self.assertEqual(rota.percurso_completo[-1], cliente)
                self.assertGreater(rota.distancia_total, 0)
                self.assertTrue(rota.calibracao_completa)
                self.assertEqual(rota.arestas_pendentes, ())

    def test_tsp_exato_visita_cinco_clientes_e_retorna_ao_deposito(self) -> None:
        rota = calcular_tsp(self.projeto, CLIENTES)
        self.assertEqual(
            rota.ordem_atendimento,
            ("D", "A", "C", "B", "F", "E", "D"),
        )
        self.assertAlmostEqual(rota.distancia_total, 8.802905)
        self.assertEqual(set(rota.ordem_atendimento[1:-1]), set(CLIENTES))
        self.assertTrue(rota.calibracao_completa)
        self.assertEqual(rota.arestas_pendentes, ())

    def test_missao_conclui_cinco_entregas_e_retorna_ao_deposito(self) -> None:
        rota = calcular_tsp(self.projeto, CLIENTES)
        missao = ControladorMissao(
            rota,
            velocidade_base=10.0,
            tempo_parada_entrega=0.0,
            velocidade_rotacao=720.0,
        )
        quadro = missao.iniciar()
        for _ in range(10_000):
            if quadro.estado is EstadoMissao.CONCLUIDA:
                break
            quadro = missao.avancar(0.02)
        self.assertEqual(quadro.estado, EstadoMissao.CONCLUIDA)
        self.assertEqual(set(quadro.clientes_atendidos), set(CLIENTES))
        self.assertEqual(quadro.posicao, self.projeto.posicoes["D"])

    def test_polilinha_inverte_sem_criar_geometria_paralela(self) -> None:
        for aresta in self.projeto.grafo.listar_arestas():
            origem = aresta.origem.identificador
            destino = aresta.destino.identificador
            with self.subTest(rua=f"{origem}-{destino}"):
                direta = self.projeto.polilinha_rua(origem, destino)
                inversa = self.projeto.polilinha_rua(destino, origem)
                self.assertEqual(direta, tuple(reversed(inversa)))


if __name__ == "__main__":
    unittest.main()
