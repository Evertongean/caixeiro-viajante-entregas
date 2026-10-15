"""Testes do movimento dinâmico, entregas e câmera da missão 3D."""

from __future__ import annotations

import unittest
from math import cos, radians, sin

from models.missao import (
    ControladorMissao,
    ErroMissao,
    EstadoMissao,
    FaseMovimento,
    TipoCurva,
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


def avancar_ate(
    missao: ControladorMissao,
    condicao,
    *,
    passo: float = 0.01,
    limite: int = 20_000,
):
    quadro = missao.quadro()
    for _ in range(limite):
        if condicao(quadro):
            return quadro
        quadro = missao.avancar(passo)
    raise AssertionError("A condição esperada não ocorreu durante a missão.")


class TestControladorMissao(unittest.TestCase):
    def test_parte_parado_acelera_progressivamente_e_respeita_maxima(self) -> None:
        rota = criar_rota([("A", "B", 20, ((0, 0, 0), (20, 0, 0)))])
        missao = ControladorMissao(
            rota,
            velocidade_base=2.0,
            aceleracao=1.0,
            desaceleracao_conforto=2.0,
            frenagem_maxima=4.0,
        )
        inicial = missao.iniciar()
        self.assertEqual(inicial.velocidade_atual, 0.0)
        self.assertEqual(inicial.fase_movimento, FaseMovimento.ACELERANDO)
        self.assertFalse(inicial.freando)
        primeira = missao.avancar(0.2)
        segunda = missao.avancar(0.2)
        self.assertGreater(primeira.velocidade_atual, 0.0)
        self.assertGreater(segunda.velocidade_atual, primeira.velocidade_atual)
        cruzeiro = missao.avancar(3.0)
        self.assertLessEqual(cruzeiro.velocidade_atual, 2.0)
        self.assertAlmostEqual(cruzeiro.velocidade_atual, 2.0)

    def test_classifica_curvas_e_ignora_pontos_quase_colineares(self) -> None:
        def rota_com_angulo(valor: float) -> RotaCalculada:
            angulo = radians(valor)
            return criar_rota(
                [
                    (
                        "A",
                        "B",
                        2,
                        (
                            (0, 0, 0),
                            (1, 0, 0),
                            (1 + cos(angulo), 0, sin(angulo)),
                        ),
                    )
                ]
            )

        suave = rota_com_angulo(25)
        moderada = rota_com_angulo(60)
        fechada = criar_rota(
            [("A", "B", 2, ((0, 0, 0), (1, 0, 0), (1, 0, 1)))]
        )
        retorno = rota_com_angulo(170)
        quase_reta = criar_rota(
            [("A", "B", 2, ((0, 0, 0), (1, 0, 0), (2, 0, 0.1)))]
        )
        self.assertEqual(
            ControladorMissao(suave).curvas_detectadas[0].tipo,
            TipoCurva.SUAVE,
        )
        self.assertEqual(
            ControladorMissao(moderada).curvas_detectadas[0].tipo,
            TipoCurva.MODERADA,
        )
        curva_90 = ControladorMissao(fechada).curvas_detectadas[0]
        self.assertEqual(curva_90.tipo, TipoCurva.FECHADA)
        self.assertAlmostEqual(curva_90.angulo_graus, 90.0)
        self.assertEqual(
            ControladorMissao(retorno).curvas_detectadas[0].tipo,
            TipoCurva.RETORNO,
        )
        self.assertEqual(ControladorMissao(quase_reta).curvas_detectadas, ())

    def test_freia_antes_da_curva_reduz_na_esquina_e_acelera_depois(self) -> None:
        rota = criar_rota(
            [("A", "B", 6, ((0, 0, 0), (2, 0, 0), (2, 0, 4)))]
        )
        missao = ControladorMissao(
            rota,
            velocidade_base=1.0,
            aceleracao=2.0,
            desaceleracao_conforto=1.0,
            frenagem_maxima=3.0,
        )
        missao.iniciar()
        frenando = avancar_ate(
            missao,
            lambda q: (
                q.fase_movimento is FaseMovimento.FREANDO_CURVA and q.freando
            ),
        )
        self.assertLess(frenando.posicao[0], 2.0)
        self.assertGreater(frenando.distancia_proxima_curva, 0.0)
        velocidade_antes = frenando.velocidade_atual
        curva = avancar_ate(
            missao,
            lambda q: q.fase_movimento is FaseMovimento.EM_CURVA,
        )
        self.assertLessEqual(curva.velocidade_atual, 0.41)
        self.assertLess(curva.velocidade_atual, velocidade_antes)
        depois = avancar_ate(
            missao,
            lambda q: q.posicao[2] > 0.5,
        )
        self.assertGreater(depois.velocidade_atual, curva.velocidade_atual)
        self.assertFalse(depois.freando)

    def test_orientacao_muda_pelo_menor_arco_sem_salto(self) -> None:
        rota = criar_rota(
            [("A", "B", 4, ((0, 0, 0), (2, 0, 0), (2, 0, 2)))]
        )
        missao = ControladorMissao(
            rota,
            velocidade_base=1.0,
            velocidade_rotacao=45.0,
        )
        missao.iniciar()
        antes = avancar_ate(missao, lambda q: q.posicao[0] > 1.95)
        depois = avancar_ate(missao, lambda q: q.posicao[2] > 0.03)
        self.assertGreaterEqual(antes.orientacao_graus, 0.0)
        self.assertLess(depois.orientacao_graus, 90.0)
        self.assertGreater(depois.orientacao_graus, -1e-6)

    def test_reta_nao_freia_antes_da_zona_do_destino(self) -> None:
        rota = criar_rota([("A", "B", 10, ((0, 0, 0), (10, 0, 0)))])
        missao = ControladorMissao(rota, velocidade_base=1.0)
        missao.iniciar()
        quadro = avancar_ate(missao, lambda q: q.posicao[0] > 5.0)
        self.assertAlmostEqual(quadro.velocidade_atual, 1.0)
        self.assertEqual(quadro.fase_movimento, FaseMovimento.CRUZEIRO)
        self.assertFalse(quadro.freando)

    def test_dijkstra_freia_para_exatamente_no_destino_sem_ultrapassar(self) -> None:
        rota = criar_rota([("A", "B", 3, ((0, 0, 0), (3, 0, 0)))])
        missao = ControladorMissao(rota, velocidade_base=2.0)
        missao.multiplicador_velocidade = 4.0
        missao.iniciar()
        frenando = avancar_ate(
            missao,
            lambda q: (
                q.fase_movimento is FaseMovimento.FREANDO_DESTINO
                and q.freando
            ),
        )
        self.assertLess(frenando.posicao[0], 3.0)
        fim = missao.avancar(10.0)
        self.assertEqual(fim.estado, EstadoMissao.CONCLUIDA)
        self.assertEqual(fim.posicao, (3, 0, 0))
        self.assertEqual(fim.velocidade_atual, 0.0)
        self.assertEqual(fim.distancia_destino_final, 0.0)
        self.assertEqual(fim.fase_movimento, FaseMovimento.CONCLUIDO)
        self.assertFalse(fim.freando)
        self.assertEqual(
            [evento.tipo for evento in fim.eventos],
            [TipoEventoMissao.CONCLUSAO],
        )

    def test_tsp_para_registra_uma_vez_aguarda_e_retoma_acelerando(self) -> None:
        rota = criar_rota(
            [
                ("D", "A", 1, ((0, 0, 0), (1, 0, 0))),
                ("A", "D", 1, ((1, 0, 0), (0, 0, 0))),
            ],
            algoritmo=AlgoritmoRota.TSP,
            ordem=("D", "A", "D"),
            clientes=("A",),
        )
        missao = ControladorMissao(
            rota, velocidade_base=1.0, tempo_parada_entrega=1.0
        )
        missao.iniciar()
        aproximacao = avancar_ate(
            missao,
            lambda q: (
                q.fase_movimento is FaseMovimento.FREANDO_ENTREGA
                and q.freando
            ),
        )
        self.assertLess(aproximacao.posicao[0], 1.0)
        entrega = avancar_ate(
            missao,
            lambda q: q.estado is EstadoMissao.EM_ENTREGA,
        )
        self.assertEqual(entrega.posicao, (1, 0, 0))
        self.assertEqual(entrega.velocidade_atual, 0.0)
        self.assertTrue(entrega.freando)
        self.assertIsNone(entrega.distancia_proxima_entrega)
        self.assertEqual(entrega.clientes_atendidos, ("A",))
        self.assertEqual(entrega.eventos[0].tipo, TipoEventoMissao.ENTREGA)
        parado = missao.avancar(0.5)
        self.assertEqual(parado.posicao, (1, 0, 0))
        self.assertTrue(parado.freando)
        retomada = missao.avancar(0.6)
        self.assertEqual(retomada.clientes_atendidos, ("A",))
        self.assertGreater(retomada.velocidade_atual, 0.0)
        self.assertFalse(retomada.freando)
        self.assertIn(
            retomada.fase_movimento,
            (FaseMovimento.RETOMANDO, FaseMovimento.EM_CURVA),
        )
        fim = avancar_ate(
            missao, lambda q: q.estado is EstadoMissao.CONCLUIDA
        )
        self.assertEqual(fim.posicao, (0, 0, 0))
        self.assertEqual(fim.clientes_atendidos, ("A",))

    def test_tsp_retorna_freando_ate_a_vaga_sem_teletransporte(self) -> None:
        rota = criar_rota(
            [
                ("D", "A", 1, ((0, 0, 0), (1, 0, 0))),
                ("A", "D", 1, ((1, 0, 0), (0, 0, 0))),
            ],
            algoritmo=AlgoritmoRota.TSP,
            ordem=("D", "A", "D"),
            clientes=("A",),
        )
        vaga = (-0.2, 0.0, 0.0)
        missao = ControladorMissao(
            rota,
            velocidade_base=1.0,
            tempo_parada_entrega=0.0,
            posicao_inicial=vaga,
        )
        missao.iniciar()
        retorno = avancar_ate(
            missao,
            lambda q: (
                q.fase_movimento is FaseMovimento.FREANDO_DESTINO
                and q.distancia_percorrida == rota.distancia_total
            ),
        )
        self.assertNotEqual(retorno.posicao, vaga)
        self.assertTrue(retorno.freando)
        fim = avancar_ate(
            missao, lambda q: q.estado is EstadoMissao.CONCLUIDA
        )
        self.assertEqual(fim.posicao, vaga)
        self.assertEqual(fim.velocidade_atual, 0.0)

    def test_pausa_preserva_posicao_velocidade_e_fase_e_continua(self) -> None:
        rota = criar_rota([("A", "B", 10, ((0, 0, 0), (10, 0, 0)))])
        missao = ControladorMissao(rota, velocidade_base=1.0)
        missao.iniciar()
        acelerando = missao.avancar(0.2)
        velocidade = acelerando.velocidade_atual
        posicao = acelerando.posicao
        pausado = missao.pausar()
        self.assertEqual(pausado.fase_movimento, FaseMovimento.PAUSADO)
        self.assertEqual(missao.avancar(5.0).posicao, posicao)
        continuado = missao.continuar()
        self.assertEqual(continuado.velocidade_atual, velocidade)
        self.assertEqual(continuado.fase_movimento, acelerando.fase_movimento)
        self.assertGreater(missao.avancar(0.1).posicao[0], posicao[0])

    def test_pausa_durante_frenagem_e_reinicio_zeram_corretamente(self) -> None:
        rota = criar_rota(
            [("A", "B", 6, ((0, 0, 0), (2, 0, 0), (2, 0, 4)))]
        )
        missao = ControladorMissao(rota, velocidade_base=1.0)
        missao.iniciar()
        frenando = avancar_ate(
            missao,
            lambda q: (
                q.fase_movimento is FaseMovimento.FREANDO_CURVA and q.freando
            ),
        )
        pausado = missao.pausar()
        self.assertTrue(pausado.freando)
        continuado = missao.continuar()
        self.assertTrue(continuado.freando)
        self.assertAlmostEqual(
            missao.quadro().velocidade_atual, frenando.velocidade_atual
        )
        reinicio = missao.reiniciar()
        self.assertEqual(reinicio.posicao, (0, 0, 0))
        self.assertEqual(reinicio.velocidade_atual, 0.0)
        self.assertEqual(reinicio.fase_movimento, FaseMovimento.ACELERANDO)
        self.assertFalse(reinicio.freando)
        encerrado = missao.encerrar()
        self.assertFalse(encerrado.freando)

    def test_multiplicadores_representam_tempo_simulado(self) -> None:
        rota = criar_rota([("A", "B", 10, ((0, 0, 0), (10, 0, 0)))])
        resultados = []
        for multiplicador in (0.5, 1.0, 2.0, 4.0):
            missao = ControladorMissao(rota, velocidade_base=1.0)
            missao.multiplicador_velocidade = multiplicador
            missao.iniciar()
            quadro = missao.avancar(1.0 / multiplicador)
            resultados.append((quadro.posicao, quadro.velocidade_atual))
        for resultado in resultados[1:]:
            self.assertAlmostEqual(resultado[0][0], resultados[0][0][0], places=8)
            self.assertAlmostEqual(resultado[1], resultados[0][1], places=8)

    def test_resultado_independe_da_variacao_de_fps(self) -> None:
        rota = criar_rota([("A", "B", 10, ((0, 0, 0), (10, 0, 0)))])
        uniforme = ControladorMissao(rota, velocidade_base=1.0)
        variavel = ControladorMissao(rota, velocidade_base=1.0)
        uniforme.iniciar()
        variavel.iniciar()
        for _ in range(100):
            quadro_uniforme = uniforme.avancar(0.01)
        for delta in (0.017, 0.033, 0.008, 0.042, 0.1, 0.2, 0.3, 0.3):
            quadro_variavel = variavel.avancar(delta)
        self.assertAlmostEqual(
            quadro_uniforme.posicao[0], quadro_variavel.posicao[0], places=4
        )
        self.assertAlmostEqual(
            quadro_uniforme.velocidade_atual,
            quadro_variavel.velocidade_atual,
            places=4,
        )

    def test_sentido_inverso_ruas_repetidas_e_distancia_preservada(self) -> None:
        rota = criar_rota(
            [
                ("D", "C", 2, ((0, 0, 0), (1, 0, 0), (1, 0, 1))),
                ("C", "D", 2, ((1, 0, 1), (1, 0, 0), (0, 0, 0))),
            ],
            algoritmo=AlgoritmoRota.TSP,
            ordem=("D", "C", "D"),
            clientes=("C",),
        )
        missao = ControladorMissao(
            rota, velocidade_base=2.0, tempo_parada_entrega=0.0
        )
        missao.iniciar()
        fim = avancar_ate(
            missao, lambda q: q.estado is EstadoMissao.CONCLUIDA
        )
        self.assertEqual(fim.posicao, (0, 0, 0))
        self.assertEqual(fim.distancia_percorrida, 4.0)
        self.assertEqual(missao.resumo().distancia_percorrida, 4.0)

    def test_formula_distancia_frenagem_e_parametros_invalidos(self) -> None:
        rota = criar_rota([("A", "B", 10, ((0, 0, 0), (10, 0, 0)))])
        missao = ControladorMissao(
            rota,
            velocidade_base=2.0,
            aceleracao=4.0,
            desaceleracao_conforto=2.0,
            frenagem_maxima=4.0,
        )
        missao.iniciar()
        avancar_ate(missao, lambda q: q.velocidade_atual == 2.0)
        self.assertAlmostEqual(missao.distancia_frenagem(1.0), 0.75)
        with self.assertRaisesRegex(ValueError, "frenagem máxima"):
            ControladorMissao(
                rota,
                desaceleracao_conforto=2.0,
                frenagem_maxima=1.0,
            )

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

    def test_camera_permanece_estavel_quando_carro_freia(self) -> None:
        camera = CameraSeguidora(distancia=2.0, altura=1.0, antecipacao=0.5)
        camera.atualizar((0, 0, 0), 0, 0, imediato=True)
        posicoes = []
        for z in (0.20, 0.35, 0.44, 0.48, 0.50, 0.50):
            posicao, _ = camera.atualizar((0, 0, z), 0, 0.05)
            posicoes.append(posicao[2])
        self.assertEqual(posicoes, sorted(posicoes))


if __name__ == "__main__":
    unittest.main()
