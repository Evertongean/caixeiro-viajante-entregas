"""Adaptador opcional para renderização real de GLB com Panda3D.

Panda3D não é importado no caminho normal da aplicação: isso mantém o modo
2D, os testes e a simulação legada utilizáveis em ambientes acadêmicos sem
OpenGL. Quando ``panda3d`` e ``panda3d-gltf`` estão instalados, a classe pode
ser usada por uma janela nativa Panda3D ou por um container Qt. O módulo não
possui fallback gráfico silencioso; ``disponivel`` e ``motivo`` informam
claramente se a cena importada pode ser exibida.
"""

from __future__ import annotations

from pathlib import Path

try:  # pragma: no cover - depende do ambiente gráfico/de pacotes opcionais
    from direct.showbase.ShowBase import ShowBase  # type: ignore
    from panda3d.core import AmbientLight, DirectionalLight, Filename, NodePath  # type: ignore
    try:
        import panda3d_gltf as gltf  # type: ignore  # noqa: F401
    except ImportError:
        try:
            import gltf  # type: ignore  # noqa: F401
        except ImportError:
            gltf = None
    PANDA3D_DISPONIVEL = gltf is not None
    MOTIVO_PANDA3D = "" if PANDA3D_DISPONIVEL else "panda3d-gltf não está instalado"
except ImportError:
    ShowBase = None  # type: ignore[assignment]
    AmbientLight = DirectionalLight = Filename = NodePath = None  # type: ignore[assignment]
    gltf = None
    PANDA3D_DISPONIVEL = False
    MOTIVO_PANDA3D = "Panda3D e panda3d-gltf não estão instalados"


class ErroRenderizador3D(RuntimeError):
    """Renderizador 3D solicitado, mas indisponível ou mal configurado."""


class RenderizadorPanda3D:
    """Pequeno adaptador de cena que preserva o GLB e seus materiais.

    A criação de ``ShowBase`` é deliberadamente explícita para evitar abrir
    uma janela durante importações ou testes. Em uma aplicação com backend
    disponível, ``iniciar`` cria a cena, carrega os dois arquivos através do
    loader glTF e configura iluminação básica; a camada Qt continua dona dos
    controles e da rota.
    """

    def __init__(self) -> None:
        self.base = None
        self.cidade = None
        self.carro = None
        self._iniciado = False

    @property
    def disponivel(self) -> bool:
        return PANDA3D_DISPONIVEL

    @property
    def motivo_indisponibilidade(self) -> str:
        return MOTIVO_PANDA3D

    @property
    def iniciado(self) -> bool:
        return self._iniciado

    def iniciar(self, caminho_cidade: str | Path, caminho_carro: str | Path) -> bool:
        if not self.disponivel:
            raise ErroRenderizador3D(self.motivo_indisponibilidade)
        if self._iniciado:
            return True
        assert ShowBase is not None
        self.base = ShowBase(windowType="onscreen")
        # O plugin gltf registra o loader para extensão .glb. Não há conversão
        # para QPainter: os nós retornados são os próprios modelos importados.
        self.cidade = self.base.loader.loadModel(Filename.fromOsSpecific(str(caminho_cidade)))
        self.carro = self.base.loader.loadModel(Filename.fromOsSpecific(str(caminho_carro)))
        if self.cidade is None or self.carro is None:
            raise ErroRenderizador3D("Panda3D não conseguiu carregar cidade.glb/carro.glb")
        self.cidade.reparentTo(self.base.render)
        self.carro.reparentTo(self.base.render)
        self._configurar_luz()
        self._iniciado = True
        return True

    def _configurar_luz(self) -> None:
        if self.base is None or AmbientLight is None or DirectionalLight is None:
            return
        ambiente = self.base.render.attachNewNode(AmbientLight("ambiente"))
        ambiente.node().setColor((0.55, 0.55, 0.55, 1))
        self.base.render.setLight(ambiente)
        direcional = self.base.render.attachNewNode(DirectionalLight("sol"))
        direcional.node().setColor((0.9, 0.9, 0.85, 1))
        direcional.setHpr(-35, -50, 0)
        self.base.render.setLight(direcional)

    def posicionar_carro(self, posicao: tuple[float, float, float], orientacao: float, escala: float) -> None:
        if self.carro is None:
            return
        self.carro.setPos(*posicao)
        self.carro.setH(orientacao)
        self.carro.setScale(escala)

    def configurar_cidade(self, posicao: tuple[float, float, float], escala: float) -> None:
        if self.cidade is None:
            return
        self.cidade.setPos(*posicao)
        self.cidade.setScale(escala)

    def parar(self) -> None:
        if self.base is not None:
            self.base.destroy()
        self.base = self.cidade = self.carro = None
        self._iniciado = False


def renderizador_3d_disponivel() -> bool:
    return PANDA3D_DISPONIVEL

