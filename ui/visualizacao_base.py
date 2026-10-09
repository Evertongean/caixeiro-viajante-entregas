"""Componentes compartilhados pelas visualizações de cidade e grafo."""

from __future__ import annotations

from math import cos, pi, sin

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsLineItem,
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
    QStyleOptionGraphicsItem,
    QWidget,
)

from models.grafo import Grafo, TipoVertice, Vertice

from .estilos import AMARELO, AZUL, AZUL_CLARO, TEXTO, VERDE


CORES_VERTICES = {
    TipoVertice.DEPOSITO: AZUL,
    TipoVertice.CLIENTE: VERDE,
    TipoVertice.CRUZAMENTO: "#64748B",
}


class ItemVertice(QGraphicsObject):
    """Vértice clicável compartilhado pelos dois modos de visualização."""

    clicado = Signal(str)

    def __init__(self, vertice: Vertice, *, modo: str) -> None:
        super().__init__()
        self.vertice = vertice
        self.modo = modo
        self._selecionado = False
        self._sob_mouse = False
        self._papel_rota: str | None = None
        self._papel_passo: str | None = None
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(
            f"{vertice.nome}\nID: {vertice.identificador}\n"
            f"Tipo: {vertice.tipo.value}"
        )
        self.setZValue(20)

    def boundingRect(self) -> QRectF:  # noqa: N802 - contrato do Qt
        if self.modo == "cidade":
            return QRectF(-24, -24, 210, 52)
        return QRectF(-88, -32, 176, 86)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cor = QColor(CORES_VERTICES[self.vertice.tipo])
        if self._sob_mouse:
            cor = cor.lighter(118)
        cores_papel = {
            "origem": AZUL_CLARO,
            "destino": "#F97316",
            "rota": VERDE,
        }
        cor_contorno = AMARELO if self._selecionado else cores_papel.get(
            self._papel_rota,
            {"atual": "#F59E0B", "processado": "#A78BFA"}.get(
                self._papel_passo, "#E5E7EB"
            ),
        )
        contorno = QColor(cor_contorno)
        largura = 4 if self._selecionado or self._papel_rota else 2
        painter.setPen(QPen(contorno, largura))
        painter.setBrush(cor)

        if self.modo == "cidade":
            painter.drawEllipse(QRectF(-16, -16, 32, 32))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#F8FAFC"))
            painter.drawEllipse(QRectF(-5, -5, 10, 10))

            painter.setPen(QPen(QColor("#334155"), 1))
            painter.setBrush(QColor(15, 23, 42, 225))
            painter.drawRoundedRect(QRectF(24, -15, 155, 30), 7, 7)
            painter.setPen(QColor(TEXTO))
            fonte = QFont()
            fonte.setPointSize(9)
            fonte.setBold(self.vertice.tipo is TipoVertice.DEPOSITO)
            painter.setFont(fonte)
            painter.drawText(
                QRectF(34, -15, 135, 30),
                Qt.AlignmentFlag.AlignVCenter,
                self.vertice.nome,
            )
            return

        painter.drawEllipse(QRectF(-25, -25, 50, 50))
        painter.setPen(QColor("#FFFFFF"))
        fonte_id = QFont()
        fonte_id.setPointSize(11)
        fonte_id.setBold(True)
        painter.setFont(fonte_id)
        painter.drawText(
            QRectF(-25, -25, 50, 50),
            Qt.AlignmentFlag.AlignCenter,
            self.vertice.identificador,
        )
        painter.setPen(QColor(TEXTO))
        fonte_nome = QFont()
        fonte_nome.setPointSize(8)
        painter.setFont(fonte_nome)
        painter.drawText(
            QRectF(-85, 31, 170, 25),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            self.vertice.nome,
        )

    def definir_selecionado(self, selecionado: bool) -> None:
        self._selecionado = selecionado
        self.update()

    def definir_papel_rota(self, papel: str | None) -> None:
        """Define o destaque do vértice sem interferir na seleção manual."""
        if papel not in {None, "origem", "destino", "rota"}:
            raise ValueError("Papel visual de rota inválido.")
        self._papel_rota = papel
        self.update()

    def definir_papel_passo(self, papel: str | None) -> None:
        """Define o papel temporário de um vértice durante uma etapa."""
        if papel not in {None, "atual", "processado"}:
            raise ValueError("Papel visual de etapa inválido.")
        self._papel_passo = papel
        self.update()

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicado.emit(self.vertice.identificador)
            event.accept()
            return
        super().mousePressEvent(event)

    def hoverEnterEvent(self, event) -> None:  # noqa: N802, ANN001
        self._sob_mouse = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802, ANN001
        self._sob_mouse = False
        self.update()
        super().hoverLeaveEvent(event)


