"""Testes do movimento, entregas e câmera da missão 3D."""

from __future__ import annotations

import unittest

from models.missao import (
    ControladorMissao,
    ErroMissao,
    EstadoMissao,
    TipoEventoMissao,
)
from models.rota import (
    AlgoritmoRota,
    EstadoEspacial,
    RotaCalculada,
    SegmentoEspacialRota,
)
from ui.camera_seguidora import CameraSeguidora


def criar_rota(
    segmentos: list[tuple[str, str, float, tuple[tuple[float, float, float], ...]]],
    *,
    algoritmo: AlgoritmoRota = AlgoritmoRota.DIJKSTRA,
    ordem: tuple[str, ...] = (),
    clientes: tuple[str, ...] = (),
    confirmada: bool = True,
) -> RotaCalculada:
    espaciais = tuple(
        SegmentoEspacialRota(i, origem, destino, peso, pontos, confirmada)
        for i, (origem, destino, peso, pontos) in enumerate(segmentos)
    )
    percurso = (segmentos[0][0], *(item[1] for item in segmentos))
    return RotaCalculada(
        algoritmo=algoritmo,
        origem=percurso[0],
        destino=percurso[-1] if algoritmo is AlgoritmoRota.DIJKSTRA else None,
        ordem_atendimento=ordem,
        percurso_completo=percurso,
        distancia_total=sum(item[2] for item in segmentos),
        segmentos_espaciais=espaciais,
        estado_espacial=(
            EstadoEspacial.COMPLETO if confirmada else EstadoEspacial.PARCIAL
        ),
        arestas_pendentes=()
        if confirmada
        else tuple((item[0], item[1]) for item in segmentos),
        clientes_selecionados=clientes,
    )


