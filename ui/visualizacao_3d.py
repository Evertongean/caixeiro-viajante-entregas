"""Widget Qt Quick 3D responsável somente pela cena e pela câmera."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

from PySide6 import QtQuick3D  # noqa: F401 - registra os tipos QML
from PySide6.QtCore import QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QVector3D
from PySide6.QtQuickWidgets import QQuickWidget

from .assets_3d import (
    ESCALA_CARRO_PADRAO,
    ESCALA_CIDADE_PADRAO,
    ConversorBalsam,
    ErroModelo3D,
    InformacoesModelo3D,
    caminho_modelo,
    inspecionar_modelo,
)
from .camera_orbital import CameraOrbital, ModoCamera


class ErroRenderizacao3D(RuntimeError):
    """Erro de inicialização explicado para evitar uma tela escura silenciosa."""


class Visualizacao3D(QQuickWidget):
    """Cena dos GLBs existentes com navegação orbital controlada em Python."""

    estado_alterado = Signal(str, bool)
    camera_alterada = Signal(str)
    ponto_selecionado = Signal(float, float, float, str, str, bool)

    def __init__(
        self,
        parent=None,
        *,
        caminho_cidade: str | os.PathLike[str] | None = None,
        caminho_carro: str | os.PathLike[str] | None = None,
        conversor: ConversorBalsam | None = None,
        auto_inicializar: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("visualizacao3D")
        self.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.setClearColor("#07111f")
        self.setMinimumSize(560, 380)
        self.setMouseTracking(True)

        self.caminho_cidade = Path(
            caminho_cidade or caminho_modelo("cidade.glb")
        ).resolve()
        self.caminho_carro = Path(
            caminho_carro or caminho_modelo("carro.glb")
        ).resolve()
        self.conversor = conversor
        self.camera = CameraOrbital()
        self.info_cidade: InformacoesModelo3D | None = None
        self.info_carro: InformacoesModelo3D | None = None
        self.posicao_carro = (0.0, 0.0, 0.0)
        self.escala_cidade = ESCALA_CIDADE_PADRAO
        self.escala_carro = ESCALA_CARRO_PADRAO
        self.inicializado = False
        self.modelos_preparados = False
        self.erro_inicializacao: str | None = None
        self.diagnosticos: list[str] = []
        self._auto_inicializar = bool(auto_inicializar)
        self._inicializacao_agendada = False
        self._posicao_mouse = None
        self._botao_mouse = None
        self._mouse_arrastou = False
        self._modo_interacao = "navegar"

    @property
    def referencias_modelos(self) -> tuple[Path, Path]:
        return self.caminho_cidade, self.caminho_carro

    @property
    def area_valida(self) -> bool:
        raiz = self.rootObject()
        return bool(
            self.width() > 0
            and self.height() > 0
            and raiz is not None
            and raiz.width() > 0
            and raiz.height() > 0
        )

    @property
    def modelos_visiveis_na_cena(self) -> bool:
        raiz = self.rootObject()
        return bool(raiz is not None and int(raiz.property("modelosProntos") or 0) == 2)

    @property
    def renderizacao_real_disponivel(self) -> bool:
        """Distingue uma cena QML válida de um backend 3D realmente utilizável."""
        backend = self.diagnostico_backend().casefold()
        return bool(
            backend
            and backend not in {"software", "unknown", "null", "indisponível"}
        )

    def showEvent(self, evento) -> None:  # noqa: N802 - API Qt
        super().showEvent(evento)
        if self._auto_inicializar and not self._inicializacao_agendada:
            self._inicializacao_agendada = True
            QTimer.singleShot(0, self.inicializar)

    def _registrar(self, mensagem: str, ok: bool = True) -> None:
        self.diagnosticos.append(mensagem)
        self.estado_alterado.emit(mensagem, ok)

    def inicializar(self) -> None:
        """Carrega a cena visível, converte os GLBs e aplica o enquadramento."""
        if self.inicializado:
            return
        if not self.isVisible() or self.width() <= 0 or self.height() <= 0:
            self._registrar("Aguardando uma área 3D visível e dimensionada…")
            QTimer.singleShot(30, self.inicializar)
            return
        try:
            self._registrar("Inicializando o renderizador Qt Quick 3D…")
            qml = Path(__file__).with_name("cena_3d.qml")
            self.setSource(QUrl.fromLocalFile(str(qml)))
            if self.status() != QQuickWidget.Status.Ready or self.rootObject() is None:
                detalhes = "; ".join(erro.toString() for erro in self.errors())
                raise ErroRenderizacao3D(
                    detalhes or "A raiz QML da cena 3D não foi criada."
                )
            if not self.area_valida:
                raise ErroRenderizacao3D("A View3D foi criada sem dimensões utilizáveis.")

            self.info_cidade = inspecionar_modelo(self.caminho_cidade)
            self.info_carro = inspecionar_modelo(self.caminho_carro)
            conversor = self.conversor or ConversorBalsam()
            self.conversor = conversor
            self._registrar("Preparando cidade.glb e carro.glb no cache Balsam…")
            cidade = conversor.converter(self.caminho_cidade)
            carro = conversor.converter(self.caminho_carro)
            raiz = self.rootObject()
            if raiz is None:
                raise ErroRenderizacao3D("A cena QML foi perdida durante a conversão.")
            raiz.setProperty("cidadeFonte", QUrl.fromLocalFile(str(cidade.qml)))
            raiz.setProperty("carroFonte", QUrl.fromLocalFile(str(carro.qml)))
            raiz.setProperty("escalaCidade", self.escala_cidade)
            raiz.setProperty("escalaCarro", self.escala_carro)
            self._configurar_carro_inicial()
            self.enquadrar_cidade()
            self.modelos_preparados = True
            self.inicializado = True
            sinal = getattr(raiz, "modelosProntosChanged", None)
            if sinal is not None:
                sinal.connect(self._atualizar_estado_modelos)
            sinal_pick = getattr(raiz, "pontoSelecionado", None)
            if sinal_pick is not None:
                sinal_pick.connect(self._receber_pick)
            QTimer.singleShot(0, self._atualizar_estado_modelos)
            self._registrar(
                "Modelos preparados; aguardando a materialização gráfica da cena."
            )
        except (ErroModelo3D, ErroRenderizacao3D, OSError) as erro:
            self.erro_inicializacao = str(erro)
            self._registrar(f"Falha na cena 3D: {erro}", False)

    def _atualizar_estado_modelos(self) -> None:
        if self.modelos_visiveis_na_cena:
            if self.renderizacao_real_disponivel:
                self._registrar("Cidade e carro carregados na cena 3D.")
            else:
                self._registrar(
                    "Modelos carregados; o backend atual não oferece renderização 3D real.",
                    False,
                )

    def _configurar_carro_inicial(self) -> None:
        if self.info_cidade is None or self.info_carro is None:
            return
        cidade = self.info_cidade.limites
        carro = self.info_carro.limites
        dimensoes_cidade = cidade.dimensoes
        # A posição de preview é derivada da própria caixa da cidade: o ponto
        # escolhido fica sobre a malha viária deste asset, sem acoplar o
        # renderizador às coordenadas futuras do grafo.
        self.posicao_carro = (
            (cidade.minimo[0] + dimensoes_cidade[0] * 0.58)
            * self.escala_cidade,
            (cidade.minimo[1] + dimensoes_cidade[1] * 0.062)
            * self.escala_cidade,
            (cidade.minimo[2] + dimensoes_cidade[2] * 0.20)
            * self.escala_cidade,
        )
        raiz = self.rootObject()
        if raiz is not None:
            raiz.setProperty("posicaoCarro", QVector3D(*self.posicao_carro))
            raiz.setProperty("centroModeloCarro", QVector3D(*carro.centro))
            raiz.setProperty("minimoModeloCarro", QVector3D(*carro.minimo))
            raiz.setProperty("alturaCarro", 0.008)

    def _aplicar_camera(self) -> None:
        raiz = self.rootObject()
        if raiz is None:
            return
        raiz.setProperty("centroCamera", QVector3D(*self.camera.centro))
        raiz.setProperty("cameraYaw", self.camera.yaw)
        raiz.setProperty("cameraPitch", self.camera.pitch)
        raiz.setProperty("cameraDistancia", self.camera.distancia)
        raiz.setProperty("cameraModo", self.camera.modo.value)
        self.camera_alterada.emit(self.camera.modo.value)

    def enquadrar_cidade(self) -> None:
        if self.info_cidade is None:
            return
        limites = self.info_cidade.limites
        self.camera.enquadrar(
            limites.minimo,
            limites.maximo,
            escala=self.escala_cidade,
        )
        self._aplicar_camera()

    def visao_aerea(self) -> None:
        if self.info_cidade is None:
            return
        self.enquadrar_cidade()
        self.camera.visao_aerea()
        self._aplicar_camera()

    def focar_carro(self) -> None:
        if self.info_carro is None:
            return
        dimensoes = tuple(
            valor * self.escala_carro
            for valor in self.info_carro.limites.dimensoes
        )
        centro = (
            self.posicao_carro[0],
            self.posicao_carro[1] + dimensoes[1] * 0.5 + 0.008,
            self.posicao_carro[2],
        )
        self.camera.focar(centro, dimensoes)
        self._aplicar_camera()

    def camera_livre(self) -> None:
        self.camera.modo = ModoCamera.LIVRE
        self._aplicar_camera()

    def camera_atras_do_carro(self) -> None:
        self.camera.preparar_camera_atras_do_carro(self.posicao_carro)
        self._aplicar_camera()

    def definir_modo_interacao(self, modo: str) -> None:
        if modo not in {
            "navegar",
            "adicionar_ponto",
            "criar_rua",
            "classificar_superficie",
            "reposicionar_vertice",
        }:
            raise ValueError(f"Modo de interação desconhecido: {modo}")
        self._modo_interacao = modo
        raiz = self.rootObject()
        if raiz is not None:
            raiz.setProperty("modoInteracao", modo)
        self.setCursor(
            Qt.CursorShape.ArrowCursor
            if modo == "navegar"
            else Qt.CursorShape.CrossCursor
        )

    def _receber_pick(
        self,
        x: float,
        y: float,
        z: float,
        objeto: str,
        material: str,
        encontrado: bool,
    ) -> None:
        self.ponto_selecionado.emit(
            float(x),
            float(y),
            float(z),
            str(objeto),
            str(material),
            bool(encontrado),
        )

    def solicitar_pick(self, x: float, y: float) -> None:
        raiz = self.rootObject()
        if raiz is None:
            return
        raiz.setProperty("pickY", -1.0)
        raiz.setProperty("pickX", float(x))
        raiz.setProperty("pickY", float(y))

    def atualizar_marcadores(self, marcadores: list[dict[str, object]]) -> None:
        raiz = self.rootObject()
        if raiz is not None:
            raiz.setProperty("marcadores", list(marcadores))

    def atualizar_ruas(self, segmentos: list[dict[str, object]]) -> None:
        raiz = self.rootObject()
        if raiz is not None:
            raiz.setProperty("segmentosRuas", list(segmentos))

    def atualizar_previa_rua(self, segmentos: list[dict[str, object]]) -> None:
        raiz = self.rootObject()
        if raiz is not None:
            raiz.setProperty("segmentosPrevia", list(segmentos))

    def atualizar_destaque_rota(
        self,
        segmentos: list[dict[str, object]],
        marcadores: list[dict[str, object]],
    ) -> None:
        raiz = self.rootObject()
        if raiz is not None:
            raiz.setProperty("segmentosRota", list(segmentos))
            raiz.setProperty("marcadoresRota", list(marcadores))

    def limpar_destaque_rota(self) -> None:
        self.atualizar_destaque_rota([], [])

    def enquadrar_pontos(self, pontos: Sequence[Sequence[float]]) -> bool:
        pontos3 = [tuple(float(valor) for valor in ponto) for ponto in pontos]
        if not pontos3 or any(len(ponto) != 3 for ponto in pontos3):
            return False
        minimo = tuple(min(ponto[eixo] for ponto in pontos3) for eixo in range(3))
        maximo = tuple(max(ponto[eixo] for ponto in pontos3) for eixo in range(3))
        centro = tuple((minimo[eixo] + maximo[eixo]) * 0.5 for eixo in range(3))
        dimensoes = tuple(
            max(maximo[eixo] - minimo[eixo], 0.04) for eixo in range(3)
        )
        self.camera.focar(centro, dimensoes)
        self._aplicar_camera()
        return True

    def mostrar_marcador_temporario(
        self, posicao: tuple[float, float, float] | None
    ) -> None:
        raiz = self.rootObject()
        if raiz is None:
            return
        raiz.setProperty("marcadorTemporarioVisivel", posicao is not None)
        if posicao is not None:
            raiz.setProperty("marcadorTemporarioPosicao", QVector3D(*posicao))

    def orbitar(self, delta_x: float, delta_y: float) -> None:
        self.camera.orbitar(delta_x, delta_y)
        self._aplicar_camera()

    def deslocar(self, delta_x: float, delta_y: float) -> None:
        self.camera.deslocar(delta_x, delta_y)
        self._aplicar_camera()

    def zoom(self, passos: float) -> None:
        self.camera.zoom(passos)
        self._aplicar_camera()

    def mousePressEvent(self, evento) -> None:  # noqa: N802 - API Qt
        if evento.button() in (
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.RightButton,
        ):
            self._posicao_mouse = evento.position()
            self._botao_mouse = evento.button()
            self._mouse_arrastou = False
            evento.accept()
            return
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802 - API Qt
        if self._posicao_mouse is not None and self._botao_mouse is not None:
            delta = evento.position() - self._posicao_mouse
            self._posicao_mouse = evento.position()
            if abs(delta.x()) + abs(delta.y()) > 2:
                self._mouse_arrastou = True
            if (
                self._botao_mouse == Qt.MouseButton.LeftButton
                and self._modo_interacao == "navegar"
            ):
                self.orbitar(delta.x(), delta.y())
            elif self._botao_mouse == Qt.MouseButton.RightButton:
                self.deslocar(delta.x(), delta.y())
            evento.accept()
            return
        super().mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802 - API Qt
        if evento.button() == self._botao_mouse:
            posicao = evento.position()
            deve_selecionar = (
                evento.button() == Qt.MouseButton.LeftButton
                and not self._mouse_arrastou
            )
            self._posicao_mouse = None
            self._botao_mouse = None
            self._mouse_arrastou = False
            if deve_selecionar:
                self.solicitar_pick(posicao.x(), posicao.y())
            evento.accept()
            return
        super().mouseReleaseEvent(evento)

    def wheelEvent(self, evento) -> None:  # noqa: N802 - API Qt
        passos = evento.angleDelta().y() / 120.0
        if passos:
            self.zoom(passos)
            evento.accept()
            return
        super().wheelEvent(evento)

    def diagnostico_backend(self) -> str:
        try:
            janela = self.quickWindow()
            interface = janela.rendererInterface() if janela else None
            api = interface.graphicsApi() if interface else None
            return getattr(api, "name", str(api))
        except (AttributeError, RuntimeError):
            return "indisponível"


__all__ = ["ErroRenderizacao3D", "Visualizacao3D"]
