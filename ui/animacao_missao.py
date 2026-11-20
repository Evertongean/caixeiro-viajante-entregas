"""Cadência Qt da missão, separada da apresentação renderizada pelo QML."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from math import isfinite
from time import perf_counter

from PySide6.QtCore import QElapsedTimer, QObject, Qt, QTimer, Signal

from models.missao import ControladorMissao, EstadoMissao, QuadroMissao


LOGGER = logging.getLogger(__name__)
INTERVALO_LOGICA_MS = 33
INTERVALO_PAINEL_SEGUNDOS = 0.10
DELTA_REAL_MAXIMO = 0.05


def _diagnostico_habilitado_por_ambiente() -> bool:
    return os.getenv("DELIVERY_ROUTE_DIAGNOSTICO_ANIMACAO", "").casefold() in {
        "1",
        "true",
        "sim",
        "yes",
        "on",
    }


@dataclass(slots=True)
class DiagnosticoDesempenho:
    """Medições opcionais sem adicionar controles técnicos à interface."""

    habilitado: bool = False
    atualizacoes_logica: int = 0
    atualizacoes_interface: int = 0
    quadros_renderizados: int = 0
    intervalos_longos: int = 0
    tempo_real_logica: float = 0.0
    tempo_renderizado: float = 0.0
    tempo_controlador_ms: float = 0.0
    tempo_envio_qml_ms: float = 0.0
    tempo_interface_ms: float = 0.0
    maior_intervalo_ms: float = 0.0
    maior_controlador_ms: float = 0.0
    maior_envio_qml_ms: float = 0.0
    maior_interface_ms: float = 0.0

    def registrar_logica(
        self, intervalo_real: float, controlador_ms: float, envio_qml_ms: float
    ) -> None:
        if not self.habilitado:
            return
        self.atualizacoes_logica += 1
        self.tempo_real_logica += max(intervalo_real, 0.0)
        self.tempo_controlador_ms += max(controlador_ms, 0.0)
        self.tempo_envio_qml_ms += max(envio_qml_ms, 0.0)
        self.maior_intervalo_ms = max(
            self.maior_intervalo_ms, intervalo_real * 1000.0
        )
        self.maior_controlador_ms = max(
            self.maior_controlador_ms, controlador_ms
        )
        self.maior_envio_qml_ms = max(self.maior_envio_qml_ms, envio_qml_ms)
        if intervalo_real > INTERVALO_LOGICA_MS / 1000.0 * 2.0:
            self.intervalos_longos += 1

    def registrar_interface(self, duracao_ms: float) -> None:
        if not self.habilitado:
            return
        self.atualizacoes_interface += 1
        self.tempo_interface_ms += max(duracao_ms, 0.0)
        self.maior_interface_ms = max(self.maior_interface_ms, duracao_ms)

    def registrar_quadro_renderizado(self, delta_segundos: float) -> None:
        if (
            not self.habilitado
            or not isfinite(delta_segundos)
            or delta_segundos <= 0
        ):
            return
        self.quadros_renderizados += 1
        self.tempo_renderizado += delta_segundos

    @staticmethod
    def _media(total: float, quantidade: int) -> float:
        return total / quantidade if quantidade else 0.0

    def resumo(self) -> dict[str, float | int | None]:
        return {
            "logica_hz": (
                self.atualizacoes_logica / self.tempo_real_logica
                if self.tempo_real_logica > 0
                else None
            ),
            "fps_renderizado": (
                self.quadros_renderizados / self.tempo_renderizado
                if self.tempo_renderizado > 0
                else None
            ),
            "interface_hz": (
                self.atualizacoes_interface / self.tempo_real_logica
                if self.tempo_real_logica > 0
                else None
            ),
            "controlador_ms_medio": self._media(
                self.tempo_controlador_ms, self.atualizacoes_logica
            ),
            "envio_qml_ms_medio": self._media(
                self.tempo_envio_qml_ms, self.atualizacoes_logica
            ),
            "interface_ms_medio": self._media(
                self.tempo_interface_ms, self.atualizacoes_interface
            ),
            "maior_intervalo_ms": self.maior_intervalo_ms,
            "maior_controlador_ms": self.maior_controlador_ms,
            "maior_envio_qml_ms": self.maior_envio_qml_ms,
            "maior_interface_ms": self.maior_interface_ms,
            "intervalos_longos": self.intervalos_longos,
            "atualizacoes_logica": self.atualizacoes_logica,
            "atualizacoes_interface": self.atualizacoes_interface,
            "quadros_renderizados": self.quadros_renderizados,
        }


class AnimacaoMissao(QObject):
    quadro_atualizado = Signal(object, float)
    painel_atualizado = Signal(object)
    concluida = Signal(object)

    def __init__(
        self,
        controlador: ControladorMissao,
        parent=None,
        *,
        diagnostico_habilitado: bool | None = None,
    ) -> None:
        super().__init__(parent)
        self.controlador = controlador
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(INTERVALO_LOGICA_MS)
        self.timer.timeout.connect(self._avancar)
        self._relogio = QElapsedTimer()
        self._tempo_painel = 0.0
        self._ultimo_estado_painel: EstadoMissao | None = None
        self.diagnostico = DiagnosticoDesempenho(
            _diagnostico_habilitado_por_ambiente()
            if diagnostico_habilitado is None
            else bool(diagnostico_habilitado)
        )

    @property
    def ativa(self) -> bool:
        return self.timer.isActive()

    def _emitir_painel(self, quadro: QuadroMissao, *, imediato: bool = False) -> None:
        mudou_estado = quadro.estado is not self._ultimo_estado_painel
        if not (
            imediato
            or mudou_estado
            or quadro.eventos
            or self._tempo_painel >= INTERVALO_PAINEL_SEGUNDOS
        ):
            return
        inicio = perf_counter()
        self.painel_atualizado.emit(quadro)
        duracao_ms = (perf_counter() - inicio) * 1000.0
        self.diagnostico.registrar_interface(duracao_ms)
        self._tempo_painel = 0.0
        self._ultimo_estado_painel = quadro.estado

    def iniciar(self) -> None:
        quadro = self.controlador.iniciar()
        self.quadro_atualizado.emit(quadro, 0.0)
        self._emitir_painel(quadro, imediato=True)
        self._relogio.start()
        self.timer.start()

    def pausar(self) -> None:
        self.timer.stop()
        quadro = self.controlador.pausar()
        self._emitir_painel(quadro, imediato=True)

    def continuar(self) -> None:
        quadro = self.controlador.continuar()
        self._emitir_painel(quadro, imediato=True)
        self._relogio.restart()
        self.timer.start()

    def reiniciar(self) -> None:
        quadro = self.controlador.reiniciar(iniciar=True)
        self.quadro_atualizado.emit(quadro, 0.0)
        self._emitir_painel(quadro, imediato=True)
        self._relogio.restart()
        self.timer.start()

    def encerrar(self) -> None:
        self.timer.stop()
        quadro = self.controlador.encerrar()
        self._emitir_painel(quadro, imediato=True)
        self._registrar_resumo()

    def _avancar(self) -> None:
        if not self._relogio.isValid():
            self._relogio.start()
            return
        delta_real = max(self._relogio.nsecsElapsed() / 1_000_000_000.0, 0.0)
        self._relogio.restart()
        delta_aplicado = min(delta_real, DELTA_REAL_MAXIMO)
        inicio_controlador = perf_counter()
        quadro: QuadroMissao = self.controlador.avancar(delta_aplicado)
        controlador_ms = (perf_counter() - inicio_controlador) * 1000.0
        inicio_envio = perf_counter()
        self.quadro_atualizado.emit(quadro, delta_aplicado)
        envio_ms = (perf_counter() - inicio_envio) * 1000.0
        self.diagnostico.registrar_logica(delta_real, controlador_ms, envio_ms)
        self._tempo_painel += delta_real
        self._emitir_painel(quadro)
        if quadro.estado is EstadoMissao.CONCLUIDA:
            self.timer.stop()
            self.concluida.emit(self.controlador.resumo())
            self._registrar_resumo()

    def _registrar_resumo(self) -> None:
        if self.diagnostico.habilitado:
            LOGGER.info("Diagnóstico da animação: %s", self.diagnostico.resumo())

    def resumo_diagnostico(self) -> dict[str, float | int | None]:
        return self.diagnostico.resumo()


__all__ = [
    "AnimacaoMissao",
    "DELTA_REAL_MAXIMO",
    "DiagnosticoDesempenho",
    "INTERVALO_LOGICA_MS",
    "INTERVALO_PAINEL_SEGUNDOS",
]
