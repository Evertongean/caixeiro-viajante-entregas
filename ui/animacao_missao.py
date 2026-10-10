"""Adaptador Qt do controlador de missão; não contém regra de percurso."""

from __future__ import annotations

from PySide6.QtCore import QElapsedTimer, QObject, Qt, QTimer, Signal

from models.missao import ControladorMissao, EstadoMissao, QuadroMissao


class AnimacaoMissao(QObject):
    quadro_atualizado = Signal(object, float)
    concluida = Signal(object)

    def __init__(self, controlador: ControladorMissao, parent=None) -> None:
        super().__init__(parent)
        self.controlador = controlador
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._avancar)
        self._relogio = QElapsedTimer()

    @property
    def ativa(self) -> bool:
        return self.timer.isActive()

    def iniciar(self) -> None:
        quadro = self.controlador.iniciar()
        self.quadro_atualizado.emit(quadro, 0.0)
        self._relogio.start()
        self.timer.start()

    def pausar(self) -> None:
        self.timer.stop()
        self.quadro_atualizado.emit(self.controlador.pausar(), 0.0)

    def continuar(self) -> None:
        quadro = self.controlador.continuar()
        self.quadro_atualizado.emit(quadro, 0.0)
        self._relogio.restart()
        self.timer.start()

    def reiniciar(self) -> None:
        quadro = self.controlador.reiniciar(iniciar=True)
        self.quadro_atualizado.emit(quadro, 0.0)
        self._relogio.restart()
        self.timer.start()

    def encerrar(self) -> None:
        self.timer.stop()
        self.quadro_atualizado.emit(self.controlador.encerrar(), 0.0)

    def _avancar(self) -> None:
        if not self._relogio.isValid():
            self._relogio.start()
            return
        delta = min(max(self._relogio.restart() / 1000.0, 0.0), 0.10)
        quadro: QuadroMissao = self.controlador.avancar(delta)
        self.quadro_atualizado.emit(quadro, delta)
        if quadro.estado is EstadoMissao.CONCLUIDA:
            self.timer.stop()
            self.concluida.emit(self.controlador.resumo())


__all__ = ["AnimacaoMissao"]
