"""Testes da cadência lógica desacoplada da apresentação e do painel."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from models.missao import ControladorMissao, EstadoMissao
    from tests.test_missao import criar_rota
    from ui.animacao_missao import (
        DELTA_REAL_MAXIMO,
        INTERVALO_LOGICA_MS,
        AnimacaoMissao,
        DiagnosticoDesempenho,
    )

    PYSIDE6_DISPONIVEL = True
except ModuleNotFoundError:
    PYSIDE6_DISPONIVEL = False


class _RelogioAtrasado:
    def isValid(self) -> bool:  # noqa: N802 - contrato de QElapsedTimer
        return True

    def nsecsElapsed(self) -> int:  # noqa: N802 - contrato de QElapsedTimer
        return 250_000_000

    def restart(self) -> int:
        return 250


@unittest.skipUnless(PYSIDE6_DISPONIVEL, "PySide6 não está instalado")
class TestAnimacaoMissao(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.aplicacao = QApplication.instance() or QApplication([])

    @staticmethod
    def _controlador() -> ControladorMissao:
        rota = criar_rota([("A", "B", 10, ((0, 0, 0), (10, 0, 0)))])
        return ControladorMissao(rota, velocidade_base=1.0)

    def test_logica_e_painel_possuem_cadencias_independentes(self) -> None:
        animacao = AnimacaoMissao(
            self._controlador(), diagnostico_habilitado=True
        )
        quadros: list[object] = []
        paineis: list[object] = []
        animacao.quadro_atualizado.connect(
            lambda quadro, _delta: quadros.append(quadro)
        )
        animacao.painel_atualizado.connect(paineis.append)

        animacao.iniciar()
        QTest.qWait(380)
        animacao.pausar()

        self.assertEqual(animacao.timer.interval(), INTERVALO_LOGICA_MS)
        self.assertEqual(len(animacao.findChildren(QTimer)), 1)
        self.assertGreaterEqual(len(quadros), 8)
        self.assertLess(len(paineis), len(quadros))
        self.assertEqual(animacao.controlador.estado, EstadoMissao.PAUSADA)
        self.assertFalse(animacao.ativa)

        quantidade = len(quadros)
        QTest.qWait(INTERVALO_LOGICA_MS * 2)
        self.assertEqual(len(quadros), quantidade)
        animacao.continuar()
        self.assertTrue(animacao.ativa)
        animacao.reiniciar()
        self.assertTrue(animacao.ativa)
        animacao.encerrar()
        self.assertFalse(animacao.ativa)
        self.assertEqual(animacao.controlador.estado, EstadoMissao.ENCERRADA)

    def test_quadro_atrasado_tem_delta_limitado_sem_teletransporte(self) -> None:
        animacao = AnimacaoMissao(self._controlador())
        deltas: list[float] = []
        animacao.quadro_atualizado.connect(
            lambda _quadro, delta: deltas.append(delta)
        )
        animacao.iniciar()
        animacao.timer.stop()
        animacao._relogio = _RelogioAtrasado()
        tempo_anterior = animacao.controlador.tempo_decorrido

        animacao._avancar()

        self.assertEqual(deltas[-1], DELTA_REAL_MAXIMO)
        self.assertAlmostEqual(
            animacao.controlador.tempo_decorrido - tempo_anterior,
            DELTA_REAL_MAXIMO,
        )
        self.assertLess(animacao.controlador.quadro().posicao[0], 0.01)

    def test_diagnostico_distingue_logica_render_e_interface(self) -> None:
        diagnostico = DiagnosticoDesempenho(habilitado=True)
        diagnostico.registrar_logica(0.033, 0.4, 0.2)
        diagnostico.registrar_logica(0.090, 0.6, 0.3)
        diagnostico.registrar_interface(1.5)
        diagnostico.registrar_quadro_renderizado(1.0 / 60.0)
        diagnostico.registrar_quadro_renderizado(1.0 / 60.0)

        resumo = diagnostico.resumo()
        self.assertEqual(resumo["atualizacoes_logica"], 2)
        self.assertEqual(resumo["atualizacoes_interface"], 1)
        self.assertEqual(resumo["quadros_renderizados"], 2)
        self.assertEqual(resumo["intervalos_longos"], 1)
        self.assertAlmostEqual(resumo["fps_renderizado"], 60.0)
        self.assertAlmostEqual(resumo["controlador_ms_medio"], 0.5)


if __name__ == "__main__":
    unittest.main()
