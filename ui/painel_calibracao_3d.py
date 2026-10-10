"""Editor pequeno e independente do alinhamento grafo↔cidade 3D."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class PainelCalibracao3D(QWidget):
    """Controles para editar vértices, curvas e o arquivo de calibração.

    O painel emite intenções; quem conhece o grafo (``Cidade3DWidget``) faz a
    validação da aresta e aplica a alteração. Isso mantém a ferramenta útil em
    uma janela independente e evita duplicar regras do algoritmo.
    """

    posicao_solicitada = Signal(str, object)
    ponto_intermediario_solicitado = Signal(str, str, object)
    salvar_solicitado = Signal(str)
    carregar_solicitado = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("painelCalibracao3D")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(QLabel("Calibração das ruas sobre o modelo importado"))
        self.combo_vertice = QComboBox()
        self.combo_vertice.setObjectName("verticeCalibracao3D")
        self.combo_aresta_origem = QComboBox()
        self.combo_aresta_destino = QComboBox()
        self._x = self._numero()
        self._y = self._numero()
        self._z = self._numero()
        formulario = QFormLayout()
        formulario.addRow("Vértice", self.combo_vertice)
        formulario.addRow("Posição X", self._x)
        formulario.addRow("Posição Y", self._y)
        formulario.addRow("Posição Z", self._z)
        layout.addLayout(formulario)
        aplicar = QPushButton("Aplicar posição do vértice")
        aplicar.clicked.connect(self._emitir_posicao)
        layout.addWidget(aplicar)

        linha_aresta = QHBoxLayout()
        linha_aresta.addWidget(self.combo_aresta_origem)
        linha_aresta.addWidget(QLabel("→"))
        linha_aresta.addWidget(self.combo_aresta_destino)
        layout.addLayout(linha_aresta)
        ponto = QPushButton("Adicionar ponto de curva")
        ponto.clicked.connect(self._emitir_ponto)
        layout.addWidget(ponto)
        botoes = QHBoxLayout()
        salvar = QPushButton("Salvar mapeamento…")
        carregar = QPushButton("Carregar mapeamento…")
        salvar.clicked.connect(self._escolher_salvar)
        carregar.clicked.connect(self._escolher_carregar)
        botoes.addWidget(salvar)
        botoes.addWidget(carregar)
        layout.addLayout(botoes)

        self.combo_vertice.currentTextChanged.connect(self._atualizar_posicao)
        self._posicoes: dict[str, tuple[float, float, float]] = {}

    @staticmethod
    def _numero() -> QDoubleSpinBox:
        controle = QDoubleSpinBox()
        controle.setRange(-100000.0, 100000.0)
        controle.setDecimals(4)
        controle.setSingleStep(0.1)
        return controle

    def definir_vertices(self, identificadores: list[str] | tuple[str, ...], arestas: list[tuple[str, str]] | tuple[tuple[str, str], ...] = ()) -> None:
        self.combo_vertice.blockSignals(True)
        self.combo_vertice.clear()
        self.combo_vertice.addItems([str(item) for item in identificadores])
        self.combo_vertice.blockSignals(False)
        self.combo_aresta_origem.clear()
        self.combo_aresta_destino.clear()
        for origem, destino in arestas:
            self.combo_aresta_origem.addItem(str(origem), str(origem))
            self.combo_aresta_destino.addItem(str(destino), str(destino))
        self._atualizar_posicao(self.combo_vertice.currentText())

    def definir_posicoes(self, posicoes: dict[str, tuple[float, float, float]]) -> None:
        self._posicoes = dict(posicoes)
        self._atualizar_posicao(self.combo_vertice.currentText())

    def _atualizar_posicao(self, identificador: str) -> None:
        valor = self._posicoes.get(identificador)
        if valor is None:
            return
        for controle, numero in zip((self._x, self._y, self._z), valor):
            controle.blockSignals(True)
            controle.setValue(float(numero))
            controle.blockSignals(False)

    def _ponto(self) -> tuple[float, float, float]:
        return (self._x.value(), self._y.value(), self._z.value())

    def _emitir_posicao(self) -> None:
        identificador = self.combo_vertice.currentText()
        if identificador:
            self.posicao_solicitada.emit(identificador, self._ponto())

    def _emitir_ponto(self) -> None:
        origem = self.combo_aresta_origem.currentData() or self.combo_aresta_origem.currentText()
        destino = self.combo_aresta_destino.currentData() or self.combo_aresta_destino.currentText()
        if origem and destino:
            self.ponto_intermediario_solicitado.emit(str(origem), str(destino), self._ponto())

    def _escolher_salvar(self) -> None:
        caminho, _ = QFileDialog.getSaveFileName(self, "Salvar mapeamento 3D", "mapeamento-3d.json", "JSON (*.json)")
        if caminho:
            self.salvar_solicitado.emit(str(Path(caminho)))

    def _escolher_carregar(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Carregar mapeamento 3D", "", "JSON (*.json)")
        if caminho:
            self.carregar_solicitado.emit(str(Path(caminho)))


__all__ = ["PainelCalibracao3D"]
