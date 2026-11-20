"""Regressões da apresentação acadêmica com 18 vértices."""

from __future__ import annotations

import unittest

from algorithms.caixeiro_viajante import (
    CalculoTSPCancelado,
    LIMITE_PADRAO_CLIENTES,
    caixeiro_viajante,
    held_karp,
    permutacoes_forca_bruta,
)
from models.cenario_academico import carregar_cenario_academico_18
from models.grafo import criar_cenario_exemplo
from models.missao import ControladorMissao, EstadoMissao, TipoEventoMissao
from models.rota import (
    AlgoritmoRota,
    EstadoEspacial,
    RotaCalculada,
    SegmentoEspacialRota,
)
from ui.formatacao import formatar_inteiro_br


class TestComplexidadeTSP(unittest.TestCase):
    def test_fatorial_e_formatacao_brasileira(self) -> None:
        self.assertEqual(permutacoes_forca_bruta(0), 1)
        self.assertEqual(permutacoes_forca_bruta(8), 40_320)
        self.assertEqual(permutacoes_forca_bruta(10), 3_628_800)
        self.assertEqual(permutacoes_forca_bruta(17), 355_687_428_096_000)
        self.assertEqual(
            formatar_inteiro_br(permutacoes_forca_bruta(17)),
            "355.687.428.096.000",
        )

    def test_forca_bruta_preserva_limite_original(self) -> None:
        projeto = carregar_cenario_academico_18()
        self.assertEqual(LIMITE_PADRAO_CLIENTES, 8)
        with self.assertRaisesRegex(ValueError, "limite de 8 clientes"):
            caixeiro_viajante(projeto.grafo)

    def test_held_karp_concorda_com_forca_bruta(self) -> None:
        grafo = criar_cenario_exemplo()
        forca_bruta = caixeiro_viajante(grafo)
        dinamica = held_karp(grafo)
        self.assertTrue(dinamica.encontrada)
        self.assertEqual(dinamica.distancia_total, 15.0)
        self.assertEqual(dinamica.distancia_total, forca_bruta.distancia_total)
        self.assertEqual(set(dinamica.ordem_entregas[1:-1]), {"A", "B", "C"})

    def test_held_karp_oferece_cancelamento_cooperativo(self) -> None:
        with self.assertRaisesRegex(CalculoTSPCancelado, "cancelado"):
            held_karp(criar_cenario_exemplo(), cancelado=lambda: True)

    def test_held_karp_atende_os_17_sem_alterar_grafo(self) -> None:
        projeto = carregar_cenario_academico_18()
        vertices = projeto.grafo.listar_vertices()
        arestas = projeto.grafo.listar_arestas()
        resultado = held_karp(projeto.grafo)
        self.assertTrue(resultado.encontrada)
        self.assertEqual(resultado.quantidade_clientes_atendidos, 17)
        self.assertEqual(len(set(resultado.ordem_entregas[1:-1])), 17)
        self.assertEqual(resultado.ordem_entregas[0], "1")
        self.assertEqual(resultado.ordem_entregas[-1], "1")
        self.assertEqual(resultado.distancia_total, 398.0)
        self.assertEqual(
            sum(segmento.distancia for segmento in resultado.segmentos),
            resultado.distancia_total,
        )
        self.assertEqual(projeto.grafo.listar_vertices(), vertices)
        self.assertEqual(projeto.grafo.listar_arestas(), arestas)


def _rota_missao_acelerada() -> RotaCalculada:
    segmentos = (
        SegmentoEspacialRota(
            0, "D", "A", 2.0, ((0, 0, 0), (1, 0, 0), (1, 0, 1)), True
        ),
        SegmentoEspacialRota(
            1, "A", "D", 2.0, ((1, 0, 1), (0, 0, 1), (0, 0, 0)), True
        ),
    )
    return RotaCalculada(
        algoritmo=AlgoritmoRota.TSP,
        origem="D",
        destino=None,
        ordem_atendimento=("D", "A", "D"),
        percurso_completo=("D", "A", "D"),
        distancia_total=4.0,
        segmentos_espaciais=segmentos,
        estado_espacial=EstadoEspacial.COMPLETO,
        arestas_pendentes=(),
        clientes_selecionados=("A",),
    )


class TestMissaoAcelerada(unittest.TestCase):
    def test_multiplicadores_altos_preservam_paradas_e_distancia(self) -> None:
        for multiplicador in (8.0, 16.0, 32.0, 64.0):
            with self.subTest(multiplicador=multiplicador):
                missao = ControladorMissao(
                    _rota_missao_acelerada(),
                    velocidade_base=2.0,
                    tempo_parada_entrega=0.1,
                )
                missao.multiplicador_velocidade = multiplicador
                quadro = missao.iniciar()
                entregas = 0
                pontos_observados = {quadro.posicao}
                for _ in range(500):
                    quadro = missao.avancar(0.05)
                    pontos_observados.update(quadro.pontos_interpolacao)
                    entregas += sum(
                        evento.tipo is TipoEventoMissao.ENTREGA
                        for evento in quadro.eventos
                    )
                    if quadro.estado is EstadoMissao.CONCLUIDA:
                        break
                self.assertEqual(quadro.estado, EstadoMissao.CONCLUIDA)
                self.assertEqual(quadro.clientes_atendidos, ("A",))
                self.assertEqual(entregas, 1)
                self.assertEqual(quadro.distancia_percorrida, 4.0)
                self.assertEqual(quadro.posicao, (0, 0, 0))
                self.assertTrue(
                    {(1, 0, 0), (1, 0, 1), (0, 0, 1)} <= pontos_observados
                )

    def test_pausa_e_reinicio_em_64x(self) -> None:
        missao = ControladorMissao(_rota_missao_acelerada(), velocidade_base=0.5)
        missao.multiplicador_velocidade = 64.0
        missao.iniciar()
        missao.avancar(0.01)
        pausado = missao.pausar()
        self.assertEqual(missao.avancar(1.0).posicao, pausado.posicao)
        missao.continuar()
        self.assertNotEqual(missao.avancar(0.01).posicao, pausado.posicao)
        reiniciado = missao.reiniciar(iniciar=True)
        self.assertEqual(reiniciado.posicao, (0.0, 0.0, 0.0))
        self.assertEqual(reiniciado.clientes_atendidos, ())


if __name__ == "__main__":
    unittest.main()