class TestControladorMissao(unittest.TestCase):
    def test_interpola_por_delta_e_converte_distancia_oficial_na_aresta(self) -> None:
        rota = criar_rota(
            [("A", "B", 10.0, ((0, 0, 0), (1, 0, 0), (3, 0, 0)))]
        )
        missao = ControladorMissao(rota, velocidade_base=1.0)
        missao.iniciar()
        quadro = missao.avancar(1.5)
        self.assertEqual(quadro.posicao, (1.5, 0.0, 0.0))
        self.assertAlmostEqual(quadro.progresso_aresta, 0.5)
        self.assertAlmostEqual(quadro.distancia_percorrida, 5.0)
        self.assertAlmostEqual(quadro.distancia_restante, 5.0)

    def test_percorre_curvas_arestas_reversas_e_repetidas_sem_pular(self) -> None:
        rota = criar_rota(
            [
                ("D", "C", 2, ((0, 0, 0), (1, 0, 0), (1, 0, 1))),
                ("C", "D", 2, ((1, 0, 1), (1, 0, 0), (0, 0, 0))),
            ]
        )
        missao = ControladorMissao(rota, velocidade_base=1.0)
        missao.iniciar()
        self.assertEqual(missao.avancar(1.0).posicao, (1.0, 0.0, 0.0))
        meio = missao.avancar(1.5)
        self.assertEqual(meio.indice_aresta, 1)
        self.assertEqual(meio.posicao, (1.0, 0.0, 0.5))
        fim = missao.avancar(1.5)
        self.assertEqual(fim.estado, EstadoMissao.CONCLUIDA)
        self.assertEqual(fim.posicao, (0.0, 0.0, 0.0))
        self.assertEqual(fim.distancia_percorrida, 4.0)
        resumo = missao.resumo()
        self.assertTrue(resumo.concluida)
        self.assertEqual(resumo.origem, "D")
        self.assertEqual(resumo.destino, "D")
        self.assertEqual(resumo.distancia_percorrida, 4.0)

    def test_orientacao_gira_pelo_menor_arco_sem_salto_na_curva(self) -> None:
        rota = criar_rota(
            [("A", "B", 2, ((0, 0, 0), (0, 0, 1), (1, 0, 1)))]
        )
        missao = ControladorMissao(
            rota, velocidade_base=1.0, velocidade_rotacao=45.0
        )
        missao.iniciar()
        self.assertEqual(missao.avancar(1.0).orientacao_graus, 0.0)
        curva = missao.avancar(0.5)
        self.assertAlmostEqual(curva.orientacao_graus, 22.5)
        self.assertEqual(curva.posicao, (0.5, 0.0, 1.0))

    def test_velocidade_pausa_continuacao_reinicio_e_encerramento(self) -> None:
        rota = criar_rota([("A", "B", 4, ((0, 0, 0), (4, 0, 0)))])
        missao = ControladorMissao(rota, velocidade_base=1.0)
        missao.multiplicador_velocidade = 2.0
        missao.iniciar()
        self.assertEqual(missao.avancar(0.5).posicao, (1.0, 0.0, 0.0))
        missao.pausar()
        self.assertEqual(missao.avancar(10).posicao, (1.0, 0.0, 0.0))
        missao.continuar()
        self.assertEqual(missao.avancar(0.5).posicao, (2.0, 0.0, 0.0))
        reinicio = missao.reiniciar()
        self.assertEqual(reinicio.posicao, (0.0, 0.0, 0.0))
        self.assertEqual(reinicio.distancia_percorrida, 0.0)
        self.assertEqual(missao.encerrar().estado, EstadoMissao.ENCERRADA)

    def test_tsp_entrega_na_ordem_sem_contar_passagem_incidental(self) -> None:
        rota = criar_rota(
            [
                ("D", "B", 1, ((0, 0, 0), (1, 0, 0))),
                ("B", "A", 1, ((1, 0, 0), (2, 0, 0))),
                ("A", "B", 1, ((2, 0, 0), (1, 0, 0))),
                ("B", "D", 1, ((1, 0, 0), (0, 0, 0))),
            ],
            algoritmo=AlgoritmoRota.TSP,
            ordem=("D", "A", "B", "D"),
            clientes=("A", "B"),
        )
        missao = ControladorMissao(
            rota, velocidade_base=1.0, tempo_parada_entrega=1.0
        )
        missao.iniciar()
        incidental = missao.avancar(1.0)
        self.assertEqual(incidental.clientes_atendidos, ())
        entrega_a = missao.avancar(1.0)
        self.assertEqual(entrega_a.clientes_atendidos, ("A",))
        self.assertEqual(entrega_a.estado, EstadoMissao.EM_ENTREGA)
        self.assertEqual(entrega_a.eventos[0].tipo, TipoEventoMissao.ENTREGA)
        missao.avancar(1.0)
        entrega_b = missao.avancar(1.0)
        self.assertEqual(entrega_b.clientes_atendidos, ("A", "B"))
        missao.avancar(1.0)
        fim = missao.avancar(1.0)
        self.assertEqual(fim.estado, EstadoMissao.CONCLUIDA)
        self.assertEqual(fim.posicao, (0.0, 0.0, 0.0))

    def test_rejeita_calibracao_incompleta_e_rota_sem_movimento(self) -> None:
        incompleta = criar_rota(
            [("A", "B", 1, ((0, 0, 0), (1, 0, 0)))], confirmada=False
        )
        with self.assertRaisesRegex(ErroMissao, "confirmados"):
            ControladorMissao(incompleta)
        sem_movimento = criar_rota(
            [("A", "B", 1, ((0, 0, 0), (0, 0, 0)))]
        )
        with self.assertRaisesRegex(ErroMissao, "comprimento espacial"):
            ControladorMissao(sem_movimento)

    def test_transicao_da_vaga_ate_rota_e_continua_e_nao_altera_distancia(self) -> None:
        rota = criar_rota([("D", "A", 2, ((0, 0, 0), (2, 0, 0)))])
        missao = ControladorMissao(
            rota,
            velocidade_base=1.0,
            posicao_inicial=(-0.5, 0, 0),
            orientacao_inicial_graus=90.0,
        )
        self.assertEqual(missao.quadro().posicao, (-0.5, 0.0, 0.0))
        missao.iniciar()
        transicao = missao.avancar(0.25)
        self.assertEqual(transicao.posicao, (-0.25, 0.0, 0.0))
        self.assertEqual(transicao.distancia_percorrida, 0.0)
        entrada = missao.avancar(0.5)
        self.assertEqual(entrada.posicao, (0.25, 0.0, 0.0))
        self.assertAlmostEqual(entrada.distancia_percorrida, 0.25)
        reinicio = missao.reiniciar(iniciar=False)
        self.assertEqual(reinicio.posicao, (-0.5, 0.0, 0.0))
        self.assertEqual(reinicio.orientacao_graus, 90.0)
        missao.iniciar()
        missao.avancar(0.2)
        encerrada = missao.encerrar()
        self.assertEqual(encerrada.estado, EstadoMissao.ENCERRADA)
        self.assertEqual(encerrada.posicao, (-0.5, 0.0, 0.0))
        self.assertEqual(encerrada.orientacao_graus, 90.0)


class TestCameraSeguidora(unittest.TestCase):
    def test_fica_atras_da_direcao_real_e_suaviza_mudanca(self) -> None:
        camera = CameraSeguidora(distancia=2.0, altura=1.0, antecipacao=0.5)
        posicao, alvo = camera.atualizar((0, 0, 0), 0, 0, imediato=True)
        self.assertEqual(posicao, (0.0, 1.0, -2.0))
        self.assertEqual(alvo, (0.0, 0.18, 0.5))
        nova, _ = camera.atualizar((0, 0, 0), 90, 0.05)
        self.assertGreater(nova[2], -2.0)
        self.assertLess(nova[0], 0.0)
        self.assertNotEqual(nova, (-2.0, 1.0, 0.0))


if __name__ == "__main__":
    unittest.main()
