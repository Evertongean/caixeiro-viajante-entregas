"""Visualização matemática do grafo do Delivery Route."""

from __future__ import annotations

from math import hypot

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsLineItem,
    QGraphicsObject,
    QStyleOptionGraphicsItem,
    QWidget,
)

from models.grafo import Grafo

from .visualizacao_base import VisualizacaoBase, calcular_posicoes


class RotuloPeso(QGraphicsObject):
    """Etiqueta compacta para o peso de uma aresta."""

    def __init__(self, peso: float) -> None:
        super().__init__()
        self.texto = f"{peso:g} km"
        self.setZValue(5)

    def boundingRect(self) -> QRectF:  # noqa: N802
        return QRectF(-26, -12, 52, 24)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#475569"), 1))
        painter.setBrush(QColor("#111827"))
        painter.drawRoundedRect(self.boundingRect(), 7, 7)
        painter.setPen(QColor("#E5E7EB"))
        fonte = QFont()
        fonte.setPointSize(8)
        fonte.setBold(True)
        painter.setFont(fonte)
        painter.drawText(self.boundingRect(), Qt.AlignmentFlag.AlignCenter, self.texto)


class VisualizadorGrafo(VisualizacaoBase):
    """Apresenta vértices, arestas e pesos em notação matemática."""

    def __init__(self, grafo: Grafo, parent: QWidget | None = None) -> None:
        super().__init__(grafo, parent)
        self.setObjectName("visualizadorGrafo")
        self.setBackgroundBrush(QColor("#121B29"))
        self.carregar_grafo(grafo)

    def _renderizar(self) -> None:
        posicoes = calcular_posicoes(self.grafo)
        if not posicoes:
            self._cena.setSceneRect(QRectF(-400, -260, 800, 520))
            return

        for aresta in self.grafo.listar_arestas():
            origem = posicoes[aresta.origem.identificador]
            destino = posicoes[aresta.destino.identificador]
            linha = QGraphicsLineItem(origem.x(), origem.y(), destino.x(), destino.y())
            linha.setPen(QPen(QColor("#64748B"), 3))
            linha.setZValue(0)
            self._cena.addItem(linha)

            destaque = QGraphicsLineItem(
                origem.x(), origem.y(), destino.x(), destino.y()
            )
            caneta_destaque = QPen(QColor("#10B981"), 7)
            caneta_destaque.setCapStyle(Qt.PenCapStyle.RoundCap)
            destaque.setPen(caneta_destaque)
            destaque.setZValue(2)
            self._registrar_destaque_aresta(
                aresta.origem.identificador,
                aresta.destino.identificador,
                destaque,
            )

            meio = QPointF((origem.x() + destino.x()) / 2, (origem.y() + destino.y()) / 2)
            dx = destino.x() - origem.x()
            dy = destino.y() - origem.y()
            comprimento = hypot(dx, dy) or 1
            deslocamento = QPointF(-dy / comprimento * 16, dx / comprimento * 16)
            rotulo = RotuloPeso(aresta.peso)
            rotulo.setPos(meio + deslocamento)
            self._cena.addItem(rotulo)

        for vertice in self.grafo.listar_vertices():
            self._adicionar_vertice(vertice, posicoes[vertice.identificador], "grafo")

        limites = self._cena.itemsBoundingRect().adjusted(-100, -90, 100, 90)
        self._cena.setSceneRect(limites)
        self.restaurar_enquadramento()
