"""Testes da vaga inicial com a geometria real da cidade e do carro."""

from __future__ import annotations

import unittest
from math import hypot
from pathlib import Path

from models.estacionamento import (
    DimensoesVeiculo,
    pontos_ocupacao_veiculo,
    resolver_estacionamento,
    validar_estacionamento,
)
from models.grafo import Grafo, TipoVertice, Vertice
from models.missao import ControladorMissao, EstadoMissao
from models.projeto_cidade import ProjetoCidade, carregar_projeto_cidade
from models.rota import calcular_dijkstra, calcular_tsp
from ui.assets_3d import (
    ESCALA_CARRO_PADRAO,
    ESCALA_CIDADE_PADRAO,
    caminho_modelo,
    extrair_mapa_superficies,
    inspecionar_modelo,
)


RAIZ = Path(__file__).resolve().parents[1]
ORIGINAL = RAIZ / "delivery-route-cidade-completa.json"
CORRIGIDO = RAIZ / "delivery-route-cidade-completa-corrigida.json"


def dimensoes_carro() -> DimensoesVeiculo:
    limites = inspecionar_modelo(caminho_modelo("carro.glb")).limites
    return DimensoesVeiculo(
        largura=limites.dimensoes[0] * ESCALA_CARRO_PADRAO,
        altura=limites.dimensoes[1] * ESCALA_CARRO_PADRAO,
        comprimento=limites.dimensoes[2] * ESCALA_CARRO_PADRAO,
    )


class TestEstacionamentoCidadeCompleta(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.projeto = carregar_projeto_cidade(CORRIGIDO)
        cls.dimensoes = dimensoes_carro()
        cls.mapa = extrair_mapa_superficies(
            caminho_modelo("cidade.glb"),
            cls.projeto.superficies,
            escala=ESCALA_CIDADE_PADRAO,
        )

    def test_associa_vaga_ao_deposito_sem_mover_vertice_logico(self) -> None:
        estacionamento = self.projeto.estacionamento_inicial
        self.assertIsNotNone(estacionamento)
        self.assertEqual(estacionamento.deposito, "D")
        self.assertEqual(
            self.projeto.posicoes["D"],
            (-0.55, -0.006227047208837454, 0.065),
        )
        self.assertLessEqual(
            abs(estacionamento.posicao[0] - self.projeto.posicoes["D"][0]),
            0.25,
        )

    def test_carroceria_inteira_fica_sobre_superficie_rua(self) -> None:
        estacionamento = self.projeto.estacionamento_inicial
        validacao = validar_estacionamento(
            estacionamento, self.mapa, self.dimensoes
        )
        self.assertTrue(validacao.valido, validacao.motivo)
        self.assertEqual(validacao.superficie, "wh_plane_0|plane")
        self.assertGreater(len(pontos_ocupacao_veiculo(
            estacionamento.posicao,
            estacionamento.orientacao_graus,
            self.dimensoes,
        )), 4)

    def test_altura_e_orientacao_correspondem_ao_pavimento_e_a_rua(self) -> None:
        estacionamento = self.projeto.estacionamento_inicial
        amostra = self.mapa.amostrar(
            estacionamento.posicao[0], estacionamento.posicao[2]
        )
        self.assertAlmostEqual(estacionamento.posicao[1], amostra.altura, places=8)
        self.assertIn(abs(estacionamento.orientacao_graus) % 180.0, (90.0,))

    def test_original_sem_vaga_e_resolvido_sem_alterar_arquivo(self) -> None:
        original = carregar_projeto_cidade(ORIGINAL)
        self.assertIsNone(original.estacionamento_inicial)
        estacionamento = resolver_estacionamento(
            original, self.mapa, self.dimensoes
        )
        self.assertTrue(estacionamento.validado)
        self.assertEqual(estacionamento.deposito, "D")

    def test_resolve_vaga_pelo_mapa_sem_arestas_saindo_do_deposito(self) -> None:
        grafo = Grafo()
        grafo.adicionar_vertice(
            Vertice("D", "Novo depósito", TipoVertice.DEPOSITO, -0.30, 0.065)
        )
        grafo.definir_deposito("D")
        projeto = ProjetoCidade(
            grafo=grafo,
            posicoes={"D": (-0.30, -0.006227047208837454, 0.065)},
        )
        estacionamento = resolver_estacionamento(
            projeto, self.mapa, self.dimensoes
        )
        self.assertTrue(estacionamento.validado)
        self.assertEqual(estacionamento.deposito, "D")
        self.assertLessEqual(
            hypot(
                estacionamento.posicao[0] - projeto.posicoes["D"][0],
                estacionamento.posicao[2] - projeto.posicoes["D"][2],
            ),
            0.25,
        )
        self.assertEqual(abs(estacionamento.orientacao_graus), 90.0)
        self.assertTrue(
            validar_estacionamento(
                estacionamento, self.mapa, self.dimensoes
            ).valido
        )

    def test_dijkstra_e_tsp_sao_identicos_no_original_e_corrigido(self) -> None:
        original = carregar_projeto_cidade(ORIGINAL)
        dijkstra_original = calcular_dijkstra(original, "D", "A")
        dijkstra_corrigido = calcular_dijkstra(self.projeto, "D", "A")
        self.assertEqual(dijkstra_original.percurso_completo, dijkstra_corrigido.percurso_completo)
        self.assertEqual(dijkstra_original.distancia_total, dijkstra_corrigido.distancia_total)
        clientes = [vertice.identificador for vertice in original.grafo.listar_clientes()]
        tsp_original = calcular_tsp(original, clientes)
        tsp_corrigido = calcular_tsp(self.projeto, clientes)
        self.assertEqual(tsp_original.percurso_completo, tsp_corrigido.percurso_completo)
        self.assertEqual(tsp_original.distancia_total, tsp_corrigido.distancia_total)

    def test_missao_parte_e_reinicia_na_vaga_sem_teletransporte(self) -> None:
        estacionamento = self.projeto.estacionamento_inicial
        rota = calcular_dijkstra(self.projeto, "D", "B")
        missao = ControladorMissao(
            rota,
            velocidade_base=0.1,
            posicao_inicial=estacionamento.posicao,
            orientacao_inicial_graus=estacionamento.orientacao_graus,
        )
        inicial = missao.quadro()
        self.assertEqual(inicial.posicao, estacionamento.posicao)
        self.assertEqual(inicial.orientacao_graus, estacionamento.orientacao_graus)
        missao.iniciar()
        movido = missao.avancar(0.1)
        self.assertLessEqual(
            sum((movido.posicao[i] - inicial.posicao[i]) ** 2 for i in range(3)) ** 0.5,
            0.011,
        )
        reiniciado = missao.reiniciar(iniciar=False)
        self.assertEqual(reiniciado.estado, EstadoMissao.PRONTA)
        self.assertEqual(reiniciado.posicao, estacionamento.posicao)
        self.assertEqual(reiniciado.orientacao_graus, estacionamento.orientacao_graus)


if __name__ == "__main__":
    unittest.main()
