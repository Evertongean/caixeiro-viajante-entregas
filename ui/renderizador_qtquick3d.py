"""Renderizador Qt Quick 3D e diagnóstico do backend gráfico.

O runtime do Qt Quick 3D não lê um ``.glb`` diretamente como geometria de um
``Model``. O arquivo precisa passar pelo importador Balsam, que gera a cena
QML, as malhas ``.mesh`` e os recursos de materiais/texturas usados pelo
runtime. Esta camada faz essa conversão uma única vez por versão do arquivo,
em um cache temporário, e só então monta a cena.

Além de evitar a tela preta silenciosa, o módulo expõe diagnósticos úteis para
a interface e para testes sem uma área de trabalho gráfica.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

try:  # pragma: no cover - depende do runtime gráfico
    from PySide6.QtCore import QCoreApplication, QMetaObject, QObject, QUrl, Qt, Signal
    from PySide6.QtGui import QVector3D
    from PySide6.QtQuickWidgets import QQuickWidget
    from PySide6 import QtQuick3D  # noqa: F401 - registra os tipos QML

    QT_QUICK3D_DISPONIVEL = True
except ImportError:  # pragma: no cover
    QCoreApplication = None  # type: ignore[assignment]
    QMetaObject = None  # type: ignore[assignment]
    QObject = None  # type: ignore[assignment]
    QUrl = None  # type: ignore[assignment]
    Qt = None  # type: ignore[assignment]
    Signal = None  # type: ignore[assignment]
    QVector3D = None  # type: ignore[assignment]
    QQuickWidget = None  # type: ignore[assignment]
    QT_QUICK3D_DISPONIVEL = False


LOGGER = logging.getLogger(__name__)


class ErroQtQuick3D(RuntimeError):
    """Erro explicado de inicialização, importação ou renderização."""


@dataclass(frozen=True, slots=True)
class DiagnosticoCena:
    """Resultado de uma verificação da cena Qt Quick 3D."""

    ok: bool
    mensagem: str
    backend: str
    modelos_com_geometria: int = 0
    modelos_encontrados: int = 0


@dataclass(frozen=True, slots=True)
class AssetQtQuick3D:
    """Cena importada pelo Balsam e pronta para ser usada por ``Loader3D``."""

    origem: Path
    arquivo_qml: Path
    diretorio: Path


def _encontrar_balsam() -> str | None:
    """Localiza o conversor da mesma instalação Python do aplicativo."""

    configurado = os.environ.get("DELIVERY_ROUTE_BALSAM")
    candidatos = [
        Path(configurado) if configurado else None,
        Path(sys.executable).with_name("pyside6-balsam"),
        Path(sys.executable).with_name("pyside6-balsam.exe"),
    ]
    encontrado = shutil.which("pyside6-balsam")
    if encontrado:
        candidatos.insert(0, Path(encontrado))
    for candidato in candidatos:
        if candidato and candidato.is_file() and os.access(candidato, os.X_OK):
            return str(candidato)
    return None


def _cache_asset(caminho: str | Path) -> AssetQtQuick3D:
    """Converte um GLB com Balsam e reutiliza o resultado enquanto ele não muda."""

    origem = Path(caminho).expanduser().resolve()
    if not origem.is_file():
        raise ErroQtQuick3D(f"Modelo GLB não encontrado: {origem}")
    try:
        estat = origem.stat()
    except OSError as erro:
        raise ErroQtQuick3D(f"Não foi possível ler o modelo GLB {origem}: {erro}") from erro
    chave = hashlib.sha256(
        f"{origem}\0{estat.st_size}\0{estat.st_mtime_ns}".encode("utf-8")
    ).hexdigest()[:16]
    # O nome contém o arquivo original: isso facilita localizar recursos nos
    # diagnósticos sem misturar as duas conversões.
    pasta = Path(tempfile.gettempdir()) / "delivery-route-balsam" / f"{origem.name}-{chave}"
    qml_existente = sorted(pasta.glob("*.qml")) if pasta.is_dir() else []
    if qml_existente:
        return AssetQtQuick3D(origem, qml_existente[0], pasta)

    balsam = _encontrar_balsam()
    if balsam is None:
        raise ErroQtQuick3D(
            "Qt Quick 3D foi encontrado, mas o conversor pyside6-balsam não está "
            "disponível. Instale os utilitários da mesma versão do PySide6."
        )
    pasta.parent.mkdir(parents=True, exist_ok=True)
    temporaria = pasta.parent / f".{pasta.name}.tmp-{os.getpid()}"
    temporaria.mkdir(parents=True, exist_ok=True)
    comando = [balsam, "-o", str(temporaria), str(origem)]
    LOGGER.info("Qt Quick 3D: convertendo %s com Balsam", origem)
    try:
        processo = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as erro:
        raise ErroQtQuick3D(f"Falha ao iniciar o importador Balsam para {origem.name}: {erro}") from erro
    if processo.returncode != 0:
        saida = (processo.stderr or processo.stdout or "sem detalhes").strip()
        raise ErroQtQuick3D(
            f"Balsam não conseguiu importar {origem.name} (código {processo.returncode}): {saida}"
        )
    gerados = sorted(temporaria.glob("*.qml"))
    if not gerados:
        saida = (processo.stdout or processo.stderr or "nenhum QML foi gerado").strip()
        raise ErroQtQuick3D(f"Balsam não gerou uma cena QML para {origem.name}: {saida}")
    # Não sobrescreve um cache válido de outra instância. replace é atômico no
    # mesmo sistema de arquivos e o diretório é sempre temporário.
    try:
        temporaria.replace(pasta)
    except FileExistsError:
        pass
    qml_final = sorted(pasta.glob("*.qml"))
    if not qml_final:
        raise ErroQtQuick3D(f"Cache do Balsam ficou incompleto para {origem.name}")
    LOGGER.info("Qt Quick 3D: cena importada disponível em %s", qml_final[0])
    return AssetQtQuick3D(origem, qml_final[0], pasta)


def _processar_eventos() -> None:
    if QCoreApplication is not None and QCoreApplication.instance() is not None:
        QCoreApplication.processEvents()


def _backend_descricao() -> str:
    plataforma = os.environ.get("QT_QPA_PLATFORM") or "padrão do Qt"
    display = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") or "sem DISPLAY"
    return f"Qt Quick 3D; plataforma={plataforma}; display={display}"


def testar_cena_minima(parent=None) -> DiagnosticoCena:
    """Verifica um cubo, câmera e luz antes de tentar importar os modelos."""

    if not QT_QUICK3D_DISPONIVEL or QQuickWidget is None:
        return DiagnosticoCena(False, "Qt Quick 3D não está instalado", _backend_descricao())
    if QCoreApplication is None or QCoreApplication.instance() is None:
        return DiagnosticoCena(
            False,
            "QApplication ainda não foi inicializada; a cena mínima não pode ser testada",
            _backend_descricao(),
        )
    widget = QQuickWidget(parent)
    widget.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    widget.setSource(QUrl.fromLocalFile(str(Path(__file__).with_name("qtquick3d_cubo.qml"))))
    _processar_eventos()
    if widget.status() != QQuickWidget.Status.Ready or widget.rootObject() is None:
        erro = "; ".join(item.toString() for item in widget.errors()) or "QML não ficou pronto"
        widget.close()
        return DiagnosticoCena(False, f"cena mínima falhou ao carregar: {erro}", _backend_descricao())
    objetos = widget.rootObject().findChildren(QObject)
    modelos = [obj for obj in objetos if obj.metaObject().className() == "QQuick3DModel"]
    geometria = 0
    fontes: list[str] = []
    for modelo in modelos:
        try:
            if modelo.property("geometry") is not None:
                geometria += 1
        except (AttributeError, RuntimeError):
            # O ponteiro QQuick3DGeometry não tem conversor PySide6 em
            # algumas versões; a fonte #Cube continua sendo verificável.
            pass
        try:
            fontes.append(str(modelo.property("source")))
        except (AttributeError, RuntimeError):
            fontes.append("")
    # O backend offscreen aceita a cena e a fonte #Cube, mas não cria o
    # objeto QRhiGeometry. Isso não é uma falha do QML; a confirmação visual
    # continua exigindo um backend real (xcb/Wayland).
    estrutura = bool(modelos and any("#Cube" in fonte for fonte in fontes))
    ok = bool(geometria or estrutura)
    if ok and geometria:
        mensagem = f"cena mínima OK: cubo configurado ({geometria}/{len(modelos)} geometria(s) materializada)"
    elif ok:
        # ``geometry`` é nulo para primitivas nativas (#Cube) mesmo quando o
        # renderizador já consegue desenhá-las; não confundir a ausência do
        # conversor PySide6 com ausência de geometria na cena.
        mensagem = (
            "cena mínima OK: cubo com fonte nativa #Cube configurado "
            "(a propriedade geometry não é exposta pelo binding PySide6)"
        )
    else:
        mensagem = "cena mínima carregou, mas o cubo não recebeu fonte de geometria"
    widget.close()
    return DiagnosticoCena(ok, mensagem, _backend_descricao(), geometria, len(modelos))


class RenderizadorQtQuick3D(QQuickWidget):
    """Widget de cena que importa GLBs e os carrega via ``Loader3D``."""

    # A ponte fica no QWidget que realmente recebe os eventos, não no
    # ``Cidade3DWidget`` que está abaixo do QQuickWidget.  Os sinais mantêm o
    # renderizador independente do controlador orbital e são fáceis de testar
    # sem sintetizar eventos QML.
    mouse_orbitado = Signal(float, float)
    mouse_deslocado = Signal(float, float)
    mouse_zoom = Signal(float)
    # Clique simples separado dos gestos de câmera. O ponto é produzido pelo
    # ``View3D.pick`` no QML, portanto representa a posição real atingida na
    # geometria importada (e não uma projeção 2D aproximada).
    ponto_clicado = Signal(float, float, float, str, bool)

    def __init__(self, parent=None) -> None:
        if not QT_QUICK3D_DISPONIVEL or QQuickWidget is None:
            raise ErroQtQuick3D("Qt Quick 3D não está disponível nesta instalação")
        super().__init__(parent)
        self.setObjectName("cenaGLBQtQuick3D")
        self.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.setClearColor("#101827")
        self._diagnosticos: list[str] = [_backend_descricao()]
        self._ultimo_backend_api: str | None = None
        self._ultima_visibilidade: tuple[bool, bool, bool, bool] | None = None
        self._ultima_dimensao_diagnosticada: tuple[int, int, float, float, float, float] | None = None
        self._frames_antes = 0
        self._frames_depois = 0
        self._mouse_posicao_anterior = None
        self._mouse_arrastando = False
        self._mouse_botao = None
        self._asset_cidade: AssetQtQuick3D | None = None
        self._asset_carro: AssetQtQuick3D | None = None
        self._diagnostico_minimo = testar_cena_minima(self)
        self._registrar(self._diagnostico_minimo.mensagem)
        arquivo_qml = Path(__file__).with_name("glb_scene.qml")
        self._registrar(f"carregando QML principal: {arquivo_qml}")
        self.setSource(QUrl.fromLocalFile(str(arquivo_qml)))
        _processar_eventos()
        if self.status() != QQuickWidget.Status.Ready or self.rootObject() is None:
            erros = "; ".join(erro.toString() for erro in self.errors())
            mensagem = erros or "não foi possível criar a cena Qt Quick 3D"
            self._registrar(f"erro ao carregar QML: {mensagem}")
            raise ErroQtQuick3D(mensagem)
        self._registrar("QML principal carregado com sucesso")
        self._conectar_sinais_renderizacao()
        self._conectar_sinal_picking()
        self._registrar_backend_efetivo()
        self._verificar_dimensoes()
        self._diagnosticar_cena_renderizacao()
        self.setMouseTracking(True)
        self._registrar("controles de câmera: eventos de mouse conectados ao QQuickWidget")
        # Offscreen não possui uma API gráfica 3D funcional. A cena ainda pode
        # ser validada, mas não deve esconder a projeção legada nos testes.
        if os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen":
            self.setVisible(False)

    def _registrar(self, mensagem: str) -> None:
        self._diagnosticos.append(mensagem)
        LOGGER.info("Qt Quick 3D: %s", mensagem)

    def _registrar_backend_efetivo(self) -> None:
        """Registra a API QRhi efetivamente escolhida pelo QQuickWindow."""

        try:
            janela = self.quickWindow()
            interface = janela.rendererInterface() if janela is not None else None
            api = interface.graphicsApi() if interface is not None else None
            nome = getattr(api, "name", str(api))
            if nome != self._ultimo_backend_api:
                self._ultimo_backend_api = nome
                self._registrar(f"backend gráfico efetivo: {nome}")
        except (AttributeError, RuntimeError) as erro:  # pragma: no cover - varia por Qt
            self._registrar(f"backend gráfico não pôde ser consultado: {erro}")

    def _conectar_sinais_renderizacao(self) -> None:
        """Conta molduras efetivamente iniciadas/finalizadas pelo QQuickWindow."""

        try:
            janela = self.quickWindow()
            if janela is None:
                self._registrar("renderização: QQuickWindow ainda não disponível")
                return
            janela.beforeRendering.connect(self._marcar_frame_antes)
            janela.afterRendering.connect(self._marcar_frame_depois)
            self._registrar("sinais de renderização conectados (beforeRendering/afterRendering)")
        except (AttributeError, RuntimeError) as erro:  # pragma: no cover - varia por Qt
            self._registrar(f"sinais de renderização indisponíveis: {erro}")

    def _conectar_sinal_picking(self) -> None:
        """Conecta o sinal QML que devolve o resultado do raycast da View3D."""

        raiz = self.rootObject()
        sinal = getattr(raiz, "pontoSelecionado", None) if raiz is not None else None
        if sinal is None:
            self._registrar("picking 3D: sinal QML indisponível")
            return
        try:
            sinal.connect(self._ponto_selecionado_qml)
            self._registrar("picking 3D: View3D.pick conectado")
        except (AttributeError, RuntimeError) as erro:  # pragma: no cover - varia no Qt
            self._registrar(f"picking 3D indisponível: {erro}")

    def _ponto_selecionado_qml(
        self, x: float, y: float, z: float, objeto: str, encontrado: bool
    ) -> None:
        self.ponto_clicado.emit(float(x), float(y), float(z), str(objeto), bool(encontrado))

    def _marcar_frame_antes(self) -> None:
        self._frames_antes += 1

    def _marcar_frame_depois(self) -> None:
        self._frames_depois += 1

    @staticmethod
    def _ler_propriedade(objeto: QObject | None, nome: str):
        if objeto is None:
            return None
        try:
            return objeto.property(nome)
        except (AttributeError, RuntimeError):
            return None

    def _encontrar_objeto(self, nome: str) -> QObject | None:
        raiz = self.rootObject()
        if raiz is None:
            return None
        if raiz.objectName() == nome:
            return raiz
        return next((obj for obj in raiz.findChildren(QObject) if obj.objectName() == nome), None)

    def _diagnosticar_cena_renderizacao(self) -> None:
        """Registra o estado que costuma produzir uma View3D escura.

        As propriedades de alguns tipos Qt Quick 3D não possuem conversor
        PySide6 (por exemplo ``renderStats``); por isso o diagnóstico nunca
        interrompe a criação do widget e informa explicitamente quando uma
        leitura não está disponível.
        """

        view = self._encontrar_objeto("view3dGLB")
        camera = self._encontrar_objeto("cameraGLB")
        janela = self.quickWindow()
        if janela is not None:
            try:
                visibilidade = janela.visibility().name
            except (AttributeError, RuntimeError):
                visibilidade = "desconhecida"
            self._registrar(
                f"janela de renderização: exposta={bool(janela.isExposed())}, visibilidade={visibilidade}"
            )
        modo = self._ler_propriedade(view, "renderMode")
        if modo is None:
            modo_texto = "não convertido pelo PySide6"
        else:
            modo_texto = str(modo)
        self._registrar(
            f"View3D: visível={bool(self._ler_propriedade(view, 'visible'))}, renderMode={modo_texto}"
        )
        if camera is not None:
            self._registrar(
                "câmera: posição=%s, clipNear=%s, clipFar=%s, visível=%s"
                % (
                    self._ler_propriedade(camera, "position"),
                    self._ler_propriedade(camera, "clipNear"),
                    self._ler_propriedade(camera, "clipFar"),
                    bool(self._ler_propriedade(camera, "visible")),
                )
            )
        self._registrar(
            f"molduras Qt: beforeRendering={self._frames_antes}, afterRendering={self._frames_depois}"
        )

    def diagnosticar_frame(self) -> dict[str, int | bool | str]:
        """Captura o framebuffer do QQuickWidget e procura pixels vermelhos.

        O contador não é uma prova de geometria em backend ``offscreen``:
        nesses ambientes o Qt pode produzir apenas a composição 2D. Ele é
        útil no desktop para confirmar que o cubo mínimo realmente chegou ao
        framebuffer exibido.
        """

        try:
            imagem = self.grabFramebuffer()
        except (AttributeError, RuntimeError) as erro:
            return {"disponivel": False, "erro": str(erro), "pixels_vermelhos": 0}
        if imagem.isNull():
            return {"disponivel": False, "erro": "framebuffer vazio", "pixels_vermelhos": 0}
        vermelhos = 0
        fundo = imagem.pixelColor(0, 0)
        fora_fundo = 0
        for y in range(imagem.height()):
            for x in range(imagem.width()):
                cor = imagem.pixelColor(x, y)
                if (
                    abs(cor.red() - fundo.red()) > 5
                    or abs(cor.green() - fundo.green()) > 5
                    or abs(cor.blue() - fundo.blue()) > 5
                ):
                    fora_fundo += 1
                if cor.alpha() > 0 and cor.red() >= 180 and cor.green() <= 110 and cor.blue() <= 110:
                    vermelhos += 1
        return {
            "disponivel": True,
            "largura": imagem.width(),
            "altura": imagem.height(),
            "pixels_vermelhos": vermelhos,
            "pixels_fora_fundo": fora_fundo,
            "frames_antes": self._frames_antes,
            "frames_depois": self._frames_depois,
        }

    def _verificar_dimensoes(self) -> None:
        """Registra separadamente widget, raiz QML e ``View3D``."""

        raiz = self.rootObject()
        view = None
        if raiz is not None:
            view = next(
                (
                    objeto
                    for objeto in raiz.findChildren(QObject)
                    if objeto.metaObject().className() == "QQuick3DViewport"
                ),
                None,
            )
        dimensoes = (
            self.width(),
            self.height(),
            float(raiz.width()) if raiz is not None else 0.0,
            float(raiz.height()) if raiz is not None else 0.0,
            float(view.width()) if view is not None else 0.0,
            float(view.height()) if view is not None else 0.0,
        )
        if dimensoes == self._ultima_dimensao_diagnosticada:
            return
        self._ultima_dimensao_diagnosticada = dimensoes
        prefixo = (
            "dimensões durante inicialização (transitório; ancestral oculto)"
            if any(valor <= 0 for valor in dimensoes)
            else "dimensões após layout (renderizador pronto)"
        )
        self._registrar(
            f"{prefixo}: widget Python=%dx%d; raiz QML=%.0fx%.0f; View3D=%.0fx%.0f"
            % dimensoes
        )

    def sincronizar_dimensoes(self) -> tuple[int, int, float, float, float, float]:
        """Atualiza eventos e retorna widget, raiz QML e View3D."""

        _processar_eventos()
        self._registrar_backend_efetivo()
        self._verificar_dimensoes()
        visibilidade = self.visibilidade_renderizacao
        estado_visibilidade = tuple(visibilidade[chave] for chave in ("widget", "ancestrais", "raiz_qml", "view3d"))
        if estado_visibilidade != self._ultima_visibilidade:
            self._ultima_visibilidade = estado_visibilidade
            self._registrar(
                "visibilidade: widget=%s, ancestrais=%s, raiz QML=%s, View3D=%s"
                % estado_visibilidade
            )
        raiz = self.rootObject()
        view = None
        if raiz is not None:
            view = next(
                (
                    objeto
                    for objeto in raiz.findChildren(QObject)
                    if objeto.metaObject().className() == "QQuick3DViewport"
                ),
                None,
            )
        return (
            self.width(),
            self.height(),
            float(raiz.width()) if raiz is not None else 0.0,
            float(raiz.height()) if raiz is not None else 0.0,
            float(view.width()) if view is not None else 0.0,
            float(view.height()) if view is not None else 0.0,
        )

    @property
    def dimensoes_renderizacao(self) -> dict[str, tuple[float, float]]:
        """Dimensões atuais de cada camada da integração QWidget/QML."""

        dimensoes = self.sincronizar_dimensoes()
        return {
            "widget_python": (float(dimensoes[0]), float(dimensoes[1])),
            "raiz_qml": (dimensoes[2], dimensoes[3]),
            "view3d": (dimensoes[4], dimensoes[5]),
        }

    @property
    def visibilidade_renderizacao(self) -> dict[str, bool]:
        """Visibilidade do widget, ancestrais Qt e itens QML principais."""

        raiz = self.rootObject()
        view = None
        if raiz is not None:
            view = next(
                (
                    objeto
                    for objeto in raiz.findChildren(QObject)
                    if objeto.metaObject().className() == "QQuick3DViewport"
                ),
                None,
            )
        ancestrais: list[bool] = []
        atual = self.parentWidget()
        while atual is not None:
            ancestrais.append(bool(atual.isVisible()))
            atual = atual.parentWidget()
        return {
            "widget": bool(self.isVisible()),
            "ancestrais": all(ancestrais) if ancestrais else True,
            "raiz_qml": bool(raiz is not None and raiz.isVisible()),
            "view3d": bool(view is not None and view.isVisible()),
        }

    def mousePressEvent(self, evento) -> None:  # noqa: N802 - contrato Qt
        """Inicia órbita/pan no widget que fica sobre a projeção 3D."""

        botoes_navegacao = Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton
        if evento.button() & botoes_navegacao:
            self._mouse_posicao_anterior = evento.position()
            self._mouse_botao = evento.button()
            self._mouse_arrastando = False
            self.setFocus()
            evento.accept()
            return
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802 - contrato Qt
        if self._mouse_posicao_anterior is not None and self._mouse_botao is not None:
            atual = evento.position()
            delta = atual - self._mouse_posicao_anterior
            if abs(delta.x()) + abs(delta.y()) > 0.0:
                self._mouse_arrastando = True
                if self._mouse_botao == Qt.MouseButton.RightButton:
                    self.mouse_deslocado.emit(float(delta.x()), float(delta.y()))
                elif evento.buttons() & Qt.MouseButton.LeftButton:
                    self.mouse_orbitado.emit(float(delta.x()), float(delta.y()))
                self._mouse_posicao_anterior = atual
                evento.accept()
                return
        super().mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802 - contrato Qt
        if self._mouse_botao is not None and evento.button() == self._mouse_botao:
            foi_clique = not self._mouse_arrastando and evento.button() == Qt.MouseButton.LeftButton
            posicao_clique = evento.position()
            self._mouse_posicao_anterior = None
            self._mouse_botao = None
            self._mouse_arrastando = False
            if foi_clique:
                self._solicitar_picking(float(posicao_clique.x()), float(posicao_clique.y()))
            evento.accept()
            return
        super().mouseReleaseEvent(evento)

    def _solicitar_picking(self, x: float, y: float) -> None:
        """Pede ao QML um raycast no pixel clicado."""

        raiz = self.rootObject()
        if raiz is None:
            return
        try:
            # Usar propriedades evita a dependência de Q_ARG/QGenericArgument,
            # que muda entre versões do binding PySide6.
            raiz.setProperty("pickY", -1.0)
            raiz.setProperty("pickX", float(x))
            raiz.setProperty("pickY", float(y))
        except (AttributeError, RuntimeError) as erro:  # pragma: no cover
            self._registrar(f"picking 3D falhou ao enviar coordenadas: {erro}")

    def wheelEvent(self, evento) -> None:  # noqa: N802 - contrato Qt
        delta = float(evento.angleDelta().y()) / 120.0
        if not delta:
            delta = float(evento.pixelDelta().y()) / 40.0
        if delta:
            self.mouse_zoom.emit(delta)
            evento.accept()
            return
        super().wheelEvent(evento)

    def resizeEvent(self, evento) -> None:  # noqa: N802 - contrato Qt
        super().resizeEvent(evento)
        self._verificar_dimensoes()

    @property
    def diagnosticos(self) -> tuple[str, ...]:
        return tuple(self._diagnosticos)

    @property
    def diagnostico_minimo(self) -> DiagnosticoCena:
        return self._diagnostico_minimo

    @property
    def renderizacao_ativa(self) -> bool:
        return os.environ.get("QT_QPA_PLATFORM", "").lower() not in {"offscreen", "minimal"}

    @property
    def mensagem_diagnostico(self) -> str:
        return " | ".join(self._diagnosticos)

    def _verificar_modelos(self) -> None:
        _processar_eventos()
        raiz = self.rootObject()
        if raiz is None:
            raise ErroQtQuick3D("raiz QML ausente após carregar os modelos")
        objetos = raiz.findChildren(QObject)
        modelos = [obj for obj in objetos if obj.metaObject().className() == "QQuick3DModel"]
        geometria = 0
        for modelo in modelos:
            try:
                if modelo.property("geometry") is not None:
                    geometria += 1
            except (AttributeError, RuntimeError):
                pass
        fontes_mesh = sum(".mesh" in str(modelo.property("source")) for modelo in modelos)
        loaders = [obj for obj in objetos if obj.metaObject().className() == "QQuick3DLoader"]
        erros_loader = []
        for loader in loaders:
            # Algumas versões do PySide6 não registram o conversor do enum
            # QQuick3DLoader::Status. O item carregado é uma verificação
            # equivalente e não depende desse conversor.
            try:
                item = loader.property("item")
            except RuntimeError:
                item = None
            if item is None and loader.property("source"):
                erros_loader.append(str(loader.property("source")))
            else:
                self._registrar(
                    f"Loader3D {loader.objectName() or '<sem nome>'}: "
                    f"{'carregado' if item is not None else 'sem fonte'}"
                )
        if erros_loader:
            raise ErroQtQuick3D("Loader3D falhou para: " + ", ".join(erros_loader))
        if len(modelos) < 2 or (geometria < 2 and fontes_mesh < 2):
            raise ErroQtQuick3D(
                f"modelos importados sem geometria renderizável ({geometria}/{len(modelos)}, "
                f"{fontes_mesh} malhas mesh); "
                "verifique o cache Balsam, as malhas e as texturas"
            )
        if geometria:
            self._registrar(f"modelos carregados: {geometria}/{len(modelos)} com geometria")
        else:
            self._registrar(
                f"modelos carregados: {fontes_mesh} fontes .mesh; geometria será materializada pelo backend gráfico"
            )

    def carregar_modelos(self, caminho_cidade: str | Path, caminho_carro: str | Path) -> None:
        raiz = self.rootObject()
        if raiz is None or QUrl is None:
            raise ErroQtQuick3D("cena Qt Quick 3D não inicializada")
        self._asset_cidade = _cache_asset(caminho_cidade)
        self._asset_carro = _cache_asset(caminho_carro)
        for asset in (self._asset_cidade, self._asset_carro):
            texto_qml = asset.arquivo_qml.read_text(encoding="utf-8")
            referencias = re.findall(
                r"(?:source|textureData\w*)\s*:\s*[\"]([^\"]+\.(?:mesh|png|jpg|jpeg|webp))",
                texto_qml,
                flags=re.IGNORECASE,
            )
            faltantes = [
                referencia
                for referencia in referencias
                if not (asset.arquivo_qml.parent / referencia).is_file()
            ]
            if faltantes:
                raise ErroQtQuick3D(
                    f"recursos ausentes na cena importada de {asset.origem.name}: "
                    + ", ".join(faltantes[:5])
                )
            meshes = list(asset.diretorio.glob("meshes/*.mesh"))
            mapas = list(asset.diretorio.glob("maps/*"))
            self._registrar(
                f"recursos {asset.origem.name}: {len(meshes)} malhas, {len(mapas)} textura(s)"
            )
        self._registrar(f"cidade importada: {self._asset_cidade.arquivo_qml}")
        self._registrar(f"carro importado: {self._asset_carro.arquivo_qml}")
        raiz.setProperty("cidadeFonte", QUrl.fromLocalFile(str(self._asset_cidade.arquivo_qml)))
        raiz.setProperty("carroFonte", QUrl.fromLocalFile(str(self._asset_carro.arquivo_qml)))
        raiz.setProperty("cidadeFonteOriginal", QUrl.fromLocalFile(str(Path(caminho_cidade).resolve())))
        raiz.setProperty("carroFonteOriginal", QUrl.fromLocalFile(str(Path(caminho_carro).resolve())))
        meshes_cidade = sorted(self._asset_cidade.diretorio.glob("meshes/*.mesh"))
        meshes_carro = sorted(self._asset_carro.diretorio.glob("meshes/*.mesh"))
        if meshes_cidade:
            raiz.setProperty("cidadeDiagnosticoMesh", QUrl.fromLocalFile(str(meshes_cidade[0])))
        if meshes_carro:
            raiz.setProperty("carroDiagnosticoMesh", QUrl.fromLocalFile(str(meshes_carro[0])))
        _processar_eventos()
        self._verificar_modelos()

    def enquadrar_cidade(
        self,
        centro: tuple[float, float, float],
        dimensoes: tuple[float, float, float],
        escala: float,
        posicao: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        raiz = self.rootObject()
        if raiz is None or QVector3D is None:
            return
        centro_mundo = tuple(float(centro[i]) * float(escala) + float(posicao[i]) for i in range(3))
        # O mesmo enquadramento é usado para cidade (~2 unidades após a
        # escala 0,01) e carro (~0,11 após a escala 0,018). Um piso de 1,5
        # tornava o carro um ponto quase invisível quando testado isolado.
        # A câmera é oblíqua: o raio deve considerar a diagonal XZ real, não
        # apenas a maior dimensão. Isso enquadra os extremos sem redimensionar
        # o GLB e ainda aproveita a área útil da janela.
        diagonal_xz = (float(dimensoes[0]) ** 2 + float(dimensoes[2]) ** 2) ** 0.5
        raio = max(
            diagonal_xz * abs(float(escala)) * 0.66,
            float(dimensoes[1]) * abs(float(escala)) * 0.58,
            0.04,
        )
        raiz.setProperty("centroCena", QVector3D(*centro_mundo))
        raiz.setProperty("raioCena", raio)
        distancia = max(raio * 1.9, 0.12)
        raiz.setProperty("distanciaCamera", distancia)
        raiz.setProperty("cameraAerea", True)
        self._aplicar_transformacao_camera(
            (centro_mundo[0] - distancia, centro_mundo[1] + distancia * 0.58, centro_mundo[2]),
            centro_mundo,
            livre=False,
        )
        self._registrar(
            "enquadramento: centro=(%.3f, %.3f, %.3f), dimensões=(%.3f, %.3f, %.3f), "
            "raio=%.3f, distância=%.3f"
            % (*centro_mundo, *dimensoes, raio, distancia)
        )
        self._diagnosticar_cena_renderizacao()

    def configurar_camera_orbital(
        self,
        centro: tuple[float, float, float],
        yaw: float,
        pitch: float,
        distancia: float,
    ) -> None:
        """Aplica o estado da câmera livre à cena QML sem tocar nos GLBs."""

        raiz = self.rootObject()
        if raiz is None or QVector3D is None:
            return
        raiz.setProperty("cameraLivre", True)
        raiz.setProperty("cameraAerea", False)
        raiz.setProperty("centroCameraLivre", QVector3D(*tuple(float(v) for v in centro)))
        raiz.setProperty("cameraYaw", float(yaw))
        raiz.setProperty("cameraPitch", float(pitch))
        raiz.setProperty("distanciaCamera", max(0.001, float(distancia)))
        distancia = max(0.001, float(distancia))
        horizontal = math.cos(float(pitch)) * distancia
        posicao = (
            float(centro[0]) + math.cos(float(yaw)) * horizontal,
            float(centro[1]) + math.sin(float(pitch)) * distancia,
            float(centro[2]) + math.sin(float(yaw)) * horizontal,
        )
        self._aplicar_transformacao_camera(posicao, centro, livre=True)
        self._registrar(
            "câmera orbital: alvo=(%.3f, %.3f, %.3f), yaw=%.3f, pitch=%.3f, distância=%.3f"
            % (*centro, yaw, pitch, distancia)
        )

    def desativar_camera_orbital(self) -> None:
        """Retorna o QML ao modo aéreo/terceira pessoa controlado pelos modelos."""

        raiz = self.rootObject()
        if raiz is not None:
            raiz.setProperty("cameraLivre", False)

    def _aplicar_transformacao_camera(
        self,
        posicao: tuple[float, float, float],
        alvo: tuple[float, float, float],
        *,
        livre: bool,
    ) -> None:
        """Atualiza posição/alvo diretamente.

        Algumas versões do binding deixam a expressão QML de ``position``
        congelada depois de uma mudança de estado de câmera. Atribuir também
        aos objetos concretos torna a transição determinística, sem depender
        do ciclo de binding do Qt Quick.
        """

        raiz = self.rootObject()
        if raiz is None:
            return
        if QMetaObject is not None:
            try:
                if QMetaObject.invokeMethod(raiz, "atualizarCamera"):
                    return
            except (AttributeError, RuntimeError, TypeError):
                pass
        if QVector3D is None:
            return
        camera = self._encontrar_objeto("cameraGLB")
        alvo_objeto = self._encontrar_objeto("alvoCameraLivre" if livre else "alvoCamera")
        if camera is not None:
            camera.setProperty("position", QVector3D(*tuple(float(v) for v in posicao)))
        if alvo_objeto is not None:
            alvo_objeto.setProperty("position", QVector3D(*tuple(float(v) for v in alvo)))

    def configurar_cidade(self, posicao: tuple[float, float, float], escala: float) -> None:
        raiz = self.rootObject()
        if raiz is not None and QVector3D is not None:
            raiz.setProperty("posicaoCidade", QVector3D(*posicao))
            raiz.setProperty("escalaCidade", float(escala))

    def configurar_limites_carro(
        self,
        centro: tuple[float, float, float],
        minimo: tuple[float, float, float],
    ) -> None:
        """Informa o pivô e o nível do solo reais do modelo importado."""

        raiz = self.rootObject()
        if raiz is not None and QVector3D is not None:
            raiz.setProperty("centroModeloCarro", QVector3D(*centro))
            raiz.setProperty("minimoModeloCarro", QVector3D(*minimo))
            self._registrar(
                "limites do carro: centro=(%.3f, %.3f, %.3f), mínimo=(%.3f, %.3f, %.3f)"
                % (*centro, *minimo)
            )

    def definir_modelos_visiveis(self, cidade: bool = True, carro: bool = True) -> None:
        """Seleciona cidade/carro para os testes isolados e para diagnóstico."""

        raiz = self.rootObject()
        if raiz is not None:
            raiz.setProperty("mostrarCidade", bool(cidade))
            raiz.setProperty("mostrarCarro", bool(carro))
            self._registrar(
                f"visibilidade dos modelos: cidade={bool(cidade)}, carro={bool(carro)}"
            )

    def configurar_marcadores(self, marcadores: list[dict[str, object]] | tuple[dict[str, object], ...]) -> None:
        """Atualiza marcadores 3D sem recriar os Loader3D.

        Cada item aceita ``posicao=(x,y,z)`` e ``cor="#RRGGBB"``. Os 16
        primeiros slots são suficientes para depósito, clientes, cruzamentos
        e os pontos da rota; excedentes são ignorados com diagnóstico.
        """

        raiz = self.rootObject()
        if raiz is None or QVector3D is None:
            return
        itens = list(marcadores)
        if len(itens) > 16:
            self._registrar(f"marcadores 3D: {len(itens)} recebidos, limitados a 16")
        visiveis: list[bool] = []
        cores: list[str] = []
        for indice in range(16):
            if indice < len(itens):
                item = itens[indice]
                posicao = tuple(float(v) for v in item.get("posicao", (0, 0, 0)))
                if len(posicao) != 3:
                    posicao = (0.0, 0.0, 0.0)
                cor = str(item.get("cor", "#F8FAFC"))
                visiveis.append(True)
                cores.append(cor)
            else:
                posicao = (0.0, 0.0, 0.0)
                visiveis.append(False)
                cores.append("#F8FAFC")
            raiz.setProperty(f"marcador{indice}Posicao", QVector3D(*posicao))
        raiz.setProperty("marcadoresVisiveis", visiveis)
        raiz.setProperty("marcadoresCores", cores)

    def configurar_segmentos_rota(self, segmentos: list[dict[str, object]] | tuple[dict[str, object], ...]) -> None:
        """Desenha até oito trechos da polilinha calculada como cubos finos."""

        raiz = self.rootObject()
        if raiz is None or QVector3D is None:
            return
        itens = list(segmentos)
        visiveis: list[bool] = []
        for indice in range(8):
            item = itens[indice] if indice < len(itens) else None
            if item is None:
                posicao = (0.0, 0.0, 0.0)
                escala = (0.001, 0.001, 0.001)
                rotacao = (0.0, 0.0, 0.0)
                visiveis.append(False)
            else:
                posicao = tuple(float(v) for v in item.get("posicao", (0, 0, 0)))
                escala = tuple(float(v) for v in item.get("escala", (0.001, 0.001, 0.001)))
                rotacao = tuple(float(v) for v in item.get("rotacao", (0, 0, 0)))
                visiveis.append(True)
            raiz.setProperty(f"segmentoRota{indice}Posicao", QVector3D(*posicao))
            raiz.setProperty(f"segmentoRota{indice}Escala", QVector3D(*escala))
            raiz.setProperty(f"segmentoRota{indice}Rotacao", QVector3D(*rotacao))
        raiz.setProperty("segmentosRotaVisiveis", visiveis)

    def posicionar_carro(self, posicao: tuple[float, float, float], orientacao: float, escala: float) -> None:
        raiz = self.rootObject()
        if raiz is not None and QVector3D is not None:
            raiz.setProperty("posicaoCarro", QVector3D(*posicao))
            raiz.setProperty("orientacaoCarro", float(orientacao * 180.0 / 3.141592653589793))
            raiz.setProperty("escalaCarro", float(escala))

    def focar_carro(
        self,
        posicao: tuple[float, float, float],
        dimensoes: tuple[float, float, float],
        escala: float,
    ) -> None:
        """Enquadra o carro sem esconder a cidade permanentemente."""

        raiz = self.rootObject()
        if raiz is None:
            return
        diagonal_xz = (float(dimensoes[0]) ** 2 + float(dimensoes[2]) ** 2) ** 0.5
        raio = max(diagonal_xz * abs(float(escala)) * 0.48, float(dimensoes[1]) * abs(float(escala)) * 0.55, 0.04)
        raiz.setProperty("centroCena", QVector3D(*posicao) if QVector3D is not None else None)
        raiz.setProperty("raioCena", raio)
        raiz.setProperty("distanciaCamera", max(raio * 1.55, 0.12))
        raiz.setProperty("cameraAerea", True)
        distancia = max(raio * 1.55, 0.12)
        self._aplicar_transformacao_camera(
            (float(posicao[0]) - distancia, float(posicao[1]) + distancia * 0.58, float(posicao[2])),
            tuple(float(v) for v in posicao),
            livre=False,
        )
        self._registrar(
            "foco carro: posição=(%.3f, %.3f, %.3f), raio=%.3f"
            % (*posicao, raio)
        )
        self._diagnosticar_cena_renderizacao()

    def configurar_eixo_carro(self, eixo: str) -> None:
        """Aplica a correção de eixo do asset sem tocar na orientação da rota."""

        raiz = self.rootObject()
        if raiz is None:
            return
        correcoes = {"+Z": 0.0, "-Z": 180.0, "+X": 90.0, "-X": -90.0, "+Y": 0.0, "-Y": 0.0}
        raiz.setProperty("correcaoEixoCarro", correcoes.get(str(eixo), 0.0))

    def configurar_camera(self, aerea: bool, distancia: float, altura: float | None = None) -> None:
        raiz = self.rootObject()
        if raiz is not None:
            raiz.setProperty("cameraLivre", False)
            raiz.setProperty("cameraAerea", bool(aerea))
            raiz.setProperty("distanciaCamera", float(distancia))
            if altura is not None:
                raiz.setProperty("alturaCamera", max(0.05, float(altura)))
            if aerea:
                alvo = raiz.property("centroCena")
                if alvo is not None:
                    centro = (float(alvo.x()), float(alvo.y()), float(alvo.z()))
                    distancia = float(distancia)
                    self._aplicar_transformacao_camera(
                        (centro[0] - distancia, centro[1] + distancia * 0.58, centro[2]),
                        centro,
                        livre=False,
                    )
            else:
                carro = raiz.property("posicaoCarro")
                if carro is not None:
                    posicao = (float(carro.x()), float(carro.y()), float(carro.z()))
                    orientacao = float(raiz.property("orientacaoCarro") or 0.0) * math.pi / 180.0
                    altura_real = float(raiz.property("alturaCamera") or (altura or 2.0))
                    alvo = (posicao[0], posicao[1], posicao[2])
                    self._aplicar_transformacao_camera(
                        (
                            posicao[0] - math.cos(orientacao) * float(distancia),
                            posicao[1] + altura_real,
                            posicao[2] - math.sin(orientacao) * float(distancia),
                        ),
                        alvo,
                        livre=False,
                    )


def qtquick3d_disponivel() -> bool:
    return QT_QUICK3D_DISPONIVEL


__all__ = [
    "AssetQtQuick3D",
    "DiagnosticoCena",
    "ErroQtQuick3D",
    "RenderizadorQtQuick3D",
    "qtquick3d_disponivel",
    "testar_cena_minima",
]
