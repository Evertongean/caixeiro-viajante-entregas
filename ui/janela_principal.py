"""Janela principal nova, sem dependências da interface descartada."""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from math import hypot
from multiprocessing import get_context
from pathlib import Path
from queue import Empty
from threading import Event
from time import perf_counter

from PySide6.QtCore import QSize, QTimer, Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QResizeEvent, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QAbstractScrollArea,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from algorithms.caixeiro_viajante import (
    CalculoTSPCancelado,
    LIMITE_HELD_KARP_CLIENTES,
    LIMITE_PADRAO_CLIENTES,
    permutacoes_forca_bruta,
)
from algorithms.forca_bruta_tempo_real import (
    ProgressoForcaBruta,
    ResultadoForcaBrutaTempoReal,
)
from algorithms.processo_forca_bruta import executar_forca_bruta_processo
from models.cenario_academico import (
    CAMINHO_CENARIO_ACADEMICO,
    CAMINHO_CENARIO_ACADEMICO_18,
)
from models.cenario_inicial import (
    ConfiguracaoCidadeInicial,
    carregar_configuracao_inicial,
    criar_projeto_inicial,
)
from models.grafo import TipoVertice
from models.missao import (
    ControladorMissao,
    ErroMissao,
    EstadoMissao,
    QuadroMissao,
    ResumoMissao,
    TipoEventoMissao,
)
from models.persistencia import ErroPersistencia
from models.projeto_cidade import (
    EstacionamentoVeiculo,
    ProjetoCidade,
    carregar_projeto_cidade,
    salvar_projeto_cidade,
)
from models.rota import (
    AlgoritmoRota,
    EstadoEspacial,
    MetodoTSP,
    RotaCalculada,
    RotaInacessivel,
    calcular_dijkstra,
    calcular_tsp,
    rota_de_resultado_forca_bruta,
)

from .assets_3d import ConversorBalsam
from .animacao_missao import AnimacaoMissao
from .dialogos_editor import (
    DialogoRua,
    DialogoSuperficie,
    DialogoVertice,
)
from .editor_cidade import EditorCidade3D, ModoEditor
from .formatacao import (
    formatar_distancia_km,
    formatar_duracao,
    formatar_inteiro_br,
    formatar_numero_br,
    formatar_percentual_progresso,
)
from .apresentacao_rota import (
    marcadores_rota_qml,
    pontos_para_enquadrar,
    segmentos_rota_qml,
)
from .tema import FOLHA_ESTILOS
from .visualizacao_3d import Visualizacao3D


LOGGER = logging.getLogger(__name__)


def _layout_sem_margem(widget: QWidget, *, espacamento: int = 0) -> QVBoxLayout:
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(espacamento)
    return layout


def _permitir_encolhimento_horizontal(widget: QWidget) -> None:
    """Impede que textos longos imponham largura mínima ao painel lateral."""
    widget.setMinimumWidth(0)
    widget.setSizePolicy(
        QSizePolicy.Policy.Ignored,
        widget.sizePolicy().verticalPolicy(),
    )


def _configurar_combo_responsivo(combo: QComboBox) -> None:
    combo.setMinimumWidth(0)
    combo.setMinimumContentsLength(12)
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    combo.currentTextChanged.connect(combo.setToolTip)


class PilhaAdaptavel(QStackedWidget):
    """Calcula altura somente pela página visível, não pela página mais alta."""

    def sizeHint(self) -> QSize:  # noqa: N802 - API Qt
        atual = self.currentWidget()
        return atual.sizeHint() if atual is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - API Qt
        atual = self.currentWidget()
        if atual is None:
            return super().minimumSizeHint()
        minimo = atual.minimumSizeHint()
        return QSize(0, minimo.height())

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - API Qt
        atual = self.currentWidget()
        return bool(atual is not None and atual.hasHeightForWidth())

    def heightForWidth(self, largura: int) -> int:  # noqa: N802 - API Qt
        atual = self.currentWidget()
        if atual is not None and atual.hasHeightForWidth():
            return atual.heightForWidth(largura)
        return self.sizeHint().height()


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
        if self.valor.text() == texto and self.valor.toolTip() == texto:
            return
        self.valor.setText(texto)
        self.valor.setToolTip(texto)


