"""Protótipo 3D leve da cidade do Delivery Route.

O projeto não precisa de um motor 3D externo para apresentar a ideia de uma
cidade navegável. Este módulo usa um pequeno projetor isométrico desenhado com
``QPainter``. O espaço continua sendo tridimensional (pontos, alturas e
projeção dependente da câmera), mas a implementação é determinística, leve e
funciona também em ambientes sem OpenGL, como os usados pela suíte de testes.

Nenhuma rua é inventada nesta camada: as ruas desenhadas e os trechos que o
veículo percorre são sempre as arestas e os vértices do :class:`Grafo`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import atan2, cos, hypot, sin
from time import monotonic
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from models.grafo import Grafo, TipoVertice

from .modelos_glb import (
    ConfiguracaoModelos3D,
    InformacoesGLB,
    MapeamentoCidadeGLB,
    inspecionar_glb,
    carregar_mapeamento_cidade_glb,
    mapear_grafo_cidade_glb,
    salvar_mapeamento_cidade_glb,
)
from .camera_orbital_3d import CameraOrbital3D
from .renderizador_panda3d import RenderizadorPanda3D, renderizador_3d_disponivel
from .renderizador_qtquick3d import RenderizadorQtQuick3D, qtquick3d_disponivel


@dataclass(frozen=True, slots=True)
class Ponto3D:
    """Coordenada no espaço da cidade (z é a altura)."""

    x: float
    y: float
    z: float = 0.0

    def interpolar(self, outro: "Ponto3D", fator: float) -> "Ponto3D":
        fator = max(0.0, min(1.0, float(fator)))
        return Ponto3D(
            self.x + (outro.x - self.x) * fator,
            self.y + (outro.y - self.y) * fator,
            self.z + (outro.z - self.z) * fator,
        )


@dataclass(frozen=True, slots=True)
class Segmento3D:
    """Representação espacial de uma aresta do grafo."""

    origem: str
    destino: str
    ponto_origem: Ponto3D
    ponto_destino: Ponto3D
    peso: float


@dataclass(frozen=True, slots=True)
class Bloco3D:
    """Bloco construtivo decorativo, sem conexão lógica com o grafo."""

    x: float
    y: float
    largura: float
    profundidade: float
    altura: float


@dataclass(frozen=True, slots=True)
class MapaEspacial3D:
    """Snapshot espacial determinístico de um grafo."""

    posicoes: dict[str, Ponto3D]
    arestas: tuple[Segmento3D, ...]
    blocos: tuple[Bloco3D, ...] = ()

    @property
    def vertices(self) -> dict[str, Ponto3D]:
        """Alias semântico útil para consumidores da camada de visualização."""

        return self.posicoes


def _blocos_da_cidade(posicoes: dict[str, Ponto3D]) -> tuple[Bloco3D, ...]:
    """Cria prédios em uma malha fixa, sem transformar prédios em arestas.

    A ordem de inserção dos vértices é usada como desempate, de modo que dois
    grafos iguais produzem exatamente a mesma cena. Blocos muito próximos a um
    vértice são omitidos para manter marcadores e cruzamentos legíveis.
    """

    if not posicoes:
        return ()
    xs = [p.x for p in posicoes.values()]
    ys = [p.y for p in posicoes.values()]
    minimo_x, maximo_x = min(xs) - 1.5, max(xs) + 1.5
    minimo_y, maximo_y = min(ys) - 1.5, max(ys) + 1.5
    blocos: list[Bloco3D] = []
    passo = 2.2
    indice = 0
    x = minimo_x
    while x <= maximo_x + 1e-9:
        y = minimo_y
        while y <= maximo_y + 1e-9:
            if all((p.x - x) ** 2 + (p.y - y) ** 2 > 0.55**2 for p in posicoes.values()):
                # Alternar alturas cria a leitura de uma cidade sem aleatoriedade.
                altura = 0.7 + (indice % 4) * 0.25
                blocos.append(Bloco3D(x, y, 1.25, 1.05, altura))
                indice += 1
            y += passo
        x += passo
    return tuple(blocos)


def construir_mapa_espacial(grafo: Grafo) -> MapaEspacial3D:
    """Converte um grafo em coordenadas 3D sem alterar o modelo.

    As coordenadas ``x`` e ``y`` cadastradas no editor são preservadas sempre
    que forem distintas. Em um grafo degenerado (todos os pontos no mesmo
    lugar), aplica-se um arranjo circular determinístico apenas à visualização.
    Cada segmento espacial corresponde a uma única aresta real e mantém seu
    peso original.
    """

    if not isinstance(grafo, Grafo):
        raise TypeError("É necessário fornecer uma instância de Grafo.")
    vertices = grafo.listar_vertices()
    coordenadas = [(float(v.x), float(v.y)) for v in vertices]
    distintas = len(set(coordenadas)) == len(coordenadas)
    posicoes: dict[str, Ponto3D] = {}
    if distintas:
        posicoes = {
            vertice.identificador: Ponto3D(float(vertice.x), float(vertice.y), 0.0)
            for vertice in vertices
        }
    elif vertices:
        raio = max(1.5, len(vertices) * 0.45)
        for indice, vertice in enumerate(vertices):
            angulo = -1.57079632679 + 2.0 * 3.14159265359 * indice / len(vertices)
            posicoes[vertice.identificador] = Ponto3D(
                raio * cos(angulo), raio * sin(angulo), 0.0
            )

    arestas = tuple(
        Segmento3D(
            origem=aresta.origem.identificador,
            destino=aresta.destino.identificador,
            ponto_origem=posicoes[aresta.origem.identificador],
            ponto_destino=posicoes[aresta.destino.identificador],
            peso=float(aresta.peso),
        )
        for aresta in grafo.listar_arestas()
    )
    return MapaEspacial3D(posicoes, arestas, _blocos_da_cidade(posicoes))


# Nomes alternativos deixam a API fácil de descobrir sem duplicar a lógica.
mapear_grafo_3d = construir_mapa_espacial
converter_grafo_para_3d = construir_mapa_espacial


class Cidade3DWidget(QWidget):
    """Cena 3D esquemática com câmera e animação não bloqueante do veículo."""

    vertice_selecionado = Signal(str)
    progresso_alterado = Signal(float)
    missao_concluida = Signal()
    voltar_planejamento = Signal()
    # Clique resolvido pelo raycast do Qt Quick 3D. O último argumento indica
    # se uma malha real foi atingida; sem hit a interface deve manter o ponto
    # pendente e explicar que a superfície precisa ser classificada.
    ponto_clicado_3d = Signal(float, float, float, str, bool)

    def __init__(self, grafo: Grafo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("cidade3D")
        self.setMinimumSize(0, 0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._grafo = grafo
        self._mapa = construir_mapa_espacial(grafo)
        # Os modelos são validados uma vez e compartilhados por cache. A
        # projeção QPainter abaixo não desenha GLB; ela permanece apenas como
        # visualização legada quando o backend Panda3D opcional não existe.
        self._configuracao_modelos_3d = ConfiguracaoModelos3D().validar()
        self._info_cidade_glb: InformacoesGLB | None = None
        self._info_carro_glb: InformacoesGLB | None = None
        self._mapeamento_glb: MapeamentoCidadeGLB | None = None
        self._renderizador_glb: RenderizadorPanda3D | None = None
        self._renderizador_qtquick3d: RenderizadorQtQuick3D | None = None
        self._carregar_diagnostico_modelos_3d()
        self._rota_destacada: tuple[str, ...] = ()
        self._arestas_passo: frozenset[frozenset[str]] = frozenset()
        self._vertices_processados: frozenset[str] = frozenset()
        self._vertice_passo_atual: str | None = None
        self._selecionado_id: str | None = None
        self._distancia_percorrida = 0.0
        self._velocidade = 1.0
        self._executando = False
        self._pausado = False
        self._ultimo_tick: float | None = None
        self._camera_yaw = -0.55
        self._camera_pitch = 0.72
        self._zoom = 1.0
        self._modo_camera = "aerea"
        self._camera_orbital = CameraOrbital3D()
        self._camera_livre_ativa = True
        # A cidade importada é reduzida para ~2 unidades no mundo Qt Quick
        # 3D; valores 4–12 (adequados ao protótipo QPainter) deixavam a
        # câmera de missão acima da cidade inteira. Estes defaults são de
        # escala de rua e continuam ajustáveis pelos controles.
        self._distancia_camera = 0.65
        self._altura_camera = 0.28
        self._camera_posicao_suave: Ponto3D | None = None
        self._camera_alvo_suave: Ponto3D | None = None
        self._em_missao = False
        self._entregas_realizadas: list[str] = []
        self._proxima_entrega = 0
        self._tempo_parada_cliente = 0.0
        self._duracao_parada_cliente = 0.35
        self._resumo_missao = ""
        self._arrastando = False
        self._inicio_arrasto = QPoint()
        self._ultimo_arrasto = QPoint()
        self._dialog_calibracao = None

        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._tick_animacao)

        controles = QWidget(self)
        controles.setObjectName("controlesCidade3D")
        controles.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        linha = QHBoxLayout(controles)
        linha.setContentsMargins(4, 4, 4, 4)
        linha.setSpacing(3)
        self.botao_iniciar_percurso = self._botao("Iniciar", self.iniciar_percurso)
        self.botao_pausar_percurso = self._botao("Pausar", self.pausar_percurso)
        self.botao_continuar_percurso = self._botao("Continuar", self.continuar_percurso)
        self.botao_reiniciar_percurso = self._botao(
            "Reiniciar", lambda: self.reiniciar_percurso(iniciar=True)
        )
        self.botao_restaurar_camera = self._botao("Câmera", self.restaurar_enquadramento)
        self.botao_foco_carro = self._botao("Foco carro", self.focar_carro)
        self.botao_foco_carro.setToolTip("Pré-visualizar o carro em escala de rua")
        self.botao_camera_modo = self._botao("Câmera aérea", self._alternar_camera_interface)
        self.botao_camera_modo.setToolTip("Alternar câmera livre/aérea ou câmera atrás do carro")
        self.botao_voltar_planejamento = self._botao(
            "Voltar", lambda: self.voltar_planejamento.emit()
        )
        self.botao_voltar_planejamento.setToolTip("Voltar ao planejamento da rota")
        for botao in (
            self.botao_iniciar_percurso,
            self.botao_pausar_percurso,
            self.botao_continuar_percurso,
            self.botao_reiniciar_percurso,
            self.botao_restaurar_camera,
            self.botao_foco_carro,
            self.botao_camera_modo,
            self.botao_voltar_planejamento,
        ):
            linha.addWidget(botao)
        self.rotulo_velocidade = QLabel("Vel.")
        self.rotulo_velocidade.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        linha.addWidget(self.rotulo_velocidade)
        self.controle_velocidade = QDoubleSpinBox()
        self.controle_velocidade.setObjectName("controleVelocidade3D")
        self.controle_velocidade.setRange(0.1, 20.0)
        self.controle_velocidade.setSingleStep(0.1)
        self.controle_velocidade.setValue(self._velocidade)
        self.controle_velocidade.setSuffix("x")
        self.controle_velocidade.setMinimumWidth(0)
        self.controle_velocidade.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.controle_velocidade.setToolTip("Velocidade do veículo em unidades do mapa por segundo")
        self.controle_velocidade.valueChanged.connect(self.definir_velocidade)
        linha.addWidget(self.controle_velocidade)
        self.rotulo_distancia_camera = QLabel("Dist.")
        self.rotulo_distancia_camera.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        linha.addWidget(self.rotulo_distancia_camera)
        self.controle_distancia_camera = QDoubleSpinBox()
        self.controle_distancia_camera.setObjectName("controleDistanciaCamera3D")
        self.controle_distancia_camera.setRange(0.15, 12.0)
        self.controle_distancia_camera.setSingleStep(0.1)
        self.controle_distancia_camera.setValue(self._distancia_camera)
        self.controle_distancia_camera.setSuffix(" m")
        self.controle_distancia_camera.setMinimumWidth(0)
        self.controle_distancia_camera.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.controle_distancia_camera.setToolTip("Distância da câmera atrás do veículo")
        self.controle_distancia_camera.valueChanged.connect(self.definir_distancia_camera)
        linha.addWidget(self.controle_distancia_camera)
        self.rotulo_altura_camera = QLabel("Alt.")
        self.rotulo_altura_camera.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        linha.addWidget(self.rotulo_altura_camera)
        self.controle_altura_camera = QDoubleSpinBox()
        self.controle_altura_camera.setObjectName("controleAlturaCamera3D")
        self.controle_altura_camera.setRange(0.05, 12.0)
        self.controle_altura_camera.setSingleStep(0.05)
        self.controle_altura_camera.setValue(self._altura_camera)
        self.controle_altura_camera.setSuffix(" m")
        self.controle_altura_camera.setMinimumWidth(0)
        self.controle_altura_camera.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.controle_altura_camera.setToolTip("Altura da câmera atrás do veículo")
        self.controle_altura_camera.valueChanged.connect(self.definir_altura_camera)
        linha.addWidget(self.controle_altura_camera)
        self.rotulo_instrucoes_camera = QLabel("Arrastar: girar · roda: zoom · botão direito: mover")
        self.rotulo_instrucoes_camera.setObjectName("instrucoesCamera3D")
        self.rotulo_instrucoes_camera.setToolTip(
            "Botão esquerdo + arrastar gira; rodinha aproxima/afasta; "
            "botão direito + arrastar desloca a câmera."
        )
        self.rotulo_instrucoes_camera.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        linha.addWidget(self.rotulo_instrucoes_camera)
        self.rotulo_progresso = QLabel("Progresso")
        self.rotulo_progresso.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        linha.addWidget(self.rotulo_progresso)
        self.barra_progresso = QProgressBar()
        self.barra_progresso.setObjectName("progressoCidade3D")
        self.barra_progresso.setRange(0, 1000)
        self.barra_progresso.setTextVisible(True)
        self.barra_progresso.setFormat("%p%")
        # O HUD é responsivo; não deixe a soma dos controles impor uma
        # largura mínima de centenas de pixels ao painel central.
        self.barra_progresso.setMinimumWidth(0)
        self.barra_progresso.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        linha.addWidget(self.barra_progresso, 1)
        self.rotulo_estado = QLabel("Nenhuma rota carregada")
        self.rotulo_estado.setObjectName("estadoCidade3D")
        self.rotulo_estado.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        linha.addWidget(self.rotulo_estado)
        self._controles = controles

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)
        layout.addWidget(controles)
        # A cena é pintada no widget inteiro e os controles ficam sobre o HUD.
        controles.raise_()
        self._atualizar_controles()
        self._atualizar_modo_missao()
        self._ajustar_controles_responsivos()

    @staticmethod
    def _botao(texto: str, callback) -> QPushButton:
        botao = QPushButton(texto)
        botao.setObjectName("botao3D")
        botao.setMinimumHeight(27)
        botao.setMinimumWidth(0)
        botao.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        botao.clicked.connect(callback)
        return botao

    @property
    def grafo(self) -> Grafo:
        return self._grafo

    @property
    def configuracao_modelos_3d(self) -> ConfiguracaoModelos3D:
        return self._configuracao_modelos_3d

    @property
    def model_config(self) -> ConfiguracaoModelos3D:
        return self._configuracao_modelos_3d

    @property
    def info_cidade_glb(self) -> InformacoesGLB | None:
        return self._info_cidade_glb

    @property
    def city_model_info(self) -> InformacoesGLB | None:
        return self._info_cidade_glb

    @property
    def info_carro_glb(self) -> InformacoesGLB | None:
        return self._info_carro_glb

    @property
    def car_model_info(self) -> InformacoesGLB | None:
        return self._info_carro_glb

    @property
    def caminho_cidade_glb(self):
        return self._configuracao_modelos_3d.caminho_cidade

    @property
    def caminho_carro_glb(self):
        return self._configuracao_modelos_3d.caminho_carro

    @property
    def mapeamento_cidade_glb(self) -> MapeamentoCidadeGLB | None:
        return self._mapeamento_glb

    @property
    def modelos_3d_prontos(self) -> bool:
        """Indica que ambos GLBs foram validados e o grafo foi mapeado."""

        return bool(
            self._info_cidade_glb
            and self._info_cidade_glb.valido
            and self._info_carro_glb
            and self._info_carro_glb.valido
            and self._mapeamento_glb
            and self._mapeamento_glb.valido
        )

    @property
    def renderizador_glb_disponivel(self) -> bool:
        """Backend GLB real disponível; falso não invalida o arquivo."""

        return self.backend_glb_disponivel

    @property
    def renderizador_panda3d_disponivel(self) -> bool:
        return renderizador_glb_disponivel()

    @property
    def renderizador_glb(self) -> RenderizadorPanda3D | None:
        return self._renderizador_glb

    @property
    def renderizador_qtquick3d(self) -> RenderizadorQtQuick3D | None:
        return self._renderizador_qtquick3d

    @property
    def diagnostico_renderizacao_3d(self) -> str:
        """Mensagens do backend Qt Quick 3D, inclusive falhas de recursos."""

        if self._renderizador_qtquick3d is None:
            return "Qt Quick 3D ainda não foi inicializado"
        return self._renderizador_qtquick3d.mensagem_diagnostico

    @property
    def backend_glb_disponivel(self) -> bool:
        return renderizador_3d_disponivel() or qtquick3d_disponivel()

    def iniciar_renderizador_qtquick3d(self) -> bool:
        """Cria a cena real Qt Quick 3D para instalações PySide6 completas."""

        if not qtquick3d_disponivel():
            return False
        if self._renderizador_qtquick3d is not None:
            cena_existente = self._renderizador_qtquick3d
            self._conectar_eventos_camera_glb(cena_existente)
            cena_existente.setGeometry(self.rect())
            cena_existente.definir_modelos_visiveis(True, True)
            if cena_existente.renderizacao_ativa:
                cena_existente.show()
                cena_existente.raise_()
                self._controles.raise_()
            cena_existente.sincronizar_dimensoes()
            self.atualizar_marcadores_3d()
            if not self._em_missao and self._camera_livre_ativa:
                self._sincronizar_camera_orbital_glb(cena_existente)
            return True
        cena = RenderizadorQtQuick3D(self)
        cena.carregar_modelos(
            self._configuracao_modelos_3d.caminho_cidade,
            self._configuracao_modelos_3d.caminho_carro,
        )
        cena.configurar_cidade(
            self._configuracao_modelos_3d.posicao_cidade,
            self._configuracao_modelos_3d.escala_cidade,
        )
        if self._info_cidade_glb is not None and self._info_cidade_glb.caixa is not None:
            cena.enquadrar_cidade(
                self._info_cidade_glb.caixa.centro,
                self._info_cidade_glb.caixa.dimensoes,
                self._configuracao_modelos_3d.escala_cidade,
                self._configuracao_modelos_3d.posicao_cidade,
            )
            self._camera_orbital.enquadrar(
                self._info_cidade_glb.caixa.centro,
                self._info_cidade_glb.caixa.dimensoes,
                self._configuracao_modelos_3d.escala_cidade,
                self._configuracao_modelos_3d.posicao_cidade,
            )
        if self._info_carro_glb is not None and self._info_carro_glb.caixa is not None:
            cena.configurar_limites_carro(
                self._info_carro_glb.caixa.centro,
                self._info_carro_glb.caixa.minimo,
            )
        cena.configurar_eixo_carro(self._configuracao_modelos_3d.eixo_frente_carro)
        # O preview pode ser aberto antes de existir uma rota. Ainda assim o
        # carro deve respeitar a escala configurada (0,018 por padrão), em
        # vez de usar a escala geométrica 1:1 e cobrir toda a cidade.
        posicao_carro_preview = (0.0, self._configuracao_modelos_3d.altura_carro, 0.0)
        if self._info_cidade_glb is not None and self._info_cidade_glb.caixa is not None:
            caixa_cidade = self._info_cidade_glb.caixa
            escala_cidade = self._configuracao_modelos_3d.escala_cidade
            centro_mundo = tuple(
                float(caixa_cidade.centro[i]) * escala_cidade
                + self._configuracao_modelos_3d.posicao_cidade[i]
                for i in range(3)
            )
            margem = max(float(valor) for valor in caixa_cidade.dimensoes) * abs(escala_cidade) * 0.50
            # O primeiro vértice do grafo é uma rua/cruzamento válido e torna
            # o carro visível já no preview. O modo "Foco carro" permite
            # inspecionar o asset sem ampliar artificialmente a cidade.
            vertices = self._grafo.listar_vertices()
            if vertices and self._mapeamento_glb is not None:
                ponto = self._mapeamento_glb.posicoes.get(vertices[0].identificador)
                if ponto is not None:
                    posicao_carro_preview = (
                        ponto[0],
                        ponto[1] + self._configuracao_modelos_3d.altura_carro,
                        ponto[2],
                    )
            else:
                posicao_carro_preview = (
                    centro_mundo[0] + margem,
                    self._configuracao_modelos_3d.altura_carro,
                    centro_mundo[2] + margem,
                )
            diagonal_xz = (
                float(caixa_cidade.dimensoes[0]) ** 2
                + float(caixa_cidade.dimensoes[2]) ** 2
            ) ** 0.5
            raio_cidade = max(
                diagonal_xz * abs(escala_cidade) * 0.66,
                float(caixa_cidade.dimensoes[1]) * abs(escala_cidade) * 0.58,
                0.08,
            )
            # O preview é aéreo para que o carro posicionado ao lado não
            # transforme a câmera de inspeção em uma câmera de perseguição.
            cena.configurar_camera(True, max(raio_cidade * 1.9, 0.32))
        cena.posicionar_carro(
            posicao_carro_preview,
            self._configuracao_modelos_3d.orientacao_carro * 3.141592653589793 / 180.0,
            self._configuracao_modelos_3d.escala_carro,
        )
        cena.setGeometry(self.rect())
        if cena.renderizacao_ativa:
            cena.show()
            cena.raise_()
            self._controles.raise_()
        else:
            # Mesmo em offscreen/minimal, mostrar por um ciclo permite ao
            # QQuickWidget propagar o tamanho para a raiz QML e para o View3D;
            # em seguida o overlay continua oculto para preservar o fallback.
            cena.show()
            cena.raise_()
            cena.sincronizar_dimensoes()
            cena.hide()
        cena.sincronizar_dimensoes()
        self._renderizador_qtquick3d = cena
        self._conectar_eventos_camera_glb(cena)
        self.atualizar_marcadores_3d()
        if not self._em_missao and self._camera_livre_ativa:
            self._sincronizar_camera_orbital_glb(cena)
        return True

    def atualizar_marcadores_3d(self) -> None:
        """Projeta depósito, clientes, cruzamentos e rota em esferas 3D."""

        cena = self._renderizador_qtquick3d
        mapeamento = self._mapeamento_glb
        if cena is None or mapeamento is None:
            return
        marcadores: list[dict[str, object]] = []
        cores = {
            TipoVertice.DEPOSITO: "#3B82F6",
            TipoVertice.CLIENTE: "#22C55E",
            TipoVertice.CRUZAMENTO: "#94A3B8",
        }
        for vertice in self._grafo.listar_vertices():
            posicao = mapeamento.posicoes.get(vertice.identificador)
            if posicao is not None:
                marcadores.append({"posicao": posicao, "cor": cores[vertice.tipo]})
        for identificador in self._rota_destacada:
            posicao = mapeamento.posicoes.get(identificador)
            if posicao is not None:
                marcadores.append({"posicao": posicao, "cor": "#F59E0B"})
        cena.configurar_marcadores(marcadores)
        pontos_rota = self._mapeamento_glb.expandir_percurso(self._rota_destacada)
        segmentos: list[dict[str, object]] = []
        for inicio, fim in zip(pontos_rota, pontos_rota[1:]):
            dx, dy, dz = (fim[indice] - inicio[indice] for indice in range(3))
            comprimento = hypot(hypot(dx, dy), dz)
            if comprimento <= 1e-9:
                continue
            horizontal = hypot(dx, dz)
            segmentos.append(
                {
                    "posicao": tuple((inicio[indice] + fim[indice]) / 2 for indice in range(3)),
                    # O cubo nativo possui 100 unidades; a escala mantém o
                    # destaque fino em cidades pequenas e grandes.
                    "escala": (0.008, 0.008, comprimento / 100.0),
                    "rotacao": (
                        -atan2(dy, horizontal) * 180.0 / 3.141592653589793,
                        atan2(dx, dz) * 180.0 / 3.141592653589793,
                        0.0,
                    ),
                }
            )
        cena.configurar_segmentos_rota(segmentos)

    def _conectar_eventos_camera_glb(self, cena: RenderizadorQtQuick3D) -> None:
        """Liga a ponte de eventos uma única vez, mesmo ao reutilizar a cena."""

        if getattr(cena, "_cidade3d_camera_conectada", False):
            return
        cena.mouse_orbitado.connect(self._orbitar_camera_glb)
        cena.mouse_deslocado.connect(self._deslocar_camera_glb)
        cena.mouse_zoom.connect(self._zoom_camera_glb)
        cena.ponto_clicado.connect(self._ponto_clicado_3d)
        cena._cidade3d_camera_conectada = True

    def _ponto_clicado_3d(
        self, x: float, y: float, z: float, objeto: str, encontrado: bool
    ) -> None:
        """Repassa o ponto do raycast para o editor 3D sem acoplar regras de UI."""

        self.ponto_clicado_3d.emit(float(x), float(y), float(z), str(objeto), bool(encontrado))

    def _sincronizar_camera_orbital_glb(self, cena: RenderizadorQtQuick3D | None = None) -> None:
        cena = cena or self._renderizador_qtquick3d
        if cena is None or not self._camera_livre_ativa:
            return
        cena.configurar_camera_orbital(
            self._camera_orbital.centro,
            self._camera_orbital.yaw,
            self._camera_orbital.pitch,
            self._camera_orbital.distancia,
        )

    def _orbitar_camera_glb(self, delta_x: float, delta_y: float) -> None:
        if self._em_missao or not self._camera_livre_ativa:
            return
        self._camera_orbital.orbitar(delta_x, delta_y)
        self._sincronizar_camera_orbital_glb()

    def _deslocar_camera_glb(self, delta_x: float, delta_y: float) -> None:
        if self._em_missao or not self._camera_livre_ativa:
            return
        self._camera_orbital.deslocar(delta_x, delta_y)
        self._sincronizar_camera_orbital_glb()

    def _zoom_camera_glb(self, passos: float) -> None:
        if self._em_missao or not self._camera_livre_ativa:
            return
        self._camera_orbital.zoom(passos)
        self._sincronizar_camera_orbital_glb()

    def parar_renderizador_qtquick3d(self) -> None:
        if self._renderizador_qtquick3d is not None:
            self._renderizador_qtquick3d.close()
            self._renderizador_qtquick3d.deleteLater()
            self._renderizador_qtquick3d = None

    def iniciar_renderizador_glb(self) -> bool:
        """Inicia o backend real quando instalado, sem fallback implícito."""

        if not self.modelos_3d_prontos or not self.backend_glb_disponivel:
            return False
        if qtquick3d_disponivel():
            return self.iniciar_renderizador_qtquick3d()
        if self._renderizador_glb is None:
            self._renderizador_glb = RenderizadorPanda3D()
        self._renderizador_glb.iniciar(
            self._configuracao_modelos_3d.caminho_cidade,
            self._configuracao_modelos_3d.caminho_carro,
        )
        self._renderizador_glb.configurar_cidade(
            self._configuracao_modelos_3d.posicao_cidade,
            self._configuracao_modelos_3d.escala_cidade,
        )
        return True

    def parar_renderizador_glb(self) -> None:
        if self._renderizador_glb is not None:
            self._renderizador_glb.parar()
            self._renderizador_glb = None
        self.parar_renderizador_qtquick3d()

    @property
    def status_modelos_3d(self) -> str:
        if not self.modelos_3d_prontos:
            mensagens = []
            for info in (self._info_cidade_glb, self._info_carro_glb):
                if info is not None and not info.valido:
                    mensagens.extend(info.mensagens)
            if self._mapeamento_glb is not None and not self._mapeamento_glb.valido:
                mensagens.extend(self._mapeamento_glb.mensagens)
            return "; ".join(mensagens) or "modelos 3D não configurados"
        if not self.backend_glb_disponivel:
            return "GLBs válidos; nenhum renderizador 3D está disponível"
        if qtquick3d_disponivel():
            if self._renderizador_qtquick3d is not None:
                base = "GLBs importados e renderizáveis pelo Qt Quick 3D"
            else:
                base = "GLBs válidos; Qt Quick 3D disponível (conversão Balsam no primeiro preview)"
        else:
            base = "GLBs carregados e prontos para renderização Panda3D"
        if not self.mapeamento_viario_calibrado:
            return base + "; mapeamento automático — calibre as ruas antes da missão real"
        return base + "; mapeamento viário calibrado"

    @property
    def modelos_glb_validos(self) -> bool:
        return self.modelos_3d_prontos

    @property
    def mapeamento_glb_valido(self) -> bool:
        return bool(self._mapeamento_glb and self._mapeamento_glb.valido)

    @property
    def mapeamento_viario_calibrado(self) -> bool:
        """True quando o usuário confirmou o alinhamento com ruas reais."""

        return bool(self._mapeamento_glb and self._mapeamento_glb.calibrado)

    def _carregar_diagnostico_modelos_3d(self) -> bool:
        """Lê os dois GLBs e calcula o alinhamento sem alterar o grafo."""

        self._info_cidade_glb = inspecionar_glb(self._configuracao_modelos_3d.caminho_cidade)
        self._info_carro_glb = inspecionar_glb(self._configuracao_modelos_3d.caminho_carro)
        if self._info_cidade_glb.valido:
            self._mapeamento_glb = mapear_grafo_cidade_glb(
                self._grafo, self._info_cidade_glb, self._configuracao_modelos_3d
            )
        else:
            self._mapeamento_glb = None
        return self.modelos_3d_prontos

    def configurar_modelos_3d(self, configuracao: ConfiguracaoModelos3D) -> bool:
        """Aplica parâmetros do painel e invalida a missão quando necessário."""

        self._configuracao_modelos_3d = configuracao.validar()
        pronto = self._carregar_diagnostico_modelos_3d()
        if not pronto and self._em_missao:
            self.sair_missao()
        self.update()
        return pronto

    def carregar_modelos_3d(self, configuracao: ConfiguracaoModelos3D | None = None) -> bool:
        """Revalida os arquivos atuais ou aplica uma configuração nova."""

        if configuracao is not None:
            return self.configurar_modelos_3d(configuracao)
        return self._carregar_diagnostico_modelos_3d()

    def configurar_mapeamento_manual(self, posicoes: dict[str, tuple[float, float, float]]) -> bool:
        """Aplica posições explícitas sem alterar o grafo ou suas arestas."""

        if self._info_cidade_glb is None:
            self._carregar_diagnostico_modelos_3d()
        if self._info_cidade_glb is None:
            return False
        self._mapeamento_glb = mapear_grafo_cidade_glb(
            self._grafo,
            self._info_cidade_glb,
            self._configuracao_modelos_3d,
            posicoes_manuais=posicoes,
        )
        if not self._mapeamento_glb.valido and self._em_missao:
            self.sair_missao()
        self.update()
        return self._mapeamento_glb.valido

    @property
    def pontos_intermediarios_3d(self) -> dict[tuple[str, str], tuple[tuple[float, float, float], ...]]:
        """Pontos de curva atualmente calibrados para as ruas."""

        return {} if self._mapeamento_glb is None else dict(self._mapeamento_glb.pontos_intermediarios)

    def definir_posicao_vertice_3d(
        self, identificador: str, posicao: Sequence[float]
    ) -> bool:
        """Ajusta um vértice no mundo 3D, preservando o grafo lógico."""

        if self._mapeamento_glb is None:
            return False
        if identificador not in {v.identificador for v in self._grafo.listar_vertices()}:
            raise KeyError(f"vértice não pertence ao grafo: {identificador}")
        self._mapeamento_glb = self._mapeamento_glb.com_posicao(identificador, posicao)
        self._sincronizar_modelo_glb()
        self.update()
        return True

    # Nomes curtos usados pelo painel/editor de calibração.
    ajustar_posicao_vertice = definir_posicao_vertice_3d
    definir_posicao_vertice = definir_posicao_vertice_3d

    def adicionar_ponto_intermediario_3d(
        self,
        origem: str,
        destino: str,
        ponto: Sequence[float],
        *,
        indice: int | None = None,
    ) -> bool:
        """Adiciona uma curva somente a uma aresta existente do grafo."""

        if self._mapeamento_glb is None:
            return False
        if origem != destino and not self._grafo.existe_aresta(origem, destino):
            raise ValueError(f"a aresta {origem}–{destino} não existe no grafo")
        self._mapeamento_glb = self._mapeamento_glb.com_ponto_intermediario(
            origem, destino, ponto, indice=indice
        )
        self._sincronizar_modelo_glb()
        self.update()
        return True

    adicionar_ponto_curva = adicionar_ponto_intermediario_3d

    def remover_pontos_intermediarios_3d(self, origem: str, destino: str) -> bool:
        if self._mapeamento_glb is None:
            return False
        self._mapeamento_glb = self._mapeamento_glb.remover_pontos_intermediarios(origem, destino)
        self._sincronizar_modelo_glb()
        self.update()
        return True

    def percurso_espacial_3d(self, percurso: Iterable[str]) -> tuple[tuple[float, float, float], ...]:
        if self._mapeamento_glb is None:
            return ()
        return self._mapeamento_glb.expandir_percurso(percurso)

    def salvar_mapeamento_3d(self, caminho: str | Path) -> Path:
        if self._mapeamento_glb is None:
            raise ValueError("não há mapeamento 3D para salvar")
        return salvar_mapeamento_cidade_glb(self._mapeamento_glb, caminho)

    def carregar_mapeamento_3d(self, caminho: str | Path) -> bool:
        """Carrega somente posições/curvas; o grafo atual continua intacto."""

        mapeamento = carregar_mapeamento_cidade_glb(caminho)
        ids_grafo = {v.identificador for v in self._grafo.listar_vertices()}
        if set(mapeamento.posicoes) != ids_grafo:
            raise ValueError("o mapeamento não corresponde aos vértices do grafo atual")
        for origem, destino in mapeamento.pontos_intermediarios:
            if origem != destino and not self._grafo.existe_aresta(origem, destino):
                raise ValueError(f"mapeamento contém aresta inexistente: {origem}–{destino}")
        self._mapeamento_glb = mapeamento
        self._sincronizar_modelo_glb()
        self.update()
        return True

    # API inglesa para scripts de calibração.
    save_spatial_mapping = salvar_mapeamento_3d
    load_spatial_mapping = carregar_mapeamento_3d

    def focar_carro(self) -> bool:
        """Mostra apenas o carro e enquadra-o em escala de rua."""

        if self._renderizador_qtquick3d is None:
            if not self.modelos_3d_prontos or not self.backend_glb_disponivel:
                return False
            try:
                if not self.iniciar_renderizador_glb():
                    return False
            except Exception as erro:  # pragma: no cover - backend opcional
                self.rotulo_estado.setText(f"Falha ao focar o carro: {erro}")
                return False
        if self._renderizador_qtquick3d is None or self._info_carro_glb is None or self._info_carro_glb.caixa is None:
            return False
        posicao, orientacao = self._estado_veiculo()
        if posicao is None:
            posicao = Ponto3D(0.0, self._configuracao_modelos_3d.altura_carro, 0.0)
            orientacao = 0.0
        self._renderizador_qtquick3d.definir_modelos_visiveis(False, True)
        self._renderizador_qtquick3d.posicionar_carro(
            (posicao.x, posicao.y + self._configuracao_modelos_3d.altura_carro, posicao.z),
            float(orientacao or 0.0),
            self._configuracao_modelos_3d.escala_carro,
        )
        self._renderizador_qtquick3d.focar_carro(
            (posicao.x, posicao.y, posicao.z),
            self._info_carro_glb.caixa.dimensoes,
            self._configuracao_modelos_3d.escala_carro,
        )
        if not self._em_missao:
            self._modo_camera = "aerea"
            self._camera_livre_ativa = True
            self._camera_orbital.focar(
                (posicao.x, posicao.y, posicao.z),
                self._info_carro_glb.caixa.dimensoes,
                self._configuracao_modelos_3d.escala_carro,
            )
            self._sincronizar_camera_orbital_glb()
        self._controles.raise_()
        self.update()
        return True

    def abrir_calibracao_3d(self):
        """Abre o editor de vértices/curvas do alinhamento espacial."""

        from .painel_calibracao_3d import PainelCalibracao3D

        if self._mapeamento_glb is None:
            self.rotulo_estado.setText("Carregue um modelo de cidade válido antes de calibrar.")
            return None
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Calibração das ruas — Cidade 3D")
        dialogo.setModal(False)
        painel = PainelCalibracao3D(dialogo)
        painel.definir_vertices(
            [v.identificador for v in self._grafo.listar_vertices()],
            [(a.origem.identificador, a.destino.identificador) for a in self._grafo.listar_arestas()],
        )
        painel.definir_posicoes(self._mapeamento_glb.posicoes)
        painel.posicao_solicitada.connect(self._aplicar_calibracao_posicao)
        painel.ponto_intermediario_solicitado.connect(self._aplicar_calibracao_ponto)
        painel.salvar_solicitado.connect(self._salvar_calibracao)
        painel.carregar_solicitado.connect(self._carregar_calibracao)
        layout = QVBoxLayout(dialogo)
        layout.addWidget(painel)
        dialogo.resize(390, 430)
        dialogo.show()
        self._dialog_calibracao = dialogo
        return dialogo

    abrir_painel_calibracao = abrir_calibracao_3d

    def _aplicar_calibracao_posicao(self, identificador: str, posicao: object) -> None:
        try:
            self.definir_posicao_vertice_3d(identificador, posicao)
            self.rotulo_estado.setText(f"Vértice {identificador} calibrado no espaço 3D.")
        except (TypeError, ValueError, KeyError) as erro:
            self.rotulo_estado.setText(f"Calibração inválida: {erro}")

    def _aplicar_calibracao_ponto(self, origem: str, destino: str, ponto: object) -> None:
        try:
            self.adicionar_ponto_intermediario_3d(origem, destino, ponto)
            self.rotulo_estado.setText(f"Curva {origem}–{destino} atualizada.")
        except (TypeError, ValueError, KeyError, IndexError) as erro:
            self.rotulo_estado.setText(f"Curva inválida: {erro}")

    def _salvar_calibracao(self, caminho: str) -> None:
        try:
            self.salvar_mapeamento_3d(caminho)
            self.rotulo_estado.setText(f"Mapeamento 3D salvo em {Path(caminho).name}.")
        except (TypeError, ValueError, OSError) as erro:
            self.rotulo_estado.setText(f"Não foi possível salvar o mapeamento: {erro}")

    def _carregar_calibracao(self, caminho: str) -> None:
        try:
            self.carregar_mapeamento_3d(caminho)
            self.rotulo_estado.setText(f"Mapeamento 3D carregado de {Path(caminho).name}.")
        except (TypeError, ValueError, OSError) as erro:
            self.rotulo_estado.setText(f"Não foi possível carregar o mapeamento: {erro}")

    @property
    def mapa_espacial(self) -> MapaEspacial3D:
        return self._mapa

    @property
    def selecionado_id(self) -> str | None:
        return self._selecionado_id

    @property
    def rota_destacada(self) -> tuple[str, ...]:
        return self._rota_destacada

    @property
    def arestas_destacadas(self) -> frozenset[frozenset[str]]:
        """Arestas reais atualmente realçadas em verde."""

        return frozenset(
            frozenset((origem, destino))
            for origem, destino in zip(self._rota_destacada, self._rota_destacada[1:])
            if origem != destino
        )

    @property
    def arestas_passo_destacadas(self) -> frozenset[frozenset[str]]:
        return self._arestas_passo

    @property
    def vertices_passo_processados(self) -> frozenset[str]:
        return self._vertices_processados

    @property
    def vertice_passo_atual(self) -> str | None:
        return self._vertice_passo_atual

    @property
    def percurso_veiculo(self) -> tuple[str, ...]:
        return self._rota_destacada

    @property
    def progresso(self) -> float:
        total = self._distancia_total()
        if not self._rota_destacada:
            return 0.0
        return 1.0 if total <= 0 else max(0.0, min(1.0, self._distancia_percorrida / total))

    @property
    def velocidade(self) -> float:
        return self._velocidade

    @property
    def em_movimento(self) -> bool:
        return self._executando

    @property
    def timer_ativo(self) -> bool:
        return self._timer.isActive()

    @property
    def pausado(self) -> bool:
        return self._pausado

    @property
    def em_missao(self) -> bool:
        return self._em_missao

    @property
    def modo_camera(self) -> str:
        return self._modo_camera

    @property
    def camera_orbital(self) -> CameraOrbital3D:
        """Controlador persistente da navegação livre (útil para testes/UI)."""

        return self._camera_orbital

    @property
    def camera_livre_ativa(self) -> bool:
        return self._camera_livre_ativa and not self._em_missao

    @property
    def estado_camera(self) -> str:
        """Estado explícito da câmera sem quebrar a API histórica.

        ``modo_camera`` continua retornando ``aerea``/``terceira_pessoa``
        para compatibilidade; esta propriedade distingue a órbita livre da
        vista aérea fixa no planejamento.
        """

        if self._em_missao:
            return "terceira_pessoa" if self._modo_camera == "terceira_pessoa" else "aerea"
        return "livre" if self._camera_livre_ativa else "aerea"

    @property
    def camera_em_terceira_pessoa(self) -> bool:
        return self._modo_camera == "terceira_pessoa"

    @property
    def clientes_atendidos(self) -> tuple[str, ...]:
        return tuple(self._entregas_realizadas)

    @property
    def entregas_realizadas(self) -> tuple[str, ...]:
        return self.clientes_atendidos

    @property
    def tempo_parada_cliente(self) -> float:
        """Segundos restantes da parada visual no cliente atual."""

        return max(0.0, self._tempo_parada_cliente)

    @property
    def destino_atual(self) -> str | None:
        if not self._rota_destacada:
            return None
        indice = min(self._proxima_entrega, len(self._rota_destacada) - 1)
        return self._rota_destacada[indice]

    @property
    def distancia_percorrida(self) -> float:
        return min(self._distancia_percorrida, self._distancia_total())

    @property
    def distancia_restante(self) -> float:
        return max(0.0, self._distancia_total() - self._distancia_percorrida)

    @property
    def resumo_missao(self) -> str:
        return self._resumo_missao

    @property
    def posicao_veiculo(self) -> Ponto3D | None:
        return self._estado_veiculo()[0]

    @property
    def veiculo_posicao(self) -> Ponto3D | None:
        return self.posicao_veiculo

    @property
    def orientacao_veiculo(self) -> float | None:
        return self._estado_veiculo()[1]

    @property
    def veiculo_orientacao(self) -> float | None:
        return self.orientacao_veiculo

    def carregar_grafo(self, grafo: Grafo) -> None:
        if not isinstance(grafo, Grafo):
            raise TypeError("É necessário fornecer uma instância de Grafo.")
        self._parar_timer()
        self.parar_renderizador_glb()
        self._grafo = grafo
        self._mapa = construir_mapa_espacial(grafo)
        self._carregar_diagnostico_modelos_3d()
        self._rota_destacada = ()
        self._arestas_passo = frozenset()
        self._vertices_processados = frozenset()
        self._vertice_passo_atual = None
        self._selecionado_id = None
        self._distancia_percorrida = 0.0
        self._em_missao = False
        self._entregas_realizadas = []
        self._proxima_entrega = 0
        self._tempo_parada_cliente = 0.0
        self._resumo_missao = ""
        self._modo_camera = "aerea"
        self._camera_livre_ativa = True
        self._camera_orbital = CameraOrbital3D()
        self.atualizar_marcadores_3d()
        self.rotulo_estado.setText("Nenhuma rota carregada")
        self._atualizar_controles()
        self._atualizar_modo_missao()
        self.update()

    def entrar_missao(self, percurso: Iterable[str]) -> bool:
        """Abre a tela de missão usando exclusivamente uma rota já calculada."""

        rota = tuple(percurso)
        if not rota:
            self.sair_missao()
            self.limpar_destaque_rota()
            self.rotulo_estado.setText("Calcule uma rota válida antes de iniciar a missão.")
            return False
        # Validar o mapeamento antes de iniciar evita que uma cena sem
        # correspondência de vértices mova o carro em ruas inventadas.
        if not self.modelos_3d_prontos:
            self.sair_missao()
            self.limpar_destaque_rota()
            self.rotulo_estado.setText(f"Modelos 3D indisponíveis: {self.status_modelos_3d}")
            return False
        assert self._mapeamento_glb is not None
        ok_mapeamento, erro_mapeamento = self._mapeamento_glb.validar_rota(self._grafo, rota)
        if not ok_mapeamento:
            self.sair_missao()
            self.limpar_destaque_rota()
            self.rotulo_estado.setText(f"Mapeamento 3D inválido: {erro_mapeamento}")
            return False
        if self.backend_glb_disponivel:
            try:
                self.iniciar_renderizador_glb()
            except Exception as erro:  # pragma: no cover - backend opcional
                self.rotulo_estado.setText(
                    f"Falha ao carregar os modelos GLB: {erro}. "
                    "A simulação compatível foi mantida."
                )
                self.parar_renderizador_glb()
        try:
            self.definir_rota(rota)
        except (KeyError, TypeError, ValueError):
            self.sair_missao()
            self.rotulo_estado.setText("A missão exige uma rota válida no grafo.")
            return False
        self._em_missao = True
        self._entregas_realizadas = []
        self._proxima_entrega = 1 if len(self._rota_destacada) > 1 else 0
        self._tempo_parada_cliente = 0.0
        self._resumo_missao = ""
        self._modo_camera = "terceira_pessoa"
        self._camera_livre_ativa = False
        self._preparar_camera_terceira_pessoa()
        self._sincronizar_modelo_glb()
        self.rotulo_estado.setText(
            "Missão pronta · pressione Iniciar percurso"
            + (" · calibre o mapeamento viário para validar ruas reais" if not self.mapeamento_viario_calibrado else "")
        )
        self._atualizar_modo_missao()
        self._atualizar_controles()
        self.update()
        return True

    def sair_missao(self) -> None:
        """Encerra apenas a simulação, preservando a rota no planejamento."""

        self._parar_timer()
        tinha_cena_qt = self._renderizador_qtquick3d is not None
        self._em_missao = False
        self._modo_camera = "aerea"
        self._camera_livre_ativa = True
        self._resumo_missao = ""
        if tinha_cena_qt:
            # Reutiliza a cena e os assets já importados, evitando uma nova
            # conversão Balsam ao deixar a missão.
            self._renderizador_qtquick3d.definir_modelos_visiveis(True, True)
            self.enquadrar_cidade()
        else:
            self.parar_renderizador_glb()
        self._atualizar_modo_missao()
        self._atualizar_controles()
        self.update()

    def reiniciar_missao(self, *, iniciar: bool = False) -> bool:
        if not self._em_missao or not self._rota_destacada:
            return False
        self._parar_timer()
        self._distancia_percorrida = 0.0
        self._entregas_realizadas = []
        self._proxima_entrega = 1 if len(self._rota_destacada) > 1 else 0
        self._tempo_parada_cliente = 0.0
        self._resumo_missao = ""
        self._preparar_camera_terceira_pessoa()
        self._sincronizar_modelo_glb()
        self.rotulo_estado.setText("Missão reiniciada · pronta para iniciar")
        self._atualizar_controles()
        self.update()
        if iniciar:
            return self.iniciar_percurso()
        return True

    def alternar_camera(self) -> str:
        """Alterna entre a câmera aérea e o enquadramento atrás do carro."""

        self._modo_camera = (
            "aerea" if self._modo_camera == "terceira_pessoa" else "terceira_pessoa"
        )
        if self._modo_camera == "terceira_pessoa":
            self._camera_livre_ativa = False
            self._preparar_camera_terceira_pessoa()
        else:
            self._camera_livre_ativa = False
        self._sincronizar_modelo_glb()
        self._atualizar_modo_missao()
        self.update()
        return self._modo_camera

    def definir_rota(self, percurso: Iterable[str]) -> None:
        """Carrega uma rota validando todos os vértices e conexões reais."""

        rota = tuple(percurso)
        self._parar_timer()
        self._distancia_percorrida = 0.0
        self._rota_destacada = ()
        if not rota:
            self.rotulo_estado.setText("Nenhuma rota carregada")
            self._atualizar_controles()
            self.update()
            return
        for identificador in rota:
            if identificador not in self._mapa.posicoes:
                self._atualizar_controles()
                self.update()
                raise KeyError(f"Não existe item visual para o vértice '{identificador}'.")
        for origem, destino in zip(rota, rota[1:]):
            if origem != destino and not self._grafo.existe_aresta(origem, destino):
                self._atualizar_controles()
                self.update()
                raise ValueError(
                    f"A rota contém uma conexão inexistente: '{origem}'–'{destino}'."
                )
        self._rota_destacada = rota
        self.atualizar_marcadores_3d()
        self.rotulo_estado.setText(f"Rota pronta · {len(rota)} paradas")
        self._atualizar_controles()
        self.progresso_alterado.emit(self.progresso)
        self.update()

    def destacar_rota(self, percurso: Iterable[str]) -> None:
        self.limpar_destaque_passo()
        self.definir_rota(percurso)

    def limpar_destaque_rota(self) -> None:
        self._parar_timer()
        self._rota_destacada = ()
        self.atualizar_marcadores_3d()
        self._distancia_percorrida = 0.0
        self._tempo_parada_cliente = 0.0
        self.rotulo_estado.setText("Nenhuma rota carregada")
        self._atualizar_controles()
        self.update()

    def destacar_passo(
        self,
        *,
        vertice_atual: str | None = None,
        vertices_processados: frozenset[str] = frozenset(),
        arestas: tuple[tuple[str, str], ...] = (),
        caminho_final: tuple[str, ...] = (),
    ) -> None:
        self._parar_timer()
        self._rota_destacada = ()
        for identificador in vertices_processados:
            if identificador not in self._mapa.posicoes:
                raise KeyError(f"Não existe item visual para o vértice '{identificador}'.")
        if vertice_atual is not None and vertice_atual not in self._mapa.posicoes:
            raise KeyError(f"Não existe item visual para o vértice '{vertice_atual}'.")
        self._vertices_processados = frozenset(vertices_processados)
        self._vertice_passo_atual = vertice_atual
        self._arestas_passo = frozenset(
            frozenset((origem, destino))
            for origem, destino in arestas
            if origem != destino and frozenset((origem, destino)) in self._chaves_arestas()
        )
        del caminho_final  # a camada 3D usa as arestas fornecidas pelo histórico
        self.update()

    def limpar_destaque_passo(self) -> None:
        self._arestas_passo = frozenset()
        self._vertices_processados = frozenset()
        self._vertice_passo_atual = None
        self.update()

    def selecionar_vertice(self, identificador: str | None, *, emitir_sinal: bool = False) -> None:
        if identificador is not None and identificador not in self._mapa.posicoes:
            raise KeyError(f"Não existe item visual para o vértice '{identificador}'.")
        self._selecionado_id = identificador
        if emitir_sinal and identificador is not None:
            self.vertice_selecionado.emit(identificador)
        self.update()

    def restaurar_enquadramento(self) -> None:
        self._camera_yaw = -0.55
        self._camera_pitch = 0.72
        self._zoom = 1.0
        if self._modo_camera == "terceira_pessoa":
            self._preparar_camera_terceira_pessoa()
            self._sincronizar_modelo_glb()
        elif self._info_cidade_glb is not None and self._info_cidade_glb.caixa is not None:
            self._camera_livre_ativa = True
            if self._renderizador_qtquick3d is not None:
                self._renderizador_qtquick3d.definir_modelos_visiveis(True, True)
            self._camera_orbital.enquadrar(
                self._info_cidade_glb.caixa.centro,
                self._info_cidade_glb.caixa.dimensoes,
                self._configuracao_modelos_3d.escala_cidade,
                self._configuracao_modelos_3d.posicao_cidade,
            )
            self._sincronizar_camera_orbital_glb()
        self.update()

    def enquadrar_cidade(self) -> bool:
        """Enquadra a cidade importada usando seu centro e dimensões reais."""

        if self._info_cidade_glb is None or self._info_cidade_glb.caixa is None:
            return False
        self.restaurar_enquadramento()
        if self._renderizador_qtquick3d is not None:
            self._renderizador_qtquick3d.definir_modelos_visiveis(True, True)
            self._renderizador_qtquick3d.enquadrar_cidade(
                self._info_cidade_glb.caixa.centro,
                self._info_cidade_glb.caixa.dimensoes,
                self._configuracao_modelos_3d.escala_cidade,
                self._configuracao_modelos_3d.posicao_cidade,
            )
            self._camera_livre_ativa = True
            self._camera_orbital.enquadrar(
                self._info_cidade_glb.caixa.centro,
                self._info_cidade_glb.caixa.dimensoes,
                self._configuracao_modelos_3d.escala_cidade,
                self._configuracao_modelos_3d.posicao_cidade,
            )
            self._sincronizar_camera_orbital_glb()
        return True

    def alternar_camera_livre(self) -> bool:
        """Alterna entre órbita livre e a vista aérea fixa no planejamento."""

        if self._em_missao:
            self.alternar_camera()
            return False
        self._camera_livre_ativa = not self._camera_livre_ativa
        if self._renderizador_qtquick3d is not None:
            if self._camera_livre_ativa:
                self._sincronizar_camera_orbital_glb()
            else:
                self._renderizador_qtquick3d.configurar_camera(
                    True, self._camera_orbital.distancia
                )
        return self._camera_livre_ativa

    def _alternar_camera_interface(self) -> None:
        if self._em_missao:
            self.alternar_camera()
        else:
            self.alternar_camera_livre()
        self._atualizar_modo_missao()

    def definir_velocidade(self, velocidade: float) -> None:
        try:
            velocidade = float(velocidade)
        except (TypeError, ValueError):
            return
        self._velocidade = max(0.1, min(20.0, velocidade))
        if abs(self.controle_velocidade.value() - self._velocidade) > 1e-9:
            self.controle_velocidade.blockSignals(True)
            self.controle_velocidade.setValue(self._velocidade)
            self.controle_velocidade.blockSignals(False)

    def definir_distancia_camera(self, distancia: float) -> None:
        try:
            distancia = float(distancia)
        except (TypeError, ValueError):
            return
        self._distancia_camera = max(0.15, min(12.0, distancia))
        if abs(self.controle_distancia_camera.value() - self._distancia_camera) > 1e-9:
            self.controle_distancia_camera.blockSignals(True)
            self.controle_distancia_camera.setValue(self._distancia_camera)
            self.controle_distancia_camera.blockSignals(False)
        if self._modo_camera == "terceira_pessoa":
            self._preparar_camera_terceira_pessoa()
            self._sincronizar_modelo_glb()
            self.update()

    def definir_altura_camera(self, altura: float) -> None:
        try:
            altura = float(altura)
        except (TypeError, ValueError):
            return
        self._altura_camera = max(0.05, min(12.0, altura))
        if abs(self.controle_altura_camera.value() - self._altura_camera) > 1e-9:
            self.controle_altura_camera.blockSignals(True)
            self.controle_altura_camera.setValue(self._altura_camera)
            self.controle_altura_camera.blockSignals(False)
        if self._modo_camera == "terceira_pessoa":
            self._preparar_camera_terceira_pessoa()
            self._sincronizar_modelo_glb()
            self.update()

    def iniciar_percurso(self) -> bool:
        if not self._rota_destacada or self.progresso >= 1.0:
            return False
        if self._em_missao and self.progresso >= 1.0:
            return False
        self._executando = True
        self._pausado = False
        self._ultimo_tick = monotonic()
        self._timer.start()
        self._atualizar_controles()
        return True

    def pausar_percurso(self) -> None:
        if self._executando:
            self._executando = False
            self._pausado = True
            self._timer.stop()
            self.rotulo_estado.setText("Percurso pausado")
            self._atualizar_controles()

    def continuar_percurso(self) -> bool:
        if not self._rota_destacada or not self._pausado:
            return False
        self._executando = True
        self._pausado = False
        self._ultimo_tick = monotonic()
        self._timer.start()
        self._atualizar_controles()
        return True

    def reiniciar_percurso(self, *, iniciar: bool = False) -> bool:
        if not self._rota_destacada:
            return False
        if self._em_missao:
            return self.reiniciar_missao(iniciar=iniciar)
        self._parar_timer()
        self._distancia_percorrida = 0.0
        self.rotulo_estado.setText(f"Rota pronta · {len(self._rota_destacada)} paradas")
        self.progresso_alterado.emit(0.0)
        self._atualizar_controles()
        self.update()
        if iniciar:
            return self.iniciar_percurso()
        return True

    # API em português mais explícita e alias em inglês para integrações simples.
    iniciar_animacao = iniciar_percurso
    pausar_animacao = pausar_percurso
    continuar_animacao = continuar_percurso
    reiniciar_animacao = reiniciar_percurso

    def avancar_simulacao(self, delta_segundos: float) -> None:
        """Avança sem esperar o relógio; útil para testes e replay determinístico."""

        if not self._executando or not self._rota_destacada:
            return
        try:
            delta = max(0.0, float(delta_segundos))
        except (TypeError, ValueError):
            return
        total = self._distancia_total()
        if total <= 0:
            self._distancia_percorrida = total
            self._finalizar_animacao()
            return
        # A parada no cliente é controlada pelo relógio, sem bloquear o event
        # loop. Avanços determinísticos maiores que a pausa simplesmente a
        # consomem e continuam no próximo tick.
        if self._tempo_parada_cliente > 0.0:
            self._tempo_parada_cliente = max(0.0, self._tempo_parada_cliente - delta)
            self._sincronizar_modelo_glb()
            self.update()
            return
        self._distancia_percorrida = min(
            total, self._distancia_percorrida + delta * self._velocidade
        )
        if self._distancia_percorrida >= total - 1e-9:
            self._distancia_percorrida = total
            self._finalizar_animacao()
        else:
            self._atualizar_entregas()
            self._atualizar_camera_seguimento(delta)
            self._sincronizar_modelo_glb()
            self.progresso_alterado.emit(self.progresso)
            self.update()

    def _tick_animacao(self) -> None:
        agora = monotonic()
        anterior = self._ultimo_tick or agora
        self._ultimo_tick = agora
        # Limite defensivo evita saltos enormes se a janela ficar minimizada.
        self.avancar_simulacao(min(0.2, max(0.0, agora - anterior)))

    def _finalizar_animacao(self) -> None:
        self._parar_timer()
        self._pausado = False
        self._atualizar_camera_seguimento(1.0)
        self._sincronizar_modelo_glb()
        self._atualizar_entregas(final=True)
        if self._em_missao:
            self._resumo_missao = (
                f"Missão concluída · {len(self._entregas_realizadas)} entrega(s) · "
                f"{self._distancia_total():g} km"
            )
            self.rotulo_estado.setText(self._resumo_missao)
            self.missao_concluida.emit()
        else:
            self.rotulo_estado.setText("Entrega concluída · retorno no último ponto")
        self.progresso_alterado.emit(1.0)
        self._atualizar_controles()
        self.update()

    def _parar_timer(self) -> None:
        self._timer.stop()
        self._executando = False
        self._pausado = False
        self._ultimo_tick = None

    def _atualizar_modo_missao(self) -> None:
        """Mostra os controles de navegação apenas durante uma missão."""

        if not hasattr(self, "botao_camera_modo"):
            return
        # No planejamento o mesmo controle alterna a órbita livre e a vista
        # aérea fixa; durante a missão ele alterna aérea/terceira pessoa.
        self.botao_camera_modo.setVisible(True)
        self.botao_voltar_planejamento.setVisible(self._em_missao)
        if self._em_missao:
            self.botao_camera_modo.setText(
                "Câmera aérea"
                if self._modo_camera == "terceira_pessoa"
                else "Câmera atrás"
            )
            self.botao_camera_modo.setToolTip(
                "Alternar para a câmera aérea"
                if self._modo_camera == "terceira_pessoa"
                else "Alternar para a câmera atrás do carro"
            )
        else:
            self.botao_camera_modo.setText(
                "Câmera aérea" if self._camera_livre_ativa else "Câmera livre"
            )
            self.botao_camera_modo.setToolTip(
                "Alternar para a vista aérea fixa"
                if self._camera_livre_ativa
                else "Retornar à navegação orbital livre"
            )
        self.botao_iniciar_percurso.setText(
            "Iniciar percurso" if self._em_missao else "Iniciar"
        )
        self.botao_iniciar_percurso.setToolTip(
            "Iniciar o percurso automático da missão"
            if self._em_missao
            else "Iniciar o percurso calculado"
        )
        self.rotulo_distancia_camera.setVisible(self._em_missao)
        self.controle_distancia_camera.setVisible(self._em_missao)
        self.rotulo_altura_camera.setVisible(self._em_missao)
        self.controle_altura_camera.setVisible(self._em_missao)
        self._ajustar_controles_responsivos()

    def _preparar_camera_terceira_pessoa(self) -> None:
        posicao, orientacao = self._estado_veiculo()
        if posicao is None:
            return
        angulo = orientacao or 0.0
        frente = Ponto3D(cos(angulo), sin(angulo), 0.0)
        self._camera_posicao_suave = Ponto3D(
            posicao.x - frente.x * self._distancia_camera,
            posicao.y - frente.y * self._distancia_camera,
            self._altura_camera,
        )
        self._camera_alvo_suave = Ponto3D(
            posicao.x + frente.x * 1.8,
            posicao.y + frente.y * 1.8,
            0.8,
        )

    def _atualizar_camera_seguimento(self, delta: float) -> None:
        if self._modo_camera != "terceira_pessoa":
            return
        posicao, orientacao = self._estado_veiculo()
        if posicao is None:
            return
        angulo = orientacao or 0.0
        frente = Ponto3D(cos(angulo), sin(angulo), 0.0)
        desejada_posicao = Ponto3D(
            posicao.x - frente.x * self._distancia_camera,
            posicao.y - frente.y * self._distancia_camera,
            self._altura_camera,
        )
        desejado_alvo = Ponto3D(
            posicao.x + frente.x * 1.8,
            posicao.y + frente.y * 1.8,
            0.8,
        )
        if self._camera_posicao_suave is None or self._camera_alvo_suave is None:
            self._camera_posicao_suave = desejada_posicao
            self._camera_alvo_suave = desejado_alvo
            return
        fator = max(0.08, min(1.0, max(0.0, delta) * 7.0))
        self._camera_posicao_suave = self._camera_posicao_suave.interpolar(
            desejada_posicao, fator
        )
        self._camera_alvo_suave = self._camera_alvo_suave.interpolar(
            desejado_alvo, fator
        )

    def _sincronizar_modelo_glb(self) -> None:
        """Copia a posição interpolada para o nó Panda3D, quando presente."""

        if (
            self._renderizador_glb is None
            and self._renderizador_qtquick3d is None
        ) or self._mapeamento_glb is None:
            return
        rota = self._rota_destacada
        if not rota:
            return
        posicao, orientacao = self._estado_modelo_glb()
        if posicao is not None and self._renderizador_glb is not None:
            altura = self._configuracao_modelos_3d.altura_carro
            self._renderizador_glb.posicionar_carro(
                (posicao[0], posicao[1] + altura, posicao[2]),
                orientacao * 180.0 / 3.141592653589793
                + self._configuracao_modelos_3d.orientacao_carro,
                self._configuracao_modelos_3d.escala_carro,
            )
        if posicao is not None and self._renderizador_qtquick3d is not None:
            altura = self._configuracao_modelos_3d.altura_carro
            self._renderizador_qtquick3d.posicionar_carro(
                (posicao[0], posicao[1] + altura, posicao[2]),
                orientacao + self._configuracao_modelos_3d.orientacao_carro * 3.141592653589793 / 180.0,
                self._configuracao_modelos_3d.escala_carro,
            )
            if self._camera_livre_ativa and not self._em_missao:
                self._sincronizar_camera_orbital_glb()
            else:
                self._renderizador_qtquick3d.configurar_camera(
                    self._modo_camera == "aerea", self._distancia_camera, self._altura_camera
                )
            self._renderizador_qtquick3d.configurar_eixo_carro(
                self._configuracao_modelos_3d.eixo_frente_carro
            )

    def _estado_modelo_glb(self) -> tuple[tuple[float, float, float] | None, float]:
        """Calcula posição/orientação na polilinha calibrada da rota.

        O relógio continua usando o peso do grafo para determinar o tempo do
        trecho; os pontos intermediários apenas definem por onde o carro passa
        no mundo importado.
        """

        if self._mapeamento_glb is None or not self._rota_destacada:
            return None, 0.0
        restante = self._distancia_percorrida
        primeiro = self._mapeamento_glb.posicoes.get(self._rota_destacada[0])
        posicao = primeiro
        orientacao = 0.0
        for origem, destino in zip(self._rota_destacada, self._rota_destacada[1:]):
            if origem == destino:
                continue
            peso = self._grafo.obter_distancia(origem, destino)
            pontos = self._mapeamento_glb.pontos_da_aresta(origem, destino)
            if len(pontos) < 2:
                continue
            if restante <= peso:
                fator = restante / peso if peso else 1.0
                comprimentos = [
                    hypot(hypot(pontos[i + 1][0] - pontos[i][0], pontos[i + 1][1] - pontos[i][1]),
                          pontos[i + 1][2] - pontos[i][2])
                    for i in range(len(pontos) - 1)
                ]
                total = sum(comprimentos)
                alvo = total * max(0.0, min(1.0, fator))
                acumulado = 0.0
                for indice, comprimento in enumerate(comprimentos):
                    p0, p1 = pontos[indice], pontos[indice + 1]
                    if alvo <= acumulado + comprimento or indice == len(comprimentos) - 1:
                        local = 0.0 if comprimento <= 1e-12 else (alvo - acumulado) / comprimento
                        posicao = tuple(p0[j] + (p1[j] - p0[j]) * local for j in range(3))
                        orientacao = atan2(p1[2] - p0[2], p1[0] - p0[0])
                        return posicao, orientacao
                    acumulado += comprimento
            restante -= peso
            posicao = pontos[-1]
            p0, p1 = pontos[-2], pontos[-1]
            orientacao = atan2(p1[2] - p0[2], p1[0] - p0[0])
        return posicao, orientacao

    def _atualizar_entregas(self, *, final: bool = False) -> None:
        if not self._em_missao or not self._rota_destacada:
            return
        acumulada = 0.0
        distancia = self._distancia_percorrida
        for indice, (origem, destino) in enumerate(
            zip(self._rota_destacada, self._rota_destacada[1:]), start=1
        ):
            acumulada += 0.0 if origem == destino else self._grafo.obter_distancia(origem, destino)
            if (distancia + 1e-9 >= acumulada or final) and indice >= self._proxima_entrega:
                identificador = self._rota_destacada[indice]
                if (
                    identificador not in self._entregas_realizadas
                    and self._grafo.obter_vertice(identificador).tipo is TipoVertice.CLIENTE
                ):
                    self._entregas_realizadas.append(identificador)
                    self._proxima_entrega = indice + 1
                    self._tempo_parada_cliente = self._duracao_parada_cliente
        if self._em_missao and self._executando:
            self.rotulo_estado.setText(
                f"Missão em andamento · {len(self._entregas_realizadas)} entrega(s)"
            )

    def _chaves_arestas(self) -> set[frozenset[str]]:
        return {frozenset((segmento.origem, segmento.destino)) for segmento in self._mapa.arestas}

    def _distancia_total(self) -> float:
        if len(self._rota_destacada) < 2:
            return 0.0
        return sum(
            self._grafo.obter_distancia(origem, destino)
            for origem, destino in zip(self._rota_destacada, self._rota_destacada[1:])
            if origem != destino
        )

    def _estado_veiculo(self) -> tuple[Ponto3D | None, float | None]:
        if not self._rota_destacada:
            return None, None
        if len(self._rota_destacada) == 1:
            return self._mapa.posicoes[self._rota_destacada[0]], 0.0
        distancia = self._distancia_percorrida
        for origem, destino in zip(self._rota_destacada, self._rota_destacada[1:]):
            if origem == destino:
                continue
            peso = self._grafo.obter_distancia(origem, destino)
            if distancia <= peso:
                fator = distancia / peso if peso else 1.0
                ponto_origem = self._mapa.posicoes[origem]
                ponto_destino = self._mapa.posicoes[destino]
                orientacao = atan2(
                    ponto_destino.y - ponto_origem.y,
                    ponto_destino.x - ponto_origem.x,
                )
                return ponto_origem.interpolar(ponto_destino, fator), orientacao
            distancia -= peso
        ultimo = self._rota_destacada[-1]
        penultimo = self._rota_destacada[-2]
        p0, p1 = self._mapa.posicoes[penultimo], self._mapa.posicoes[ultimo]
        return p1, atan2(p1.y - p0.y, p1.x - p0.x)

    def _projetar(self, ponto: Ponto3D, area: QRectF) -> QPointF:
        if (
            self._modo_camera == "terceira_pessoa"
            and self._camera_posicao_suave is not None
            and self._camera_alvo_suave is not None
        ):
            camera = self._camera_posicao_suave
            alvo = self._camera_alvo_suave
            dx, dy, dz = alvo.x - camera.x, alvo.y - camera.y, alvo.z - camera.z
            comprimento = hypot(hypot(dx, dy), dz) or 1.0
            frente = Ponto3D(dx / comprimento, dy / comprimento, dz / comprimento)
            # O eixo vertical do mundo permanece fixo, produzindo uma câmera
            # estável atrás do veículo mesmo nas curvas.
            lateral = Ponto3D(frente.y, -frente.x, 0.0)
            lateral_comprimento = hypot(lateral.x, lateral.y) or 1.0
            lateral = Ponto3D(
                lateral.x / lateral_comprimento,
                lateral.y / lateral_comprimento,
                0.0,
            )
            cima = Ponto3D(
                lateral.y * frente.z,
                -lateral.x * frente.z,
                lateral.x * frente.y - lateral.y * frente.x,
            )
            delta = Ponto3D(ponto.x - camera.x, ponto.y - camera.y, ponto.z - camera.z)
            profundidade = (
                delta.x * frente.x + delta.y * frente.y + delta.z * frente.z
            )
            lateral_tela = delta.x * lateral.x + delta.y * lateral.y
            vertical_tela = delta.x * cima.x + delta.y * cima.y + delta.z * cima.z
            focal = 4.0 * self._zoom
            perspectiva = focal / max(0.5, focal + profundidade)
            escala = min(area.width(), area.height()) / 3.3
            return QPointF(
                area.center().x() + lateral_tela * escala * perspectiva,
                area.center().y() - vertical_tela * escala * perspectiva,
            )
        posicoes = self._mapa.posicoes.values()
        if posicoes:
            centro_x = sum(p.x for p in posicoes) / len(self._mapa.posicoes)
            centro_y = sum(p.y for p in posicoes) / len(self._mapa.posicoes)
        else:
            centro_x = centro_y = 0.0
        x, y = ponto.x - centro_x, ponto.y - centro_y
        cos_yaw, sin_yaw = cos(self._camera_yaw), sin(self._camera_yaw)
        lateral = cos_yaw * x - sin_yaw * y
        profundidade = sin_yaw * x + cos_yaw * y
        cos_pitch, sin_pitch = cos(self._camera_pitch), sin(self._camera_pitch)
        vertical = cos_pitch * ponto.z - sin_pitch * profundidade
        profundidade_camera = sin_pitch * ponto.z + cos_pitch * profundidade
        escala = min(area.width(), area.height()) / 7.0 * self._zoom
        perspectiva = 1.0 / max(0.45, 1.0 + profundidade_camera * 0.035)
        escala *= perspectiva
        return QPointF(area.center().x() + lateral * escala, area.center().y() - vertical * escala)

    def _pintar_cubiculo(self, painter: QPainter, bloco: Bloco3D, area: QRectF) -> None:
        base = [
            Ponto3D(bloco.x - bloco.largura / 2, bloco.y - bloco.profundidade / 2, 0),
            Ponto3D(bloco.x + bloco.largura / 2, bloco.y - bloco.profundidade / 2, 0),
            Ponto3D(bloco.x + bloco.largura / 2, bloco.y + bloco.profundidade / 2, 0),
            Ponto3D(bloco.x - bloco.largura / 2, bloco.y + bloco.profundidade / 2, 0),
        ]
        topo = [Ponto3D(p.x, p.y, bloco.altura) for p in base]
        p_base = [self._projetar(p, area) for p in base]
        p_topo = [self._projetar(p, area) for p in topo]
        painter.setPen(QPen(QColor("#0F172A"), 1))
        painter.setBrush(QColor("#334155"))
        painter.drawPolygon(QPolygonF([p_base[0], p_base[1], p_topo[1], p_topo[0]]))
        painter.setBrush(QColor("#263449"))
        painter.drawPolygon(QPolygonF([p_base[1], p_base[2], p_topo[2], p_topo[1]]))
        painter.setBrush(QColor("#64748B"))
        painter.drawPolygon(QPolygonF(p_topo))

    def _pintar_arvore(self, painter: QPainter, x: float, y: float, area: QRectF) -> None:
        """Decoração local determinística: tronco, copa e sombra."""

        base = self._projetar(Ponto3D(x, y, 0.0), area)
        topo = self._projetar(Ponto3D(x, y, 0.8), area)
        painter.setPen(QPen(QColor("#422006"), 3))
        painter.drawLine(base, topo)
        painter.setPen(QPen(QColor("#14532D"), 1))
        painter.setBrush(QColor("#22C55E"))
        painter.drawEllipse(topo, 9, 8)

    def paintEvent(self, evento) -> None:  # noqa: N802 - contrato Qt
        del evento
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0B1220"))
        area = QRectF(self.rect()).adjusted(0, 0, 0, -self._controles.height())
        painter.fillRect(area, QColor("#101B2D"))
        if not self._mapa.posicoes:
            painter.setPen(QColor("#94A3B8"))
            painter.drawText(area, Qt.AlignmentFlag.AlignCenter, "Grafo vazio — adicione locais para visualizar a cidade")
            painter.end()
            return

        # Quarteirão de fundo, sem linhas que possam ser confundidas com arestas.
        pontos = list(self._mapa.posicoes.values())
        margem = 2.4
        minimo_x = min(p.x for p in pontos) - margem
        maximo_x = max(p.x for p in pontos) + margem
        minimo_y = min(p.y for p in pontos) - margem
        maximo_y = max(p.y for p in pontos) + margem
        chao = [
            self._projetar(Ponto3D(minimo_x, minimo_y), area),
            self._projetar(Ponto3D(maximo_x, minimo_y), area),
            self._projetar(Ponto3D(maximo_x, maximo_y), area),
            self._projetar(Ponto3D(minimo_x, maximo_y), area),
        ]
        painter.setPen(QPen(QColor("#26364D"), 1))
        painter.setBrush(QColor("#172337"))
        painter.drawPolygon(QPolygonF(chao))

        # Prédios são desenhados antes das ruas para que a rede do grafo fique legível.
        for indice, bloco in enumerate(sorted(self._mapa.blocos, key=lambda b: b.y + b.x)):
            self._pintar_cubiculo(painter, bloco, area)
            if indice % 3 == 0:
                self._pintar_arvore(
                    painter,
                    bloco.x + bloco.largura * 0.75,
                    bloco.y + bloco.profundidade * 0.75,
                    area,
                )

        chaves_rota = {
            frozenset((origem, destino))
            for origem, destino in zip(self._rota_destacada, self._rota_destacada[1:])
            if origem != destino
        }
        for segmento in self._mapa.arestas:
            chave = frozenset((segmento.origem, segmento.destino))
            p0 = self._projetar(segmento.ponto_origem, area)
            p1 = self._projetar(segmento.ponto_destino, area)
            painter.setPen(QPen(QColor("#0F172A"), 18, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(p0, p1)
            painter.setPen(QPen(QColor("#64748B"), 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(p0, p1)
            painter.setPen(QPen(QColor("#CBD5E1"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(p0, p1)
            if chave in chaves_rota:
                painter.setPen(QPen(QColor("#10B981"), 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(p0, p1)
            elif chave in self._arestas_passo:
                painter.setPen(QPen(QColor("#F59E0B"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(p0, p1)
            meio = QPointF((p0.x() + p1.x()) / 2, (p0.y() + p1.y()) / 2)
            painter.setPen(QColor("#CBD5E1"))
            fonte = QFont()
            fonte.setPointSize(8)
            painter.setFont(fonte)
            painter.drawText(meio + QPointF(5, -4), f"{segmento.peso:g}")

        for vertice in self._grafo.listar_vertices():
            ponto = self._projetar(self._mapa.posicoes[vertice.identificador], area)
            cor = {
                TipoVertice.DEPOSITO: QColor("#60A5FA"),
                TipoVertice.CLIENTE: QColor("#34D399"),
                TipoVertice.CRUZAMENTO: QColor("#94A3B8"),
            }[vertice.tipo]
            if vertice.identificador in self._vertices_processados:
                cor = QColor("#A78BFA")
            if vertice.identificador == self._vertice_passo_atual:
                cor = QColor("#F59E0B")
            raio = 10 if vertice.identificador != self._selecionado_id else 13
            painter.setPen(QPen(QColor("#F8FAFC" if vertice.identificador == self._selecionado_id else "#0F172A"), 3))
            painter.setBrush(cor)
            painter.drawEllipse(ponto, raio, raio)
            painter.setPen(QColor("#F8FAFC"))
            fonte = QFont()
            fonte.setPointSize(9)
            fonte.setBold(True)
            painter.setFont(fonte)
            painter.drawText(ponto + QPointF(14, 4), f"{vertice.identificador} · {vertice.nome}")

        posicao, orientacao = self._estado_veiculo()
        if posicao is not None:
            self._pintar_veiculo(painter, posicao, orientacao or 0.0, area)

        if self._em_missao:
            self._pintar_hud_missao(painter, area)

        if not self._em_missao:
            painter.setPen(QColor("#CBD5E1"))
            fonte_hud = QFont()
            fonte_hud.setPointSize(9)
            painter.setFont(fonte_hud)
            painter.drawText(
                area.adjusted(12, 10, -12, -10),
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                "Arraste para orbitar · roda para zoom · Câmera para restaurar",
            )
        painter.end()

    def _pintar_veiculo(
        self, painter: QPainter, posicao: Ponto3D, orientacao: float, area: QRectF
    ) -> None:
        """Desenha um pequeno furgão com carroceria, teto e rodas."""

        frente = Ponto3D(cos(orientacao), sin(orientacao), 0.0)
        lado = Ponto3D(-sin(orientacao), cos(orientacao), 0.0)

        def deslocar(lateral: float, longitudinal: float, altura: float) -> QPointF:
            return self._projetar(
                Ponto3D(
                    posicao.x + lado.x * lateral + frente.x * longitudinal,
                    posicao.y + lado.y * lateral + frente.y * longitudinal,
                    altura,
                ),
                area,
            )

        corpo = QPolygonF(
            [
                deslocar(-0.22, -0.35, 0.08),
                deslocar(0.22, -0.35, 0.08),
                deslocar(0.22, 0.35, 0.08),
                deslocar(-0.22, 0.35, 0.08),
            ]
        )
        teto = QPolygonF(
            [
                deslocar(-0.18, -0.18, 0.28),
                deslocar(0.18, -0.18, 0.28),
                deslocar(0.18, 0.25, 0.28),
                deslocar(-0.18, 0.25, 0.28),
            ]
        )
        painter.setPen(QPen(QColor("#F8FAFC"), 1))
        painter.setBrush(QColor("#DC2626"))
        painter.drawPolygon(corpo)
        painter.setBrush(QColor("#FCA5A5"))
        painter.drawPolygon(teto)
        for lateral in (-0.23, 0.23):
            for longitudinal in (-0.22, 0.25):
                roda = deslocar(lateral, longitudinal, 0.04)
                painter.setPen(QPen(QColor("#111827"), 3))
                painter.drawPoint(roda)

    def _pintar_hud_missao(self, painter: QPainter, area: QRectF) -> None:
        total_clientes = len(
            {
                identificador
                for identificador in self._rota_destacada
                if self._grafo.obter_vertice(identificador).tipo is TipoVertice.CLIENTE
            }
        )
        destino = self.destino_atual or "Final"
        status = "Concluída" if self._resumo_missao else "Em andamento" if self._executando else "Pausada" if self._pausado else "Pronta"
        linhas = (
            "MISSÃO 3D · CÂMERA EM TERCEIRA PESSOA"
            if self._modo_camera == "terceira_pessoa"
            else "MISSÃO 3D · CÂMERA AÉREA",
            f"Destino: {destino}    Status: {status}",
            f"Entregas: {len(self._entregas_realizadas)}/{total_clientes}",
            f"Distância: {self.distancia_percorrida:g} / {self._distancia_total():g} km",
            f"Restante: {self.distancia_restante:g} km · Progresso: {self.progresso:.0%}",
        )
        caixa = QRectF(12, 12, min(380.0, area.width() - 24), 101)
        painter.setPen(QPen(QColor("#475569"), 1))
        painter.setBrush(QColor(15, 23, 42, 225))
        painter.drawRoundedRect(caixa, 8, 8)
        painter.setPen(QColor("#E2E8F0"))
        fonte = QFont()
        fonte.setPointSize(8)
        painter.setFont(fonte)
        for indice, linha in enumerate(linhas):
            painter.drawText(caixa.adjusted(10, 7 + indice * 18, -8, 0), linha)

    def mousePressEvent(self, evento) -> None:  # noqa: N802 - contrato Qt
        if evento.button() == Qt.MouseButton.LeftButton:
            self._arrastando = False
            self._inicio_arrasto = evento.position().toPoint()
            self._ultimo_arrasto = self._inicio_arrasto
            evento.accept()
            return
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802 - contrato Qt
        if evento.buttons() & Qt.MouseButton.LeftButton:
            atual = evento.position().toPoint()
            delta = atual - self._ultimo_arrasto
            if (atual - self._inicio_arrasto).manhattanLength() > 3:
                self._arrastando = True
            self._camera_yaw += delta.x() * 0.012
            self._camera_pitch = max(0.25, min(1.25, self._camera_pitch + delta.y() * 0.009))
            self._ultimo_arrasto = atual
            self.update()
            evento.accept()
            return
        super().mouseMoveEvent(evento)

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802 - contrato Qt
        if evento.button() == Qt.MouseButton.LeftButton:
            if not self._arrastando:
                self._selecionar_mais_proximo(evento.position().toPoint())
            evento.accept()
            return
        super().mouseReleaseEvent(evento)

    def wheelEvent(self, evento) -> None:  # noqa: N802 - contrato Qt
        fator = 1.12 if evento.angleDelta().y() > 0 else 1 / 1.12
        self._zoom = max(0.35, min(3.5, self._zoom * fator))
        self.update()
        evento.accept()

    def _selecionar_mais_proximo(self, ponto: QPoint) -> None:
        area = QRectF(self.rect()).adjusted(0, 0, 0, -self._controles.height())
        melhor: tuple[float, str] | None = None
        for identificador, posicao in self._mapa.posicoes.items():
            tela = self._projetar(posicao, area)
            distancia = (tela.x() - ponto.x()) ** 2 + (tela.y() - ponto.y()) ** 2
            if distancia <= 24**2 and (melhor is None or distancia < melhor[0]):
                melhor = (distancia, identificador)
        if melhor is not None:
            self.selecionar_vertice(melhor[1], emitir_sinal=True)

    def _atualizar_controles(self) -> None:
        tem_rota = bool(self._rota_destacada)
        self.botao_iniciar_percurso.setEnabled(tem_rota and not self._executando and not self._pausado and self.progresso < 1.0)
        self.botao_pausar_percurso.setEnabled(self._executando)
        self.botao_continuar_percurso.setEnabled(tem_rota and self._pausado)
        self.botao_reiniciar_percurso.setEnabled(tem_rota)
        self.barra_progresso.setValue(round(self.progresso * 1000))

    def _ajustar_controles_responsivos(self) -> None:
        compacto = self.width() < 900
        distancia_compacta = self.width() < 680
        muito_compacto = self.width() < 420
        if hasattr(self, "rotulo_estado"):
            self.rotulo_estado.setVisible(not compacto)
        if hasattr(self, "rotulo_progresso"):
            self.rotulo_progresso.setVisible(not compacto)
        if hasattr(self, "rotulo_velocidade"):
            self.rotulo_velocidade.setVisible(not compacto)
        if hasattr(self, "rotulo_distancia_camera"):
            self.rotulo_distancia_camera.setVisible(self._em_missao and not distancia_compacta)
        if hasattr(self, "controle_distancia_camera"):
            self.controle_distancia_camera.setVisible(self._em_missao and not distancia_compacta)
        if hasattr(self, "rotulo_altura_camera"):
            self.rotulo_altura_camera.setVisible(self._em_missao and not distancia_compacta)
        if hasattr(self, "controle_altura_camera"):
            self.controle_altura_camera.setVisible(self._em_missao and not distancia_compacta)
        if hasattr(self, "botao_restaurar_camera"):
            self.botao_restaurar_camera.setVisible(not muito_compacto)
        if hasattr(self, "botao_camera_modo"):
            self.botao_camera_modo.setText("◉" if muito_compacto else self.botao_camera_modo.text())
            self.botao_camera_modo.setMinimumWidth(34 if muito_compacto else 0)
            self.botao_camera_modo.setMaximumWidth(34 if muito_compacto else 16777215)
        if hasattr(self, "botao_voltar_planejamento"):
            self.botao_voltar_planejamento.setText("↩" if muito_compacto else "Voltar")
            self.botao_voltar_planejamento.setMinimumWidth(34 if muito_compacto else 0)
            self.botao_voltar_planejamento.setMaximumWidth(34 if muito_compacto else 16777215)
        if hasattr(self, "barra_progresso"):
            self.barra_progresso.setMinimumWidth(45 if muito_compacto else 55 if compacto else 90)
        if hasattr(self, "controle_velocidade"):
            self.controle_velocidade.setFixedWidth(48 if muito_compacto else 55 if compacto else 65)
        if hasattr(self, "controle_distancia_camera"):
            self.controle_distancia_camera.setFixedWidth(
                48 if muito_compacto else 55 if compacto else 65
            )
        if hasattr(self, "controle_altura_camera"):
            self.controle_altura_camera.setFixedWidth(48 if muito_compacto else 55 if compacto else 65)
        if muito_compacto and hasattr(self, "botao_restaurar_camera"):
            self.botao_restaurar_camera.setVisible(False)
        if hasattr(self, "botao_iniciar_percurso"):
            botoes = (
                self.botao_iniciar_percurso,
                self.botao_pausar_percurso,
                self.botao_continuar_percurso,
                self.botao_reiniciar_percurso,
            )
            simbolos = ("▶", "Ⅱ", "▶▶", "↺")
            textos = ("Iniciar", "Pausar", "Continuar", "Reiniciar")
            for botao, simbolo, texto in zip(botoes, simbolos, textos):
                botao.setText(simbolo if muito_compacto else texto)
                botao.setMinimumWidth(34 if muito_compacto else 0)
                botao.setMaximumWidth(34 if muito_compacto else 16777215)
        if hasattr(self, "botao_camera_modo"):
            controles_missao = (
                self.botao_iniciar_percurso,
                self.botao_pausar_percurso,
                self.botao_continuar_percurso,
                self.botao_reiniciar_percurso,
                self.botao_restaurar_camera,
                self.botao_foco_carro,
                self.botao_camera_modo,
                self.botao_voltar_planejamento,
            )
            for botao in controles_missao:
                if compacto and not muito_compacto:
                    botao.setMinimumWidth(56)
                    botao.setMaximumWidth(62)
                elif not muito_compacto:
                    botao.setMinimumWidth(0)
                    botao.setMaximumWidth(16777215)
            if compacto and not muito_compacto:
                self.botao_restaurar_camera.setText("Câmera")
                self.botao_foco_carro.setText("Carro")
                self.botao_camera_modo.setText(
                    "Aérea" if self._modo_camera == "terceira_pessoa" else "Atrás"
                )
                self.botao_voltar_planejamento.setText("Voltar")

    def resizeEvent(self, evento) -> None:  # noqa: N802 - contrato Qt
        super().resizeEvent(evento)
        if self._renderizador_qtquick3d is not None:
            self._renderizador_qtquick3d.setGeometry(self.rect())
            self._controles.raise_()
        self._ajustar_controles_responsivos()

    def closeEvent(self, evento) -> None:  # noqa: N802 - contrato Qt
        self._parar_timer()
        self.parar_renderizador_glb()
        evento.accept()


# Aliases de descoberta para integrações que tratam as visualizações como
# ``MapaCidade``/``VisualizadorGrafo``.
MapaCidade3D = Cidade3DWidget
VisualizadorCidade3D = Cidade3DWidget