class VisualizacaoBase(QGraphicsView):
    """Base com zoom, navegação e seleção sincronizável."""

    vertice_selecionado = Signal(str)

    def __init__(self, grafo: Grafo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._grafo = grafo
        self._itens_vertices: dict[str, ItemVertice] = {}
        self._itens_destaque_arestas: dict[
            frozenset[str], QGraphicsLineItem
        ] = {}
        self._rota_destacada: tuple[str, ...] = ()
        self._arestas_passo_destacadas: frozenset[frozenset[str]] = frozenset()
        self._vertices_passo_processados: frozenset[str] = frozenset()
        self._vertice_passo_atual: str | None = None
        self._selecionado_id: str | None = None
        self._cena = QGraphicsScene(self)
        self.setScene(self._cena)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    @property
    def grafo(self) -> Grafo:
        return self._grafo

    @property
    def selecionado_id(self) -> str | None:
        return self._selecionado_id

    @property
    def rota_destacada(self) -> tuple[str, ...]:
        return self._rota_destacada

    @property
    def arestas_destacadas(self) -> frozenset[frozenset[str]]:
        return frozenset(
            chave
            for chave, item in self._itens_destaque_arestas.items()
            if item.isVisible()
        )

    @property
    def arestas_passo_destacadas(self) -> frozenset[frozenset[str]]:
        return self._arestas_passo_destacadas

    @property
    def vertices_passo_processados(self) -> frozenset[str]:
        return self._vertices_passo_processados

    @property
    def vertice_passo_atual(self) -> str | None:
        return self._vertice_passo_atual

    def carregar_grafo(self, grafo: Grafo) -> None:
        if not isinstance(grafo, Grafo):
            raise TypeError("É necessário fornecer uma instância de Grafo.")
        self._grafo = grafo
        self._selecionado_id = None
        self._rota_destacada = ()
        self._arestas_passo_destacadas = frozenset()
        self._vertices_passo_processados = frozenset()
        self._vertice_passo_atual = None
        self._itens_vertices.clear()
        self._itens_destaque_arestas.clear()
        self._cena.clear()
        self._renderizar()

    def selecionar_vertice(
        self, identificador: str | None, *, emitir_sinal: bool = False
    ) -> None:
        if identificador is not None and identificador not in self._itens_vertices:
            raise KeyError(f"Não existe item visual para o vértice '{identificador}'.")
        if self._selecionado_id in self._itens_vertices:
            self._itens_vertices[self._selecionado_id].definir_selecionado(False)
        self._selecionado_id = identificador
        if identificador is not None:
            self._itens_vertices[identificador].definir_selecionado(True)
        if emitir_sinal and identificador is not None:
            self.vertice_selecionado.emit(identificador)

    def restaurar_enquadramento(self) -> None:
        limites = self._cena.sceneRect()
        if limites.isEmpty():
            return
        self.resetTransform()
        self.fitInView(limites, Qt.AspectRatioMode.KeepAspectRatio)

    def destacar_rota(self, percurso: list[str]) -> None:
        """Destaca apenas as conexões reais que compõem ``percurso``."""
        self.limpar_destaque_passo()
        self.limpar_destaque_rota()
        for identificador in percurso:
            if identificador not in self._itens_vertices:
                raise KeyError(
                    f"Não existe item visual para o vértice '{identificador}'."
                )

        for origem, destino in zip(percurso, percurso[1:]):
            if origem == destino:
                continue
            chave = frozenset((origem, destino))
            try:
                self._itens_destaque_arestas[chave].setVisible(True)
            except KeyError as erro:
                raise ValueError(
                    f"A rota contém uma conexão inexistente: "
                    f"'{origem}'–'{destino}'."
                ) from erro

        for identificador in dict.fromkeys(percurso):
            self._itens_vertices[identificador].definir_papel_rota("rota")
        if percurso:
            self._itens_vertices[percurso[0]].definir_papel_rota("origem")
        if len(percurso) > 1 and percurso[-1] != percurso[0]:
            self._itens_vertices[percurso[-1]].definir_papel_rota("destino")
        self._rota_destacada = tuple(percurso)

    def destacar_passo(
        self,
        *,
        vertice_atual: str | None = None,
        vertices_processados: frozenset[str] = frozenset(),
        arestas: tuple[tuple[str, str], ...] = (),
        caminho_final: tuple[str, ...] = (),
    ) -> None:
        """Aplica destaques temporários de uma etapa em qualquer visualização."""
        self.limpar_destaque_rota()
        self.limpar_destaque_passo()
        processados = frozenset(vertices_processados)
        for identificador in processados:
            if identificador not in self._itens_vertices:
                raise KeyError(f"Não existe item visual para o vértice '{identificador}'.")
            self._itens_vertices[identificador].definir_papel_passo("processado")
        if vertice_atual is not None:
            if vertice_atual not in self._itens_vertices:
                raise KeyError(f"Não existe item visual para o vértice '{vertice_atual}'.")
            self._itens_vertices[vertice_atual].definir_papel_passo("atual")

        caminho_chaves = {
            frozenset((origem, destino))
            for origem, destino in zip(caminho_final, caminho_final[1:])
            if origem != destino
        }
        chaves: set[frozenset[str]] = set()
        for origem, destino in arestas:
            chave = frozenset((origem, destino))
            if chave not in self._itens_destaque_arestas:
                continue
            item = self._itens_destaque_arestas[chave]
            caneta = item.pen()
            caneta.setColor(QColor("#10B981" if chave in caminho_chaves else "#F59E0B"))
            item.setPen(caneta)
            item.setVisible(True)
            chaves.add(chave)
        self._arestas_passo_destacadas = frozenset(chaves)
        self._vertices_passo_processados = processados
        self._vertice_passo_atual = vertice_atual

    def limpar_destaque_passo(self) -> None:
        """Remove somente os destaques temporários da sessão didática."""
        for item in self._itens_destaque_arestas.values():
            caneta = item.pen()
            caneta.setColor(QColor("#10B981"))
            item.setPen(caneta)
            item.setVisible(False)
        for item in self._itens_vertices.values():
            item.definir_papel_passo(None)
        self._arestas_passo_destacadas = frozenset()
        self._vertices_passo_processados = frozenset()
        self._vertice_passo_atual = None

    def limpar_destaque_rota(self) -> None:
        """Restaura arestas e vértices sem modificar o grafo."""
        for item in self._itens_destaque_arestas.values():
            item.setVisible(False)
        for item in self._itens_vertices.values():
            item.definir_papel_rota(None)
        self._rota_destacada = ()
        self.limpar_destaque_passo()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        fator_atual = self.transform().m11()
        fator = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        novo_fator = fator_atual * fator
        if 0.2 <= novo_fator <= 5.0:
            self.scale(fator, fator)
        event.accept()

    def _renderizar(self) -> None:
        raise NotImplementedError

    def _adicionar_vertice(self, vertice: Vertice, posicao: QPointF, modo: str) -> None:
        item = ItemVertice(vertice, modo=modo)
        item.setPos(posicao)
        item.clicado.connect(self._item_clicado)
        self._cena.addItem(item)
        self._itens_vertices[vertice.identificador] = item

    def _registrar_destaque_aresta(
        self,
        origem: str,
        destino: str,
        item: QGraphicsLineItem,
    ) -> None:
        chave = frozenset((origem, destino))
        item.setVisible(False)
        self._itens_destaque_arestas[chave] = item
        self._cena.addItem(item)

    def _item_clicado(self, identificador: str) -> None:
        self.selecionar_vertice(identificador)
        self.vertice_selecionado.emit(identificador)


def calcular_posicoes(grafo: Grafo) -> dict[str, QPointF]:
    """Transforma coordenadas do modelo em posições visuais sem alterá-las."""
    vertices = grafo.listar_vertices()
    if not vertices:
        return {}
    if len(vertices) == 1:
        return {vertices[0].identificador: QPointF(0, 0)}

    coordenadas = [(float(v.x), float(v.y)) for v in vertices]
    # Coordenadas coincidentes não são adequadas para interação; nesse caso,
    # aplica-se um arranjo circular somente na camada de apresentação.
    if len(set(coordenadas)) != len(coordenadas):
        raio = max(180.0, len(vertices) * 34.0)
        return {
            vertice.identificador: QPointF(
                raio * cos(2 * pi * indice / len(vertices) - pi / 2),
                raio * sin(2 * pi * indice / len(vertices) - pi / 2),
            )
            for indice, vertice in enumerate(vertices)
        }

    xs = [x for x, _ in coordenadas]
    ys = [y for _, y in coordenadas]
    amplitude_x = max(xs) - min(xs)
    amplitude_y = max(ys) - min(ys)

    def normalizar(valor: float, minimo: float, amplitude: float, alcance: float) -> float:
        if amplitude == 0:
            return 0.0
        return ((valor - minimo) / amplitude - 0.5) * alcance

    return {
        vertice.identificador: QPointF(
            normalizar(float(vertice.x), min(xs), amplitude_x, 720),
            normalizar(float(vertice.y), min(ys), amplitude_y, 440),
        )
        for vertice in vertices
    }
