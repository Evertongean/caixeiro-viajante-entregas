"""Janela principal e coordenação da execução dos algoritmos."""

from __future__ import annotations

import logging
from html import escape
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QMenuBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from algorithms.caixeiro_viajante import (
    ResultadoCaixeiroViajante,
    caixeiro_viajante,
)
from algorithms.dijkstra import ResultadoDijkstra, dijkstra
from models.grafo import Grafo, TipoVertice, Vertice, criar_cenario_exemplo
from models.persistencia import ErroPersistencia, carregar_grafo, salvar_grafo

from .editor_dialogos import DialogoAresta, DialogoArestaExistente, DialogoVertice
from .cidade_3d import Cidade3DWidget
from .execucao_passos import SessaoPassoAPasso
from .mapa_cidade import MapaCidade
from .painel_passos import PainelPassos
from .painel_modelos_3d import PainelModelos3D
from .painel_resultados import PainelResultados
from .visualizador_grafo import VisualizadorGrafo


logger = logging.getLogger(__name__)


class JanelaPrincipal(QMainWindow):
    """Organiza painéis e mantém as visualizações ligadas ao mesmo grafo."""

    def __init__(self, grafo: Grafo | None = None) -> None:
        super().__init__()
        self._grafo = grafo if grafo is not None else criar_cenario_exemplo()
        self._modo_atual = "cidade"
        self._vertice_selecionado: str | None = None
        self._resultado_atual: ResultadoDijkstra | ResultadoCaixeiroViajante | None = None
        self._algoritmo_resultado: str | None = None
        self._calculando = False
        self._modo_interface = "visualizacao"
        self._grafo_modificado = False
        self._caminho_projeto: Path | None = None
        self._sessao_passos: SessaoPassoAPasso | None = None

        self.setWindowTitle("Delivery Route — Otimização de Entregas")
        self.resize(1300, 800)
        # O conteúdo principal tem painéis com rolagem; 800x600 é o menor
        # tamanho demonstrável sem remover controles essenciais.
        self.setMinimumSize(800, 600)
        self._construir_interface()
        self._atualizar_dados_interface()
        QTimer.singleShot(0, self._enquadrar_todas_as_visualizacoes)

    @property
    def grafo(self) -> Grafo:
        return self._grafo

    @property
    def modo_atual(self) -> str:
        return self._modo_atual

    @property
    def vertice_selecionado(self) -> str | None:
        return self._vertice_selecionado

    @property
    def resultado_atual(self) -> ResultadoDijkstra | ResultadoCaixeiroViajante | None:
        """Única referência ao resultado calculado pela interface."""
        return self._resultado_atual

    @property
    def calculando(self) -> bool:
        return self._calculando

    @property
    def modo_interface(self) -> str:
        """Modo funcional atual: somente visualização ou edição do cenário."""
        return self._modo_interface

    @property
    def grafo_modificado(self) -> bool:
        return self._grafo_modificado

    @property
    def alteracoes_pendentes(self) -> bool:
        """Informa se há edições ainda não gravadas no arquivo do projeto."""
        return self._grafo_modificado

    @property
    def caminho_projeto(self) -> Path | None:
        return self._caminho_projeto

    @property
    def sessao_passos(self) -> SessaoPassoAPasso | None:
        return self._sessao_passos

    @property
    def passo_a_passo_ativo(self) -> bool:
        return self._sessao_passos is not None

    def _construir_interface(self) -> None:
        raiz = QWidget()
        raiz.setObjectName("raiz")
        layout_raiz = QVBoxLayout(raiz)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)
        layout_raiz.addWidget(self._criar_menu_projeto())
        layout_raiz.addWidget(self._criar_barra_superior())

        conteudo = QWidget()
        layout_conteudo = QVBoxLayout(conteudo)
        layout_conteudo.setContentsMargins(14, 14, 14, 14)
        layout_conteudo.setSpacing(12)

        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.setChildrenCollapsible(False)
        divisor.addWidget(self._criar_painel_ferramentas())
        divisor.addWidget(self._criar_area_visualizacao())
        divisor.addWidget(self._criar_painel_rotas())
        divisor.setStretchFactor(0, 0)
        divisor.setStretchFactor(1, 1)
        divisor.setStretchFactor(2, 0)
        divisor.setSizes([235, 760, 290])
        self._divisor_visualizacao = divisor
        layout_conteudo.addWidget(divisor, 1)

        self.painel_resultados = PainelResultados()
        self.painel_resultados.limpar_solicitado.connect(self.limpar_rota)
        self.botao_limpar = self.painel_resultados.botao_limpar
        layout_conteudo.addWidget(self.painel_resultados)
        layout_raiz.addWidget(conteudo, 1)
        self.setCentralWidget(raiz)
        self._ajustar_barra_superior()

    def _criar_menu_projeto(self) -> QMenuBar:
        """Cria os comandos persistentes sem misturar serialização à UI."""
        menu_barra = QMenuBar()
        menu_barra.setObjectName("menuProjeto")
        menu = menu_barra.addMenu("Projeto")

        self.acao_abrir_projeto = QAction("Abrir projeto…", self)
        self.acao_abrir_projeto.triggered.connect(lambda: self.abrir_projeto())
        menu.addAction(self.acao_abrir_projeto)

        self.acao_salvar_projeto = QAction("Salvar", self)
        self.acao_salvar_projeto.triggered.connect(lambda: self.salvar_projeto())
        menu.addAction(self.acao_salvar_projeto)

        self.acao_salvar_projeto_como = QAction("Salvar como…", self)
        self.acao_salvar_projeto_como.triggered.connect(lambda: self.salvar_projeto_como())
        menu.addAction(self.acao_salvar_projeto_como)
        menu.addSeparator()

        self.acao_restaurar_exemplo = QAction("Restaurar cenário de demonstração", self)
        self.acao_restaurar_exemplo.triggered.connect(
            lambda: self.restaurar_cenario_exemplo()
        )
        menu.addAction(self.acao_restaurar_exemplo)
        return menu_barra

    def _criar_barra_superior(self) -> QFrame:
        barra = QFrame()
        barra.setObjectName("barraSuperior")
        barra.setFixedHeight(72)
        layout = QHBoxLayout(barra)
        # A barra pode ser compactada sem impor sua largura natural à janela.
        # Os elementos secundários são ocultados em resoluções estreitas por
        # ``_ajustar_barra_superior``.
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(12)
        barra.setMinimumWidth(0)

        marca = QLabel("DR")
        marca.setObjectName("marca")
        marca.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(marca)

        textos = QVBoxLayout()
        textos.setSpacing(1)
        titulo = QLabel("DELIVERY ROUTE")
        titulo.setObjectName("tituloAplicacao")
        titulo.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.rotulo_titulo_aplicacao = titulo
        subtitulo = QLabel("Sistema Inteligente de Otimização de Entregas")
        subtitulo.setObjectName("subtituloAplicacao")
        self.rotulo_subtitulo_aplicacao = subtitulo
        textos.addWidget(titulo)
        textos.addWidget(subtitulo)
        layout.addLayout(textos)
        layout.addStretch(1)

        self.rotulo_cenario = QLabel("Cenário: Demonstração")
        self.rotulo_cenario.setObjectName("cenario")
        layout.addWidget(self.rotulo_cenario)

        self.botao_restaurar = QPushButton("Restaurar exemplo")
        self.botao_restaurar.setObjectName("botaoPrimario")
        self.botao_restaurar.clicked.connect(lambda: self.restaurar_cenario_exemplo())
        layout.addWidget(self.botao_restaurar)

        self.botao_visualizacao = QPushButton("Visualização")
        self.botao_visualizacao.setCheckable(True)
        self.botao_visualizacao.setChecked(True)
        self.botao_visualizacao.clicked.connect(
            lambda: self.definir_modo_interface("visualizacao")
        )
        layout.addWidget(self.botao_visualizacao)

        self.botao_edicao = QPushButton("Edição")
        self.botao_edicao.setCheckable(True)
        self.botao_edicao.clicked.connect(lambda: self.definir_modo_interface("edicao"))
        layout.addWidget(self.botao_edicao)

        self.botao_cidade = QPushButton("Cidade")
        self.botao_cidade.setCheckable(True)
        self.botao_cidade.setChecked(True)
        self.botao_cidade.clicked.connect(lambda: self.definir_modo("cidade"))
        layout.addWidget(self.botao_cidade)

        self.botao_grafo = QPushButton("Grafo")
        self.botao_grafo.setCheckable(True)
        self.botao_grafo.clicked.connect(lambda: self.definir_modo("grafo"))
        layout.addWidget(self.botao_grafo)

        self.botao_cidade_3d = QPushButton("Cidade 3D")
        self.botao_cidade_3d.setObjectName("botao3D")
        self.botao_cidade_3d.setCheckable(True)
        self.botao_cidade_3d.setToolTip("Abrir o protótipo 3D navegável da cidade")
        self.botao_cidade_3d.clicked.connect(lambda: self.definir_modo("cidade3d"))
        layout.addWidget(self.botao_cidade_3d)
        return barra

    def _ajustar_barra_superior(self) -> None:
        """Mantém os controles do cabeçalho acessíveis em larguras menores."""
        if not hasattr(self, "rotulo_subtitulo_aplicacao"):
            return
        compacto = self.width() < 1_000
        self.rotulo_subtitulo_aplicacao.setVisible(not compacto)
        self.rotulo_cenario.setVisible(not compacto)
        self.botao_enquadrar.setText(
            "Enquadrar" if compacto else "Restaurar enquadramento"
        )
        # O cabeçalho mantém todos os modos acessíveis mesmo na largura mínima
        # prevista para a janela. Os tooltips preservam os nomes completos.
        self.botao_visualizacao.setText("Vis." if compacto else "Visualização")
        self.botao_visualizacao.setToolTip("Modo de visualização")
        self.botao_edicao.setText("Ed." if compacto else "Edição")
        self.botao_edicao.setToolTip("Modo de edição")
        self.botao_cidade.setText("2D" if compacto else "Cidade")
        self.botao_cidade.setToolTip("Cidade 2D")
        self.botao_grafo.setText("Grafo")
        self.botao_grafo.setToolTip("Representação matemática do grafo")
        self.botao_cidade_3d.setText("3D" if compacto else "Cidade 3D")
        barra = self.rotulo_titulo_aplicacao.parentWidget()
        if barra is not None and barra.layout() is not None:
            barra.layout().invalidate()
            barra.layout().activate()
        area = self.botao_enquadrar.parentWidget()
        if area is not None and area.layout() is not None:
            area.layout().invalidate()
            area.layout().activate()
        self._atualizar_titulo_visualizacao(compacto=compacto)

    def _atualizar_titulo_visualizacao(self, *, compacto: bool | None = None) -> None:
        if not hasattr(self, "titulo_visualizacao"):
            return
        if compacto is None:
            compacto = self.width() < 1_000
        if compacto:
            texto = {
                "cidade": "Cidade",
                "grafo": "Grafo",
                "cidade3d": (
                    "Missão 3D"
                    if hasattr(self, "cidade_3d") and self.cidade_3d.em_missao
                    else "Cidade 3D"
                ),
            }.get(self._modo_atual, "Cidade")
        else:
            texto = {
                "cidade": "Mapa da cidade",
                "grafo": "Representação matemática do grafo",
                "cidade3d": (
                    "Missão 3D — terceira pessoa"
                    if hasattr(self, "cidade_3d") and self.cidade_3d.em_missao
                    else "Protótipo 3D navegável"
                ),
            }.get(self._modo_atual, "Mapa da cidade")
        self.titulo_visualizacao.setText(texto)

    def resizeEvent(self, evento) -> None:  # noqa: N802 - contrato Qt
        super().resizeEvent(evento)
        self._ajustar_barra_superior()

    def _criar_painel_ferramentas(self) -> QFrame:
        painel = QFrame()
        painel.setObjectName("painel")
        painel.setMinimumWidth(205)
        painel.setMaximumWidth(275)
        layout_painel = QVBoxLayout(painel)
        layout_painel.setContentsMargins(0, 0, 0, 0)

        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        conteudo = QWidget()
        conteudo.setObjectName("conteudoPainel")
        # O conteúdo deve acompanhar a viewport; sem esta política o tamanho
        # natural dos controles pode deixar uma faixa horizontal cortada.
        conteudo.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        layout = QVBoxLayout(conteudo)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(6)
        layout.addWidget(self._titulo_painel("FERRAMENTAS"))

        self.botao_selecionar = QPushButton("Selecionar elemento")
        self.botao_selecionar.setObjectName("botaoFerramenta")
        self.botao_selecionar.setCheckable(True)
        self.botao_selecionar.setChecked(True)
        layout.addWidget(self.botao_selecionar)

        layout.addWidget(self._titulo_painel("EDITAR CENÁRIO"))
        self.botao_adicionar_vertice = self._botao_ferramenta(
            "Adicionar local", self._abrir_dialogo_adicionar_vertice
        )
        self.botao_editar_vertice = self._botao_ferramenta(
            "Editar local", self._abrir_dialogo_editar_vertice
        )
        self.botao_remover_vertice = self._botao_ferramenta(
            "Remover local", self._abrir_dialogo_remover_vertice
        )
        self.botao_adicionar_aresta = self._botao_ferramenta(
            "Criar rua", self._abrir_dialogo_adicionar_aresta
        )
        self.botao_editar_aresta = self._botao_ferramenta(
            "Editar rua", self._abrir_dialogo_editar_aresta
        )
        self.botao_remover_aresta = self._botao_ferramenta(
            "Remover rua", self._abrir_dialogo_remover_aresta
        )
        for botao in (
            self.botao_adicionar_vertice,
            self.botao_editar_vertice,
            self.botao_remover_vertice,
            self.botao_adicionar_aresta,
            self.botao_editar_aresta,
            self.botao_remover_aresta,
        ):
            layout.addWidget(botao)

        layout.addSpacing(8)
        layout.addWidget(self._titulo_painel("LOCAIS CADASTRADOS"))
        self.lista_locais = QListWidget()
        self.lista_locais.setMinimumHeight(105)
        self.lista_locais.setMaximumHeight(125)
        self.lista_locais.itemClicked.connect(self._local_clicado_na_lista)
        layout.addWidget(self.lista_locais)

        layout.addWidget(self._titulo_painel("DETALHES DO LOCAL"))
        self.rotulo_detalhes = QLabel("Selecione um vértice no mapa ou no grafo.")
        self.rotulo_detalhes.setObjectName("detalhesLocal")
        self.rotulo_detalhes.setWordWrap(True)
        self.rotulo_detalhes.setTextFormat(Qt.TextFormat.RichText)
        self.rotulo_detalhes.setMinimumHeight(95)
        layout.addWidget(self.rotulo_detalhes)
        rolagem.setWidget(conteudo)
        layout_painel.addWidget(rolagem)
        self._atualizar_modo_interface()
        return painel

    @staticmethod
    def _botao_ferramenta(texto: str, callback) -> QPushButton:
        botao = QPushButton(texto)
        botao.setObjectName("botaoFerramenta")
        botao.clicked.connect(callback)
        return botao

    def _criar_area_visualizacao(self) -> QFrame:
        painel = QFrame()
        painel.setObjectName("areaVisualizacao")
        painel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(painel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        cabecalho = QHBoxLayout()
        self.titulo_visualizacao = QLabel("Mapa da cidade")
        self.titulo_visualizacao.setObjectName("tituloVisualizacao")
        cabecalho.addWidget(self.titulo_visualizacao)
        cabecalho.addStretch(1)
        restaurar = QPushButton("Restaurar enquadramento")
        restaurar.setToolTip("Restaurar enquadramento")
        restaurar.clicked.connect(self.restaurar_enquadramento)
        self.botao_enquadrar = restaurar
        cabecalho.addWidget(restaurar)
        layout.addLayout(cabecalho)

        self.mapa_cidade = MapaCidade(self._grafo)
        self.visualizador_grafo = VisualizadorGrafo(self._grafo)
        self.cidade_3d = Cidade3DWidget(self._grafo)
        self.mapa_cidade.vertice_selecionado.connect(self.selecionar_vertice)
        self.visualizador_grafo.vertice_selecionado.connect(self.selecionar_vertice)
        self.cidade_3d.vertice_selecionado.connect(self.selecionar_vertice)
        self.cidade_3d.missao_concluida.connect(self._missao_3d_concluida)
        self.cidade_3d.voltar_planejamento.connect(self._voltar_da_missao_3d)

        self.pilha_visualizacoes = QStackedWidget()
        self.pilha_visualizacoes.addWidget(self.mapa_cidade)
        self.pilha_visualizacoes.addWidget(self.visualizador_grafo)
        self.pilha_visualizacoes.addWidget(self.cidade_3d)
        layout.addWidget(self.pilha_visualizacoes, 1)
        return painel

    def _criar_painel_rotas(self) -> QFrame:
        painel = QFrame()
        painel.setObjectName("painel")
        painel.setMinimumWidth(255)
        painel.setMaximumWidth(325)
        layout_painel = QVBoxLayout(painel)
        layout_painel.setContentsMargins(0, 0, 0, 0)

        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        conteudo = QWidget()
        conteudo.setObjectName("conteudoPainel")
        conteudo.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        layout = QVBoxLayout(conteudo)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(9)
        layout.addWidget(self._titulo_painel("OTIMIZAÇÃO DE ROTAS"))

        rotulo_algoritmo = QLabel("Algoritmo")
        rotulo_algoritmo.setObjectName("textoSecundario")
        layout.addWidget(rotulo_algoritmo)
        self.combo_algoritmo = QComboBox()
        self.combo_algoritmo.addItem("Dijkstra — Menor caminho", "dijkstra")
        self.combo_algoritmo.addItem("Caixeiro Viajante — Rota de entregas", "tsp")
        self.combo_algoritmo.currentIndexChanged.connect(self._algoritmo_alterado)
        layout.addWidget(self.combo_algoritmo)

        self.pilha_configuracao = QStackedWidget()
        self.pilha_configuracao.addWidget(self._criar_configuracao_dijkstra())
        self.pilha_configuracao.addWidget(self._criar_configuracao_tsp())
        layout.addWidget(self.pilha_configuracao, 1)

        self.botao_calcular = QPushButton("Calcular menor caminho")
        self.botao_calcular.setObjectName("botaoPrimario")
        self.botao_calcular.clicked.connect(self.calcular_rota)
        layout.addWidget(self.botao_calcular)
        self.botao_iniciar_missao_3d = QPushButton("Iniciar missão 3D")
        self.botao_iniciar_missao_3d.setObjectName("botaoMissao3D")
        self.botao_iniciar_missao_3d.setToolTip(
            "Abrir a simulação 3D em terceira pessoa para a rota calculada"
        )
        self.botao_iniciar_missao_3d.clicked.connect(self._iniciar_missao_3d)
        self.botao_iniciar_missao_3d.setEnabled(False)
        layout.addWidget(self.botao_iniciar_missao_3d)
        self.painel_modelos_3d = PainelModelos3D()
        self.painel_modelos_3d.configuracao_alterada.connect(
            self._configuracao_modelos_3d_alterada
        )
        self.painel_modelos_3d.visualizar_solicitado.connect(
            self._visualizar_modelos_3d
        )
        self.painel_modelos_3d.enquadrar_solicitado.connect(
            self._enquadrar_cidade_3d
        )
        self.painel_modelos_3d.calibrar_solicitado.connect(
            self._calibrar_cidade_3d
        )
        self.botao_selecionar_cidade_glb = self.painel_modelos_3d.botao_selecionar_cidade
        self.botao_selecionar_carro_glb = self.painel_modelos_3d.botao_selecionar_carro
        self.botao_restaurar_modelos_3d = self.painel_modelos_3d.botao_restaurar
        self.botao_visualizar_modelos_3d = self.painel_modelos_3d.botao_visualizar
        self.controle_escala_carro_glb = self.painel_modelos_3d.controle_escala_carro
        self.controle_orientacao_carro_glb = self.painel_modelos_3d.controle_orientacao_carro
        self.controle_altura_carro_glb = self.painel_modelos_3d.controle_altura_carro
        self.controle_escala_cidade_glb = self.painel_modelos_3d.controle_escala_cidade
        layout.addWidget(self.painel_modelos_3d)
        self.rotulo_aviso = QLabel("Configure uma rota e clique em calcular.")
        self.rotulo_aviso.setObjectName("aviso")
        self.rotulo_aviso.setWordWrap(True)
        layout.addWidget(self.rotulo_aviso)
        self.painel_passos = PainelPassos()
        self.painel_passos.iniciar_solicitado.connect(self.iniciar_passo_a_passo)
        self.painel_passos.avancar_solicitado.connect(self.avancar_passo)
        self.painel_passos.retroceder_solicitado.connect(self.retroceder_passo)
        self.painel_passos.primeiro_solicitado.connect(self.ir_para_primeiro_passo)
        self.painel_passos.ultimo_solicitado.connect(self.ir_para_ultimo_passo)
        self.painel_passos.encerrar_solicitado.connect(self.encerrar_passo_a_passo)
        layout.addWidget(self.painel_passos)
        rolagem.setWidget(conteudo)
        layout_painel.addWidget(rolagem)
        return painel

    def _criar_configuracao_dijkstra(self) -> QWidget:
        conteudo = QWidget()
        layout = QVBoxLayout(conteudo)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(7)
        rotulo_origem = QLabel("Origem")
        rotulo_origem.setObjectName("textoSecundario")
        layout.addWidget(rotulo_origem)
        self.combo_origem = QComboBox()
        layout.addWidget(self.combo_origem)
        rotulo_destino = QLabel("Destino")
        rotulo_destino.setObjectName("textoSecundario")
        layout.addWidget(rotulo_destino)
        self.combo_destino = QComboBox()
        layout.addWidget(self.combo_destino)
        layout.addStretch(1)
        return conteudo

    def _criar_configuracao_tsp(self) -> QWidget:
        conteudo = QWidget()
        layout = QVBoxLayout(conteudo)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(7)
        rotulo_deposito = QLabel("Depósito principal")
        rotulo_deposito.setObjectName("textoSecundario")
        layout.addWidget(rotulo_deposito)
        self.rotulo_deposito_tsp = QLabel("Ainda não definido")
        self.rotulo_deposito_tsp.setObjectName("detalhesLocal")
        self.rotulo_deposito_tsp.setWordWrap(True)
        layout.addWidget(self.rotulo_deposito_tsp)
        rotulo_clientes = QLabel("Clientes para entregas")
        rotulo_clientes.setObjectName("textoSecundario")
        layout.addWidget(rotulo_clientes)
        self.lista_clientes_rota = QListWidget()
        self.lista_clientes_rota.setMinimumHeight(120)
        self.lista_clientes_rota.itemChanged.connect(self._clientes_alterados)
        layout.addWidget(self.lista_clientes_rota, 1)
        selecao = QLabel("Desmarque clientes que não farão parte desta rota.")
        selecao.setObjectName("textoSecundario")
        selecao.setWordWrap(True)
        layout.addWidget(selecao)
        return conteudo

    @staticmethod
    def _titulo_painel(texto: str) -> QLabel:
        titulo = QLabel(texto)
        titulo.setObjectName("tituloPainel")
        return titulo

    def definir_modo_interface(self, modo: str) -> None:
        """Alterna entre consultar o cenário e habilitar suas ferramentas de edição."""
        if modo not in {"visualizacao", "edicao"}:
            raise ValueError("O modo deve ser 'visualizacao' ou 'edicao'.")
        if (self._calculando or self._sessao_passos is not None) and modo == "edicao":
            # Botões checkable podem alternar visualmente antes de o slot ser
            # chamado; restaure o estado real quando a troca é recusada.
            self.botao_visualizacao.setChecked(self._modo_interface == "visualizacao")
            self.botao_edicao.setChecked(self._modo_interface == "edicao")
            return
        self._modo_interface = modo
        self.botao_visualizacao.setChecked(modo == "visualizacao")
        self.botao_edicao.setChecked(modo == "edicao")
        self._atualizar_modo_interface()
        self.rotulo_aviso.setText(
            "Modo de edição ativo: alterações invalidam a rota atual."
            if modo == "edicao"
            else "Modo de visualização ativo."
        )

    def _atualizar_modo_interface(self) -> None:
        """Habilita as seis operações somente no modo de edição."""
        if not hasattr(self, "botao_adicionar_vertice"):
            return
        habilitado = (
            self._modo_interface == "edicao"
            and not self._calculando
            and self._sessao_passos is None
        )
        for botao in (
            self.botao_adicionar_vertice,
            self.botao_editar_vertice,
            self.botao_remover_vertice,
            self.botao_adicionar_aresta,
            self.botao_editar_aresta,
            self.botao_remover_aresta,
        ):
            botao.setEnabled(habilitado)

    def definir_modo(self, modo: str) -> None:
        if modo in {"cidade_3d", "cidade-3d", "3d"}:
            modo = "cidade3d"
        if modo not in {"cidade", "grafo", "cidade3d"}:
            raise ValueError("O modo deve ser 'cidade', 'grafo' ou 'cidade3d'.")
        self._modo_atual = modo
        # Trocar a página do QStackedWidget pode recalcular o sizeHint do
        # painel central (especialmente quando o QQuickWidget é criado). A
        # navegação entre Cidade, Grafo e Cidade 3D não deve mover os divisores
        # que o usuário já ajustou.
        tamanhos_divisor = (
            self._divisor_visualizacao.sizes()
            if hasattr(self, "_divisor_visualizacao")
            else []
        )
        cidade = modo == "cidade"
        cidade_3d = modo == "cidade3d"
        self.botao_cidade.setChecked(cidade)
        self.botao_grafo.setChecked(modo == "grafo")
        self.botao_cidade_3d.setChecked(cidade_3d)
        self.pilha_visualizacoes.setCurrentIndex(
            0 if cidade else 1 if modo == "grafo" else 2
        )
        if getattr(self.cidade_3d, "renderizador_qtquick3d", None) is not None:
            cena_glb = self.cidade_3d.renderizador_qtquick3d
            cena_glb.setVisible(cidade_3d and cena_glb.renderizacao_ativa)
        self._atualizar_titulo_visualizacao()
        visualizacao = (
            self.mapa_cidade
            if cidade
            else self.visualizador_grafo
            if modo == "grafo"
            else self.cidade_3d
        )
        visualizacao.selecionar_vertice(self._vertice_selecionado)
        if len(tamanhos_divisor) == 3 and all(tamanho > 0 for tamanho in tamanhos_divisor):
            QTimer.singleShot(0, lambda: self._divisor_visualizacao.setSizes(tamanhos_divisor))

    def carregar_cenario_exemplo(self) -> None:
        """Compatibilidade com o botão e com o código da primeira versão."""
        self.restaurar_cenario_exemplo()

    def restaurar_cenario_exemplo(self, confirmar: bool = True) -> bool:
        """Restaura o cenário de demonstração, confirmando perda de alterações."""
        if confirmar and not self._confirmar_alteracoes_pendentes():
            return False
        self.carregar_grafo(criar_cenario_exemplo(), nome_cenario="Demonstração")
        self.rotulo_aviso.setText("Cenário de demonstração restaurado.")
        return True

    def salvar_projeto(self, caminho: str | Path | None = None) -> bool:
        """Salva no caminho atual ou abre o seletor no primeiro salvamento."""
        if caminho is None:
            if self._caminho_projeto is None:
                return self.salvar_projeto_como()
            caminho_path = self._caminho_projeto
        else:
            try:
                caminho_path = self._normalizar_caminho_projeto(caminho)
            except (TypeError, ValueError) as erro:
                self._mostrar_erro_persistencia("salvar", erro)
                return False
        return self._salvar_no_caminho(caminho_path)

    def salvar_projeto_como(self, caminho: str | Path | None = None) -> bool:
        """Escolhe um novo arquivo JSON e o associa ao projeto corrente."""
        if caminho is None:
            selecionado, _ = QFileDialog.getSaveFileName(
                self,
                "Salvar projeto",
                str(self._caminho_projeto or "projeto.json"),
                "Projetos Delivery Route (*.json);;Todos os arquivos (*)",
            )
            if not selecionado:
                return False
            try:
                caminho_path = self._normalizar_caminho_projeto(selecionado)
            except (TypeError, ValueError) as erro:
                self._mostrar_erro_persistencia("salvar", erro)
                return False
        else:
            try:
                caminho_path = self._normalizar_caminho_projeto(caminho)
            except (TypeError, ValueError) as erro:
                self._mostrar_erro_persistencia("salvar", erro)
                return False
        return self._salvar_no_caminho(caminho_path)

    def abrir_projeto(
        self, caminho: str | Path | None = None, confirmar: bool = True
    ) -> bool:
        """Valida um arquivo em memória e só então troca o projeto aberto."""
        if caminho is None:
            selecionado, _ = QFileDialog.getOpenFileName(
                self,
                "Abrir projeto",
                str(self._caminho_projeto.parent if self._caminho_projeto else ""),
                "Projetos Delivery Route (*.json);;Todos os arquivos (*)",
            )
            if not selecionado:
                return False
            try:
                caminho_path = self._normalizar_caminho_projeto(
                    selecionado, adicionar_extensao=False
                )
            except (TypeError, ValueError) as erro:
                self._mostrar_erro_persistencia("carregar", erro)
                return False
        else:
            try:
                caminho_path = self._normalizar_caminho_projeto(
                    caminho, adicionar_extensao=False
                )
            except (TypeError, ValueError) as erro:
                self._mostrar_erro_persistencia("carregar", erro)
                return False

        if confirmar and not self._confirmar_alteracoes_pendentes():
            return False
        try:
            grafo_carregado = carregar_grafo(caminho_path)
        except (OSError, TypeError, ValueError, ErroPersistencia) as erro:
            self._mostrar_erro_persistencia("carregar", erro)
            return False

        self.carregar_grafo(grafo_carregado, nome_cenario=caminho_path.stem)
        self._caminho_projeto = caminho_path
        self._grafo_modificado = False
        self._atualizar_titulo_projeto()
        self.rotulo_aviso.setText(f"Projeto carregado: {caminho_path.name}.")
        return True

    def _salvar_no_caminho(self, caminho: Path) -> bool:
        try:
            salvar_grafo(self._grafo, caminho)
        except (OSError, TypeError, ValueError, ErroPersistencia) as erro:
            self._mostrar_erro_persistencia("salvar", erro)
            return False
        self._caminho_projeto = caminho
        self._grafo_modificado = False
        self._atualizar_titulo_projeto()
        self.rotulo_aviso.setText(f"Projeto salvo: {caminho.name}.")
        return True

    @staticmethod
    def _normalizar_caminho_projeto(
        caminho: str | Path, *, adicionar_extensao: bool = True
    ) -> Path:
        if not isinstance(caminho, (str, Path)):
            raise TypeError("O caminho do projeto deve ser texto ou Path.")
        caminho_path = Path(caminho).expanduser()
        if not caminho_path.name:
            raise ValueError("O caminho do projeto não pode ser vazio.")
        if adicionar_extensao and caminho_path.suffix == "":
            caminho_path = caminho_path.with_suffix(".json")
        return caminho_path

    def _mostrar_erro_persistencia(self, operacao: str, erro: Exception) -> None:
        logger.info("Falha ao %s projeto: %s", operacao, erro)
        mensagem = f"Não foi possível {operacao} o projeto: {erro}"
        # O projeto e um eventual resultado anterior permanecem intactos;
        # o aviso não deve transformar uma falha de I/O em uma nova edição.
        self.rotulo_aviso.setText(mensagem)

    def _confirmar_alteracoes_pendentes(self) -> bool:
        """Retorna se uma ação destrutiva pode prosseguir."""
        if not self._grafo_modificado:
            return True
        caixa = QMessageBox(self)
        caixa.setIcon(QMessageBox.Icon.Warning)
        caixa.setWindowTitle("Alterações não salvas")
        caixa.setText("O projeto possui alterações não salvas.")
        caixa.setInformativeText("Deseja salvar antes de continuar?")
        caixa.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        caixa.setDefaultButton(QMessageBox.StandardButton.Save)
        resposta = caixa.exec()
        if resposta == QMessageBox.StandardButton.Save:
            return self.salvar_projeto()
        if resposta == QMessageBox.StandardButton.Discard:
            return True
        return False

    def _atualizar_titulo_projeto(self) -> None:
        nome = self._caminho_projeto.name if self._caminho_projeto else "Demonstração"
        marcador = " *" if self._grafo_modificado else ""
        self.setWindowTitle(f"Delivery Route — {nome}{marcador}")

    def carregar_grafo(
        self, grafo: Grafo, *, nome_cenario: str = "Personalizado"
    ) -> None:
        if not isinstance(grafo, Grafo):
            raise TypeError("É necessário fornecer uma instância de Grafo.")
        if self._sessao_passos is not None:
            self._encerrar_passo_a_passo(preservar_resultado=False)
        self._limpar_estado_rota()
        self._grafo = grafo
        self._grafo_modificado = False
        self._caminho_projeto = None
        self._vertice_selecionado = None
        self.mapa_cidade.carregar_grafo(grafo)
        self.visualizador_grafo.carregar_grafo(grafo)
        self.cidade_3d.carregar_grafo(grafo)
        self.rotulo_cenario.setText(f"Cenário: {nome_cenario}")
        self.rotulo_detalhes.setText("Selecione um vértice no mapa ou no grafo.")
        self._atualizar_dados_interface()
        self.definir_modo_interface("visualizacao")
        self._atualizar_titulo_visualizacao()
        self._atualizar_titulo_projeto()
        QTimer.singleShot(0, self._enquadrar_todas_as_visualizacoes)

    def adicionar_vertice(
        self,
        identificador: str,
        nome: str,
        tipo: TipoVertice | str,
        x: float,
        y: float,
    ) -> Vertice:
        """Adiciona um local e atualiza as duas visualizações imediatamente."""
        self._verificar_editavel()
        vertice = Vertice(identificador.strip(), nome.strip(), self._tipo_vertice(tipo), x, y)
        self._grafo.adicionar_vertice(vertice)
        self._registrar_alteracao("Local adicionado. Recalcule a rota.")
        return vertice

    def editar_vertice(
        self,
        identificador: str,
        *,
        nome: str,
        tipo: TipoVertice | str,
        x: float,
        y: float,
    ) -> Vertice:
        """Atualiza um local sem quebrar as arestas já existentes."""
        self._verificar_editavel()
        vertice = self._grafo.atualizar_vertice(
            identificador,
            nome=nome.strip(),
            tipo=self._tipo_vertice(tipo),
            x=x,
            y=y,
        )
        self._registrar_alteracao("Local atualizado. Recalcule a rota.")
        return vertice

    def remover_vertice(self, identificador: str, *, confirmar: bool = False) -> Vertice:
        """Remove um local e todas as ruas incidentes."""
        self._verificar_editavel()
        if confirmar and not self._confirmar(
            "Remover local?", "As ruas ligadas a este local também serão removidas.", self
        ):
            return self._grafo.obter_vertice(identificador)
        removido = self._grafo.remover_vertice(identificador)
        self._registrar_alteracao("Local removido. Recalcule a rota.")
        return removido

    def adicionar_aresta(self, origem: str, destino: str, peso: float) -> None:
        """Cria uma rua bidirecional no grafo em edição."""
        self._verificar_editavel()
        self._grafo.adicionar_aresta(origem, destino, peso)
        self._registrar_alteracao("Rua criada. Recalcule a rota.")

    def editar_aresta(self, origem: str, destino: str, peso: float) -> None:
        """Altera o peso de uma rua existente nos dois sentidos."""
        self._verificar_editavel()
        self._grafo.atualizar_peso_aresta(origem, destino, peso)
        self._registrar_alteracao("Rua atualizada. Recalcule a rota.")

    def remover_aresta(
        self, origem: str, destino: str, *, confirmar: bool = False
    ) -> None:
        """Remove uma rua bidirecional."""
        self._verificar_editavel()
        if confirmar and not self._confirmar(
            "Remover rua?", "A conexão será removida nos dois sentidos.", self
        ):
            return
        self._grafo.remover_aresta(origem, destino)
        self._registrar_alteracao("Rua removida. Recalcule a rota.")

    @staticmethod
    def _tipo_vertice(tipo: TipoVertice | str) -> TipoVertice:
        if isinstance(tipo, TipoVertice):
            return tipo
        try:
            return TipoVertice(tipo)
        except (TypeError, ValueError) as erro:
            raise ValueError("Tipo de vértice inválido.") from erro

    def _verificar_editavel(self) -> None:
        if self._calculando:
            raise RuntimeError("Aguarde o cálculo terminar antes de editar o grafo.")
        if self._sessao_passos is not None:
            raise RuntimeError(
                "Encerre a sessão passo a passo antes de editar o grafo."
            )

    @staticmethod
    def _confirmar(titulo: str, mensagem: str, parent=None) -> bool:
        resposta = QMessageBox.question(
            parent,
            titulo,
            mensagem,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return resposta == QMessageBox.StandardButton.Yes

    def _registrar_alteracao(self, mensagem: str) -> None:
        """Invalida a rota uma única vez e repinta Cidade e Grafo com o mesmo modelo."""
        self._grafo_modificado = True
        self._atualizar_titulo_projeto()
        self._resultado_atual = None
        self._algoritmo_resultado = None
        self.mapa_cidade.limpar_destaque_rota()
        self.visualizador_grafo.limpar_destaque_rota()
        if self.cidade_3d.em_missao:
            self.cidade_3d.sair_missao()
        self.cidade_3d.limpar_destaque_rota()
        selecionado = self._vertice_selecionado
        self.mapa_cidade.carregar_grafo(self._grafo)
        self.visualizador_grafo.carregar_grafo(self._grafo)
        self.cidade_3d.carregar_grafo(self._grafo)
        self._atualizar_dados_interface()
        if selecionado is not None and any(
            vertice.identificador == selecionado for vertice in self._grafo.listar_vertices()
        ):
            self.selecionar_vertice(selecionado)
        else:
            self._vertice_selecionado = None
            self.rotulo_detalhes.setText("Selecione um vértice no mapa ou no grafo.")
        self.painel_resultados.exibir_grafo_alterado()
        self._atualizar_botao_missao_3d()
        self._atualizar_titulo_visualizacao()
        self.rotulo_aviso.setText(mensagem)
        QTimer.singleShot(0, self._enquadrar_todas_as_visualizacoes)

    def _mostrar_erro_edicao(self, erro: Exception) -> None:
        logger.info("Edição recusada: %s", erro)
        self.painel_resultados.exibir_erro(str(erro))
        self.rotulo_aviso.setText("Não foi possível alterar o grafo.")

    def _proxima_posicao(self) -> tuple[float, float]:
        vertices = self._grafo.listar_vertices()
        if not vertices:
            return (0.0, 0.0)
        return (max(vertice.x for vertice in vertices) + 2.0, max(vertice.y for vertice in vertices))

    def _abrir_dialogo_adicionar_vertice(self) -> None:
        dialogo = DialogoVertice(posicao=self._proxima_posicao(), parent=self)
        if dialogo.exec() != DialogoVertice.DialogCode.Accepted:
            return
        try:
            dados = dialogo.dados()
            self.adicionar_vertice(**dados)
        except (KeyError, TypeError, ValueError, RuntimeError) as erro:
            self._mostrar_erro_edicao(erro)

    def _abrir_dialogo_editar_vertice(self) -> None:
        if self._vertice_selecionado is None:
            self._mostrar_erro_edicao(ValueError("Selecione um local para editar."))
            return
        vertice = self._grafo.obter_vertice(self._vertice_selecionado)
        dialogo = DialogoVertice(vertice=vertice, parent=self)
        if dialogo.exec() != DialogoVertice.DialogCode.Accepted:
            return
        try:
            dados = dialogo.dados()
            dados.pop("identificador")
            self.editar_vertice(vertice.identificador, **dados)
        except (KeyError, TypeError, ValueError, RuntimeError) as erro:
            self._mostrar_erro_edicao(erro)

    def _abrir_dialogo_remover_vertice(self) -> None:
        if self._vertice_selecionado is None:
            self._mostrar_erro_edicao(ValueError("Selecione um local para remover."))
            return
        try:
            self.remover_vertice(self._vertice_selecionado, confirmar=True)
        except (KeyError, TypeError, ValueError, RuntimeError) as erro:
            self._mostrar_erro_edicao(erro)

    def _abrir_dialogo_adicionar_aresta(self) -> None:
        dialogo = DialogoAresta(self._grafo, parent=self)
        if dialogo.exec() != DialogoAresta.DialogCode.Accepted:
            return
        try:
            self.adicionar_aresta(**dialogo.dados())
        except (KeyError, TypeError, ValueError, RuntimeError) as erro:
            self._mostrar_erro_edicao(erro)

    def _abrir_dialogo_editar_aresta(self) -> None:
        if not self._grafo.listar_arestas():
            self._mostrar_erro_edicao(ValueError("Não há ruas cadastradas para editar."))
            return
        dialogo = DialogoArestaExistente(
            self._grafo, titulo="Editar rua", parent=self
        )
        if dialogo.exec() != DialogoArestaExistente.DialogCode.Accepted:
            return
        try:
            self.editar_aresta(**dialogo.dados())
        except (KeyError, TypeError, ValueError, RuntimeError) as erro:
            self._mostrar_erro_edicao(erro)

    def _abrir_dialogo_remover_aresta(self) -> None:
        if not self._grafo.listar_arestas():
            self._mostrar_erro_edicao(ValueError("Não há ruas cadastradas para remover."))
            return
        dialogo = DialogoArestaExistente(
            self._grafo, titulo="Remover rua", parent=self
        )
        if dialogo.exec() != DialogoArestaExistente.DialogCode.Accepted:
            return
        dados = dialogo.dados()
        try:
            self.remover_aresta(dados["origem"], dados["destino"], confirmar=True)
        except (KeyError, TypeError, ValueError, RuntimeError) as erro:
            self._mostrar_erro_edicao(erro)

    def selecionar_vertice(self, identificador: str) -> None:
        vertice = self._grafo.obter_vertice(identificador)
        self._vertice_selecionado = identificador
        self.mapa_cidade.selecionar_vertice(identificador)
        self.visualizador_grafo.selecionar_vertice(identificador)
        self.cidade_3d.selecionar_vertice(identificador)

        self.lista_locais.blockSignals(True)
        for indice in range(self.lista_locais.count()):
            item = self.lista_locais.item(indice)
            if item.data(Qt.ItemDataRole.UserRole) == identificador:
                self.lista_locais.setCurrentItem(item)
                break
        self.lista_locais.blockSignals(False)

        vizinhos = self._grafo.obter_vizinhos(identificador)
        if vizinhos:
            conexoes = "<br>".join(
                f"{escape(self._grafo.obter_vertice(vizinho).nome)} "
                f"({peso:g} km)"
                for vizinho, peso in sorted(vizinhos.items())
            )
        else:
            conexoes = "Sem conexões"
        self.rotulo_detalhes.setText(
            f"<b>{escape(vertice.nome)}</b><br>"
            f"Identificador: {escape(vertice.identificador)}<br>"
            f"Tipo: {escape(vertice.tipo.value.capitalize())}<br><br>"
            f"<b>Conexões</b><br>{conexoes}"
        )

    def restaurar_enquadramento(self) -> None:
        visualizacao = {
            "cidade": self.mapa_cidade,
            "grafo": self.visualizador_grafo,
            "cidade3d": self.cidade_3d,
        }[self._modo_atual]
        visualizacao.restaurar_enquadramento()

    def _enquadrar_todas_as_visualizacoes(self) -> None:
        self.mapa_cidade.restaurar_enquadramento()
        self.visualizador_grafo.restaurar_enquadramento()
        self.cidade_3d.restaurar_enquadramento()

    def _local_clicado_na_lista(self, item: QListWidgetItem) -> None:
        self.selecionar_vertice(item.data(Qt.ItemDataRole.UserRole))

    def _algoritmo_alterado(self, indice: int) -> None:
        algoritmo = self.combo_algoritmo.itemData(indice)
        if hasattr(self, "painel_passos") and algoritmo:
            self.painel_passos.configurar_algoritmo(algoritmo)
        if algoritmo == "tsp":
            self.pilha_configuracao.setCurrentIndex(1)
            self.botao_calcular.setText("Calcular melhor rota")
            self.rotulo_aviso.setText("Selecione os clientes e calcule a rota ótima.")
        else:
            self.pilha_configuracao.setCurrentIndex(0)
            self.botao_calcular.setText("Calcular menor caminho")
            self.rotulo_aviso.setText("Escolha origem e destino para calcular.")

    def _clientes_alterados(self, item: QListWidgetItem) -> None:
        del item
        if not self._calculando and self.combo_algoritmo.currentData() == "tsp":
            self.rotulo_aviso.setText(
                f"{len(self.clientes_selecionados())} cliente(s) selecionado(s)."
            )

    def clientes_selecionados(self) -> list[str]:
        return [
            self.lista_clientes_rota.item(indice).data(Qt.ItemDataRole.UserRole)
            for indice in range(self.lista_clientes_rota.count())
            if self.lista_clientes_rota.item(indice).checkState()
            == Qt.CheckState.Checked
        ]

    def iniciar_passo_a_passo(self) -> None:
        """Prepara um histórico e exibe sua primeira etapa sem animar."""
        if self._calculando or self._sessao_passos is not None:
            return
        self._calculando = True
        self._atualizar_controles_calculo()
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        try:
            self._limpar_estado_rota()
            if self.combo_algoritmo.currentData() == "tsp":
                sessao = SessaoPassoAPasso.criar_tsp(
                    self._grafo, self.clientes_selecionados()
                )
            else:
                origem = self.combo_origem.currentData()
                destino = self.combo_destino.currentData()
                if not origem or not destino:
                    raise ValueError("Selecione uma origem e um destino válidos.")
                sessao = SessaoPassoAPasso.criar_dijkstra(
                    self._grafo, origem, destino
                )
            self._sessao_passos = sessao
            self._mostrar_passo_atual()
            self.rotulo_aviso.setText("Sessão passo a passo iniciada.")
        except (KeyError, TypeError, ValueError) as erro:
            logger.info("Não foi possível iniciar a sessão passo a passo: %s", erro)
            self._sessao_passos = None
            self.painel_passos.limpar()
            self.rotulo_aviso.setText(str(erro))
        finally:
            self._calculando = False
            self._atualizar_controles_calculo()

    def avancar_passo(self) -> None:
        self._navegar_passo("avancar")

    def retroceder_passo(self) -> None:
        self._navegar_passo("retroceder")

    def ir_para_primeiro_passo(self) -> None:
        self._navegar_passo("primeiro")

    def ir_para_ultimo_passo(self) -> None:
        self._navegar_passo("ultimo")

    def _navegar_passo(self, operacao: str) -> None:
        sessao = self._sessao_passos
        if sessao is None:
            return
        if sessao.grafo_foi_alterado(self._grafo):
            mensagem = "O grafo foi alterado; o histórico passo a passo foi encerrado."
            self._encerrar_passo_a_passo(preservar_resultado=False)
            self._registrar_alteracao(mensagem)
            return
        getattr(sessao, {"avancar": "avancar", "retroceder": "retroceder", "primeiro": "ir_para_primeiro", "ultimo": "ir_para_ultimo"}[operacao])()
        self._mostrar_passo_atual()

    def _mostrar_passo_atual(self) -> None:
        sessao = self._sessao_passos
        if sessao is None or sessao.passo_atual is None:
            return
        passo = sessao.passo_atual
        arestas = passo.arestas_avaliadas
        if passo.caminho_final:
            arestas = arestas + tuple(
                zip(passo.caminho_final, passo.caminho_final[1:])
            )
        self.mapa_cidade.destacar_passo(
            vertice_atual=passo.vertice_atual,
            vertices_processados=passo.vertices_processados,
            arestas=arestas,
            caminho_final=passo.caminho_final,
        )
        self.visualizador_grafo.destacar_passo(
            vertice_atual=passo.vertice_atual,
            vertices_processados=passo.vertices_processados,
            arestas=arestas,
            caminho_final=passo.caminho_final,
        )
        self.cidade_3d.destacar_passo(
            vertice_atual=passo.vertice_atual,
            vertices_processados=passo.vertices_processados,
            arestas=arestas,
            caminho_final=passo.caminho_final,
        )
        self.painel_passos.mostrar_passo(passo, sessao.total, sessao.indice_atual)
        self.rotulo_aviso.setText(passo.descricao)

        if passo.concluido:
            self._resultado_atual = sessao.resultado
            self._algoritmo_resultado = sessao.algoritmo
            if sessao.algoritmo == "tsp":
                self.painel_resultados.exibir_tsp(self._grafo, sessao.resultado)
            else:
                self.painel_resultados.exibir_dijkstra(self._grafo, sessao.resultado)
        else:
            self._resultado_atual = None
            self._algoritmo_resultado = None
            self.painel_resultados.limpar()

    def encerrar_passo_a_passo(
        self,
        preservar_resultado: bool = True,
        mensagem: str | None = None,
    ) -> None:
        """Encerra a sessão e remove apenas os destaques didáticos."""
        sessao = self._sessao_passos
        self._sessao_passos = None
        self.mapa_cidade.limpar_destaque_passo()
        self.visualizador_grafo.limpar_destaque_passo()
        self.cidade_3d.limpar_destaque_passo()
        self.painel_passos.limpar()
        if not (preservar_resultado and sessao is not None and sessao.finalizada):
            self._limpar_estado_rota()
        elif sessao is not None:
            self._resultado_atual = sessao.resultado
            self._algoritmo_resultado = sessao.algoritmo
            percurso = (
                sessao.resultado.percurso_completo
                if sessao.algoritmo == "tsp"
                else sessao.resultado.caminho
            )
            if percurso:
                self._destacar_percurso(percurso)
        self._atualizar_controles_calculo()
        if mensagem is not None:
            self.rotulo_aviso.setText(mensagem)

    def _encerrar_passo_a_passo(
        self, *, preservar_resultado: bool, mensagem: str | None = None
    ) -> None:
        self.encerrar_passo_a_passo(preservar_resultado, mensagem)

    def calcular_rota(self) -> None:
        """Executa o algoritmo selecionado e apresenta um único resultado."""
        if self._calculando or self._sessao_passos is not None:
            return
        self._limpar_estado_rota()
        self._calculando = True
        self._atualizar_controles_calculo()
        self.painel_resultados.exibir_calculando()
        self.rotulo_aviso.setText("Calculando…")
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

        try:
            if self.combo_algoritmo.currentData() == "tsp":
                clientes = self.clientes_selecionados()
                resultado = caixeiro_viajante(self._grafo, clientes)
                self._resultado_atual = resultado
                self._algoritmo_resultado = "tsp"
                self.painel_resultados.exibir_tsp(self._grafo, resultado)
                if resultado.encontrada:
                    self._destacar_percurso(resultado.percurso_completo)
                else:
                    self.mapa_cidade.limpar_destaque_rota()
                    self.visualizador_grafo.limpar_destaque_rota()
                    self.cidade_3d.limpar_destaque_rota()
                if resultado.encontrada:
                    self.rotulo_aviso.setText("Rota calculada.")
                elif resultado.clientes_inacessiveis:
                    inacessiveis = ", ".join(resultado.clientes_inacessiveis)
                    self.rotulo_aviso.setText(
                        f"Clientes inacessíveis: {inacessiveis}."
                    )
                else:
                    self.rotulo_aviso.setText("Não existe rota viável.")
            else:
                origem = self.combo_origem.currentData()
                destino = self.combo_destino.currentData()
                if not origem or not destino:
                    raise ValueError("Selecione uma origem e um destino válidos.")
                resultado = dijkstra(self._grafo, origem, destino)
                self._resultado_atual = resultado
                self._algoritmo_resultado = "dijkstra"
                self.painel_resultados.exibir_dijkstra(self._grafo, resultado)
                if resultado.encontrado:
                    self._destacar_percurso(resultado.caminho)
                else:
                    self.mapa_cidade.limpar_destaque_rota()
                    self.visualizador_grafo.limpar_destaque_rota()
                    self.cidade_3d.limpar_destaque_rota()
                self.rotulo_aviso.setText(
                    "Caminho calculado."
                    if resultado.encontrado
                    else "Destino inalcançável; nenhuma rota foi destacada."
                )
        except (KeyError, TypeError, ValueError) as erro:
            logger.info("Entrada inválida ao calcular rota: %s", erro)
            self._limpar_estado_rota()
            self.painel_resultados.exibir_erro(str(erro))
            self.rotulo_aviso.setText("Verifique os dados informados.")
        except Exception:
            logger.exception("Erro inesperado ao calcular rota")
            self._limpar_estado_rota()
            self.painel_resultados.exibir_erro(
                "Ocorreu um erro inesperado. Consulte os registros da aplicação."
            )
            self.rotulo_aviso.setText("Não foi possível concluir o cálculo.")
        finally:
            self._calculando = False
            self._atualizar_controles_calculo()

    def limpar_rota(self) -> None:
        """Remove o resultado e destaques, preservando o grafo e os campos."""
        if self._calculando:
            return
        if self._sessao_passos is not None:
            self.encerrar_passo_a_passo(preservar_resultado=False)
            self.rotulo_aviso.setText("Sessão passo a passo encerrada.")
            return
        self._limpar_estado_rota()
        self.rotulo_aviso.setText("Configure uma rota e clique em calcular.")

    def _percurso_resultado_atual(self) -> tuple[str, ...]:
        """Obtém o percurso já calculado sem executar novamente o algoritmo."""

        resultado = self._resultado_atual
        if resultado is None:
            return ()
        if self._algoritmo_resultado == "tsp":
            return tuple(resultado.percurso_completo)
        return tuple(resultado.caminho)

    def _iniciar_missao_3d(self) -> None:
        if self._calculando or self._sessao_passos is not None:
            return
        percurso = self._percurso_resultado_atual()
        if not percurso:
            self.rotulo_aviso.setText("Calcule uma rota válida antes de iniciar a missão 3D.")
            self._atualizar_botao_missao_3d()
            return
        if not self.cidade_3d.modelos_3d_prontos:
            self.rotulo_aviso.setText(
                f"Não foi possível iniciar a missão 3D: {self.cidade_3d.status_modelos_3d}."
            )
            self._atualizar_botao_missao_3d()
            return
        # A cena 3D deve ser criada com o ancestral já visível; caso contrário
        # o QQuickWidget recebe 0x0 durante a inicialização.
        self.definir_modo("cidade3d")
        QApplication.processEvents()
        if not self.cidade_3d.entrar_missao(percurso):
            self.rotulo_aviso.setText(
                "Não foi possível iniciar a missão 3D: rota ou mapeamento inválido."
            )
            self._atualizar_botao_missao_3d()
            return
        self.rotulo_aviso.setText(
            "Missão 3D pronta. Use Iniciar percurso para começar a entrega."
        )
        self._atualizar_botao_missao_3d()

    def _voltar_da_missao_3d(self) -> None:
        self.cidade_3d.sair_missao()
        self.definir_modo("cidade3d")
        self.rotulo_aviso.setText("Missão encerrada; planejamento preservado.")
        self._atualizar_botao_missao_3d()

    def _missao_3d_concluida(self) -> None:
        self.rotulo_aviso.setText(self.cidade_3d.resumo_missao or "Missão 3D concluída.")
        self._atualizar_botao_missao_3d()

    def _atualizar_botao_missao_3d(self) -> None:
        if not hasattr(self, "botao_iniciar_missao_3d"):
            return
        habilitado = (
            bool(self._percurso_resultado_atual())
            and not self._calculando
            and self.cidade_3d.modelos_3d_prontos
        )
        self.botao_iniciar_missao_3d.setEnabled(habilitado)
        self.botao_iniciar_missao_3d.setToolTip(
            "Abrir a simulação 3D em terceira pessoa para a rota calculada"
            if self.cidade_3d.modelos_3d_prontos
            else f"Modelos 3D indisponíveis: {self.cidade_3d.status_modelos_3d}"
        )
        self.botao_iniciar_missao_3d.setText(
            "Reiniciar missão 3D" if self.cidade_3d.em_missao else "Iniciar missão 3D"
        )

    def _configuracao_modelos_3d_alterada(self, configuracao) -> None:
        """Atualiza somente a cena; nenhum algoritmo é executado novamente."""

        try:
            pronto = self.cidade_3d.configurar_modelos_3d(configuracao)
        except (TypeError, ValueError) as erro:
            self.rotulo_aviso.setText(f"Configuração 3D inválida: {erro}")
            self._atualizar_botao_missao_3d()
            return
        if pronto:
            self.rotulo_aviso.setText(
                "Modelos 3D validados. A rota calculada permanece preservada."
            )
        else:
            self.rotulo_aviso.setText(
                f"Modelos 3D indisponíveis: {self.cidade_3d.status_modelos_3d}"
            )
        self._atualizar_botao_missao_3d()

    def _visualizar_modelos_3d(self) -> None:
        """Exibe o diagnóstico sem iniciar rota ou recalcular algoritmos."""

        if self.cidade_3d.modelos_3d_prontos:
            # O QQuickWidget só recebe o tamanho final quando o ancestral do
            # QStackedWidget está visível. Criá-lo antes desta troca inicializa
            # a raiz QML e o View3D em 0x0.
            self.definir_modo("cidade3d")
            QApplication.processEvents()
            if self.cidade_3d.backend_glb_disponivel:
                try:
                    self.cidade_3d.iniciar_renderizador_glb()
                except Exception as erro:  # pragma: no cover - backend gráfico
                    self.rotulo_aviso.setText(f"Falha ao abrir preview GLB: {erro}")
                    return
            backend = (
                "Qt Quick 3D/Panda3D disponível."
                if self.cidade_3d.backend_glb_disponivel
                else "Nenhum backend GLB real disponível; a simulação legada permanece disponível."
            )
            diagnostico = self.cidade_3d.diagnostico_renderizacao_3d
            self.rotulo_aviso.setText(
                f"{self.cidade_3d.info_cidade_glb.resumo} · "
                f"{self.cidade_3d.info_carro_glb.resumo} {backend} {diagnostico}"
            )
        else:
            self.rotulo_aviso.setText(
                f"Falha nos modelos 3D: {self.cidade_3d.status_modelos_3d}"
            )

    def _enquadrar_cidade_3d(self) -> None:
        """Reposiciona a câmera sem recalcular ou alterar a rota."""

        if (
            self.cidade_3d.renderizador_qtquick3d is None
            and self.cidade_3d.backend_glb_disponivel
            and self.cidade_3d.modelos_3d_prontos
        ):
            try:
                self.cidade_3d.iniciar_renderizador_glb()
            except Exception as erro:  # pragma: no cover - backend gráfico
                self.rotulo_aviso.setText(f"Falha ao preparar o enquadramento 3D: {erro}")
                return
        if self.cidade_3d.enquadrar_cidade():
            self.definir_modo("cidade3d")
            self.rotulo_aviso.setText("Câmera enquadrada pelos limites reais da cidade importada.")
        else:
            self.rotulo_aviso.setText("Não foi possível enquadrar: os limites da cidade não estão disponíveis.")

    def _calibrar_cidade_3d(self) -> None:
        """Abre o editor espacial sem recalcular a rota ou alterar o grafo."""

        if not self.cidade_3d.modelos_3d_prontos:
            self.rotulo_aviso.setText(
                f"Não foi possível calibrar: {self.cidade_3d.status_modelos_3d}"
            )
            return
        self.definir_modo("cidade3d")
        QApplication.processEvents()
        try:
            self.cidade_3d.iniciar_renderizador_glb()
            self.cidade_3d.abrir_calibracao_3d()
            self.rotulo_aviso.setText(
                "Calibração aberta: ajuste vértices e pontos de curva sem alterar as arestas."
            )
        except Exception as erro:  # pragma: no cover - backend gráfico opcional
            self.rotulo_aviso.setText(f"Falha ao abrir calibração 3D: {erro}")

    def selecionar_cidade_glb(self, caminho) -> None:
        """API programática equivalente ao botão de seleção da UI."""

        self.painel_modelos_3d.selecionar_cidade(caminho)

    def selecionar_carro_glb(self, caminho) -> None:
        """API programática equivalente ao botão de seleção da UI."""

        self.painel_modelos_3d.selecionar_carro(caminho)

    def restaurar_modelos_3d(self) -> None:
        self.painel_modelos_3d.restaurar_padrao()

    def _limpar_estado_rota(self) -> None:
        self._resultado_atual = None
        self._algoritmo_resultado = None
        if hasattr(self, "mapa_cidade"):
            self.mapa_cidade.limpar_destaque_rota()
            self.visualizador_grafo.limpar_destaque_rota()
            if self.cidade_3d.em_missao:
                self.cidade_3d.sair_missao()
            self.cidade_3d.limpar_destaque_rota()
            self._atualizar_titulo_visualizacao()
        if hasattr(self, "painel_resultados"):
            self.painel_resultados.limpar()
        self._atualizar_botao_missao_3d()

    def _destacar_percurso(self, percurso: list[str]) -> None:
        self.mapa_cidade.destacar_rota(percurso)
        self.visualizador_grafo.destacar_rota(percurso)
        self.cidade_3d.destacar_rota(percurso)
        self._atualizar_botao_missao_3d()

    def _atualizar_controles_calculo(self) -> None:
        habilitado = not self._calculando and self._sessao_passos is None
        self.combo_algoritmo.setEnabled(habilitado)
        self.combo_origem.setEnabled(habilitado)
        self.combo_destino.setEnabled(habilitado)
        self.lista_clientes_rota.setEnabled(habilitado)
        self.botao_calcular.setEnabled(habilitado)
        self._atualizar_modo_interface()
        self._atualizar_botao_missao_3d()
        if hasattr(self, "painel_passos"):
            self.painel_passos.bloquear_inicio(not habilitado)

    def closeEvent(self, evento: QCloseEvent) -> None:  # noqa: N802 - contrato Qt
        if self._confirmar_alteracoes_pendentes():
            if hasattr(self, "cidade_3d"):
                self.cidade_3d.sair_missao()
            evento.accept()
        else:
            evento.ignore()

    def _atualizar_dados_interface(self) -> None:
        self.lista_locais.clear()
        self.combo_origem.clear()
        self.combo_destino.clear()
        self.lista_clientes_rota.clear()

        siglas = {
            TipoVertice.DEPOSITO: "DEP",
            TipoVertice.CLIENTE: "CLI",
            TipoVertice.CRUZAMENTO: "CRZ",
        }
        vertices = self._grafo.listar_vertices()
        for vertice in vertices:
            item = QListWidgetItem(f"[{siglas[vertice.tipo]}]  {vertice.nome}")
            item.setData(Qt.ItemDataRole.UserRole, vertice.identificador)
            self.lista_locais.addItem(item)
            texto_combo = f"{vertice.identificador} — {vertice.nome}"
            self.combo_origem.addItem(texto_combo, vertice.identificador)
            self.combo_destino.addItem(texto_combo, vertice.identificador)

        deposito = self._grafo.obter_deposito()
        if deposito is not None:
            self.rotulo_deposito_tsp.setText(
                f"{deposito.nome} ({deposito.identificador})"
            )
            indice_origem = self.combo_origem.findData(deposito.identificador)
            if indice_origem >= 0:
                self.combo_origem.setCurrentIndex(indice_origem)
        else:
            self.rotulo_deposito_tsp.setText("Nenhum depósito definido")

        clientes = self._grafo.listar_clientes()
        for cliente in clientes:
            item = QListWidgetItem(cliente.nome)
            item.setData(Qt.ItemDataRole.UserRole, cliente.identificador)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.lista_clientes_rota.addItem(item)

        if clientes:
            indice_destino = self.combo_destino.findData(clientes[0].identificador)
        elif len(vertices) > 1:
            indice_destino = 1
        else:
            indice_destino = 0
        if indice_destino >= 0:
            self.combo_destino.setCurrentIndex(indice_destino)
        self._algoritmo_alterado(self.combo_algoritmo.currentIndex())
