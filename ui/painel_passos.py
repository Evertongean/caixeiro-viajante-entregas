"""Painel de controles da execução didática passo a passo."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .execucao_passos import PassoExecucao


class PainelPassos(QFrame):
    """Apresenta uma etapa e emite somente intenções de navegação."""

    iniciar_solicitado = Signal()
    avancar_solicitado = Signal()
    retroceder_solicitado = Signal()
    primeiro_solicitado = Signal()
    ultimo_solicitado = Signal()
    encerrar_solicitado = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("painelPassos")
        self.setMaximumHeight(190)
        self._construir()
        self.limpar()

    def _construir(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        cabecalho = QHBoxLayout()
        self.titulo = QLabel("PASSO A PASSO")
        self.titulo.setObjectName("tituloPainel")
        cabecalho.addWidget(self.titulo)
        cabecalho.addStretch(1)
        self.botao_iniciar = QPushButton("Iniciar")
        self.botao_iniciar.setObjectName("botaoPrimario")
        self.botao_iniciar.clicked.connect(lambda: self.iniciar_solicitado.emit())
        cabecalho.addWidget(self.botao_iniciar)
        layout.addLayout(cabecalho)

        self.rotulo_progresso = QLabel("Nenhuma sessão ativa")
        self.rotulo_progresso.setObjectName("textoSecundario")
        layout.addWidget(self.rotulo_progresso)

        self.rotulo_descricao = QLabel(
            "Inicie uma execução para acompanhar as decisões do algoritmo."
        )
        self.rotulo_descricao.setObjectName("descricaoPasso")
        self.rotulo_descricao.setWordWrap(True)
        self.rotulo_descricao.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.rotulo_descricao, 1)

        controles = QHBoxLayout()
        controles.setSpacing(5)
        self.botao_primeiro = self._botao("|<", self.primeiro_solicitado.emit)
        self.botao_retroceder = self._botao("Anterior", self.retroceder_solicitado.emit)
        self.botao_avancar = self._botao("Próximo", self.avancar_solicitado.emit)
        self.botao_ultimo = self._botao(">|", self.ultimo_solicitado.emit)
        self.botao_encerrar = self._botao("Encerrar", self.encerrar_solicitado.emit)
        for botao in (
            self.botao_primeiro,
            self.botao_retroceder,
            self.botao_avancar,
            self.botao_ultimo,
            self.botao_encerrar,
        ):
            controles.addWidget(botao)
        layout.addLayout(controles)

    @staticmethod
    def _botao(texto: str, callback) -> QPushButton:
        botao = QPushButton(texto)
        botao.setObjectName("botaoPasso")
        botao.clicked.connect(lambda: callback())
        return botao

    def configurar_algoritmo(self, algoritmo: str) -> None:
        nome = "Dijkstra" if algoritmo == "dijkstra" else "Caixeiro Viajante (TSP)"
        self.titulo.setText(f"PASSO A PASSO — {nome}")

    def mostrar_passo(self, passo: PassoExecucao, total: int, indice: int) -> None:
        self.rotulo_progresso.setText(f"Etapa {indice + 1} de {total}")
        self.rotulo_descricao.setText(passo.descricao)
        self.botao_iniciar.setEnabled(False)
        self.botao_primeiro.setEnabled(indice > 0)
        self.botao_retroceder.setEnabled(indice > 0)
        self.botao_avancar.setEnabled(indice < total - 1)
        self.botao_ultimo.setEnabled(indice < total - 1)
        self.botao_encerrar.setEnabled(True)

    def limpar(self) -> None:
        self.rotulo_progresso.setText("Nenhuma sessão ativa")
        self.rotulo_descricao.setText(
            "Inicie uma execução para acompanhar as decisões do algoritmo."
        )
        self.botao_iniciar.setEnabled(True)
        for botao in (
            self.botao_primeiro,
            self.botao_retroceder,
            self.botao_avancar,
            self.botao_ultimo,
            self.botao_encerrar,
        ):
            botao.setEnabled(False)

    def bloquear_inicio(self, bloqueado: bool) -> None:
        if self.rotulo_progresso.text() == "Nenhuma sessão ativa":
            self.botao_iniciar.setEnabled(not bloqueado)

