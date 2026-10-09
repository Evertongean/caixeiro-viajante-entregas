"""Visualização estilizada do grafo como mapa de uma cidade."""

from __future__ import annotations

from math import floor

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsLineItem, QWidget

from models.grafo import Grafo

from .visualizacao_base import VisualizacaoBase, calcular_posicoes


class MapaCidade(VisualizacaoBase):
    """Apresenta arestas como ruas e vértices como marcadores logísticos."""

    def __init__(self, grafo: Grafo, parent: QWidget | None = None) -> None:
        super().__init__(grafo, parent)
        self.setObjectName("mapaCidade")
        self.carregar_grafo(grafo)

    def _renderizar(self) -> None:
        posicoes = calcular_posicoes(self.grafo)
        if not posicoes:
            self._cena.setSceneRect(QRectF(-400, -260, 800, 520))
            return

        for aresta in self.grafo.listar_arestas():
            origem = posicoes[aresta.origem.identificador]
            destino = posicoes[aresta.destino.identificador]

            contorno = QGraphicsLineItem(origem.x(), origem.y(), destino.x(), destino.y())
            caneta_contorno = QPen(QColor("#1E293B"), 20)
            caneta_contorno.setCapStyle(Qt.PenCapStyle.RoundCap)
            contorno.setPen(caneta_contorno)
            contorno.setZValue(-8)
            self._cena.addItem(contorno)

            rua = QGraphicsLineItem(origem.x(), origem.y(), destino.x(), destino.y())
            caneta_rua = QPen(QColor("#475569"), 13)
            caneta_rua.setCapStyle(Qt.PenCapStyle.RoundCap)
            rua.setPen(caneta_rua)
            rua.setToolTip(
                f"{aresta.origem.nome} ↔ {aresta.destino.nome}\n"
                f"Distância: {aresta.peso:g} km"
            )
            rua.setZValue(-7)
            self._cena.addItem(rua)

            faixa = QGraphicsLineItem(origem.x(), origem.y(), destino.x(), destino.y())
            caneta_faixa = QPen(QColor("#94A3B8"), 1)
            caneta_faixa.setStyle(Qt.PenStyle.DashLine)
            faixa.setPen(caneta_faixa)
            faixa.setZValue(-6)
            self._cena.addItem(faixa)

            destaque = QGraphicsLineItem(
                origem.x(), origem.y(), destino.x(), destino.y()
            )
            caneta_destaque = QPen(QColor("#10B981"), 9)
            caneta_destaque.setCapStyle(Qt.PenCapStyle.RoundCap)
            destaque.setPen(caneta_destaque)
            destaque.setZValue(-5)
            self._registrar_destaque_aresta(
                aresta.origem.identificador,
                aresta.destino.identificador,
                destaque,
            )

        for vertice in self.grafo.listar_vertices():
            self._adicionar_vertice(vertice, posicoes[vertice.identificador], "cidade")

        limites = self._cena.itemsBoundingRect().adjusted(-65, -55, 65, 55)
        self._cena.setSceneRect(limites)
        self.restaurar_enquadramento()

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        painter.fillRect(rect, QColor("#101923"))
        tamanho = 150
        inicio_x = floor(rect.left() / tamanho) * tamanho
        inicio_y = floor(rect.top() / tamanho) * tamanho
        painter.setPen(QPen(QColor("#253247"), 1))
        for x in range(int(inicio_x), int(rect.right()) + tamanho, tamanho):
            for y in range(int(inicio_y), int(rect.bottom()) + tamanho, tamanho):
                bloco = QRectF(x + 16, y + 16, tamanho - 32, tamanho - 32)
                if ((x // tamanho) + (y // tamanho)) % 7 == 0:
                    painter.setBrush(QColor("#173A32"))
                    painter.setPen(QPen(QColor("#225746"), 1))
                else:
                    painter.setBrush(QColor("#182436"))
                    painter.setPen(QPen(QColor("#26364D"), 1))
                painter.drawRoundedRect(bloco, 8, 8)
