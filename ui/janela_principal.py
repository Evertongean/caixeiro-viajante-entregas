"""Janela principal nova, sem dependências da interface descartada."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from models.grafo import criar_cenario_exemplo

from .assets_3d import ConversorBalsam
from .tema import FOLHA_ESTILOS
from .visualizacao_3d import Visualizacao3D


def _layout_sem_margem(widget: QWidget, *, espacamento: int = 0) -> QVBoxLayout:
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(espacamento)
    return layout


class CartaoInformacao(QFrame):
    def __init__(self, icone: str, titulo: str, valor: str, object_name: str) -> None:
        super().__init__()
        self.setObjectName("cartaoInformacao")
        self.setMinimumHeight(88)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 13, 15, 13)
        layout.setSpacing(12)
        rotulo_icone = QLabel(icone)
        rotulo_icone.setObjectName("iconeCartao")
        rotulo_icone.setFixedSize(38, 38)
        rotulo_icone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        textos = QVBoxLayout()
        textos.setSpacing(4)
        rotulo = QLabel(titulo.upper())
        rotulo.setObjectName("rotuloCartao")
        self.valor = QLabel(valor)
        self.valor.setObjectName(object_name)
        self.valor.setProperty("classe", "valorCartao")
        self.valor.setStyleSheet(
            "color:#F5F9FF;font-size:16px;font-weight:700;background:transparent;"
        )
        self.valor.setWordWrap(True)
        textos.addWidget(rotulo)
        textos.addWidget(self.valor)
        layout.addWidget(rotulo_icone)
        layout.addLayout(textos, 1)

    def definir(self, texto: str) -> None:
        self.valor.setText(texto)


class JanelaPrincipal(QMainWindow):
    """Composição responsiva da cidade, controles e cartões de estado."""

    def __init__(
        self,
        *,
        conversor: ConversorBalsam | None = None,
        auto_inicializar_3d: bool = True,
    ) -> None:
        super().__init__()
        self.setObjectName("janelaPrincipal")
        self.setWindowTitle("Delivery Route — Simulador de Rotas")
        self.setMinimumSize(1040, 700)
        self.resize(1440, 900)
        self.setStyleSheet(FOLHA_ESTILOS)
        self._primeira_exibicao = True
        self.grafo = criar_cenario_exemplo()

        raiz = QWidget()
        raiz.setObjectName("raizAplicacao")
        self.setCentralWidget(raiz)
        layout_raiz = QVBoxLayout(raiz)
        layout_raiz.setContentsMargins(18, 0, 18, 16)
        layout_raiz.setSpacing(14)
        layout_raiz.addWidget(self._criar_cabecalho())

        self.divisor = QSplitter(Qt.Orientation.Horizontal)
        self.divisor.setObjectName("divisorPrincipal")
        self.divisor.setChildrenCollapsible(False)
        self.divisor.addWidget(self._criar_painel_cena(conversor, auto_inicializar_3d))
        self.divisor.addWidget(self._criar_painel_controles())
        self.divisor.setStretchFactor(0, 3)
        self.divisor.setStretchFactor(1, 1)
        layout_raiz.addWidget(self.divisor, 1)
        layout_raiz.addLayout(self._criar_cartoes())

        self.visualizacao.estado_alterado.connect(self._atualizar_estado_cena)
        self.visualizacao.camera_alterada.connect(self._camera_alterada)

    def _criar_cabecalho(self) -> QFrame:
        cabecalho = QFrame()
        cabecalho.setObjectName("cabecalho")
        cabecalho.setFixedHeight(76)
        layout = QHBoxLayout(cabecalho)
        layout.setContentsMargins(4, 12, 4, 12)
        layout.setSpacing(12)
        marca = QLabel("DR")
        marca.setObjectName("marca")
        marca.setFixedSize(46, 46)
        marca.setAlignment(Qt.AlignmentFlag.AlignCenter)
        textos = QVBoxLayout()
        textos.setSpacing(1)
        titulo = QLabel("Delivery Route")
        titulo.setObjectName("tituloAplicacao")
        subtitulo = QLabel("Sistema inteligente de otimização de rotas")
        subtitulo.setObjectName("subtituloAplicacao")
        textos.addWidget(titulo)
        textos.addWidget(subtitulo)
        selo = QLabel("SIMULADOR 3D")
        selo.setObjectName("seloAplicacao")
        selo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(marca)
        layout.addLayout(textos)
        layout.addStretch(1)
        layout.addWidget(selo)
        return cabecalho

    def _criar_painel_cena(
        self,
        conversor: ConversorBalsam | None,
        auto_inicializar: bool,
    ) -> QFrame:
        painel = QFrame()
        painel.setObjectName("painelCena")
        painel.setMinimumWidth(620)
        layout = _layout_sem_margem(painel)

        barra = QFrame()
        barra.setObjectName("barraCena")
        barra.setFixedHeight(56)
        barra_layout = QHBoxLayout(barra)
        barra_layout.setContentsMargins(16, 9, 12, 9)
        titulo = QLabel("Cidade 3D")
        titulo.setObjectName("tituloSecao")
        self.estado_cena = QLabel("Aguardando inicialização")
        self.estado_cena.setObjectName("estadoCena")
        barra_layout.addWidget(titulo)
        barra_layout.addWidget(self.estado_cena)
        barra_layout.addStretch(1)
        self.botao_enquadrar = QPushButton("Enquadrar")
        self.botao_aerea = QPushButton("Visão aérea")
        self.botao_focar_carro = QPushButton("Focar carro")
        for botao in (
            self.botao_enquadrar,
            self.botao_aerea,
            self.botao_focar_carro,
        ):
            botao.setEnabled(False)
            barra_layout.addWidget(botao)
        layout.addWidget(barra)

        self.visualizacao = Visualizacao3D(
            painel,
            conversor=conversor,
            auto_inicializar=auto_inicializar,
        )
        layout.addWidget(self.visualizacao, 1)
        dica = QLabel(
            "Arraste com o botão esquerdo para girar  •  botão direito para mover  •  roda para zoom"
        )
        dica.setObjectName("textoSecundario")
        dica.setContentsMargins(16, 7, 16, 9)
        layout.addWidget(dica)
        self.botao_enquadrar.clicked.connect(self.visualizacao.enquadrar_cidade)
        self.botao_aerea.clicked.connect(self.visualizacao.visao_aerea)
        self.botao_focar_carro.clicked.connect(self.visualizacao.focar_carro)
        return painel

    @staticmethod
    def _botao_futuro(texto: str, object_name: str = "") -> QPushButton:
        botao = QPushButton(f"{texto}  ·  Em breve")
        if object_name:
            botao.setObjectName(object_name)
        botao.setEnabled(False)
        botao.setToolTip("Funcionalidade planejada para uma próxima etapa.")
        return botao

    def _criar_painel_controles(self) -> QFrame:
        painel = QFrame()
        painel.setObjectName("painelLateral")
        painel.setMinimumWidth(310)
        painel.setMaximumWidth(440)
        layout = _layout_sem_margem(painel)
        topo = QLabel("Controles")
        topo.setObjectName("tituloSecao")
        topo.setContentsMargins(16, 16, 16, 2)
        layout.addWidget(topo)

        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        conteudo = QWidget()
        grupos = QVBoxLayout(conteudo)
        grupos.setContentsMargins(12, 4, 12, 14)
        grupos.setSpacing(10)
        grupos.addWidget(self._grupo_edicao())
        grupos.addWidget(self._grupo_rota())
        grupos.addWidget(self._grupo_missao())
        grupos.addStretch(1)
        rolagem.setWidget(conteudo)
        layout.addWidget(rolagem, 1)
        return painel

    def _grupo_edicao(self) -> QGroupBox:
        grupo = QGroupBox("Editar cidade")
        layout = QVBoxLayout(grupo)
        layout.setSpacing(7)
        self.botoes_edicao = [
            self._botao_futuro("Adicionar ponto"),
            self._botao_futuro("Adicionar cliente"),
            self._botao_futuro("Definir depósito"),
            self._botao_futuro("Criar rua"),
            self._botao_futuro("Salvar projeto"),
        ]
        for botao in self.botoes_edicao:
            layout.addWidget(botao)
        nota = QLabel("Editor visual reservado para a próxima entrega.")
        nota.setObjectName("notaFutura")
        nota.setWordWrap(True)
        layout.addWidget(nota)
        return grupo

    def _grupo_rota(self) -> QGroupBox:
        grupo = QGroupBox("Calcular rota")
        layout = QVBoxLayout(grupo)
        layout.setSpacing(8)
        self.seletor_algoritmo = QComboBox()
        self.seletor_algoritmo.setObjectName("seletorAlgoritmo")
        self.seletor_algoritmo.addItem("Dijkstra — menor caminho", "dijkstra")
        self.seletor_algoritmo.addItem("Caixeiro Viajante — TSP", "tsp")
        layout.addWidget(self.seletor_algoritmo)

        self.campos_algoritmo = QStackedWidget()
        pagina_dijkstra = QWidget()
        campos_dijkstra = QVBoxLayout(pagina_dijkstra)
        campos_dijkstra.setContentsMargins(0, 0, 0, 0)
        self.origem = QComboBox()
        self.destino = QComboBox()
        for vertice in self.grafo.listar_vertices():
            texto = f"{vertice.identificador} — {vertice.nome}"
            self.origem.addItem(texto, vertice.identificador)
            self.destino.addItem(texto, vertice.identificador)
        self.destino.setCurrentIndex(self.destino.findData("B"))
        self.origem.setEnabled(False)
        self.destino.setEnabled(False)
        campos_dijkstra.addWidget(QLabel("Origem"))
        campos_dijkstra.addWidget(self.origem)
        campos_dijkstra.addWidget(QLabel("Destino"))
        campos_dijkstra.addWidget(self.destino)

        pagina_tsp = QWidget()
        campos_tsp = QVBoxLayout(pagina_tsp)
        campos_tsp.setContentsMargins(0, 0, 0, 0)
        campos_tsp.addWidget(QLabel("Clientes"))
        self.lista_clientes = QListWidget()
        self.lista_clientes.setMaximumHeight(92)
        for cliente in self.grafo.listar_clientes():
            item = QListWidgetItem(f"{cliente.identificador} — {cliente.nome}")
            item.setCheckState(Qt.CheckState.Checked)
            self.lista_clientes.addItem(item)
        self.lista_clientes.setEnabled(False)
        campos_tsp.addWidget(self.lista_clientes)
        self.campos_algoritmo.addWidget(pagina_dijkstra)
        self.campos_algoritmo.addWidget(pagina_tsp)
        layout.addWidget(self.campos_algoritmo)
        self.botao_calcular = self._botao_futuro("Calcular rota", "botaoPrimario")
        layout.addWidget(self.botao_calcular)
        nota = QLabel("A integração matemática será ativada na próxima etapa.")
        nota.setObjectName("notaFutura")
        nota.setWordWrap(True)
        layout.addWidget(nota)
        self.seletor_algoritmo.currentIndexChanged.connect(
            self.campos_algoritmo.setCurrentIndex
        )
        return grupo

    def _grupo_missao(self) -> QGroupBox:
        grupo = QGroupBox("Missão 3D")
        layout = QVBoxLayout(grupo)
        layout.setSpacing(7)
        self.botao_iniciar = self._botao_futuro("Iniciar missão", "botaoMissao")
        self.botao_pausar = self._botao_futuro("Pausar")
        self.botao_continuar = self._botao_futuro("Continuar")
        self.botao_reiniciar = self._botao_futuro("Reiniciar")
        for botao in (
            self.botao_iniciar,
            self.botao_pausar,
            self.botao_continuar,
            self.botao_reiniciar,
        ):
            layout.addWidget(botao)
        cameras = QHBoxLayout()
        self.botao_camera_livre = QPushButton("Câmera livre")
        self.botao_camera_atras = QPushButton("Atrás do carro")
        self.botao_camera_livre.setEnabled(False)
        self.botao_camera_atras.setEnabled(False)
        cameras.addWidget(self.botao_camera_livre)
        cameras.addWidget(self.botao_camera_atras)
        layout.addLayout(cameras)
        nota = QLabel("As câmeras estão prontas; a animação da missão ainda não.")
        nota.setObjectName("notaFutura")
        nota.setWordWrap(True)
        layout.addWidget(nota)
        self.botao_camera_livre.clicked.connect(self.visualizacao.camera_livre)
        self.botao_camera_atras.clicked.connect(
            self.visualizacao.camera_atras_do_carro
        )
        return grupo

    def _criar_cartoes(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)
        self.cartao_distancia = CartaoInformacao(
            "↔", "Distância total", "—", "valorDistancia"
        )
        self.cartao_percurso = CartaoInformacao(
            "⌁", "Percurso", "Nenhuma rota calculada", "valorPercurso"
        )
        self.cartao_clientes = CartaoInformacao(
            "◎", "Clientes atendidos", "0", "valorClientes"
        )
        self.cartao_status = CartaoInformacao(
            "●", "Status", "Preparando cena 3D", "valorStatus"
        )
        for cartao in (
            self.cartao_distancia,
            self.cartao_percurso,
            self.cartao_clientes,
            self.cartao_status,
        ):
            layout.addWidget(cartao, 1)
        return layout

    def _atualizar_estado_cena(self, mensagem: str, ok: bool) -> None:
        resumo = mensagem
        if "Cidade e carro carregados" in mensagem:
            resumo = "Cena 3D pronta"
        elif "backend atual" in mensagem:
            resumo = "Backend 3D indisponível"
        elif "Modelos preparados" in mensagem:
            resumo = "Finalizando modelos…"
        elif "Falha" in mensagem:
            resumo = "Falha no renderizador"
        elif "Preparando" in mensagem:
            resumo = "Convertendo modelos…"
        elif "Inicializando" in mensagem:
            resumo = "Inicializando 3D…"
        self.estado_cena.setText(resumo)
        self.cartao_status.definir(resumo)
        pronto = ok and (
            self.visualizacao.modelos_preparados
            or "Modelos preparados" in mensagem
            or "Cidade e carro carregados" in mensagem
        )
        if pronto:
            for botao in (
                self.botao_enquadrar,
                self.botao_aerea,
                self.botao_focar_carro,
                self.botao_camera_livre,
                self.botao_camera_atras,
            ):
                botao.setEnabled(True)

    def _camera_alterada(self, modo: str) -> None:
        nomes = {
            "livre": "Câmera livre",
            "aerea": "Visão aérea",
            "atras_do_carro": "Câmera atrás do carro",
        }
        if self.visualizacao.modelos_preparados:
            self.estado_cena.setText(nomes.get(modo, "Cena 3D pronta"))

    def showEvent(self, evento) -> None:  # noqa: N802 - API Qt
        super().showEvent(evento)
        if self._primeira_exibicao:
            self._primeira_exibicao = False
            largura = max(self.divisor.width(), 1000)
            self.divisor.setSizes([int(largura * 0.75), int(largura * 0.25)])

    def closeEvent(self, evento: QCloseEvent) -> None:  # noqa: N802 - API Qt
        evento.accept()


__all__ = ["CartaoInformacao", "JanelaPrincipal"]