class JanelaPrincipal(QMainWindow):
    """Composição responsiva da cidade, controles e cartões de estado."""

    def __init__(
        self,
        *,
        conversor: ConversorBalsam | None = None,
        auto_inicializar_3d: bool = True,
        projeto_inicial: ProjetoCidade | None = None,
    ) -> None:
        super().__init__()
        self.setObjectName("janelaPrincipal")
        self.setWindowTitle("Delivery Route — Simulador de Rotas")
        self.setMinimumSize(900, 600)
        self.resize(1440, 900)
        self.setStyleSheet(FOLHA_ESTILOS)
        self._primeira_exibicao = True
        self._editor_inicializado = False
        self.configuracao_inicial: ConfiguracaoCidadeInicial = (
            carregar_configuracao_inicial()
        )
        self._cenario_inicial_limpo = projeto_inicial is None
        self.projeto = projeto_inicial or criar_projeto_inicial(
            self.configuracao_inicial
        )
        self.editor = EditorCidade3D(self.projeto)
        self.grafo = self.projeto.grafo
        self.caminho_projeto: Path | None = None
        self.projeto_modificado = False
        self.rota_calculada: RotaCalculada | None = None
        self._calculando_rota = False
        self._executor_calculo = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="calculo-rota"
        )
        self._futuro_calculo: Future[RotaCalculada] | None = None
        self._cancelamento_calculo: Event | None = None
        self._inicio_calculo = 0.0
        self._timer_calculo = QTimer(self)
        self._timer_calculo.setInterval(50)
        self._timer_calculo.timeout.connect(self._verificar_calculo_rota)
        self._processo_forca_bruta = None
        self._fila_forca_bruta = None
        self._evento_forca_bruta = None
        self._inicio_forca_bruta = 0.0
        self._progresso_forca_bruta: ProgressoForcaBruta | None = None
        self._timer_forca_bruta = QTimer(self)
        self._timer_forca_bruta.setInterval(100)
        self._timer_forca_bruta.timeout.connect(self._verificar_forca_bruta)
        self._ultimo_resultado_held: RotaCalculada | None = None
        self._ultimo_resultado_forca: RotaCalculada | None = None
        self._atualizando_campos_rota = False
        self.controlador_missao: ControladorMissao | None = None
        self.animacao_missao: AnimacaoMissao | None = None
        self._sessao_missao_ativa = False
        self._chave_visual_missao: tuple[object, ...] | None = None
        self._assinatura_campos_grafo: (
            tuple[tuple[str, str, str], ...] | None
        ) = None
        self._colunas_cartoes = 0
        self._aguardando_insercao_curva = False
        self._arraste_superficie_valida = False
        self._validacoes_ruas: dict[tuple[str, str], tuple[bool, bool, str]] = {}

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
        layout_raiz.addWidget(self._criar_cartoes())

        self.visualizacao.estado_alterado.connect(self._atualizar_estado_cena)
        self.visualizacao.camera_alterada.connect(self._camera_alterada)
        self.visualizacao.ponto_selecionado.connect(self._processar_pick)
        self.visualizacao.arraste_controle_iniciado.connect(
            self._iniciar_arraste_controle
        )
        self.visualizacao.arraste_controle_atualizado.connect(
            self._atualizar_arraste_controle
        )
        self.visualizacao.arraste_controle_finalizado.connect(
            self._finalizar_arraste_controle
        )
        self._criar_atalhos_editor()
        self._atualizar_controles_missao()
        self._atualizar_disponibilidade_calculo()

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
        painel.setMinimumWidth(480)
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
        self.botao_aerea = QPushButton("Aérea")
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
            "Arraste com o botão esquerdo para girar  •  botão direito para mover  "
            "•  roda para zoom"
        )
        dica.setObjectName("textoSecundario")
        dica.setContentsMargins(16, 7, 16, 9)
        layout.addWidget(dica)
        self.botao_enquadrar.clicked.connect(self.visualizacao.enquadrar_cidade)
        self.botao_aerea.clicked.connect(self.visualizacao.visao_aerea)
        self.botao_focar_carro.clicked.connect(self.visualizacao.focar_carro)
        return painel

    def _criar_painel_controles(self) -> QFrame:
        painel = QFrame()
        painel.setObjectName("painelLateral")
        painel.setMinimumWidth(320)
        painel.setMaximumWidth(440)
        layout = _layout_sem_margem(painel)
        topo = QLabel("Controles")
        topo.setObjectName("tituloSecao")
        topo.setContentsMargins(16, 16, 16, 2)
        layout.addWidget(topo)

        self.rolagem_controles = QScrollArea()
        self.rolagem_controles.setWidgetResizable(True)
        self.rolagem_controles.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored
        )
        self.rolagem_controles.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        conteudo = QWidget()
        conteudo.setObjectName("conteudoControles")
        conteudo.setMinimumWidth(0)
        conteudo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.conteudo_controles = conteudo
        grupos = QVBoxLayout(conteudo)
        grupos.setContentsMargins(12, 4, 12, 14)
        grupos.setSpacing(10)
        grupos.setAlignment(Qt.AlignmentFlag.AlignTop)
        for grupo in (
            self._grupo_edicao(),
            self._grupo_rota(),
            self._grupo_missao(),
        ):
            grupo.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
            )
            grupos.addWidget(grupo)
        self.rolagem_controles.setWidget(conteudo)
        layout.addWidget(self.rolagem_controles, 1)
        return painel

    def _grupo_edicao(self) -> QGroupBox:
        grupo = QGroupBox("Editar cidade")
        layout = QVBoxLayout(grupo)
        layout.setSpacing(7)
        self.botao_navegar = QPushButton("Navegar")
        self.botao_adicionar_ponto = QPushButton("Adicionar ponto")
        self.botao_adicionar_cliente = QPushButton("Adicionar cliente")
        self.botao_definir_deposito = QPushButton("Definir depósito")
        self.botao_criar_rua = QPushButton("Criar rua")
        # Mantido apenas como adaptador de compatibilidade para projetos/testes
        # antigos. Não integra mais a interface principal nem o fluxo normal.
        self.botao_classificar = QPushButton("Classificar superfície")
        self.botao_classificar.hide()
        self.botoes_edicao = [
            self.botao_navegar,
            self.botao_adicionar_ponto,
            self.botao_adicionar_cliente,
            self.botao_definir_deposito,
            self.botao_criar_rua,
        ]
        self.grupo_ferramentas = QButtonGroup(self)
        self.grupo_ferramentas.setExclusive(True)
        for botao in self.botoes_edicao:
            botao.setCheckable(True)
            self.grupo_ferramentas.addButton(botao)
            botao.setEnabled(False)
            layout.addWidget(botao)
        self.botao_classificar.setCheckable(True)
        self.grupo_ferramentas.addButton(self.botao_classificar)

        self.estado_ferramenta = QLabel("Ferramenta ativa: aguardando a cena 3D")
        self.estado_ferramenta.setObjectName("estadoFerramenta")
        self.estado_ferramenta.setWordWrap(True)
        layout.addWidget(self.estado_ferramenta)

        self.instrucao_editor = QLabel("Aguarde o carregamento da cidade 3D.")
        self.instrucao_editor.setObjectName("instrucaoEditor")
        self.instrucao_editor.setWordWrap(True)
        layout.addWidget(self.instrucao_editor)

        self.resumo_editor = QLabel()
        self.resumo_editor.setObjectName("resumoEditor")
        self.resumo_editor.setWordWrap(True)
        layout.addWidget(self.resumo_editor)

        self.detalhes_rua = QLabel("Nenhuma rua selecionada.")
        self.detalhes_rua.setObjectName("notaFutura")
        self.detalhes_rua.setWordWrap(True)
        layout.addWidget(self.detalhes_rua)

        self.snap_editor = QCheckBox("Snap inteligente")
        self.snap_editor.setChecked(True)
        self.snap_editor.setToolTip(
            "Encaixa pontos próximos a vértices e segmentos já confirmados."
        )
        layout.addWidget(self.snap_editor)

        curvas = QGridLayout()
        self.botao_adicionar_curva = QPushButton("Adicionar ponto")
        self.botao_remover_curva = QPushButton("Remover ponto")
        self.botao_adicionar_curva.setEnabled(False)
        self.botao_remover_curva.setEnabled(False)
        curvas.addWidget(self.botao_adicionar_curva, 0, 0)
        curvas.addWidget(self.botao_remover_curva, 0, 1)
        layout.addLayout(curvas)

        operacao = QGridLayout()
        self.botao_confirmar_edicao = QPushButton("Confirmar")
        self.botao_confirmar_edicao.setObjectName("botaoMissao")
        self.botao_desfazer_edicao = QPushButton("Desfazer")
        self.botao_refazer_edicao = QPushButton("Refazer")
        self.botao_cancelar_edicao = QPushButton("Cancelar")
        for indice, botao in enumerate(
            (
                self.botao_confirmar_edicao,
                self.botao_desfazer_edicao,
                self.botao_refazer_edicao,
            )
        ):
            botao.setEnabled(False)
            operacao.addWidget(botao, 0, indice)
        self.botao_cancelar_edicao.setEnabled(False)
        operacao.addWidget(self.botao_cancelar_edicao, 1, 0, 1, 3)
        layout.addLayout(operacao)

        selecao = QGridLayout()
        self.botao_editar_selecao = QPushButton("Editar")
        self.botao_reposicionar = QPushButton("Reposicionar")
        self.botao_excluir_selecao = QPushButton("Excluir")
        for indice, botao in enumerate(
            (self.botao_editar_selecao, self.botao_reposicionar)
        ):
            botao.setEnabled(False)
            selecao.addWidget(botao, 0, indice)
        self.botao_excluir_selecao.setEnabled(False)
        selecao.addWidget(self.botao_excluir_selecao, 1, 0, 1, 2)
        layout.addLayout(selecao)

        arquivos = QHBoxLayout()
        self.botao_novo_projeto = QPushButton("Novo")
        self.botao_abrir_projeto = QPushButton("Abrir")
        self.botao_salvar_projeto = QPushButton("Salvar")
        arquivos.addWidget(self.botao_novo_projeto)
        arquivos.addWidget(self.botao_abrir_projeto)
        arquivos.addWidget(self.botao_salvar_projeto)
        layout.addLayout(arquivos)
        self.botao_carregar_grafo_academico = QPushButton(
            "Carregar grafo acadêmico"
        )
        self.botao_carregar_grafo_academico.setToolTip(
            "Abre o exemplo de 5 vértices e 8 arestas sobre as ruas da cidade."
        )
        layout.addWidget(self.botao_carregar_grafo_academico)
        self.botao_carregar_grafo_academico_18 = QPushButton(
            "Carregar grafo de 18 vértices"
        )
        self.botao_carregar_grafo_academico_18.setToolTip(
            "Abre o grafo acadêmico completo com 45 arestas viárias validadas."
        )
        layout.addWidget(self.botao_carregar_grafo_academico_18)

        self.botao_navegar.clicked.connect(self._modo_navegar)
        self.botao_adicionar_ponto.clicked.connect(
            lambda: self._ativar_adicao(None)
        )
        self.botao_adicionar_cliente.clicked.connect(
            lambda: self._ativar_adicao(TipoVertice.CLIENTE)
        )
        self.botao_definir_deposito.clicked.connect(
            self._ativar_definicao_deposito
        )
        self.botao_criar_rua.clicked.connect(self._ativar_criacao_rua)
        self.botao_classificar.clicked.connect(self._ativar_classificacao)
        self.botao_confirmar_edicao.clicked.connect(self._confirmar_operacao)
        self.botao_desfazer_edicao.clicked.connect(self._desfazer_operacao)
        self.botao_refazer_edicao.clicked.connect(self._refazer_operacao)
        self.botao_cancelar_edicao.clicked.connect(self._cancelar_operacao)
        self.botao_adicionar_curva.clicked.connect(self._ativar_insercao_curva)
        self.botao_remover_curva.clicked.connect(self._remover_curva_selecionada)
        self.snap_editor.toggled.connect(self._alternar_snap)
        self.botao_editar_selecao.clicked.connect(self._editar_selecao)
        self.botao_reposicionar.clicked.connect(self._reposicionar_selecao)
        self.botao_excluir_selecao.clicked.connect(self._excluir_selecao)
        self.botao_novo_projeto.clicked.connect(self.novo_cenario)
        self.botao_abrir_projeto.clicked.connect(lambda: self.abrir_projeto())
        self.botao_salvar_projeto.clicked.connect(lambda: self.salvar_projeto())
        self.botao_carregar_grafo_academico.clicked.connect(
            lambda: self.carregar_grafo_academico()
        )
        self.botao_carregar_grafo_academico_18.clicked.connect(
            lambda: self.carregar_grafo_academico_18()
        )
        return grupo

    def _grupo_rota(self) -> QGroupBox:
        grupo = QGroupBox("Calcular rota")
        layout = QVBoxLayout(grupo)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.seletor_algoritmo = QComboBox()
        self.seletor_algoritmo.setObjectName("seletorAlgoritmo")
        _configurar_combo_responsivo(self.seletor_algoritmo)
        self.seletor_algoritmo.addItem("Dijkstra — menor caminho", "dijkstra")
        self.seletor_algoritmo.addItem("Caixeiro Viajante — TSP", "tsp")
        layout.addWidget(self.seletor_algoritmo)

        self.campos_algoritmo = PilhaAdaptavel()
        self.campos_algoritmo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        pagina_dijkstra = QWidget()
        pagina_dijkstra.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        campos_dijkstra = QVBoxLayout(pagina_dijkstra)
        campos_dijkstra.setContentsMargins(0, 0, 0, 0)
        campos_dijkstra.setSpacing(5)
        campos_dijkstra.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.origem = QComboBox()
        self.destino = QComboBox()
        _configurar_combo_responsivo(self.origem)
        _configurar_combo_responsivo(self.destino)
        for vertice in self.grafo.listar_vertices():
            texto = f"{vertice.identificador} — {vertice.nome}"
            self.origem.addItem(texto, vertice.identificador)
            self.destino.addItem(texto, vertice.identificador)
        self.destino.setCurrentIndex(self.destino.findData("B"))
        campos_dijkstra.addWidget(QLabel("Origem"))
        campos_dijkstra.addWidget(self.origem)
        campos_dijkstra.addWidget(QLabel("Destino"))
        campos_dijkstra.addWidget(self.destino)

        pagina_tsp = QWidget()
        pagina_tsp.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        campos_tsp = QVBoxLayout(pagina_tsp)
        campos_tsp.setContentsMargins(0, 0, 0, 0)
        campos_tsp.setSpacing(6)
        campos_tsp.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.deposito_tsp = QLabel()
        self.deposito_tsp.setObjectName("depositoTsp")
        deposito = self.grafo.obter_deposito()
        self.deposito_tsp.setText(
            f"{deposito.identificador} — {deposito.nome}"
            if deposito is not None
            else "Nenhum depósito cadastrado"
        )
        self.deposito_tsp.setWordWrap(True)
        _permitir_encolhimento_horizontal(self.deposito_tsp)
        campos_tsp.addWidget(QLabel("Depósito"))
        campos_tsp.addWidget(self.deposito_tsp)
        self.selecionar_todos_clientes = QCheckBox("Selecionar todos")
        self.selecionar_todos_clientes.setTristate(True)
        self.selecionar_todos_clientes.setChecked(True)
        campos_tsp.addWidget(self.selecionar_todos_clientes)
        campos_tsp.addWidget(QLabel("Clientes"))
        self.lista_clientes = QListWidget()
        self.lista_clientes.setMinimumWidth(0)
        self.lista_clientes.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.lista_clientes.setMaximumHeight(108)
        for cliente in self.grafo.listar_clientes():
            item = QListWidgetItem(f"{cliente.identificador} — {cliente.nome}")
            item.setData(Qt.ItemDataRole.UserRole, cliente.identificador)
            item.setCheckState(Qt.CheckState.Checked)
            self.lista_clientes.addItem(item)
        campos_tsp.addWidget(self.lista_clientes)
        self.quantidade_clientes = QLabel()
        self.quantidade_clientes.setObjectName("quantidadeClientes")
        self.quantidade_clientes.setWordWrap(True)
        _permitir_encolhimento_horizontal(self.quantidade_clientes)
        campos_tsp.addWidget(self.quantidade_clientes)
        campos_tsp.addWidget(QLabel("Método de cálculo"))
        self.seletor_metodo_tsp = QComboBox()
        _configurar_combo_responsivo(self.seletor_metodo_tsp)
        self.seletor_metodo_tsp.addItem(
            "Held–Karp — programação dinâmica exata",
            MetodoTSP.HELD_KARP.value,
        )
        self.seletor_metodo_tsp.addItem(
            "Força Bruta — Demonstração em Tempo Real",
            MetodoTSP.FORCA_BRUTA_DEMONSTRACAO.value,
        )
        self.seletor_metodo_tsp.addItem(
            "Força bruta — permutações (máx. 8)",
            MetodoTSP.FORCA_BRUTA.value,
        )
        campos_tsp.addWidget(self.seletor_metodo_tsp)

        painel_complexidade = QGroupBox("Análise de complexidade")
        grade_complexidade = QGridLayout(painel_complexidade)
        grade_complexidade.setContentsMargins(9, 9, 9, 9)
        grade_complexidade.setHorizontalSpacing(8)
        grade_complexidade.setVerticalSpacing(5)
        grade_complexidade.setColumnStretch(0, 1)
        grade_complexidade.setColumnStretch(1, 1)
        self.complexidade_vertices = QLabel()
        self.complexidade_clientes = QLabel()
        self.complexidade_permutacoes = QLabel()
        self.complexidade_algoritmo = QLabel()
        self.complexidade_tempo = QLabel("—")
        self.complexidade_peso = QLabel("—")
        campos_complexidade = (
            ("Vértices do grafo", self.complexidade_vertices),
            ("Clientes selecionados", self.complexidade_clientes),
            ("Permutações (n!)", self.complexidade_permutacoes),
            ("Algoritmo", self.complexidade_algoritmo),
            ("Tempo de execução", self.complexidade_tempo),
            ("Peso total", self.complexidade_peso),
        )
        for linha, (rotulo, valor) in enumerate(campos_complexidade):
            etiqueta = QLabel(rotulo)
            etiqueta.setWordWrap(True)
            _permitir_encolhimento_horizontal(etiqueta)
            grade_complexidade.addWidget(etiqueta, linha, 0)
            valor.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
            )
            valor.setWordWrap(True)
            _permitir_encolhimento_horizontal(valor)
            valor.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            grade_complexidade.addWidget(valor, linha, 1)
        explicacao = QLabel(
            "n! representa o espaço de busca da força bruta; não é a quantidade "
            "de operações executadas por Held–Karp ou por uma heurística."
        )
        explicacao.setObjectName("notaFutura")
        explicacao.setWordWrap(True)
        _permitir_encolhimento_horizontal(explicacao)
        grade_complexidade.addWidget(explicacao, len(campos_complexidade), 0, 1, 2)
        campos_tsp.addWidget(painel_complexidade)

        self.painel_progresso_forca = QGroupBox("Progresso da força bruta")
        progresso_layout = QVBoxLayout(self.painel_progresso_forca)
        progresso_layout.setContentsMargins(9, 9, 9, 9)
        progresso_layout.setSpacing(7)

        def titulo_bloco(texto: str) -> QLabel:
            titulo = QLabel(texto)
            titulo.setObjectName("subtituloPainel")
            return titulo

        def preparar_grade(grade: QGridLayout) -> None:
            grade.setContentsMargins(0, 0, 0, 0)
            grade.setHorizontalSpacing(8)
            grade.setVerticalSpacing(4)
            grade.setColumnStretch(0, 1)
            grade.setColumnStretch(1, 1)

        def adicionar_metrica(
            grade: QGridLayout,
            linha: int,
            texto: str,
            valor: QLabel,
        ) -> None:
            etiqueta = QLabel(texto)
            etiqueta.setWordWrap(True)
            _permitir_encolhimento_horizontal(etiqueta)
            valor.setWordWrap(True)
            valor.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
            )
            valor.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            _permitir_encolhimento_horizontal(valor)
            grade.addWidget(etiqueta, linha, 0)
            grade.addWidget(valor, linha, 1)

        self.progresso_clientes = QLabel("—")
        self.progresso_total = QLabel("—")
        self.progresso_avaliadas = QLabel("0")
        self.progresso_percentual = QLabel("0,000000%")
        progresso_layout.addWidget(titulo_bloco("PROGRESSO"))
        grade_progresso = QGridLayout()
        preparar_grade(grade_progresso)
        for linha, (rotulo, valor) in enumerate(
            (
                ("Clientes selecionados", self.progresso_clientes),
                ("Total de permutações", self.progresso_total),
                ("Realmente avaliadas", self.progresso_avaliadas),
                ("Percentual concluído", self.progresso_percentual),
            )
        ):
            adicionar_metrica(grade_progresso, linha, rotulo, valor)
        progresso_layout.addLayout(grade_progresso)
        self.barra_progresso_forca = QProgressBar()
        self.barra_progresso_forca.setRange(0, 1_000_000)
        self.barra_progresso_forca.setValue(0)
        self.barra_progresso_forca.setFormat("0,000000%")
        self.barra_progresso_forca.setTextVisible(True)
        progresso_layout.addWidget(self.barra_progresso_forca)

        self.progresso_taxa = QLabel("—")
        self.progresso_tempo = QLabel("0,0 s")
        self.progresso_estimativa = QLabel("Aguardando dados suficientes")
        progresso_layout.addWidget(titulo_bloco("DESEMPENHO"))
        grade_desempenho = QGridLayout()
        preparar_grade(grade_desempenho)
        for linha, (rotulo, valor) in enumerate(
            (
                ("Permutações por segundo", self.progresso_taxa),
                ("Tempo decorrido", self.progresso_tempo),
                ("Tempo restante estimado", self.progresso_estimativa),
            )
        ):
            adicionar_metrica(grade_desempenho, linha, rotulo, valor)
        progresso_layout.addLayout(grade_desempenho)

        progresso_layout.addWidget(titulo_bloco("MELHOR SOLUÇÃO PARCIAL"))
        self.progresso_melhor_custo = QLabel("—")
        grade_melhor = QGridLayout()
        preparar_grade(grade_melhor)
        adicionar_metrica(
            grade_melhor, 0, "Melhor custo encontrado", self.progresso_melhor_custo
        )
        progresso_layout.addLayout(grade_melhor)
        rotulo_sequencia = QLabel("Melhor sequência encontrada")
        rotulo_sequencia.setWordWrap(True)
        _permitir_encolhimento_horizontal(rotulo_sequencia)
        progresso_layout.addWidget(rotulo_sequencia)
        self.progresso_melhor_ordem = QPlainTextEdit()
        self.progresso_melhor_ordem.setReadOnly(True)
        self.progresso_melhor_ordem.setPlainText("—")
        self.progresso_melhor_ordem.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )
        self.progresso_melhor_ordem.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.progresso_melhor_ordem.setMinimumHeight(62)
        self.progresso_melhor_ordem.setMaximumHeight(88)
        self.progresso_melhor_ordem.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        progresso_layout.addWidget(self.progresso_melhor_ordem)

        progresso_layout.addWidget(titulo_bloco("CONTROLES"))
        grade_controles = QGridLayout()
        preparar_grade(grade_controles)
        grade_controles.addWidget(QLabel("Duração máxima"), 0, 0)
        self.duracao_maxima_forca = QComboBox()
        _configurar_combo_responsivo(self.duracao_maxima_forca)
        self.duracao_maxima_forca.addItem("Sem limite", None)
        self.duracao_maxima_forca.addItem("10 segundos", 10.0)
        self.duracao_maxima_forca.addItem("30 segundos", 30.0)
        self.duracao_maxima_forca.addItem("60 segundos", 60.0)
        self.duracao_maxima_forca.setCurrentIndex(1)
        grade_controles.addWidget(self.duracao_maxima_forca, 0, 1)
        self.botao_iniciar_forca = QPushButton("Iniciar cálculo")
        self.botao_iniciar_forca.setObjectName("botaoPrimario")
        self.botao_interromper_forca = QPushButton("Interromper cálculo")
        self.botao_interromper_forca.setEnabled(False)
        grade_controles.addWidget(self.botao_iniciar_forca, 1, 0, 1, 2)
        grade_controles.addWidget(self.botao_interromper_forca, 2, 0, 1, 2)
        progresso_layout.addLayout(grade_controles)
        self.estado_forca_bruta = QLabel("Aguardando início.")
        self.estado_forca_bruta.setObjectName("notaFutura")
        self.estado_forca_bruta.setWordWrap(True)
        _permitir_encolhimento_horizontal(self.estado_forca_bruta)
        progresso_layout.addWidget(self.estado_forca_bruta)
        self.painel_progresso_forca.setVisible(False)
        campos_tsp.addWidget(self.painel_progresso_forca)

        comparacao = QGroupBox("Comparação dos métodos")
        comparacao_layout = QVBoxLayout(comparacao)
        self.comparacao_held = QLabel("Held–Karp: ainda não executado.")
        self.comparacao_forca = QLabel("Força bruta: ainda não executada.")
        self.comparacao_held.setWordWrap(True)
        self.comparacao_forca.setWordWrap(True)
        _permitir_encolhimento_horizontal(self.comparacao_held)
        _permitir_encolhimento_horizontal(self.comparacao_forca)
        comparacao_layout.addWidget(self.comparacao_held)
        comparacao_layout.addWidget(self.comparacao_forca)
        campos_tsp.addWidget(comparacao)
        self.campos_algoritmo.addWidget(pagina_dijkstra)
        self.campos_algoritmo.addWidget(pagina_tsp)
        self.campos_algoritmo.currentChanged.connect(
            lambda _indice: self._recalcular_layout_controles()
        )
        layout.addWidget(self.campos_algoritmo)
        self.botao_calcular = QPushButton("Calcular menor caminho")
        self.botao_calcular.setObjectName("botaoPrimario")
        layout.addWidget(self.botao_calcular)
        self.botao_cancelar_calculo = QPushButton("Cancelar cálculo")
        self.botao_cancelar_calculo.setEnabled(False)
        self.botao_cancelar_calculo.setVisible(False)
        layout.addWidget(self.botao_cancelar_calculo)
        acoes = QHBoxLayout()
        self.botao_limpar_rota = QPushButton("Limpar rota")
        self.botao_enquadrar_rota = QPushButton("Enquadrar rota")
        self.botao_limpar_rota.setEnabled(False)
        self.botao_enquadrar_rota.setEnabled(False)
        acoes.addWidget(self.botao_limpar_rota)
        acoes.addWidget(self.botao_enquadrar_rota)
        layout.addLayout(acoes)
        self.mostrar_rede_ruas = QCheckBox("Mostrar rede de ruas")
        self.mostrar_rede_ruas.setChecked(True)
        self.mostrar_rede_ruas.setToolTip(
            "Mantém as conexões cadastradas visíveis sob o destaque da rota."
        )
        layout.addWidget(self.mostrar_rede_ruas)

        self.resultado_ordem = QLabel()
        self.resultado_ordem.setObjectName("resultadoRota")
        self.resultado_ordem.setWordWrap(True)
        self.resultado_percurso = QLabel()
        self.resultado_percurso.setObjectName("resultadoRota")
        self.resultado_percurso.setWordWrap(True)
        self.resultado_clientes = QLabel()
        self.resultado_clientes.setObjectName("resultadoRota")
        self.resultado_clientes.setWordWrap(True)
        self.resultado_calibracao = QLabel("Aguardando cálculo.")
        self.resultado_calibracao.setObjectName("notaFutura")
        self.resultado_calibracao.setWordWrap(True)
        layout.addWidget(self.resultado_ordem)
        layout.addWidget(self.resultado_percurso)
        layout.addWidget(self.resultado_clientes)
        self.resultado_metricas = QLabel()
        self.resultado_metricas.setObjectName("resultadoRota")
        self.resultado_metricas.setWordWrap(True)
        for resultado in (
            self.resultado_ordem,
            self.resultado_percurso,
            self.resultado_clientes,
            self.resultado_metricas,
            self.resultado_calibracao,
        ):
            _permitir_encolhimento_horizontal(resultado)
        layout.addWidget(self.resultado_metricas)
        layout.addWidget(self.resultado_calibracao)

        self.seletor_algoritmo.currentIndexChanged.connect(
            self._algoritmo_rota_alterado
        )
        self.mostrar_rede_ruas.toggled.connect(
            self.visualizacao.definir_rede_ruas_visivel
        )
        self.origem.currentIndexChanged.connect(self._entrada_rota_alterada)
        self.destino.currentIndexChanged.connect(self._entrada_rota_alterada)
        self.lista_clientes.itemChanged.connect(self._clientes_alterados)
        self.seletor_metodo_tsp.currentIndexChanged.connect(
            self._metodo_tsp_alterado
        )
        self.selecionar_todos_clientes.toggled.connect(
            self._selecionar_todos_clientes
        )
        self.botao_calcular.clicked.connect(self._calcular_rota)
        self.botao_cancelar_calculo.clicked.connect(self._cancelar_calculo_rota)
        self.botao_interromper_forca.clicked.connect(
            self._interromper_forca_bruta
        )
        self.botao_iniciar_forca.clicked.connect(self._calcular_rota)
        self.botao_limpar_rota.clicked.connect(lambda: self.limpar_rota())
        self.botao_enquadrar_rota.clicked.connect(self._enquadrar_rota)
        self._atualizar_resumo_clientes()
        return grupo

    def _grupo_missao(self) -> QGroupBox:
        grupo = QGroupBox("Missão 3D")
        layout = QVBoxLayout(grupo)
        layout.setSpacing(7)
        self.botao_iniciar = QPushButton("Iniciar missão")
        self.botao_iniciar.setObjectName("botaoMissao")
        self.botao_pausar = QPushButton("Pausar")
        self.botao_continuar = QPushButton("Continuar")
        self.botao_reiniciar = QPushButton("Reiniciar")
        self.botao_encerrar = QPushButton("Encerrar missão")
        for botao in (
            self.botao_iniciar,
            self.botao_pausar,
            self.botao_continuar,
            self.botao_reiniciar,
            self.botao_encerrar,
        ):
            botao.setEnabled(False)
            layout.addWidget(botao)

        velocidade = QHBoxLayout()
        velocidade.addWidget(QLabel("Velocidade"))
        self.seletor_velocidade = QComboBox()
        for texto, valor in (
            ("0,5×", 0.5), ("1×", 1.0), ("2×", 2.0), ("4×", 4.0),
            ("8×", 8.0), ("16×", 16.0), ("32×", 32.0), ("64×", 64.0),
        ):
            self.seletor_velocidade.addItem(texto, valor)
        self.seletor_velocidade.setCurrentIndex(1)
        velocidade.addWidget(self.seletor_velocidade, 1)
        layout.addLayout(velocidade)
        self.modo_apresentacao = QCheckBox("Modo apresentação (inicia em 16×)")
        self.modo_apresentacao.setToolTip(
            "Os valores são multiplicadores do tempo de simulação, não velocidades reais."
        )
        layout.addWidget(self.modo_apresentacao)
        self.indicador_velocidade = QLabel(
            "Velocidade: 0,000 unid./s · Parado"
        )
        self.indicador_velocidade.setObjectName("notaFutura")
        self.indicador_velocidade.setWordWrap(True)
        _permitir_encolhimento_horizontal(self.indicador_velocidade)
        layout.addWidget(self.indicador_velocidade)

        cameras = QGridLayout()
        self.botao_camera_livre = QPushButton("Câmera livre")
        self.botao_camera_atras = QPushButton("Atrás do carro")
        self.botao_camera_aerea_missao = QPushButton("Aérea")
        self.botao_camera_livre.setEnabled(False)
        self.botao_camera_atras.setEnabled(False)
        self.botao_camera_aerea_missao.setEnabled(False)
        cameras.addWidget(self.botao_camera_livre, 0, 0)
        cameras.addWidget(self.botao_camera_atras, 0, 1)
        cameras.addWidget(self.botao_camera_aerea_missao, 1, 0, 1, 2)
        layout.addLayout(cameras)
        ajustes_camera = QHBoxLayout()
        self.distancia_camera = QDoubleSpinBox()
        self.distancia_camera.setRange(0.12, 0.80)
        self.distancia_camera.setSingleStep(0.02)
        self.distancia_camera.setValue(0.34)
        self.distancia_camera.setSuffix(" dist.")
        self.altura_camera = QDoubleSpinBox()
        self.altura_camera.setRange(0.06, 0.50)
        self.altura_camera.setSingleStep(0.02)
        self.altura_camera.setValue(0.18)
        self.altura_camera.setSuffix(" alt.")
        ajustes_camera.addWidget(self.distancia_camera)
        ajustes_camera.addWidget(self.altura_camera)
        layout.addLayout(ajustes_camera)
        self.resumo_missao = QLabel("Calcule e calibre uma rota para iniciar.")
        self.resumo_missao.setObjectName("notaFutura")
        self.resumo_missao.setWordWrap(True)
        _permitir_encolhimento_horizontal(self.resumo_missao)
        layout.addWidget(self.resumo_missao)
        self.botao_iniciar.clicked.connect(self._iniciar_missao)
        self.botao_pausar.clicked.connect(self._pausar_missao)
        self.botao_continuar.clicked.connect(self._continuar_missao)
        self.botao_reiniciar.clicked.connect(self._reiniciar_missao)
        self.botao_encerrar.clicked.connect(self._encerrar_missao)
        self.seletor_velocidade.currentIndexChanged.connect(
            self._velocidade_missao_alterada
        )
        self.modo_apresentacao.toggled.connect(self._modo_apresentacao_alterado)
        self.distancia_camera.valueChanged.connect(self._configurar_camera_missao)
        self.altura_camera.valueChanged.connect(self._configurar_camera_missao)
        self.botao_camera_livre.clicked.connect(self.visualizacao.camera_livre)
        self.botao_camera_atras.clicked.connect(
            self.visualizacao.camera_atras_do_carro
        )
        self.botao_camera_aerea_missao.clicked.connect(
            self.visualizacao.visao_aerea
        )
        return grupo

    def _rota_apta_para_missao(self) -> tuple[bool, str]:
        rota = self.rota_calculada
        if rota is None:
            return False, "Calcule uma rota antes de iniciar a missão."
        if (
            rota.metodo_tsp is MetodoTSP.FORCA_BRUTA_DEMONSTRACAO
            and not rota.busca_tsp_completa
        ):
            return (
                False,
                "A solução parcial pode ser visualizada, mas a missão exige "
                "uma busca concluída ou uma rota exata do Held–Karp.",
            )
        if not rota.segmentos_espaciais:
            return False, "A rota é trivial e não possui um trajeto para animar."
        if not rota.calibracao_completa:
            return False, self._texto_ruas_pendentes(rota.arestas_pendentes)
        if not self.visualizacao.modelos_preparados:
            return False, "Aguarde o carregamento do carro e da cidade 3D."
        deposito = self.grafo.obter_deposito()
        if deposito is None:
            return False, "Defina um depósito antes de iniciar a missão."
        estacionamento = self.projeto.estacionamento_inicial
        if (
            estacionamento is None
            or not estacionamento.validado
            or estacionamento.deposito != deposito.identificador
        ):
            return False, "Aguarde a validação do carro junto ao depósito atual."
        if rota.origem != deposito.identificador:
            return False, "A missão deve partir do depósito atual."
        if self.visualizacao.mapa_trafegabilidade is not None:
            for segmento in rota.segmentos_espaciais:
                validacao = self.visualizacao.validar_rua_automatica(segmento.pontos)
                if not validacao.valido:
                    estado = "inconclusiva" if not validacao.conclusivo else "inválida"
                    return (
                        False,
                        f"Rua {segmento.origem} ↔ {segmento.destino} {estado}: "
                        f"{validacao.motivo}",
                    )
        return True, "Rota calibrada e pronta para iniciar."

    @staticmethod
    def _texto_ruas_pendentes(
        arestas: tuple[tuple[str, str], ...],
    ) -> str:
        nomes = [f"{origem} ↔ {destino}" for origem, destino in arestas]
        if len(nomes) == 1:
            introducao = f"Rua {nomes[0]} necessita de calibração espacial."
        else:
            introducao = (
                f"Ruas {'; '.join(nomes)} necessitam de calibração espacial."
            )
        return introducao + " Use Criar rua para traçar e confirmar cada conexão."

    def _atualizar_controles_missao(self) -> None:
        estado = (
            self.controlador_missao.estado
            if self.controlador_missao is not None
            else None
        )
        if self._sessao_missao_ativa:
            # A rota já foi integralmente validada antes de iniciar. Repetir a
            # validação espacial a cada atualização textual percorria todas as
            # ruas e bloqueava a thread gráfica por dezenas de milissegundos.
            apta, motivo = False, "Encerre a missão atual antes de iniciar outra."
        else:
            apta, motivo = self._rota_apta_para_missao()
        self.botao_iniciar.setEnabled(apta and not self._sessao_missao_ativa)
        self.botao_iniciar.setToolTip(motivo)
        self.botao_pausar.setEnabled(
            estado in (EstadoMissao.EM_MOVIMENTO, EstadoMissao.EM_ENTREGA)
        )
        self.botao_continuar.setEnabled(estado is EstadoMissao.PAUSADA)
        self.botao_reiniciar.setEnabled(
            self._sessao_missao_ativa
            and estado
            in (
                EstadoMissao.EM_MOVIMENTO,
                EstadoMissao.EM_ENTREGA,
                EstadoMissao.PAUSADA,
                EstadoMissao.CONCLUIDA,
            )
        )
        self.botao_encerrar.setEnabled(self._sessao_missao_ativa)
        self.seletor_velocidade.setEnabled(
            not self._sessao_missao_ativa
            or estado is not EstadoMissao.CONCLUIDA
        )

    def _definir_bloqueio_missao(self, bloqueado: bool) -> None:
        self._sessao_missao_ativa = bloqueado
        controles_rota = (
            self.seletor_algoritmo,
            self.seletor_metodo_tsp,
            self.origem,
            self.destino,
            self.lista_clientes,
            self.selecionar_todos_clientes,
            self.duracao_maxima_forca,
            self.botao_calcular,
            self.botao_iniciar_forca,
            self.botao_limpar_rota,
        )
        for controle in controles_rota:
            controle.setEnabled(not bloqueado)
        self.botao_abrir_projeto.setEnabled(not bloqueado)
        self.botao_novo_projeto.setEnabled(not bloqueado)
        self.botao_carregar_grafo_academico.setEnabled(not bloqueado)
        self.botao_carregar_grafo_academico_18.setEnabled(not bloqueado)
        if bloqueado:
            self._modo_navegar()
            for botao in self.botoes_edicao:
                botao.setEnabled(False)
            for botao in (
                self.botao_confirmar_edicao,
                self.botao_desfazer_edicao,
                self.botao_refazer_edicao,
                self.botao_cancelar_edicao,
                self.botao_adicionar_curva,
                self.botao_remover_curva,
                self.botao_editar_selecao,
                self.botao_reposicionar,
                self.botao_excluir_selecao,
            ):
                botao.setEnabled(False)
            self.visualizacao.definir_modo_interacao(ModoEditor.NAVEGAR.value)
        else:
            if self.visualizacao.modelos_preparados:
                for botao in self.botoes_edicao:
                    botao.setEnabled(True)
                self._atualizar_disponibilidade_editor()
            self._atualizar_botoes_operacao()
            self._atualizar_botoes_selecao()
            self._atualizar_disponibilidade_calculo()
            self.botao_limpar_rota.setEnabled(self.rota_calculada is not None)
        self._atualizar_controles_missao()

    def _iniciar_missao(self) -> None:
        if self._sessao_missao_ativa:
            return
        apta, motivo = self._rota_apta_para_missao()
        if not apta or self.rota_calculada is None:
            self._mostrar_erro(motivo)
            return
        try:
            estacionamento = self.projeto.estacionamento_inicial
            usar_estacionamento = (
                estacionamento is not None
                and estacionamento.validado
                and self.rota_calculada.origem == estacionamento.deposito
            )
            controlador = ControladorMissao(
                self.rota_calculada,
                posicao_inicial=(
                    estacionamento.posicao if usar_estacionamento else None
                ),
                orientacao_inicial_graus=(
                    estacionamento.orientacao_graus
                    if usar_estacionamento
                    else None
                ),
            )
            controlador.multiplicador_velocidade = float(
                self.seletor_velocidade.currentData()
            )
        except (ErroMissao, TypeError, ValueError) as erro:
            self._mostrar_erro(str(erro))
            return
        self.controlador_missao = controlador
        self.animacao_missao = AnimacaoMissao(controlador, self)
        self.animacao_missao.quadro_atualizado.connect(
            self._atualizar_pose_missao
        )
        self.animacao_missao.painel_atualizado.connect(
            self._atualizar_painel_missao
        )
        self.animacao_missao.concluida.connect(self._missao_concluida)
        self.visualizacao.configurar_diagnostico_desempenho(
            self.animacao_missao.diagnostico
        )
        self._chave_visual_missao = None
        self.resumo_missao.setText("Missão em andamento.")
        self._definir_bloqueio_missao(True)
        self._configurar_camera_missao()
        self.visualizacao.camera_atras_do_carro()
        self.visualizacao.iniciar_apresentacao_missao()
        self.animacao_missao.iniciar()
        self._atualizar_controles_missao()

    def _pausar_missao(self) -> None:
        if self.animacao_missao is None:
            return
        try:
            self.animacao_missao.pausar()
        except ErroMissao:
            return
        self.visualizacao.pausar_apresentacao_missao()
        self._atualizar_controles_missao()

    def _continuar_missao(self) -> None:
        if self.animacao_missao is None:
            return
        try:
            self.animacao_missao.continuar()
        except ErroMissao:
            return
        self.visualizacao.continuar_apresentacao_missao()
        self._atualizar_controles_missao()

    def _reiniciar_missao(self) -> None:
        if self.animacao_missao is None:
            return
        try:
            self._chave_visual_missao = None
            self.resumo_missao.setText("Missão reiniciada.")
            self.visualizacao.encerrar_apresentacao_missao()
            self._aplicar_pose_estacionamento()
            self.visualizacao.iniciar_apresentacao_missao()
            self.animacao_missao.reiniciar()
        except ErroMissao:
            return
        self.visualizacao.camera_atras_do_carro()
        self._atualizar_controles_missao()

    def _encerrar_missao(self) -> None:
        if not self._sessao_missao_ativa:
            return
        resumo = (
            self.controlador_missao.resumo()
            if self.controlador_missao is not None
            else None
        )
        if self.animacao_missao is not None:
            self.animacao_missao.encerrar()
            self.animacao_missao.deleteLater()
        self.visualizacao.encerrar_apresentacao_missao()
        self.visualizacao.configurar_diagnostico_desempenho(None)
        self.animacao_missao = None
        self.controlador_missao = None
        self._chave_visual_missao = None
        self._definir_bloqueio_missao(False)
        if self.rota_calculada is not None:
            self._apresentar_rota(self.rota_calculada)
        if resumo is not None:
            self.resumo_missao.setText(self._texto_resumo_missao(resumo))
        self._aplicar_pose_estacionamento()
        self.cartao_status.definir("Missão encerrada; edição liberada.")

    def _velocidade_missao_alterada(self, _indice: int = -1) -> None:
        if self.controlador_missao is not None:
            self.controlador_missao.multiplicador_velocidade = float(
                self.seletor_velocidade.currentData()
            )

    def _modo_apresentacao_alterado(self, ativo: bool) -> None:
        if ativo:
            indice = self.seletor_velocidade.findData(16.0)
            if indice >= 0:
                self.seletor_velocidade.setCurrentIndex(indice)

    def _configurar_camera_missao(self, *_args) -> None:
        self.visualizacao.configurar_camera_seguidora(
            self.distancia_camera.value(), self.altura_camera.value()
        )

    def _atualizar_pose_missao(
        self, quadro: QuadroMissao, delta_segundos: float
    ) -> None:
        self.visualizacao.atualizar_carro(
            quadro.posicao,
            quadro.orientacao_graus,
            delta_segundos,
            imediato=delta_segundos == 0.0,
            freando=quadro.freando,
            pontos_interpolacao=quadro.pontos_interpolacao,
        )

    def _atualizar_quadro_missao(
        self, quadro: QuadroMissao, delta_segundos: float
    ) -> None:
        """Adaptador de compatibilidade para testes e integrações síncronas."""
        self._atualizar_pose_missao(quadro, delta_segundos)
        self._atualizar_painel_missao(quadro)

    def _atualizar_painel_missao(self, quadro: QuadroMissao) -> None:
        rota = self.rota_calculada
        if rota is None:
            return
        concluida = quadro.estado is EstadoMissao.CONCLUIDA
        chave = (
            quadro.indice_aresta,
            quadro.clientes_atendidos,
            quadro.proximo_cliente,
            concluida,
        )
        if chave != self._chave_visual_missao:
            self.visualizacao.atualizar_destaque_rota(
                segmentos_rota_qml(
                    rota, quadro.indice_aresta, concluida=concluida
                ),
                marcadores_rota_qml(
                    rota,
                    self.projeto,
                    set(quadro.clientes_atendidos),
                    quadro.proximo_cliente,
                ),
            )
            self._chave_visual_missao = chave
        self.cartao_distancia.definir(
            f"{formatar_distancia_km(rota.distancia_total)} · "
            f"{formatar_distancia_km(quadro.distancia_percorrida)} perc. · "
            f"{formatar_distancia_km(quadro.distancia_restante)} rest."
        )
        self.cartao_percurso.definir(
            f"{' → '.join(rota.percurso_completo)} · atual: "
            f"{quadro.origem_aresta} → {quadro.destino_aresta} "
            f"({quadro.indice_aresta + 1}/{len(rota.segmentos_espaciais)})"
        )
        self.cartao_clientes.definir(
            f"{len(quadro.clientes_atendidos)} / {quadro.total_clientes}"
        )
        self.indicador_velocidade.setText(
            f"Velocidade: {quadro.velocidade_atual:.3f} unid./s · "
            f"{quadro.fase_movimento.value.capitalize()}"
        )
        if quadro.estado is EstadoMissao.PAUSADA:
            status = "Missão pausada."
        elif quadro.estado is EstadoMissao.EM_ENTREGA:
            cliente = quadro.clientes_atendidos[-1]
            status = f"Entregando ao cliente {cliente}…"
        elif quadro.estado is EstadoMissao.CONCLUIDA:
            status = "Missão concluída; encerre para liberar a edição."
        elif quadro.estado is EstadoMissao.ENCERRADA:
            status = "Missão encerrada."
        else:
            if (
                rota.algoritmo is AlgoritmoRota.TSP
                and quadro.total_clientes > 0
                and len(quadro.clientes_atendidos) == quadro.total_clientes
            ):
                status = "Retornando ao depósito."
            elif quadro.proximo_cliente is not None:
                status = f"Seguindo para o cliente {quadro.proximo_cliente}."
            else:
                status = quadro.fase_movimento.value.capitalize() + "."
        for evento in quadro.eventos:
            if evento.tipo is TipoEventoMissao.ENTREGA:
                status = f"Entrega em {evento.vertice} confirmada."
        self.cartao_status.definir(status)
        self._atualizar_controles_missao()

    def _missao_concluida(self, resumo: ResumoMissao) -> None:
        self.visualizacao.concluir_apresentacao_missao()
        self.resumo_missao.setText(self._texto_resumo_missao(resumo))
        self._atualizar_controles_missao()

    @staticmethod
    def _texto_resumo_missao(resumo: ResumoMissao) -> str:
        algoritmo = "Dijkstra" if resumo.algoritmo is AlgoritmoRota.DIJKSTRA else "TSP"
        if resumo.algoritmo is AlgoritmoRota.TSP:
            alvo = "clientes: " + (", ".join(resumo.clientes_selecionados) or "nenhum")
            ordem = " · ordem: " + " → ".join(resumo.ordem_atendimento)
        else:
            alvo = f"destino: {resumo.destino}"
            ordem = ""
        estado = "concluída" if resumo.concluida else "interrompida"
        return (
            f"Missão {estado} · algoritmo: {algoritmo} · origem: {resumo.origem} · "
            f"{alvo} · distância: {formatar_numero_br(resumo.distancia_percorrida)}/"
            f"{formatar_distancia_km(resumo.distancia_total)} · "
            f"entregas: {resumo.clientes_atendidos}/"
            f"{resumo.total_clientes}{ordem} · tempo da simulação: "
            f"{resumo.tempo_decorrido:.1f} s."
        )

    def _algoritmo_rota_alterado(self, indice: int) -> None:
        self.campos_algoritmo.setCurrentIndex(indice)
        tsp = self.seletor_algoritmo.currentData() == AlgoritmoRota.TSP.value
        self.botao_calcular.setText(
            "Calcular melhor rota" if tsp else "Calcular menor caminho"
        )
        self._entrada_rota_alterada()
        self._atualizar_visibilidade_controles_rota()
        self._atualizar_complexidade()
        self._atualizar_disponibilidade_calculo()
        self._recalcular_layout_controles()

    def _recalcular_layout_controles(self) -> None:
        """Recalcula alturas após trocar páginas ou revelar painéis internos."""
        self._aplicar_recalculo_layout_controles()
        QTimer.singleShot(0, self._aplicar_recalculo_layout_controles)

    def _aplicar_recalculo_layout_controles(self) -> None:
        if not hasattr(self, "campos_algoritmo"):
            return
        pagina = self.campos_algoritmo.currentWidget()
        if pagina is not None:
            if pagina.layout() is not None:
                pagina.layout().activate()
            pagina.updateGeometry()
        self.campos_algoritmo.updateGeometry()
        if hasattr(self, "conteudo_controles"):
            layout = self.conteudo_controles.layout()
            if layout is not None:
                layout.activate()
            self.conteudo_controles.updateGeometry()
        if hasattr(self, "rolagem_controles"):
            self.rolagem_controles.viewport().update()

    def _metodo_tsp_atual(self) -> MetodoTSP:
        return MetodoTSP(str(self.seletor_metodo_tsp.currentData()))

    def _atualizar_visibilidade_controles_rota(self) -> None:
        tsp = self.seletor_algoritmo.currentData() == AlgoritmoRota.TSP.value
        demonstracao = (
            tsp
            and self._metodo_tsp_atual()
            is MetodoTSP.FORCA_BRUTA_DEMONSTRACAO
        )
        self.painel_progresso_forca.setVisible(demonstracao)
        self.botao_calcular.setVisible(not demonstracao)

    def _limite_tsp_atual(self) -> int:
        return (
            LIMITE_PADRAO_CLIENTES
            if self._metodo_tsp_atual() is MetodoTSP.FORCA_BRUTA
            else LIMITE_HELD_KARP_CLIENTES
        )

    def _metodo_tsp_alterado(self, _indice: int = -1) -> None:
        if self._atualizando_campos_rota:
            return
        self._atualizar_visibilidade_controles_rota()
        limite = self._limite_tsp_atual()
        selecionados = self._clientes_selecionados()
        if len(selecionados) > limite:
            self._atualizando_campos_rota = True
            mantidos = set(selecionados[:limite])
            for indice in range(self.lista_clientes.count()):
                item = self.lista_clientes.item(indice)
                identificador = str(item.data(Qt.ItemDataRole.UserRole))
                item.setCheckState(
                    Qt.CheckState.Checked
                    if identificador in mantidos
                    else Qt.CheckState.Unchecked
                )
            self._atualizando_campos_rota = False
            self._definir_instrucao(
                f"A força bruta preserva o limite de {LIMITE_PADRAO_CLIENTES} clientes."
            )
        self._atualizar_resumo_clientes()
        self._entrada_rota_alterada()
        self._recalcular_layout_controles()

    def _entrada_rota_alterada(self, *_args) -> None:
        if self._atualizando_campos_rota:
            return
        if self.rota_calculada is not None:
            self.limpar_rota(status="Parâmetros alterados. Calcule novamente.")
        self._atualizar_disponibilidade_calculo()

    def _clientes_selecionados(self) -> list[str]:
        return [
            str(self.lista_clientes.item(indice).data(Qt.ItemDataRole.UserRole))
            for indice in range(self.lista_clientes.count())
            if self.lista_clientes.item(indice).checkState()
            == Qt.CheckState.Checked
        ]

    def _selecionar_todos_clientes(self, marcado: bool) -> None:
        if self._atualizando_campos_rota:
            return
        self._atualizando_campos_rota = True
        limite = self._limite_tsp_atual()
        for indice in range(self.lista_clientes.count()):
            selecionar = marcado and indice < limite
            self.lista_clientes.item(indice).setCheckState(
                Qt.CheckState.Checked
                if selecionar
                else Qt.CheckState.Unchecked
            )
        self._atualizando_campos_rota = False
        self._atualizar_resumo_clientes()
        self._entrada_rota_alterada()

    def _clientes_alterados(self, _item: QListWidgetItem) -> None:
        if self._atualizando_campos_rota:
            return
        selecionados = self._clientes_selecionados()
        limite = self._limite_tsp_atual()
        if len(selecionados) > limite:
            self._atualizando_campos_rota = True
            _item.setCheckState(Qt.CheckState.Unchecked)
            self._atualizando_campos_rota = False
            self._definir_instrucao(
                f"O método selecionado aceita até {limite} clientes; "
                "desmarque um cliente antes de escolher outro."
            )
        self._atualizar_resumo_clientes()
        self._entrada_rota_alterada()

    def _atualizar_resumo_clientes(self) -> None:
        total = self.lista_clientes.count()
        selecionados = len(self._clientes_selecionados())
        limite = self._limite_tsp_atual()
        self.quantidade_clientes.setText(
            f"{selecionados} de {total} clientes selecionados · "
            f"limite do método: {limite}"
        )
        self.selecionar_todos_clientes.setText(
            "Selecionar todos"
            if total <= limite
            else f"Selecionar os primeiros {limite}"
        )
        self._atualizando_campos_rota = True
        if selecionados == total:
            estado = Qt.CheckState.Checked
        elif selecionados == 0:
            estado = Qt.CheckState.Unchecked
        else:
            estado = Qt.CheckState.PartiallyChecked
        self.selecionar_todos_clientes.setCheckState(estado)
        self._atualizando_campos_rota = False
        self._atualizar_complexidade()
        if hasattr(self, "comparacao_held"):
            self._atualizar_comparacao_metodos()

    def _atualizar_complexidade(self) -> None:
        if not hasattr(self, "complexidade_vertices"):
            return
        quantidade = len(self._clientes_selecionados())
        total_vertices = len(self.grafo.listar_vertices())
        self.complexidade_vertices.setText(formatar_inteiro_br(total_vertices))
        self.complexidade_clientes.setText(formatar_inteiro_br(quantidade))
        self.complexidade_permutacoes.setText(
            formatar_inteiro_br(permutacoes_forca_bruta(quantidade))
        )
        self.complexidade_algoritmo.setText(
            self._metodo_tsp_atual().nome_exibicao
        )
        if self.rota_calculada is None:
            self.complexidade_tempo.setText("—")
            self.complexidade_peso.setText("—")

    def _calcular_rota(self) -> None:
        if self._calculando_rota or self._sessao_missao_ativa:
            return
        try:
            algoritmo = self.seletor_algoritmo.currentData()
            if algoritmo == AlgoritmoRota.DIJKSTRA.value:
                origem, destino = self.origem.currentData(), self.destino.currentData()
                if origem is None or destino is None:
                    raise ValueError("Selecione uma origem e um destino válidos.")
                argumentos = (str(origem), str(destino))
                metodo = None
            elif algoritmo == AlgoritmoRota.TSP.value:
                clientes = self._clientes_selecionados()
                if not clientes:
                    raise ValueError(
                        "Selecione pelo menos um cliente para calcular a rota TSP."
                    )
                metodo = self._metodo_tsp_atual()
                argumentos = (tuple(clientes),)
            else:
                raise ValueError("Selecione um algoritmo de rota válido.")
        except (KeyError, TypeError, ValueError) as erro:
            self._tratar_erro_calculo(erro)
            return

        if metodo is MetodoTSP.FORCA_BRUTA_DEMONSTRACAO:
            self._iniciar_forca_bruta(tuple(argumentos[0]))
            return

        cancelamento = Event()
        projeto = self.projeto

        def executar() -> RotaCalculada:
            inicio = perf_counter()
            if algoritmo == AlgoritmoRota.DIJKSTRA.value:
                rota = calcular_dijkstra(projeto, *argumentos)
            else:
                rota = calcular_tsp(
                    projeto,
                    argumentos[0],
                    metodo=metodo,
                    cancelado=cancelamento.is_set,
                )
            if cancelamento.is_set():
                raise CalculoTSPCancelado("Cálculo cancelado pelo usuário.")
            return replace(
                rota,
                tempo_processamento_segundos=perf_counter() - inicio,
                total_vertices_grafo=len(projeto.grafo.listar_vertices()),
            )

        calculo_pesado = (
            algoritmo == AlgoritmoRota.TSP.value
            and len(argumentos[0]) > LIMITE_PADRAO_CLIENTES
        )
        if not calculo_pesado:
            try:
                self._apresentar_rota(executar())
            except (KeyError, TypeError, ValueError, MemoryError) as erro:
                self._tratar_erro_calculo(erro)
            return

        self._calculando_rota = True
        self._cancelamento_calculo = cancelamento
        self._futuro_calculo = self._executor_calculo.submit(executar)
        self._inicio_calculo = perf_counter()
        self.botao_calcular.setEnabled(False)
        self.botao_cancelar_calculo.setVisible(True)
        self.botao_cancelar_calculo.setEnabled(True)
        self.cartao_status.definir("Calculando rota em segundo plano…")
        self.complexidade_tempo.setText("Em execução…")
        self.complexidade_peso.setText("—")
        self._definir_controles_calculo(False)
        self._timer_calculo.start()

    def _iniciar_forca_bruta(self, clientes: tuple[str, ...]) -> None:
        contexto = get_context("spawn")
        evento = contexto.Event()
        fila = contexto.Queue(maxsize=16)
        duracao = self.duracao_maxima_forca.currentData()
        processo = contexto.Process(
            target=executar_forca_bruta_processo,
            args=(self.grafo, clientes, duracao, evento, fila),
            name="forca-bruta-tsp",
            daemon=True,
        )
        try:
            processo.start()
        except (OSError, RuntimeError, TypeError) as erro:
            fila.close()
            self._tratar_erro_calculo(
                ValueError(f"Não foi possível iniciar o processo: {erro}")
            )
            return

        self._calculando_rota = True
        self._processo_forca_bruta = processo
        self._fila_forca_bruta = fila
        self._evento_forca_bruta = evento
        self._inicio_forca_bruta = perf_counter()
        self._progresso_forca_bruta = None
        total = permutacoes_forca_bruta(len(clientes))
        self.progresso_clientes.setText(formatar_inteiro_br(len(clientes)))
        self.progresso_total.setText(formatar_inteiro_br(total))
        self.progresso_avaliadas.setText("0")
        self.progresso_percentual.setText("0,000000%")
        self.progresso_taxa.setText("Aguardando medições")
        self.progresso_tempo.setText("0,0 s")
        self.progresso_melhor_custo.setText("—")
        self.progresso_melhor_ordem.setPlainText("—")
        self.progresso_estimativa.setText("Aguardando dados suficientes")
        self.barra_progresso_forca.setValue(0)
        self.barra_progresso_forca.setFormat("0,000000%")
        self.estado_forca_bruta.setText(
            "Busca exaustiva em execução; cada incremento representa uma "
            "permutação realmente avaliada."
        )
        self.botao_interromper_forca.setText("Interromper cálculo")
        self.botao_interromper_forca.setEnabled(True)
        self.botao_calcular.setEnabled(False)
        self.botao_iniciar_forca.setEnabled(False)
        self.cartao_status.definir("Força bruta real em execução…")
        self.complexidade_tempo.setText("Em execução…")
        self.complexidade_peso.setText("—")
        self._definir_controles_calculo(False)
        self._timer_forca_bruta.start()

    def _interromper_forca_bruta(self) -> None:
        if self._evento_forca_bruta is None:
            return
        self._evento_forca_bruta.set()
        self.botao_interromper_forca.setEnabled(False)
        self.botao_interromper_forca.setText("Interrompendo…")
        self.estado_forca_bruta.setText(
            "Solicitação enviada; aguardando a última permutação em execução."
        )

    def _atualizar_progresso_forca(
        self, progresso: ProgressoForcaBruta
    ) -> None:
        self._progresso_forca_bruta = progresso
        self.progresso_clientes.setText(formatar_inteiro_br(progresso.clientes))
        self.progresso_total.setText(
            formatar_inteiro_br(progresso.total_permutacoes)
        )
        self.progresso_avaliadas.setText(
            formatar_inteiro_br(progresso.permutacoes_avaliadas)
        )
        percentual = formatar_percentual_progresso(
            progresso.permutacoes_avaliadas,
            progresso.total_permutacoes,
        )
        self.progresso_percentual.setText(percentual)
        valor_barra = (
            progresso.permutacoes_avaliadas * 1_000_000
            // progresso.total_permutacoes
        )
        self.barra_progresso_forca.setValue(valor_barra)
        self.barra_progresso_forca.setFormat(percentual)
        taxa = progresso.taxa_por_segundo
        self.progresso_taxa.setText(
            f"{formatar_inteiro_br(round(taxa))} perm/s"
            if taxa >= 1
            else f"{taxa:.2f} perm/s".replace(".", ",")
        )
        self.progresso_tempo.setText(
            formatar_duracao(progresso.tempo_decorrido)
        )
        self.progresso_melhor_custo.setText(
            formatar_distancia_km(progresso.melhor_custo)
            if progresso.melhor_custo is not None
            else "—"
        )
        self.progresso_melhor_ordem.setPlainText(
            " → ".join(progresso.melhor_ordem)
            if progresso.melhor_ordem
            else "—"
        )
        if progresso.permutacoes_avaliadas >= progresso.total_permutacoes:
            estimativa = "Concluída"
        elif (
            progresso.tempo_decorrido >= 1.0
            and progresso.permutacoes_avaliadas >= 100
            and taxa > 0
        ):
            restante = (
                progresso.total_permutacoes - progresso.permutacoes_avaliadas
            ) / taxa
            estimativa = f"Estimativa pela taxa real: {formatar_duracao(restante)}"
        else:
            estimativa = "Aguardando dados suficientes"
        self.progresso_estimativa.setText(estimativa)

    def _verificar_forca_bruta(self) -> None:
        fila = self._fila_forca_bruta
        processo = self._processo_forca_bruta
        if fila is None or processo is None:
            self._timer_forca_bruta.stop()
            return
        resultado: ResultadoForcaBrutaTempoReal | None = None
        erro: str | None = None
        while True:
            try:
                tipo, carga = fila.get_nowait()
            except Empty:
                break
            if tipo == "progresso":
                self._atualizar_progresso_forca(carga)
            elif tipo == "resultado":
                resultado = carga
            elif tipo == "erro":
                erro = str(carga)

        if resultado is not None:
            self._finalizar_forca_bruta(resultado)
            return
        if erro is not None:
            self._falhar_forca_bruta(erro)
            return
        if self._progresso_forca_bruta is None:
            decorrido = perf_counter() - self._inicio_forca_bruta
            self.progresso_tempo.setText(formatar_duracao(decorrido))
        if not processo.is_alive():
            self._falhar_forca_bruta(
                f"O processo terminou inesperadamente (código {processo.exitcode})."
            )

    def _finalizar_forca_bruta(
        self, resultado: ResultadoForcaBrutaTempoReal
    ) -> None:
        melhor = resultado.melhor_resultado
        progresso_final = ProgressoForcaBruta(
            clientes=len(resultado.clientes),
            total_permutacoes=resultado.total_permutacoes,
            permutacoes_avaliadas=resultado.permutacoes_avaliadas,
            tempo_decorrido=resultado.tempo_decorrido,
            melhor_custo=(
                melhor.distancia_total if melhor is not None else None
            ),
            melhor_ordem=(
                tuple(melhor.ordem_entregas) if melhor is not None else ()
            ),
        )
        self._atualizar_progresso_forca(progresso_final)
        rota = rota_de_resultado_forca_bruta(self.projeto, resultado)
        self._liberar_processo_forca_bruta()
        if resultado.concluida:
            estado = "Busca exaustiva concluída — solução ótima encontrada."
        else:
            estado = (
                "Busca interrompida — melhor solução encontrada até o momento."
            )
            if resultado.motivo_interrupcao == "tempo_limite":
                estado += " Limite de tempo atingido."
        self.estado_forca_bruta.setText(estado)
        if rota is not None:
            self._apresentar_rota(rota)
            nota_espacial = self.resultado_calibracao.text()
            self.resultado_calibracao.setText(f"{estado} {nota_espacial}")
        else:
            self.cartao_status.definir(estado)
            self.resultado_calibracao.setText(
                estado + " Nenhuma permutação chegou a ser avaliada."
            )
        self.cartao_status.definir(estado)
        self.botao_interromper_forca.setText("Interromper cálculo")
        self.botao_interromper_forca.setEnabled(False)
        self._atualizar_comparacao_metodos()

    def _falhar_forca_bruta(self, mensagem: str) -> None:
        self._liberar_processo_forca_bruta()
        self.estado_forca_bruta.setText(f"Falha no cálculo: {mensagem}")
        self._tratar_erro_calculo(ValueError(mensagem))

    def _liberar_processo_forca_bruta(self) -> None:
        self._timer_forca_bruta.stop()
        processo = self._processo_forca_bruta
        fila = self._fila_forca_bruta
        if processo is not None:
            processo.join(timeout=0.2)
        if fila is not None:
            fila.close()
            fila.join_thread()
        self._processo_forca_bruta = None
        self._fila_forca_bruta = None
        self._evento_forca_bruta = None
        self._calculando_rota = False
        self._definir_controles_calculo(True)
        self._atualizar_disponibilidade_calculo()

    def _definir_controles_calculo(self, habilitados: bool) -> None:
        for controle in (
            self.seletor_algoritmo,
            self.seletor_metodo_tsp,
            self.origem,
            self.destino,
            self.lista_clientes,
            self.selecionar_todos_clientes,
            self.duracao_maxima_forca,
            self.botao_iniciar_forca,
            self.botao_abrir_projeto,
            self.botao_novo_projeto,
            self.botao_carregar_grafo_academico,
            self.botao_carregar_grafo_academico_18,
        ):
            controle.setEnabled(habilitados)
        if not habilitados:
            self._modo_navegar()
            for botao in self.botoes_edicao:
                botao.setEnabled(False)
            for botao in (
                self.botao_confirmar_edicao,
                self.botao_desfazer_edicao,
                self.botao_refazer_edicao,
                self.botao_cancelar_edicao,
                self.botao_adicionar_curva,
                self.botao_remover_curva,
                self.botao_editar_selecao,
                self.botao_reposicionar,
                self.botao_excluir_selecao,
            ):
                botao.setEnabled(False)
        elif self.visualizacao.modelos_preparados:
            for botao in self.botoes_edicao:
                botao.setEnabled(True)
            self._atualizar_disponibilidade_editor()
            self._atualizar_botoes_operacao()
            self._atualizar_botoes_selecao()

    def _cancelar_calculo_rota(self) -> None:
        if self._cancelamento_calculo is None:
            return
        self._cancelamento_calculo.set()
        self.botao_cancelar_calculo.setEnabled(False)
        self.botao_cancelar_calculo.setText("Cancelando…")
        self.cartao_status.definir("Cancelando cálculo com segurança…")

    def _verificar_calculo_rota(self) -> None:
        futuro = self._futuro_calculo
        if futuro is None:
            self._timer_calculo.stop()
            return
        if not futuro.done():
            decorrido = perf_counter() - self._inicio_calculo
            self.complexidade_tempo.setText(f"{decorrido:.3f} s (em execução)")
            return
        self._timer_calculo.stop()
        try:
            rota = futuro.result()
        except CalculoTSPCancelado:
            self.cartao_status.definir("Cálculo cancelado.")
            self.resultado_calibracao.setText(
                "O cálculo foi cancelado sem alterar a rota."
            )
            self.complexidade_tempo.setText("Cancelado")
        except (KeyError, TypeError, ValueError, MemoryError) as erro:
            self._tratar_erro_calculo(erro)
        except Exception as erro:  # pragma: no cover - proteção da fronteira da thread
            LOGGER.exception("Falha inesperada no cálculo da rota", exc_info=erro)
            self._tratar_erro_calculo(ValueError(f"Falha inesperada: {erro}"))
        else:
            self._apresentar_rota(rota)
        finally:
            self._futuro_calculo = None
            self._cancelamento_calculo = None
            self._calculando_rota = False
            self.botao_cancelar_calculo.setText("Cancelar cálculo")
            self.botao_cancelar_calculo.setVisible(False)
            self.botao_cancelar_calculo.setEnabled(False)
            self._definir_controles_calculo(True)
            self._atualizar_disponibilidade_calculo()

    def _tratar_erro_calculo(self, erro: Exception) -> None:
        self.rota_calculada = None
        self.visualizacao.limpar_destaque_rota()
        self.cartao_distancia.definir("—")
        self.cartao_percurso.definir("Nenhuma rota disponível")
        self.cartao_clientes.definir("0 / 0")
        self.resultado_ordem.setText("")
        self.resultado_percurso.setText("")
        self.resultado_clientes.setText("")
        self.resultado_metricas.setText("")
        self.resultado_calibracao.setText(str(erro))
        status = (
            "Destino inacessível."
            if isinstance(erro, RotaInacessivel)
            else f"Não foi possível calcular: {erro}"
        )
        self.cartao_status.definir(status)
        self.botao_limpar_rota.setEnabled(False)
        self.botao_enquadrar_rota.setEnabled(False)
        self._atualizar_controles_missao()

    def _apresentar_rota(self, rota: RotaCalculada) -> None:
        self.rota_calculada = rota
        if rota.metodo_tsp is MetodoTSP.HELD_KARP:
            self._ultimo_resultado_held = rota
        elif rota.metodo_tsp is MetodoTSP.FORCA_BRUTA_DEMONSTRACAO:
            self._ultimo_resultado_forca = rota
        percurso = " → ".join(rota.percurso_completo)
        self.cartao_distancia.definir(formatar_distancia_km(rota.distancia_total))
        self.cartao_percurso.definir(percurso)
        quantidade = len(rota.clientes_selecionados)
        self.cartao_clientes.definir(f"0 / {quantidade}")
        if rota.ordem_atendimento:
            ordem = " → ".join(rota.ordem_atendimento)
            self.resultado_ordem.setText(f"Ordem de atendimento: {ordem}")
        else:
            self.resultado_ordem.setText("")
        self.resultado_percurso.setText(f"Percurso completo: {percurso}")
        if rota.algoritmo is AlgoritmoRota.TSP:
            clientes = ", ".join(rota.clientes_selecionados)
            self.resultado_clientes.setText(f"Clientes selecionados: {clientes}")
        else:
            clientes_no_percurso = [
                identificador
                for identificador in rota.percurso_completo
                if self.grafo.obter_vertice(identificador).tipo is TipoVertice.CLIENTE
            ]
            texto = ", ".join(clientes_no_percurso) or "nenhum"
            self.resultado_clientes.setText(f"Clientes no percurso: {texto}")
        tempo = rota.tempo_processamento_segundos or 0.0
        algoritmo = (
            rota.metodo_tsp.nome_exibicao
            if rota.metodo_tsp is not None
            else "Dijkstra"
        )
        permutacoes = (
            rota.permutacoes_teoricas
            if rota.algoritmo is AlgoritmoRota.TSP
            else 0
        )
        self.resultado_metricas.setText(
            f"Vértices: {formatar_inteiro_br(rota.total_vertices_grafo)} · "
            f"clientes atendidos: {formatar_inteiro_br(quantidade)} · "
            f"permutações teóricas: {formatar_inteiro_br(permutacoes)} · "
            f"algoritmo: {algoritmo} · processamento: {tempo:.3f} s · "
            f"peso total: {formatar_distancia_km(rota.distancia_total)}"
            + (
                f" · permutações realmente avaliadas: "
                f"{formatar_inteiro_br(rota.permutacoes_avaliadas)} · "
                f"estado: {'concluída' if rota.busca_tsp_completa else 'interrompida'}"
                if rota.metodo_tsp
                is MetodoTSP.FORCA_BRUTA_DEMONSTRACAO
                else ""
            )
        )
        self.complexidade_tempo.setText(f"{tempo:.3f} s")
        self.complexidade_peso.setText(formatar_distancia_km(rota.distancia_total))
        if rota.estado_espacial is EstadoEspacial.COMPLETO:
            apta, motivo = self._rota_apta_para_missao()
            self.resultado_calibracao.setText(
                "Todos os trechos foram validados automaticamente no mapa viário."
                if apta and self.visualizacao.mapa_trafegabilidade is not None
                else motivo
            )
            self.cartao_status.definir(
                "Rota pronta para missão 3D."
                if apta
                else "Rota calculada; ajuste o traçado espacial."
            )
        else:
            self.resultado_calibracao.setText(
                self._texto_ruas_pendentes(rota.arestas_pendentes)
            )
            self.cartao_status.definir(
                "Rota calculada, mas com ruas pendentes de calibração."
            )
        self.visualizacao.atualizar_destaque_rota(
            segmentos_rota_qml(rota),
            marcadores_rota_qml(rota, self.projeto),
        )
        self.botao_limpar_rota.setEnabled(True)
        self.botao_enquadrar_rota.setEnabled(
            bool(pontos_para_enquadrar(rota, self.projeto))
        )
        apta, motivo = self._rota_apta_para_missao()
        self.resumo_missao.setText(motivo)
        self.botao_iniciar.setEnabled(apta and not self._sessao_missao_ativa)
        self._atualizar_controles_missao()
        self._atualizar_comparacao_metodos()

    def _atualizar_comparacao_metodos(self) -> None:
        selecionados = frozenset(self._clientes_selecionados())
        held = self._ultimo_resultado_held
        if held is not None and frozenset(held.clientes_selecionados) == selecionados:
            tempo = held.tempo_processamento_segundos or 0.0
            self.comparacao_held.setText(
                f"Held–Karp — tempo: {tempo:.3f} s · custo ótimo: "
                f"{formatar_distancia_km(held.distancia_total)} · ordem: "
                f"{' → '.join(held.ordem_atendimento)}"
            )
        else:
            self.comparacao_held.setText(
                "Held–Karp: ainda não executado para esta seleção."
            )

        forca = self._ultimo_resultado_forca
        if (
            forca is not None
            and frozenset(forca.clientes_selecionados) == selecionados
        ):
            tempo = forca.tempo_processamento_segundos or 0.0
            estado = "concluída" if forca.busca_tsp_completa else "interrompida"
            comparacao = (
                f"Força bruta — tempo: {tempo:.3f} s · permutações: "
                f"{formatar_inteiro_br(forca.permutacoes_avaliadas)}/"
                f"{formatar_inteiro_br(forca.permutacoes_teoricas)} · "
                f"melhor custo: {formatar_distancia_km(forca.distancia_total)} · "
                f"estado: {estado}."
            )
            if (
                held is not None
                and frozenset(held.clientes_selecionados) == selecionados
                and held.distancia_total == forca.distancia_total
                and not forca.busca_tsp_completa
            ):
                comparacao += (
                    " O custo coincide com o ótimo garantido pelo Held–Karp; "
                    "a busca de força bruta permanece parcial."
                )
            self.comparacao_forca.setText(comparacao)
        else:
            self.comparacao_forca.setText(
                "Força bruta: ainda não executada para esta seleção."
            )

    def limpar_rota(self, *, status: str = "Aguardando cálculo.") -> None:
        if self._sessao_missao_ativa:
            return
        self.rota_calculada = None
        self.visualizacao.limpar_destaque_rota()
        self.cartao_distancia.definir("—")
        self.cartao_percurso.definir("Nenhuma rota calculada")
        self.cartao_clientes.definir("0 / 0")
        self.cartao_status.definir(status)
        self.resultado_ordem.setText("")
        self.resultado_percurso.setText("")
        self.resultado_clientes.setText("")
        self.resultado_metricas.setText("")
        self.resultado_calibracao.setText(status)
        self._atualizar_complexidade()
        self.botao_limpar_rota.setEnabled(False)
        self.botao_enquadrar_rota.setEnabled(False)
        self.resumo_missao.setText("Calcule e calibre uma rota para iniciar.")
        self.indicador_velocidade.setText(
            "Velocidade: 0,000 unid./s · Parado"
        )
        self._aplicar_pose_estacionamento()
        self._atualizar_controles_missao()

    def _aplicar_pose_estacionamento(self) -> bool:
        estacionamento = self.projeto.estacionamento_inicial
        deposito = self.grafo.obter_deposito()
        if (
            estacionamento is None
            or deposito is None
            or not estacionamento.validado
            or estacionamento.deposito != deposito.identificador
        ):
            return False
        self.visualizacao.atualizar_carro(
            estacionamento.posicao,
            estacionamento.orientacao_graus,
            0.0,
            imediato=True,
        )
        return True

    def _sincronizar_carro_com_deposito(
        self, *, marcar_modificado: bool = True
    ) -> bool:
        """Mantém a pose física vinculada ao único depósito do projeto."""
        if not self.visualizacao.modelos_preparados:
            return False
        deposito = self.grafo.obter_deposito()
        if deposito is None:
            if self.projeto.estacionamento_inicial is not None:
                self.projeto.estacionamento_inicial = None
                if marcar_modificado:
                    self._definir_projeto_modificado(True)
            return False
        posicao_deposito = self.projeto.posicoes.get(deposito.identificador)
        if posicao_deposito is None:
            self._definir_instrucao(
                "O depósito atual ainda não possui uma posição espacial."
            )
            return False
        anterior = self.projeto.estacionamento_inicial
        if self.visualizacao.mapa_trafegabilidade is None:
            reutilizavel = bool(
                anterior is not None
                and anterior.deposito == deposito.identificador
                and hypot(
                    anterior.posicao[0] - posicao_deposito[0],
                    anterior.posicao[2] - posicao_deposito[2],
                )
                <= 0.25
            )
            estacionamento = (
                anterior
                if reutilizavel
                else EstacionamentoVeiculo(
                    deposito=deposito.identificador,
                    posicao=posicao_deposito,
                    orientacao_graus=0.0,
                    superficie=None,
                    validado=False,
                )
            )
            self.projeto.estacionamento_inicial = estacionamento
            self.visualizacao.atualizar_carro(
                estacionamento.posicao,
                estacionamento.orientacao_graus,
                0.0,
                imediato=True,
            )
            if marcar_modificado and estacionamento != anterior:
                self._definir_projeto_modificado(True)
            self._definir_instrucao(
                "Carro vinculado provisoriamente ao depósito; o reconhecimento "
                "automático é necessário para validar a vaga."
            )
            return estacionamento.validado
        try:
            estacionamento = self.visualizacao.posicionar_estacionamento(
                self.projeto
            )
        except (OSError, TypeError, ValueError, RuntimeError) as erro:
            LOGGER.warning("Estacionamento inicial indisponível: %s", erro)
            self._definir_instrucao(
                "Não foi possível validar o estacionamento inicial: " + str(erro)
            )
            return False
        if marcar_modificado and estacionamento != anterior:
            self._definir_projeto_modificado(True)
        self._definir_instrucao(
            f"Carro estacionado sobre {estacionamento.superficie}, "
            f"associado ao depósito {estacionamento.deposito}."
        )
        return True

    def _resolver_pose_estacionamento(self) -> bool:
        """Nome legado para a regra central de sincronização carro–depósito."""
        return self._sincronizar_carro_com_deposito()

    def _preparar_cenario_inicial(self) -> bool:
        """Revalida depósito e carro da configuração contra o GLB carregado."""
        deposito = self.grafo.obter_deposito()
        if deposito is None:
            self._definir_instrucao(
                "A configuração inicial não possui depósito. Defina um no asfalto."
            )
            return False
        posicao = self.projeto.posicoes.get(deposito.identificador)
        if posicao is None:
            self._definir_instrucao(
                "O depósito inicial não possui posição espacial válida."
            )
            return False
        if self.visualizacao.mapa_trafegabilidade is None:
            self._sincronizar_carro_com_deposito(
                marcar_modificado=False
            )
            return False
        validacao = self.visualizacao.validar_posicao_trafegavel(posicao)
        if not validacao.valido:
            self._definir_instrucao(
                "O depósito inicial precisa ser reposicionado no asfalto: "
                + validacao.motivo
            )
            return False
        if not self.configuracao_inicial.modelo_corresponde(
            self.visualizacao.caminho_cidade
        ):
            LOGGER.warning(
                "A cidade mudou desde a configuração inicial; a pose será "
                "aceita somente após validação geométrica."
            )
        if not self._sincronizar_carro_com_deposito(
            marcar_modificado=False
        ):
            self._definir_instrucao(
                "Selecione o depósito e use Reposicionar para escolher outro "
                "ponto de asfalto próximo a uma vaga válida."
            )
            return False
        self._definir_projeto_modificado(False)
        return True

    def _invalidar_rota_por_edicao(self) -> None:
        self._definir_projeto_modificado(True)
        if self.rota_calculada is not None:
            self.limpar_rota(
                status="Cidade alterada. É necessário recalcular a rota."
            )

    def _enquadrar_rota(self) -> None:
        if self.rota_calculada is None:
            return
        pontos = pontos_para_enquadrar(self.rota_calculada, self.projeto)
        if not self.visualizacao.enquadrar_pontos(pontos):
            self.cartao_status.definir(
                "A rota não possui posições espaciais para enquadramento."
            )

    def _atualizar_disponibilidade_calculo(self) -> None:
        algoritmo = self.seletor_algoritmo.currentData()
        if algoritmo == AlgoritmoRota.DIJKSTRA.value:
            origem = self.origem.currentData()
            destino = self.destino.currentData()
            disponivel = bool(
                self.origem.count() >= 2
                and self.destino.count() >= 2
                and origem is not None
                and destino is not None
                and origem != destino
            )
            motivo = (
                "Cadastre ao menos dois pontos conectados e selecione extremos distintos."
                if not disponivel
                else "Calcula o menor caminho entre os pontos selecionados."
            )
        else:
            tem_deposito = self.grafo.obter_deposito() is not None
            tem_clientes = bool(self._clientes_selecionados())
            disponivel = tem_deposito and tem_clientes
            motivo = (
                "Cadastre um depósito antes de calcular a rota TSP."
                if not tem_deposito
                else "Adicione pelo menos um cliente."
                if not tem_clientes
                else "Selecione ao menos um cliente e calcule a rota de entregas."
            )
        self.botao_calcular.setToolTip(motivo)
        habilitado = (
            disponivel
            and not self._calculando_rota
            and not self._sessao_missao_ativa
        )
        self.botao_calcular.setEnabled(habilitado)
        self.botao_iniciar_forca.setEnabled(habilitado)
        self.botao_iniciar_forca.setToolTip(motivo)

    def _definir_instrucao(self, texto: str) -> None:
        self.instrucao_editor.setText(texto)

    def _criar_atalhos_editor(self) -> None:
        self.atalho_cancelar = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.atalho_cancelar.activated.connect(self._cancelar_operacao)
        self.atalho_excluir_ponto = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        self.atalho_excluir_ponto.activated.connect(self._remover_curva_selecionada)
        self.atalho_desfazer = QShortcut(QKeySequence.StandardKey.Undo, self)
        self.atalho_desfazer.activated.connect(self._desfazer_operacao)
        self.atalho_refazer = QShortcut(QKeySequence.StandardKey.Redo, self)
        self.atalho_refazer.activated.connect(self._refazer_operacao)
        self.atalho_confirmar = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        self.atalho_confirmar.activated.connect(self._confirmar_operacao)

    def _operacao_rua_ativa(self) -> bool:
        return self.editor.modo in {ModoEditor.CRIAR_RUA, ModoEditor.EDITAR_TRACADO}

    def _marcar_ferramenta(self, botao: QPushButton, nome: str) -> None:
        botao.setChecked(True)
        self.estado_ferramenta.setText(f"Ferramenta ativa: {nome}")

    def _modo_navegar(self) -> None:
        self.editor.definir_modo(ModoEditor.NAVEGAR)
        self._aguardando_insercao_curva = False
        self.visualizacao.definir_modo_interacao(ModoEditor.NAVEGAR.value)
        self.visualizacao.mostrar_marcador_temporario(None)
        self.visualizacao.atualizar_previa_rua([])
        self.visualizacao.atualizar_controles_rua([])
        self._marcar_ferramenta(self.botao_navegar, "Navegar")
        self._definir_instrucao(
            "Clique em um marcador ou rua para selecionar. Use Editar, Reposicionar "
            "ou Excluir; Cancelar encerra qualquer operação em curso."
        )
        self._atualizar_botoes_operacao()

    def _ativar_adicao(self, tipo: TipoVertice | None) -> None:
        self.editor.definir_modo(
            ModoEditor.ADICIONAR_PONTO, tipo_sugerido=tipo
        )
        self.visualizacao.definir_modo_interacao(ModoEditor.ADICIONAR_PONTO.value)
        descricao = {
            TipoVertice.CLIENTE: "um cliente",
            TipoVertice.DEPOSITO: "o depósito",
        }.get(tipo, "um ponto")
        botao = {
            TipoVertice.CLIENTE: self.botao_adicionar_cliente,
            TipoVertice.DEPOSITO: self.botao_definir_deposito,
        }.get(tipo, self.botao_adicionar_ponto)
        self._marcar_ferramenta(botao, botao.text())
        self._definir_instrucao(
            "Clique sobre uma rua reconhecida automaticamente para "
            f"adicionar {descricao}. Cancelar volta à navegação."
        )
        self._atualizar_botoes_operacao()

    def _ativar_definicao_deposito(self) -> None:
        """Cria o primeiro depósito ou reposiciona o único depósito ativo."""
        deposito = self.grafo.obter_deposito()
        if deposito is None:
            self._ativar_adicao(TipoVertice.DEPOSITO)
            return
        self.editor.selecao = ("vertice", deposito.identificador)
        self._reposicionar_selecao()
        self._definir_instrucao(
            "Clique no novo local de asfalto do depósito. O carro será "
            "reposicionado automaticamente."
        )

    def _ativar_criacao_rua(self) -> None:
        self.editor.iniciar_rua()
        self.editor.definir_snap_ativo(self.snap_editor.isChecked())
        self._aguardando_insercao_curva = False
        self.visualizacao.definir_modo_interacao(ModoEditor.CRIAR_RUA.value)
        self._marcar_ferramenta(self.botao_criar_rua, "Criar rua")
        self._definir_instrucao(
            "Selecione o ponto inicial e o final. O sistema sugerirá um traçado sobre "
            "a malha viária; ajuste as curvas se necessário."
        )
        self._sincronizar_cena()
        self._atualizar_botoes_operacao()

    def _ativar_classificacao(self) -> None:
        self.editor.definir_modo(ModoEditor.CLASSIFICAR_SUPERFICIE)
        self.visualizacao.definir_modo_interacao(
            ModoEditor.CLASSIFICAR_SUPERFICIE.value
        )
        self._marcar_ferramenta(self.botao_classificar, "Classificar superfície")
        self._definir_instrucao(
            "Clique em uma malha e confirme manualmente se ela é rua, calçada ou área "
            "bloqueada. A aparência do modelo não é interpretada automaticamente."
        )
        self._atualizar_botoes_operacao()

    def _cancelar_operacao(self) -> None:
        era_edicao = self._operacao_rua_ativa()
        self._modo_navegar()
        if era_edicao:
            self._definir_instrucao(
                "Edição cancelada; o traçado original foi preservado."
            )

    def _atualizar_botoes_operacao(self) -> None:
        if self._sessao_missao_ativa:
            for botao in (
                self.botao_confirmar_edicao,
                self.botao_desfazer_edicao,
                self.botao_refazer_edicao,
                self.botao_cancelar_edicao,
                self.botao_adicionar_curva,
                self.botao_remover_curva,
            ):
                botao.setEnabled(False)
            return
        operacao = self.editor.operacao_rua
        criando_rua = self._operacao_rua_ativa()
        self.botao_confirmar_edicao.setEnabled(
            criando_rua
            and operacao.origem is not None
            and operacao.destino is not None
        )
        self.botao_desfazer_edicao.setEnabled(
            criando_rua
            and (
                bool(operacao.historico)
                or (
                    self.editor.modo is ModoEditor.CRIAR_RUA
                    and (
                        operacao.origem is not None
                        or operacao.destino is not None
                        or bool(operacao.pontos_intermediarios)
                    )
                )
            )
        )
        self.botao_refazer_edicao.setEnabled(
            criando_rua and bool(operacao.futuro)
        )
        self.botao_cancelar_edicao.setEnabled(
            self.editor.modo is not ModoEditor.NAVEGAR
        )
        editando = self.editor.modo is ModoEditor.EDITAR_TRACADO
        self.botao_adicionar_curva.setEnabled(editando)
        self.botao_remover_curva.setEnabled(
            criando_rua and operacao.ponto_selecionado is not None
        )
        self.snap_editor.setEnabled(criando_rua)

    def _sincronizar_cena(self) -> None:
        self._revalidar_ruas_automaticamente()
        self.visualizacao.atualizar_marcadores(self.editor.marcadores_qml())
        self.visualizacao.atualizar_ruas(
            self.editor.segmentos_ruas_qml(self._validacoes_ruas)
        )
        self.visualizacao.atualizar_previa_rua(
            self.editor.segmentos_previa_qml()
        )
        self.visualizacao.atualizar_controles_rua(
            self.editor.controles_rua_qml()
            if self._operacao_rua_ativa()
            else []
        )
        if self.rota_calculada is not None:
            self.visualizacao.atualizar_destaque_rota(
                segmentos_rota_qml(self.rota_calculada),
                marcadores_rota_qml(self.rota_calculada, self.projeto),
            )
        self._atualizar_campos_grafo()
        calibradas = sum(
            estado[0] for estado in self._validacoes_ruas.values()
        ) if self.visualizacao.mapa_trafegabilidade is not None else sum(
            geometria.calibrada_manualmente
            and len(self.projeto.polilinha_rua(*chave)) >= 2
            for chave, geometria in self.projeto.ruas.items()
        )
        total_conexoes = len(self.grafo.listar_arestas())
        total_tracadas = len(self.projeto.ruas)
        inconclusivas = sum(
            not valido and not conclusivo
            for valido, conclusivo, _ in self._validacoes_ruas.values()
        )
        invalidas = sum(
            not valido and conclusivo
            for valido, conclusivo, _ in self._validacoes_ruas.values()
        )
        if self.visualizacao.mapa_trafegabilidade is None:
            superficies_rua = sum(
                classificacao.value == "rua"
                for classificacao in self.projeto.superficies.values()
            )
            self.resumo_editor.setText(
                f"Superfícies rua: {superficies_rua} · conexões: {total_conexoes} · "
                f"traçadas: {total_tracadas} · confirmadas: {calibradas} · "
                f"pendentes: {total_conexoes - calibradas}\n"
                "Azul acinzentado = calibrada · laranja = pendente/selecionada"
            )
        else:
            self.resumo_editor.setText(
                f"Reconhecimento automático · conexões: {total_conexoes} · "
                f"traçadas: {total_tracadas} · válidas: {calibradas} · "
                f"incertas: {inconclusivas} · inválidas: {invalidas}\n"
                "Azul acinzentado = validada · laranja = pendente/selecionada"
            )
        self._atualizar_disponibilidade_editor()
        self._atualizar_detalhes_rua()

    def _atualizar_disponibilidade_editor(self) -> None:
        if not self._editor_inicializado or self._sessao_missao_ativa:
            return
        quantidade_vertices = len(self.grafo.listar_vertices())
        self.botao_navegar.setEnabled(True)
        self.botao_adicionar_ponto.setEnabled(True)
        self.botao_adicionar_cliente.setEnabled(True)
        self.botao_definir_deposito.setEnabled(True)
        self.botao_criar_rua.setEnabled(quantidade_vertices >= 2)

    def _revalidar_ruas_automaticamente(self) -> None:
        self._validacoes_ruas.clear()
        if self.visualizacao.mapa_trafegabilidade is None:
            return
        for chave in self.projeto.ruas:
            pontos = self.projeto.polilinha_rua(*chave)
            resultado = self.visualizacao.validar_rua_automatica(pontos)
            self._validacoes_ruas[chave] = (
                resultado.valido,
                resultado.conclusivo,
                resultado.motivo,
            )

    def _atualizar_campos_grafo(self, *, force: bool = False) -> None:
        assinatura = tuple(
            (vertice.identificador, vertice.nome, vertice.tipo.value)
            for vertice in self.grafo.listar_vertices()
        )
        if not force and assinatura == self._assinatura_campos_grafo:
            return
        clientes_anteriores = {
            str(self.lista_clientes.item(indice).data(Qt.ItemDataRole.UserRole))
            for indice in range(self.lista_clientes.count())
        }
        clientes_selecionados = set(self._clientes_selecionados())
        origem_atual = self.origem.currentData() if self.origem.count() else None
        destino_atual = self.destino.currentData() if self.destino.count() else None
        self._atualizando_campos_rota = True
        self.origem.clear()
        self.destino.clear()
        for vertice in self.grafo.listar_vertices():
            texto = f"{vertice.identificador} — {vertice.nome}"
            self.origem.addItem(texto, vertice.identificador)
            self.destino.addItem(texto, vertice.identificador)
        if origem_atual is not None and self.origem.findData(origem_atual) >= 0:
            self.origem.setCurrentIndex(self.origem.findData(origem_atual))
        if destino_atual is not None and self.destino.findData(destino_atual) >= 0:
            self.destino.setCurrentIndex(self.destino.findData(destino_atual))
        self.lista_clientes.clear()
        clientes = self.grafo.listar_clientes()
        limite_selecao = self._limite_tsp_atual()
        for indice, cliente in enumerate(clientes):
            item = QListWidgetItem(f"{cliente.identificador} — {cliente.nome}")
            item.setData(Qt.ItemDataRole.UserRole, cliente.identificador)
            selecionado = (
                cliente.identificador in clientes_selecionados
                or (
                    cliente.identificador not in clientes_anteriores
                    and indice < limite_selecao
                )
            )
            item.setCheckState(
                Qt.CheckState.Checked
                if selecionado
                else Qt.CheckState.Unchecked
            )
            self.lista_clientes.addItem(item)
        deposito = self.grafo.obter_deposito()
        self.deposito_tsp.setText(
            f"{deposito.identificador} — {deposito.nome}"
            if deposito is not None
            else "Nenhum depósito cadastrado"
        )
        self._atualizando_campos_rota = False
        self._assinatura_campos_grafo = assinatura
        self._atualizar_resumo_clientes()
        self._atualizar_disponibilidade_calculo()

    def _atualizar_detalhes_rua(self) -> None:
        operacao = self.editor.operacao_rua
        if self._operacao_rua_ativa() and operacao.origem and operacao.destino:
            peso = (
                self.grafo.obter_distancia(operacao.origem, operacao.destino)
                if self.grafo.existe_aresta(operacao.origem, operacao.destino)
                else None
            )
            estado = "não salvas" if operacao.modificada else "sem alterações"
            snap = f" · snap: {operacao.snap_origem}" if operacao.snap_origem else ""
            cabecalho = (
                f"{operacao.origem} ↔ {operacao.destino} · "
                f"peso: {formatar_distancia_km(peso)} · "
                if peso is not None
                else f"{operacao.origem} ↔ {operacao.destino} · peso: novo · "
            )
            self.detalhes_rua.setText(
                cabecalho
                + "comprimento 3D: "
                + formatar_numero_br(self.editor.comprimento_operacao_rua())
                + " unidades · "
                f"intermediários: {len(operacao.pontos_intermediarios)} · "
                f"alterações {estado}{snap}"
            )
            return
        selecao = self.editor.selecao
        if selecao is None or selecao[0] != "aresta":
            self.detalhes_rua.setText("Nenhuma rua selecionada.")
            return
        origem, destino = selecao[1], selecao[2]
        geometria = self.projeto.geometria_rua(origem, destino)
        peso = self.grafo.obter_distancia(origem, destino)
        polilinha = self.projeto.polilinha_rua(origem, destino)
        comprimento = (
            self.editor.comprimento_geometrico(polilinha) if polilinha else 0.0
        )
        intermediarios = len(geometria.pontos_intermediarios) if geometria else 0
        validacao = self._validacoes_ruas.get(
            self.projeto.chave_aresta(origem, destino)
        )
        if validacao is None:
            calibracao = (
                "confirmada (legado)"
                if geometria and geometria.calibrada_manualmente
                else "pendente"
            )
        elif validacao[0]:
            calibracao = "válida automaticamente"
        elif validacao[1]:
            calibracao = "inválida — " + validacao[2]
        else:
            calibracao = "inconclusiva — " + validacao[2]
        self.detalhes_rua.setText(
            f"{origem} ↔ {destino} · peso: {formatar_distancia_km(peso)} · "
            f"comprimento 3D: {formatar_numero_br(comprimento)} unidades · "
            f"intermediários: {intermediarios} · "
            f"calibração {calibracao} · sem alterações"
        )

    def _processar_pick(
        self,
        x: float,
        y: float,
        z: float,
        objeto: str,
        material: str,
        encontrado: bool,
    ) -> None:
        if self._sessao_missao_ativa:
            self._definir_instrucao(
                "Encerre a missão antes de editar ou selecionar itens da cidade."
            )
            return
        if not encontrado:
            diagnostico = self.visualizacao.diagnostico_ultimo_pick
            mensagens = {
                "fora_viewport": "O clique ficou fora da área útil da cena 3D.",
                "cena_nao_pronta": (
                    "A cena 3D ainda não terminou de carregar; aguarde e tente novamente."
                ),
                "sem_geometria": "Clique realmente fora da geometria da cidade.",
                "sem_superficie_cidade": "Nenhuma superfície da cidade foi atingida.",
            }
            self._definir_instrucao(
                mensagens.get(
                    diagnostico,
                    "Nenhuma geometria foi atingida. Tente novamente sobre a cidade.",
                )
            )
            return
        posicao = (x, y, z)
        if objeto.startswith("controle-rua:"):
            try:
                indice = int(objeto.partition(":")[2])
                self.editor.selecionar_ponto_intermediario(indice)
            except (ValueError, IndexError):
                return
            self._definir_instrucao(
                "Ponto de controle selecionado. Arraste-o sobre o asfalto ou "
                "use Remover ponto."
            )
            self._sincronizar_cena()
            self._atualizar_botoes_operacao()
            return
        if objeto.startswith("segmento-edicao:"):
            if not self._aguardando_insercao_curva:
                self._definir_instrucao(
                    "Segmento selecionado. Use Adicionar ponto para inserir uma curva aqui."
                )
                return
            validacao = self.visualizacao.validar_posicao_trafegavel(
                posicao
            )
            if self.visualizacao.mapa_trafegabilidade is not None and not validacao.valido:
                self._definir_instrucao(
                    "Ponto rejeitado pelo mapa automático: " + validacao.motivo
                )
                return
            try:
                indice_segmento = int(objeto.partition(":")[2])
                resultado = self.editor.aplicar_snap(posicao)
                self.editor.inserir_ponto_intermediario(
                    indice_segmento, resultado.posicao
                )
            except (ValueError, IndexError) as erro:
                self._definir_instrucao(str(erro))
                return
            self._aguardando_insercao_curva = False
            self._definir_instrucao("Ponto intermediário inserido no segmento.")
            self._sincronizar_cena()
            self._atualizar_botoes_operacao()
            return
        if objeto.startswith("vertice:"):
            self._clicar_vertice(objeto.partition(":")[2])
            return
        if objeto.startswith("aresta:"):
            self._clicar_aresta(objeto.partition(":")[2])
            return
        if objeto in {"marcador-temporario", "previa-rua"}:
            return
        origem_pick = self.visualizacao.origem_ultimo_pick
        if origem_pick != "cidade":
            mensagens = {
                "carro": "O carro não pode ser classificado como superfície da cidade.",
                "editor": "Marcadores e linhas do editor não podem ser classificados.",
                "outro": "O objeto selecionado não pertence à malha da cidade.",
                "nenhuma": "Nenhuma malha da cidade foi selecionada.",
            }
            self._definir_instrucao(mensagens.get(origem_pick, mensagens["outro"]))
            return
        referencia = self.editor.referencia_superficie(objeto, material)
        self._clicar_superficie(posicao, referencia)

    def _clicar_vertice(self, identificador: str) -> None:
        try:
            self.grafo.obter_vertice(identificador)
        except KeyError:
            return
        if self.editor.modo is ModoEditor.CRIAR_RUA:
            try:
                etapa = self.editor.selecionar_extremo_rua(identificador)
            except ValueError as erro:
                self._definir_instrucao(str(erro))
                return
            if etapa == "origem":
                self._definir_instrucao("Selecione o ponto final da rua.")
            else:
                operacao = self.editor.operacao_rua
                inicio = self.projeto.posicoes.get(operacao.origem or "")
                fim = self.projeto.posicoes.get(operacao.destino or "")
                caminho = (
                    self.visualizacao.sugerir_tracado_rua(inicio, fim)
                    if inicio is not None and fim is not None
                    else None
                )
                if caminho is not None:
                    operacao.pontos_intermediarios = list(caminho[1:-1])
                    operacao.pontos_originais = tuple(
                        operacao.pontos_intermediarios
                        if operacao.editando_aresta is not None
                        else ()
                    )
                    self._definir_instrucao(
                        "Traçado sugerido automaticamente sobre ruas reconhecidas. "
                        "Ajuste os controles ou confirme."
                    )
                else:
                    self._definir_instrucao(
                        "Não foi encontrado um corredor viário com largura suficiente "
                        "entre os extremos. Ajuste os pontos ou trace manualmente."
                    )
            self._sincronizar_cena()
            self._atualizar_botoes_operacao()
            return
        self.editor.selecao = ("vertice", identificador)
        vertice = self.grafo.obter_vertice(identificador)
        self._definir_instrucao(
            f"Selecionado {vertice.identificador} · {vertice.nome}."
        )
        self._sincronizar_cena()
        self._atualizar_botoes_selecao()

    def _clicar_aresta(self, identificador: str) -> None:
        partes = identificador.split("|", 1)
        if len(partes) != 2:
            return
        origem, destino = partes
        try:
            peso = self.grafo.obter_distancia(origem, destino)
        except (KeyError, ValueError):
            return
        self.editor.selecao = ("aresta", *self.projeto.chave_aresta(origem, destino))
        ambiguidade = self.visualizacao.diagnostico_ultimo_pick
        complemento = ""
        if ambiguidade.startswith("ruas_ambiguas:"):
            complemento = (
                f" · opção {ambiguidade.partition(':')[2]}; clique novamente "
                "no mesmo local para alternar"
            )
        self._definir_instrucao(
            f"Rua selecionada: {origem} ↔ {destino} · "
            f"peso oficial {formatar_distancia_km(peso)}"
            f"{complemento}."
        )
        self._sincronizar_cena()
        self._atualizar_botoes_selecao()

    def _clicar_superficie(
        self,
        posicao: tuple[float, float, float],
        referencia: str,
    ) -> None:
        modo = self.editor.modo
        if modo is ModoEditor.CLASSIFICAR_SUPERFICIE:
            dialogo = DialogoSuperficie(
                referencia,
                self.editor.classificacao_superficie(referencia),
                self,
            )
            if dialogo.exec() == QDialog.DialogCode.Accepted:
                try:
                    classificacao = dialogo.valor()
                    LOGGER.debug(
                        "Classificação recebida para %s: %r (%s)",
                        referencia,
                        classificacao,
                        type(classificacao).__name__,
                    )
                    self.editor.classificar_superficie(referencia, classificacao)
                except (TypeError, ValueError) as erro:
                    LOGGER.warning(
                        "Classificação rejeitada para %s: %s", referencia, erro
                    )
                    self._mostrar_erro(
                        "Não foi possível salvar a classificação selecionada. "
                        "Escolha uma opção válida e tente novamente."
                    )
                    return
                nomes = {
                    "rua": "rua trafegável",
                    "calcada": "calçada",
                    "bloqueada": "área bloqueada",
                    "nao_classificada": "não classificada",
                }
                self._definir_instrucao(
                    f"Classificação manual salva: {nomes[classificacao.value]}."
                )
                self._definir_projeto_modificado(True)
                self._sincronizar_cena()
            return

        if modo not in {
            ModoEditor.ADICIONAR_PONTO,
            ModoEditor.CRIAR_RUA,
            ModoEditor.EDITAR_TRACADO,
            ModoEditor.REPOSICIONAR_VERTICE,
        }:
            self.editor.selecao = None
            self._sincronizar_cena()
            self._atualizar_botoes_selecao()
            return

        if self.visualizacao.mapa_trafegabilidade is not None:
            validacao = self.visualizacao.validar_posicao_trafegavel(posicao)
            if not validacao.valido:
                prefixo = "Área incerta" if not validacao.conclusivo else "Clique rejeitado"
                self._definir_instrucao(f"{prefixo}: {validacao.motivo}")
                return
        else:
            # Contingência deliberadamente restrita ao material de pista já
            # verificado neste GLB. A interface não pede classificação manual.
            if referencia != self.configuracao_inicial.superficie_estacionamento:
                # Projetos antigos ainda podem carregar a classificação que
                # gravaram; ela só é consultada nesta contingência e nunca é
                # solicitada pela interface nova.
                try:
                    if self._cenario_inicial_limpo:
                        raise ValueError
                    self.editor.validar_superficie_trafegavel(referencia)
                except ValueError:
                    self._definir_instrucao(
                        "Reconhecimento indisponível: selecione a faixa de asfalto "
                        "identificada visualmente."
                    )
                    return

        if modo is ModoEditor.REPOSICIONAR_VERTICE:
            identificador = self.editor.vertice_reposicionado
            if identificador is None:
                return
            era_deposito = (
                self.grafo.obter_vertice(identificador).tipo
                is TipoVertice.DEPOSITO
            )
            try:
                self.editor.reposicionar_vertice(identificador, posicao)
            except (TypeError, ValueError, KeyError) as erro:
                self._mostrar_erro(str(erro))
                return
            self._invalidar_rota_por_edicao()
            if era_deposito:
                self._sincronizar_carro_com_deposito()
            self._sincronizar_cena()
            self._modo_navegar()
            self._definir_instrucao(
                f"Ponto {identificador} reposicionado"
                + (" e carro vinculado ao novo depósito." if era_deposito else ".")
            )
            return

        if modo is ModoEditor.ADICIONAR_PONTO:
            self._criar_vertice_no_ponto(posicao, self.editor.tipo_sugerido)
            return

        if modo is ModoEditor.EDITAR_TRACADO:
            if not self._aguardando_insercao_curva:
                self._definir_instrucao(
                    "Selecione e arraste um controle, ou ative Adicionar ponto."
                )
                return
            try:
                indice, _, _ = self.editor.segmento_operacao_mais_proximo(posicao)
                resultado = self.editor.aplicar_snap(posicao)
                self.editor.inserir_ponto_intermediario(indice, resultado.posicao)
            except (ValueError, IndexError) as erro:
                self._definir_instrucao(str(erro))
                return
            self._aguardando_insercao_curva = False
            self._definir_instrucao("Ponto intermediário inserido na ordem da rua.")
            self._sincronizar_cena()
            self._atualizar_botoes_operacao()
            return

        operacao = self.editor.operacao_rua
        if operacao.origem is not None and operacao.destino is not None:
            self.editor.adicionar_ponto_intermediario(posicao)
            self._definir_instrucao(
                "Curva adicionada. Adicione outra, desfaça ou confirme a rua."
            )
            self._sincronizar_cena()
            self._atualizar_botoes_operacao()
            return

        proximo = self.editor.vertice_proximo(posicao)
        if proximo is None:
            proximo = self._criar_vertice_no_ponto(
                posicao, TipoVertice.CRUZAMENTO, permanecer_no_modo=True
            )
        if proximo is not None:
            self._clicar_vertice(proximo)

    def _identificador_sugerido(self, tipo: TipoVertice | None) -> str:
        prefixo = {
            TipoVertice.DEPOSITO: "D",
            TipoVertice.CLIENTE: "C",
            TipoVertice.CRUZAMENTO: "X",
        }.get(tipo, "P")
        existentes = {
            vertice.identificador for vertice in self.grafo.listar_vertices()
        }
        numero = 1
        while f"{prefixo}{numero}" in existentes:
            numero += 1
        return f"{prefixo}{numero}"

    def _criar_vertice_no_ponto(
        self,
        posicao: tuple[float, float, float],
        tipo: TipoVertice | None,
        *,
        permanecer_no_modo: bool = False,
    ) -> str | None:
        proximo = self.editor.vertice_proximo(posicao)
        if proximo is not None:
            resposta = QMessageBox.question(
                self,
                "Ponto próximo",
                f"Já existe o vértice {proximo} próximo deste local. Deseja reutilizá-lo?",
            )
            if resposta == QMessageBox.StandardButton.Yes:
                if not permanecer_no_modo:
                    self._modo_navegar()
                    self._clicar_vertice(proximo)
                return proximo
        self.visualizacao.mostrar_marcador_temporario(posicao)
        dialogo = DialogoVertice(
            self,
            tipo_sugerido=tipo,
            identificador_sugerido=self._identificador_sugerido(tipo),
        )
        try:
            if dialogo.exec() != QDialog.DialogCode.Accepted:
                return None
            identificador, nome, tipo_escolhido = dialogo.dados()
            self.editor.criar_vertice(
                identificador, nome, tipo_escolhido, posicao
            )
        except (TypeError, ValueError, KeyError) as erro:
            self._mostrar_erro(str(erro))
            return None
        finally:
            self.visualizacao.mostrar_marcador_temporario(None)
        self._invalidar_rota_por_edicao()
        if tipo_escolhido is TipoVertice.DEPOSITO:
            self._sincronizar_carro_com_deposito()
        self._sincronizar_cena()
        self._definir_instrucao(
            f"Ponto {identificador} criado e associado ao grafo oficial."
        )
        if not permanecer_no_modo:
            self._modo_navegar()
        return identificador

    def _confirmar_operacao(self) -> None:
        if not self._operacao_rua_ativa():
            return
        operacao = self.editor.operacao_rua
        if operacao.origem is None or operacao.destino is None:
            return
        problemas = self.editor.validar_operacao_rua()
        if problemas:
            self._mostrar_erro("\n".join(problemas))
            return
        pontos = self.editor.pontos_rua(
            operacao.origem,
            operacao.destino,
            operacao.pontos_intermediarios,
        )
        validacao_automatica = (
            self.visualizacao.validar_rua_automatica(pontos)
            if self.visualizacao.mapa_trafegabilidade is not None
            else None
        )
        if validacao_automatica is not None and not validacao_automatica.valido:
            estado = "inconclusiva" if not validacao_automatica.conclusivo else "inválida"
            self._mostrar_erro(
                f"Validação automática {estado}: {validacao_automatica.motivo} "
                "Ajuste os extremos ou os pontos de controle antes de confirmar."
            )
            return
        peso_atual = None
        if operacao.editando_aresta is not None:
            peso_atual = self.grafo.obter_distancia(
                operacao.origem, operacao.destino
            )
        dialogo = DialogoRua(
            operacao.origem,
            operacao.destino,
            self,
            peso_atual=peso_atual,
        )
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        peso = dialogo.dados()
        try:
            self.editor.confirmar_rua(
                peso,
                validada_automaticamente=(
                    validacao_automatica.valido
                    if validacao_automatica is not None
                    else True
                ),
            )
        except (TypeError, ValueError, KeyError) as erro:
            self._mostrar_erro(str(erro))
            return
        self._invalidar_rota_por_edicao()
        self._sincronizar_cena()
        self._modo_navegar()
        self._definir_instrucao(
            "Traçado validado automaticamente e confirmado. A rota anterior foi "
            "invalidada para impedir o uso de geometria em cache."
        )

    def _desfazer_operacao(self) -> None:
        if self._operacao_rua_ativa() and self.editor.operacao_rua.historico:
            if self.editor.desfazer_edicao_rua():
                self._definir_instrucao("Última alteração do traçado desfeita.")
            self._sincronizar_cena()
            self._atualizar_botoes_operacao()
        elif self.editor.modo is ModoEditor.CRIAR_RUA:
            removido = self.editor.desfazer_ponto_rua()
            if removido is not None:
                self._definir_instrucao(f"Último {removido.replace('_', ' ')} removido.")
            self._sincronizar_cena()
            self._atualizar_botoes_operacao()

    def _refazer_operacao(self) -> None:
        if self._operacao_rua_ativa() and self.editor.refazer_edicao_rua():
            self._definir_instrucao("Alteração do traçado refeita.")
            self._sincronizar_cena()
            self._atualizar_botoes_operacao()

    def _alternar_snap(self, ativo: bool) -> None:
        if self._operacao_rua_ativa():
            self.editor.definir_snap_ativo(ativo)
            self._sincronizar_cena()

    def _ativar_insercao_curva(self) -> None:
        if not self._operacao_rua_ativa():
            return
        self._aguardando_insercao_curva = True
        self._definir_instrucao(
            "Clique em um segmento amarelo ou no asfalto próximo para inserir o ponto."
        )

    def _remover_curva_selecionada(self) -> None:
        if not self._operacao_rua_ativa():
            return
        try:
            self.editor.remover_ponto_intermediario()
        except ValueError as erro:
            self._definir_instrucao(str(erro))
            return
        self._definir_instrucao("Ponto intermediário removido da prévia.")
        self._sincronizar_cena()
        self._atualizar_botoes_operacao()

    def _iniciar_arraste_controle(self, indice: int) -> None:
        if not self._operacao_rua_ativa():
            return
        try:
            self.editor.iniciar_arraste_ponto(indice)
        except (ValueError, IndexError) as erro:
            self._definir_instrucao(str(erro))
            return
        self._arraste_superficie_valida = True
        self._definir_instrucao("Arrastando ponto: solte-o sobre o asfalto.")
        self._sincronizar_cena()

    def _superficie_valida_no_arraste(
        self, referencia: str, posicao: tuple[float, float, float] | None = None
    ) -> bool:
        if posicao is not None and self.visualizacao.mapa_trafegabilidade is not None:
            return self.visualizacao.validar_posicao_trafegavel(
                posicao
            ).valido
        classificacao = self.editor.classificacao_superficie(referencia)
        if classificacao.value == "rua":
            return True
        if classificacao.value in {"calcada", "bloqueada"}:
            return False
        operacao = self.editor.operacao_rua
        geometria = (
            self.projeto.geometria_rua(*operacao.editando_aresta)
            if operacao.editando_aresta is not None
            else None
        )
        # Fallback restrito a projetos legados enquanto o mapa não existe.
        return bool(geometria and geometria.calibrada_manualmente)

    def _atualizar_arraste_controle(
        self,
        x: float,
        y: float,
        z: float,
        objeto: str,
        material: str,
        encontrado: bool,
    ) -> None:
        if self.editor.operacao_rua.arrastando is None:
            return
        if not encontrado:
            self.editor.operacao_rua.previa_valida = False
            self._arraste_superficie_valida = False
            self._definir_instrucao(
                "Posição inválida: nenhuma superfície da cidade sob o cursor."
            )
            self._sincronizar_cena()
            return
        referencia = self.editor.referencia_superficie(objeto, material)
        valida = self._superficie_valida_no_arraste(referencia, (x, y, z))
        resultado = self.editor.aplicar_snap((x, y, z)) if valida else None
        posicao = resultado.posicao if resultado is not None else (x, y, z)
        self.editor.atualizar_arraste_ponto(
            posicao,
            valida=valida,
            snap_origem=resultado.origem if resultado is not None else None,
        )
        self._arraste_superficie_valida = valida
        if not valida:
            self._definir_instrucao(
                "Posição inválida: fora da rua ou sem largura livre para o veículo."
            )
        elif resultado is not None and resultado.encaixado:
            self._definir_instrucao(f"Snap ativo: {resultado.origem}.")
        else:
            self._definir_instrucao("Prévia do ponto atualizada; solte para validar.")
        self._sincronizar_cena()

    def _finalizar_arraste_controle(self, encontrado: bool) -> None:
        if self.editor.operacao_rua.arrastando is None:
            return
        valida = bool(encontrado and self._arraste_superficie_valida)
        alterou = self.editor.finalizar_arraste_ponto(valida=valida)
        self._definir_instrucao(
            "Ponto reposicionado na prévia; confirme para salvar."
            if alterou
            else "Posição inválida; o ponto voltou à posição anterior."
        )
        self._sincronizar_cena()
        self._atualizar_botoes_operacao()

    def _atualizar_botoes_selecao(self) -> None:
        if self._sessao_missao_ativa:
            self.botao_editar_selecao.setEnabled(False)
            self.botao_excluir_selecao.setEnabled(False)
            self.botao_reposicionar.setEnabled(False)
            return
        selecao = self.editor.selecao
        self.botao_editar_selecao.setEnabled(selecao is not None)
        self.botao_excluir_selecao.setEnabled(selecao is not None)
        self.botao_reposicionar.setEnabled(
            selecao is not None and selecao[0] == "vertice"
        )

    def _editar_selecao(self) -> None:
        selecao = self.editor.selecao
        if selecao is None:
            return
        if selecao[0] == "vertice":
            identificador = selecao[1]
            vertice = self.grafo.obter_vertice(identificador)
            dialogo = DialogoVertice(self, vertice=vertice)
            if dialogo.exec() != QDialog.DialogCode.Accepted:
                return
            _, nome, tipo = dialogo.dados()
            try:
                atualizado = self.editor.editar_vertice(
                    identificador, nome=nome, tipo=tipo
                )
            except (TypeError, ValueError, KeyError) as erro:
                self._mostrar_erro(str(erro))
                return
            self._invalidar_rota_por_edicao()
            if (
                vertice.tipo is TipoVertice.DEPOSITO
                or atualizado.tipo is TipoVertice.DEPOSITO
            ):
                self._sincronizar_carro_com_deposito()
            self._sincronizar_cena()
            self._definir_instrucao(f"Ponto {identificador} atualizado.")
            return
        origem, destino = selecao[1], selecao[2]
        self.editor.iniciar_rua(origem, destino, editar=True)
        self.editor.definir_snap_ativo(self.snap_editor.isChecked())
        self._aguardando_insercao_curva = False
        self.visualizacao.definir_modo_interacao(ModoEditor.EDITAR_TRACADO.value)
        self._marcar_ferramenta(self.botao_criar_rua, "Editar rua")
        self._definir_instrucao(
            "Pontos verdes/laranja são extremos fixos. Arraste os controles claros; "
            "use Adicionar ponto em um segmento e confirme somente ao terminar."
        )
        self._sincronizar_cena()
        self._atualizar_botoes_operacao()

    def _reposicionar_selecao(self) -> None:
        selecao = self.editor.selecao
        if selecao is None or selecao[0] != "vertice":
            return
        self.editor.definir_modo(ModoEditor.REPOSICIONAR_VERTICE)
        self.editor.vertice_reposicionado = selecao[1]
        self.visualizacao.definir_modo_interacao(
            ModoEditor.REPOSICIONAR_VERTICE.value
        )
        self.grupo_ferramentas.setExclusive(False)
        for botao in self.botoes_edicao:
            botao.setChecked(False)
        self.grupo_ferramentas.setExclusive(True)
        self.estado_ferramenta.setText("Ferramenta ativa: Reposicionar")
        self._definir_instrucao(
            f"Clique no novo local sobre o asfalto para reposicionar {selecao[1]}."
        )
        self._atualizar_botoes_operacao()

    def _excluir_selecao(self) -> None:
        selecao = self.editor.selecao
        if selecao is None:
            return
        descricao = (
            f"o vértice {selecao[1]} e todas as suas ruas"
            if selecao[0] == "vertice"
            else f"a rua {selecao[1]} ↔ {selecao[2]}"
        )
        resposta = QMessageBox.question(
            self,
            "Confirmar exclusão",
            f"Deseja excluir {descricao}?",
        )
        if resposta != QMessageBox.StandardButton.Yes:
            return
        removendo_deposito = bool(
            selecao[0] == "vertice"
            and self.grafo.obter_vertice(selecao[1]).tipo
            is TipoVertice.DEPOSITO
        )
        try:
            if selecao[0] == "vertice":
                self.editor.remover_vertice(selecao[1])
            else:
                self.editor.remover_aresta(selecao[1], selecao[2])
        except (TypeError, ValueError, KeyError) as erro:
            self._mostrar_erro(str(erro))
            return
        self.editor.selecao = None
        self._invalidar_rota_por_edicao()
        if removendo_deposito:
            self._sincronizar_carro_com_deposito()
        self._sincronizar_cena()
        self._atualizar_botoes_selecao()
        self._definir_instrucao("Item excluído com sucesso.")

    def salvar_projeto(self, caminho: str | Path | None = None) -> bool:
        if caminho is None:
            selecionado, _ = QFileDialog.getSaveFileName(
                self,
                "Salvar projeto da cidade",
                str(self.caminho_projeto or Path("delivery-route.json")),
                "Projeto Delivery Route (*.json)",
            )
            if not selecionado:
                return False
            caminho = selecionado
        try:
            self.caminho_projeto = salvar_projeto_cidade(self.projeto, caminho)
        except (OSError, TypeError, ValueError) as erro:
            self._mostrar_erro(f"Não foi possível salvar o projeto: {erro}")
            return False
        self._definir_projeto_modificado(False)
        self._definir_instrucao(f"Projeto salvo em {self.caminho_projeto.name}.")
        return True

    def novo_cenario(self, *, confirmar: bool = True) -> bool:
        """Volta ao estado mínimo sem escrever ou alterar projetos existentes."""
        if self._sessao_missao_ativa:
            self._mostrar_erro(
                "Encerre explicitamente a missão antes de iniciar uma nova cidade."
            )
            return False
        if confirmar and self.projeto_modificado:
            resposta = QMessageBox.question(
                self,
                "Novo cenário",
                "As alterações não salvas serão descartadas. Deseja continuar?",
            )
            if resposta != QMessageBox.StandardButton.Yes:
                return False

        self.projeto = criar_projeto_inicial(self.configuracao_inicial)
        self.grafo = self.projeto.grafo
        self.editor = EditorCidade3D(self.projeto)
        self._cenario_inicial_limpo = True
        self._assinatura_campos_grafo = None
        self.caminho_projeto = None
        self._atualizando_campos_rota = True
        self.lista_clientes.clear()
        self._atualizando_campos_rota = False
        self.limpar_rota(
            status="Cidade pronta. Adicione clientes para começar."
        )
        self._sincronizar_cena()
        if self._editor_inicializado:
            self._preparar_cenario_inicial()
        self._modo_navegar()
        self._definir_projeto_modificado(False)
        if self.visualizacao.mapa_trafegabilidade is not None:
            self._definir_instrucao(
                "Cidade pronta. Adicione clientes para começar."
            )
        return True

    def abrir_projeto(self, caminho: str | Path | None = None) -> bool:
        if self._sessao_missao_ativa:
            self._mostrar_erro(
                "Encerre explicitamente a missão antes de abrir outro projeto."
            )
            return False
        if caminho is None:
            selecionado, _ = QFileDialog.getOpenFileName(
                self,
                "Abrir projeto da cidade",
                str(self.caminho_projeto or Path.cwd()),
                "Projeto Delivery Route (*.json)",
            )
            if not selecionado:
                return False
            caminho = selecionado
        try:
            carregado = carregar_projeto_cidade(caminho)
        except (OSError, TypeError, ValueError, ErroPersistencia) as erro:
            self._mostrar_erro(f"Não foi possível abrir o projeto: {erro}")
            return False
        self.projeto = carregado
        self.grafo = carregado.grafo
        self.editor = EditorCidade3D(carregado)
        self._cenario_inicial_limpo = False
        self._assinatura_campos_grafo = None
        self.caminho_projeto = Path(caminho)
        self._definir_projeto_modificado(False)
        self.limpar_rota(status="Projeto carregado. Calcule uma nova rota.")
        self._atualizando_campos_rota = True
        self.lista_clientes.clear()
        self._atualizando_campos_rota = False
        self._inicializar_posicoes_legadas()
        self._sincronizar_cena()
        self._sincronizar_carro_com_deposito()
        self._modo_navegar()
        self._definir_instrucao(f"Projeto {self.caminho_projeto.name} carregado.")
        return True

    def carregar_grafo_academico(self, *, confirmar: bool = True) -> bool:
        """Abre o exemplo distribuído como modelo, sem torná-lo o padrão."""
        if self._sessao_missao_ativa:
            self._mostrar_erro(
                "Encerre explicitamente a missão antes de carregar o exemplo."
            )
            return False
        if confirmar and self.projeto_modificado:
            resposta = QMessageBox.question(
                self,
                "Carregar grafo acadêmico",
                "As alterações não salvas serão descartadas. Deseja continuar?",
            )
            if resposta != QMessageBox.StandardButton.Yes:
                return False
        if not self.abrir_projeto(CAMINHO_CENARIO_ACADEMICO):
            return False

        # O arquivo instalado é um modelo somente para carga. Uma edição
        # posterior usa Salvar como novo projeto e não sobrescreve o exemplo.
        self.caminho_projeto = None
        self._definir_projeto_modificado(False)
        self._definir_instrucao(
            "Grafo acadêmico carregado: vértices 1–5 e oito conexões viárias."
        )
        return True

    def carregar_grafo_academico_18(self, *, confirmar: bool = True) -> bool:
        """Abre o cenário completo sem substituir o exemplo acadêmico menor."""
        if self._sessao_missao_ativa:
            self._mostrar_erro(
                "Encerre explicitamente a missão antes de carregar o exemplo."
            )
            return False
        if confirmar and self.projeto_modificado:
            resposta = QMessageBox.question(
                self,
                "Carregar grafo de 18 vértices",
                "As alterações não salvas serão descartadas. Deseja continuar?",
            )
            if resposta != QMessageBox.StandardButton.Yes:
                return False
        if not self.abrir_projeto(CAMINHO_CENARIO_ACADEMICO_18):
            return False
        self.caminho_projeto = None
        self._definir_projeto_modificado(False)
        self._definir_instrucao(
            "Grafo acadêmico carregado: 18 vértices, 45 conexões viárias "
            "validadas e até 17 clientes selecionáveis com Held–Karp."
        )
        return True

    def _definir_projeto_modificado(self, modificado: bool) -> None:
        self.projeto_modificado = bool(modificado)
        if hasattr(self, "botao_salvar_projeto"):
            self.botao_salvar_projeto.setText(
                "Salvar •" if self.projeto_modificado else "Salvar"
            )

    def _inicializar_posicoes_legadas(self) -> None:
        if self.visualizacao.info_cidade is None:
            return
        limites = self.visualizacao.info_cidade.limites
        self.editor.inicializar_posicoes_legadas(
            limites.minimo,
            limites.maximo,
            self.visualizacao.escala_cidade,
        )

    def _mostrar_erro(self, mensagem: str) -> None:
        QMessageBox.warning(self, "Delivery Route", mensagem)
        self._definir_instrucao(mensagem)
        self.cartao_status.definir(mensagem)

    def _criar_cartoes(self) -> QWidget:
        recipiente = QWidget()
        self.layout_cartoes = QGridLayout(recipiente)
        self.layout_cartoes.setContentsMargins(0, 0, 0, 0)
        self.layout_cartoes.setHorizontalSpacing(12)
        self.layout_cartoes.setVerticalSpacing(10)
        self.cartao_distancia = CartaoInformacao(
            "↔", "Distância total", "—", "valorDistancia"
        )
        self.cartao_percurso = CartaoInformacao(
            "⌁", "Percurso", "Nenhuma rota calculada", "valorPercurso"
        )
        self.cartao_clientes = CartaoInformacao(
            "◎", "Clientes atendidos", "0 / 0", "valorClientes"
        )
        self.cartao_status = CartaoInformacao(
            "●", "Status", "Preparando cena 3D", "valorStatus"
        )
        self.cartoes = (
            self.cartao_distancia,
            self.cartao_percurso,
            self.cartao_clientes,
            self.cartao_status,
        )
        self._organizar_cartoes(4)
        return recipiente

    def _organizar_cartoes(self, colunas: int) -> None:
        if colunas == self._colunas_cartoes:
            return
        self._colunas_cartoes = colunas
        for indice, cartao in enumerate(self.cartoes):
            self.layout_cartoes.addWidget(cartao, indice // colunas, indice % colunas)
        for coluna in range(4):
            self.layout_cartoes.setColumnStretch(coluna, 1 if coluna < colunas else 0)

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
        elif "Analisando" in mensagem or "geometria" in mensagem:
            resumo = "Reconhecendo ruas…"
        elif "Mapa viário automático pronto" in mensagem:
            resumo = "Mapa viário pronto"
        elif "Inicializando" in mensagem:
            resumo = "Inicializando 3D…"
        self.estado_cena.setText(resumo)
        self.estado_cena.setToolTip(mensagem)
        if not ok:
            self._definir_instrucao(
                "Não foi possível preparar a cena 3D. Confira o backend gráfico e "
                "passe o mouse sobre o indicador da cena para ver o diagnóstico."
            )
        if not self._editor_inicializado:
            self.cartao_status.definir(resumo)
        pronto = bool(ok and self.visualizacao.modelos_preparados)
        if pronto:
            for botao in (
                self.botao_enquadrar,
                self.botao_aerea,
                self.botao_focar_carro,
                self.botao_camera_livre,
                self.botao_camera_atras,
                self.botao_camera_aerea_missao,
            ):
                botao.setEnabled(True)
            if not self._sessao_missao_ativa:
                for botao in self.botoes_edicao:
                    botao.setEnabled(True)
            if not self._editor_inicializado:
                self._editor_inicializado = True
                self._inicializar_posicoes_legadas()
                self._sincronizar_cena()
                cenario_preparado = True
                if self._cenario_inicial_limpo:
                    cenario_preparado = self._preparar_cenario_inicial()
                else:
                    self._sincronizar_carro_com_deposito()
                self._modo_navegar()
                if self.rota_calculada is None:
                    status = (
                        "Cidade pronta. Adicione clientes para começar."
                        if self._cenario_inicial_limpo
                        else "Aguardando cálculo."
                    )
                    self.limpar_rota(status=status)
                    if self._cenario_inicial_limpo and cenario_preparado:
                        self._definir_instrucao(status)
            self._atualizar_controles_missao()

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

    def resizeEvent(self, evento: QResizeEvent) -> None:  # noqa: N802 - API Qt
        super().resizeEvent(evento)
        if hasattr(self, "cartoes"):
            self._organizar_cartoes(4 if evento.size().width() >= 1180 else 2)

    def closeEvent(self, evento: QCloseEvent) -> None:  # noqa: N802 - API Qt
        self._timer_calculo.stop()
        self._timer_forca_bruta.stop()
        if self._evento_forca_bruta is not None:
            self._evento_forca_bruta.set()
        if self._processo_forca_bruta is not None:
            self._processo_forca_bruta.join(timeout=0.5)
            if self._processo_forca_bruta.is_alive():
                self._processo_forca_bruta.terminate()
                self._processo_forca_bruta.join(timeout=0.2)
        if self._fila_forca_bruta is not None:
            self._fila_forca_bruta.cancel_join_thread()
            self._fila_forca_bruta.close()
        if self._cancelamento_calculo is not None:
            self._cancelamento_calculo.set()
        self._executor_calculo.shutdown(wait=False, cancel_futures=True)
        if self.animacao_missao is not None:
            self.animacao_missao.timer.stop()
            if self.controlador_missao is not None:
                self.controlador_missao.encerrar()
            self.animacao_missao.deleteLater()
        self.visualizacao.encerrar_apresentacao_missao()
        self.visualizacao.configurar_diagnostico_desempenho(None)
        self.animacao_missao = None
        self.controlador_missao = None
        self._sessao_missao_ativa = False
        evento.accept()


__all__ = ["CartaoInformacao", "JanelaPrincipal"]
