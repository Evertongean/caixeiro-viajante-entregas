"""Janela principal nova, sem dependências da interface descartada."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
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

from models.grafo import TipoVertice, criar_cenario_exemplo
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
    ProjetoCidade,
    carregar_projeto_cidade,
    salvar_projeto_cidade,
)
from models.rota import (
    AlgoritmoRota,
    EstadoEspacial,
    RotaCalculada,
    RotaInacessivel,
    calcular_dijkstra,
    calcular_tsp,
)

from .assets_3d import ConversorBalsam
from .animacao_missao import AnimacaoMissao
from .dialogos_editor import DialogoRua, DialogoSuperficie, DialogoVertice
from .editor_cidade import EditorCidade3D, ModoEditor
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
        self.valor.setToolTip(texto)


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
        self.setMinimumSize(900, 600)
        self.resize(1440, 900)
        self.setStyleSheet(FOLHA_ESTILOS)
        self._primeira_exibicao = True
        self._editor_inicializado = False
        self.projeto = ProjetoCidade(grafo=criar_cenario_exemplo())
        self.editor = EditorCidade3D(self.projeto)
        self.grafo = self.projeto.grafo
        self.caminho_projeto: Path | None = None
        self.projeto_modificado = False
        self.rota_calculada: RotaCalculada | None = None
        self._calculando_rota = False
        self._atualizando_campos_rota = False
        self.controlador_missao: ControladorMissao | None = None
        self.animacao_missao: AnimacaoMissao | None = None
        self._sessao_missao_ativa = False
        self._chave_visual_missao: tuple[object, ...] | None = None
        self._assinatura_campos_grafo: (
            tuple[tuple[str, str, str], ...] | None
        ) = None
        self._colunas_cartoes = 0

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
        self._atualizar_controles_missao()

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
        painel.setMinimumWidth(280)
        painel.setMaximumWidth(440)
        layout = _layout_sem_margem(painel)
        topo = QLabel("Controles")
        topo.setObjectName("tituloSecao")
        topo.setContentsMargins(16, 16, 16, 2)
        layout.addWidget(topo)

        self.rolagem_controles = QScrollArea()
        self.rolagem_controles.setWidgetResizable(True)
        self.rolagem_controles.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        conteudo = QWidget()
        grupos = QVBoxLayout(conteudo)
        grupos.setContentsMargins(12, 4, 12, 14)
        grupos.setSpacing(10)
        grupos.addWidget(self._grupo_edicao())
        grupos.addWidget(self._grupo_rota())
        grupos.addWidget(self._grupo_missao())
        grupos.addStretch(1)
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
        self.botao_classificar = QPushButton("Classificar superfície")
        self.botoes_edicao = [
            self.botao_navegar,
            self.botao_adicionar_ponto,
            self.botao_adicionar_cliente,
            self.botao_definir_deposito,
            self.botao_criar_rua,
            self.botao_classificar,
        ]
        self.grupo_ferramentas = QButtonGroup(self)
        self.grupo_ferramentas.setExclusive(True)
        for botao in self.botoes_edicao:
            botao.setCheckable(True)
            self.grupo_ferramentas.addButton(botao)
            botao.setEnabled(False)
            layout.addWidget(botao)

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

        operacao = QGridLayout()
        self.botao_confirmar_edicao = QPushButton("Confirmar")
        self.botao_confirmar_edicao.setObjectName("botaoMissao")
        self.botao_desfazer_edicao = QPushButton("Desfazer")
        self.botao_cancelar_edicao = QPushButton("Cancelar")
        for indice, botao in enumerate(
            (self.botao_confirmar_edicao, self.botao_desfazer_edicao)
        ):
            botao.setEnabled(False)
            operacao.addWidget(botao, 0, indice)
        self.botao_cancelar_edicao.setEnabled(False)
        operacao.addWidget(self.botao_cancelar_edicao, 1, 0, 1, 2)
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
        self.botao_abrir_projeto = QPushButton("Abrir")
        self.botao_salvar_projeto = QPushButton("Salvar")
        arquivos.addWidget(self.botao_abrir_projeto)
        arquivos.addWidget(self.botao_salvar_projeto)
        layout.addLayout(arquivos)

        self.botao_navegar.clicked.connect(self._modo_navegar)
        self.botao_adicionar_ponto.clicked.connect(
            lambda: self._ativar_adicao(None)
        )
        self.botao_adicionar_cliente.clicked.connect(
            lambda: self._ativar_adicao(TipoVertice.CLIENTE)
        )
        self.botao_definir_deposito.clicked.connect(
            lambda: self._ativar_adicao(TipoVertice.DEPOSITO)
        )
        self.botao_criar_rua.clicked.connect(self._ativar_criacao_rua)
        self.botao_classificar.clicked.connect(self._ativar_classificacao)
        self.botao_confirmar_edicao.clicked.connect(self._confirmar_operacao)
        self.botao_desfazer_edicao.clicked.connect(self._desfazer_operacao)
        self.botao_cancelar_edicao.clicked.connect(self._cancelar_operacao)
        self.botao_editar_selecao.clicked.connect(self._editar_selecao)
        self.botao_reposicionar.clicked.connect(self._reposicionar_selecao)
        self.botao_excluir_selecao.clicked.connect(self._excluir_selecao)
        self.botao_abrir_projeto.clicked.connect(lambda: self.abrir_projeto())
        self.botao_salvar_projeto.clicked.connect(lambda: self.salvar_projeto())
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
        campos_dijkstra.addWidget(QLabel("Origem"))
        campos_dijkstra.addWidget(self.origem)
        campos_dijkstra.addWidget(QLabel("Destino"))
        campos_dijkstra.addWidget(self.destino)

        pagina_tsp = QWidget()
        campos_tsp = QVBoxLayout(pagina_tsp)
        campos_tsp.setContentsMargins(0, 0, 0, 0)
        self.deposito_tsp = QLabel()
        self.deposito_tsp.setObjectName("depositoTsp")
        deposito = self.grafo.obter_deposito()
        self.deposito_tsp.setText(
            f"{deposito.identificador} — {deposito.nome}"
            if deposito is not None
            else "Nenhum depósito cadastrado"
        )
        campos_tsp.addWidget(QLabel("Depósito"))
        campos_tsp.addWidget(self.deposito_tsp)
        self.selecionar_todos_clientes = QCheckBox("Selecionar todos")
        self.selecionar_todos_clientes.setTristate(True)
        self.selecionar_todos_clientes.setChecked(True)
        campos_tsp.addWidget(self.selecionar_todos_clientes)
        campos_tsp.addWidget(QLabel("Clientes"))
        self.lista_clientes = QListWidget()
        self.lista_clientes.setMaximumHeight(108)
        for cliente in self.grafo.listar_clientes():
            item = QListWidgetItem(f"{cliente.identificador} — {cliente.nome}")
            item.setData(Qt.ItemDataRole.UserRole, cliente.identificador)
            item.setCheckState(Qt.CheckState.Checked)
            self.lista_clientes.addItem(item)
        campos_tsp.addWidget(self.lista_clientes)
        self.quantidade_clientes = QLabel()
        self.quantidade_clientes.setObjectName("quantidadeClientes")
        campos_tsp.addWidget(self.quantidade_clientes)
        self.campos_algoritmo.addWidget(pagina_dijkstra)
        self.campos_algoritmo.addWidget(pagina_tsp)
        layout.addWidget(self.campos_algoritmo)
        self.botao_calcular = QPushButton("Calcular menor caminho")
        self.botao_calcular.setObjectName("botaoPrimario")
        layout.addWidget(self.botao_calcular)
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
        self.selecionar_todos_clientes.toggled.connect(
            self._selecionar_todos_clientes
        )
        self.botao_calcular.clicked.connect(self._calcular_rota)
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
        for texto, valor in (("0,5x", 0.5), ("1x", 1.0), ("2x", 2.0), ("4x", 4.0)):
            self.seletor_velocidade.addItem(texto, valor)
        self.seletor_velocidade.setCurrentIndex(1)
        velocidade.addWidget(self.seletor_velocidade, 1)
        layout.addLayout(velocidade)

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
        layout.addWidget(self.resumo_missao)
        self.botao_iniciar.clicked.connect(self._iniciar_missao)
        self.botao_pausar.clicked.connect(self._pausar_missao)
        self.botao_continuar.clicked.connect(self._continuar_missao)
        self.botao_reiniciar.clicked.connect(self._reiniciar_missao)
        self.botao_encerrar.clicked.connect(self._encerrar_missao)
        self.seletor_velocidade.currentIndexChanged.connect(
            self._velocidade_missao_alterada
        )
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
        if not rota.segmentos_espaciais:
            return False, "A rota é trivial e não possui um trajeto para animar."
        if not rota.calibracao_completa:
            return False, self._texto_ruas_pendentes(rota.arestas_pendentes)
        if not self.visualizacao.modelos_preparados:
            return False, "Aguarde o carregamento do carro e da cidade 3D."
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
            self.origem,
            self.destino,
            self.lista_clientes,
            self.selecionar_todos_clientes,
            self.botao_calcular,
            self.botao_limpar_rota,
        )
        for controle in controles_rota:
            controle.setEnabled(not bloqueado)
        self.botao_abrir_projeto.setEnabled(not bloqueado)
        if bloqueado:
            self._modo_navegar()
            for botao in self.botoes_edicao:
                botao.setEnabled(False)
            for botao in (
                self.botao_confirmar_edicao,
                self.botao_desfazer_edicao,
                self.botao_cancelar_edicao,
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
            controlador = ControladorMissao(self.rota_calculada)
            controlador.multiplicador_velocidade = float(
                self.seletor_velocidade.currentData()
            )
        except (ErroMissao, TypeError, ValueError) as erro:
            self._mostrar_erro(str(erro))
            return
        self.controlador_missao = controlador
        self.animacao_missao = AnimacaoMissao(controlador, self)
        self.animacao_missao.quadro_atualizado.connect(
            self._atualizar_quadro_missao
        )
        self.animacao_missao.concluida.connect(self._missao_concluida)
        self._chave_visual_missao = None
        self.resumo_missao.setText("Missão em andamento.")
        self._definir_bloqueio_missao(True)
        self._configurar_camera_missao()
        self.visualizacao.camera_atras_do_carro()
        self.animacao_missao.iniciar()
        self._atualizar_controles_missao()

    def _pausar_missao(self) -> None:
        if self.animacao_missao is None:
            return
        try:
            self.animacao_missao.pausar()
        except ErroMissao:
            return
        self._atualizar_controles_missao()

    def _continuar_missao(self) -> None:
        if self.animacao_missao is None:
            return
        try:
            self.animacao_missao.continuar()
        except ErroMissao:
            return
        self._atualizar_controles_missao()

    def _reiniciar_missao(self) -> None:
        if self.animacao_missao is None:
            return
        try:
            self._chave_visual_missao = None
            self.resumo_missao.setText("Missão reiniciada.")
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
        self.animacao_missao = None
        self.controlador_missao = None
        self._chave_visual_missao = None
        self._definir_bloqueio_missao(False)
        if self.rota_calculada is not None:
            self._apresentar_rota(self.rota_calculada)
        if resumo is not None:
            self.resumo_missao.setText(self._texto_resumo_missao(resumo))
        self.cartao_status.definir("Missão encerrada; edição liberada.")

    def _velocidade_missao_alterada(self, _indice: int = -1) -> None:
        if self.controlador_missao is not None:
            self.controlador_missao.multiplicador_velocidade = float(
                self.seletor_velocidade.currentData()
            )

    def _configurar_camera_missao(self, *_args) -> None:
        self.visualizacao.configurar_camera_seguidora(
            self.distancia_camera.value(), self.altura_camera.value()
        )

    def _atualizar_quadro_missao(
        self, quadro: QuadroMissao, delta_segundos: float
    ) -> None:
        self.visualizacao.atualizar_carro(
            quadro.posicao,
            quadro.orientacao_graus,
            delta_segundos,
            imediato=delta_segundos == 0.0,
        )
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
            f"{rota.distancia_total:g} km · {quadro.distancia_percorrida:.2f} perc. · "
            f"{quadro.distancia_restante:.2f} rest."
        )
        self.cartao_percurso.definir(
            f"{' → '.join(rota.percurso_completo)} · atual: "
            f"{quadro.origem_aresta} → {quadro.destino_aresta} "
            f"({quadro.indice_aresta + 1}/{len(rota.segmentos_espaciais)})"
        )
        self.cartao_clientes.definir(
            f"{len(quadro.clientes_atendidos)} / {quadro.total_clientes}"
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
                status = "Em deslocamento."
        for evento in quadro.eventos:
            if evento.tipo is TipoEventoMissao.ENTREGA:
                status = f"Entrega em {evento.vertice} confirmada."
        self.cartao_status.definir(status)
        self._atualizar_controles_missao()

    def _missao_concluida(self, resumo: ResumoMissao) -> None:
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
            f"{alvo} · distância: {resumo.distancia_percorrida:.2f}/"
            f"{resumo.distancia_total:g} km · entregas: {resumo.clientes_atendidos}/"
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
        self._atualizar_disponibilidade_calculo()

    def _entrada_rota_alterada(self, *_args) -> None:
        if self._atualizando_campos_rota:
            return
        if self.rota_calculada is not None:
            self.limpar_rota(status="Parâmetros alterados. Calcule novamente.")

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
        estado = Qt.CheckState.Checked if marcado else Qt.CheckState.Unchecked
        for indice in range(self.lista_clientes.count()):
            self.lista_clientes.item(indice).setCheckState(estado)
        self._atualizando_campos_rota = False
        self._atualizar_resumo_clientes()
        self._entrada_rota_alterada()

    def _clientes_alterados(self, _item: QListWidgetItem) -> None:
        if self._atualizando_campos_rota:
            return
        self._atualizar_resumo_clientes()
        self._entrada_rota_alterada()

    def _atualizar_resumo_clientes(self) -> None:
        total = self.lista_clientes.count()
        selecionados = len(self._clientes_selecionados())
        self.quantidade_clientes.setText(
            f"{selecionados} de {total} clientes selecionados"
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

    def _calcular_rota(self) -> None:
        if self._calculando_rota or self._sessao_missao_ativa:
            return
        self._calculando_rota = True
        self.botao_calcular.setEnabled(False)
        self.cartao_status.definir("Calculando rota…")
        QApplication.processEvents()
        try:
            algoritmo = self.seletor_algoritmo.currentData()
            if algoritmo == AlgoritmoRota.DIJKSTRA.value:
                origem, destino = self.origem.currentData(), self.destino.currentData()
                if origem is None or destino is None:
                    raise ValueError("Selecione uma origem e um destino válidos.")
                rota = calcular_dijkstra(self.projeto, str(origem), str(destino))
            elif algoritmo == AlgoritmoRota.TSP.value:
                clientes = self._clientes_selecionados()
                if not clientes:
                    raise ValueError(
                        "Selecione pelo menos um cliente para calcular a rota TSP."
                    )
                rota = calcular_tsp(self.projeto, clientes)
            else:
                raise ValueError("Selecione um algoritmo de rota válido.")
        except (KeyError, TypeError, ValueError) as erro:
            self.rota_calculada = None
            self.visualizacao.limpar_destaque_rota()
            self.cartao_distancia.definir("—")
            self.cartao_percurso.definir("Nenhuma rota disponível")
            self.cartao_clientes.definir("0 / 0")
            self.resultado_ordem.setText("")
            self.resultado_percurso.setText("")
            self.resultado_clientes.setText("")
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
        else:
            self._apresentar_rota(rota)
        finally:
            self._calculando_rota = False
            self._atualizar_disponibilidade_calculo()

    def _apresentar_rota(self, rota: RotaCalculada) -> None:
        self.rota_calculada = rota
        percurso = " → ".join(rota.percurso_completo)
        self.cartao_distancia.definir(f"{rota.distancia_total:g} km")
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
        if rota.estado_espacial is EstadoEspacial.COMPLETO:
            self.resultado_calibracao.setText(
                "Todos os trechos possuem traçado espacial confirmado manualmente."
            )
            self.cartao_status.definir("Rota pronta para missão 3D.")
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
        self.resultado_calibracao.setText(status)
        self.botao_limpar_rota.setEnabled(False)
        self.botao_enquadrar_rota.setEnabled(False)
        self.resumo_missao.setText("Calcule e calibre uma rota para iniciar.")
        self._atualizar_controles_missao()

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
            disponivel = self.origem.count() > 0 and self.destino.count() > 0
            motivo = (
                "Selecione uma origem e um destino."
                if not disponivel
                else "Calcula o menor caminho entre os pontos selecionados."
            )
        else:
            disponivel = self.grafo.obter_deposito() is not None
            motivo = (
                "Cadastre um depósito antes de calcular a rota TSP."
                if not disponivel
                else "Selecione ao menos um cliente e calcule a rota de entregas."
            )
        self.botao_calcular.setToolTip(motivo)
        self.botao_calcular.setEnabled(
            disponivel and not self._calculando_rota and not self._sessao_missao_ativa
        )

    def _definir_instrucao(self, texto: str) -> None:
        self.instrucao_editor.setText(texto)

    def _marcar_ferramenta(self, botao: QPushButton, nome: str) -> None:
        botao.setChecked(True)
        self.estado_ferramenta.setText(f"Ferramenta ativa: {nome}")

    def _modo_navegar(self) -> None:
        self.editor.definir_modo(ModoEditor.NAVEGAR)
        self.visualizacao.definir_modo_interacao(ModoEditor.NAVEGAR.value)
        self.visualizacao.mostrar_marcador_temporario(None)
        self.visualizacao.atualizar_previa_rua([])
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
            "Clique sobre uma superfície previamente classificada como rua para "
            f"adicionar {descricao}. Cancelar volta à navegação."
        )
        self._atualizar_botoes_operacao()

    def _ativar_criacao_rua(self) -> None:
        self.editor.iniciar_rua()
        self.visualizacao.definir_modo_interacao(ModoEditor.CRIAR_RUA.value)
        self._marcar_ferramenta(self.botao_criar_rua, "Criar rua")
        self._definir_instrucao(
            "Selecione o ponto inicial e o final. Depois clique no asfalto para traçar "
            "curvas; Desfazer remove a última etapa e Cancelar abandona a operação."
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
        self._modo_navegar()

    def _atualizar_botoes_operacao(self) -> None:
        if self._sessao_missao_ativa:
            for botao in (
                self.botao_confirmar_edicao,
                self.botao_desfazer_edicao,
                self.botao_cancelar_edicao,
            ):
                botao.setEnabled(False)
            return
        operacao = self.editor.operacao_rua
        criando_rua = self.editor.modo is ModoEditor.CRIAR_RUA
        self.botao_confirmar_edicao.setEnabled(
            criando_rua
            and operacao.origem is not None
            and operacao.destino is not None
        )
        self.botao_desfazer_edicao.setEnabled(
            criando_rua
            and (
                operacao.origem is not None
                or operacao.destino is not None
                or bool(operacao.pontos_intermediarios)
            )
        )
        self.botao_cancelar_edicao.setEnabled(
            self.editor.modo is not ModoEditor.NAVEGAR
        )

    def _sincronizar_cena(self) -> None:
        self.visualizacao.atualizar_marcadores(self.editor.marcadores_qml())
        self.visualizacao.atualizar_ruas(self.editor.segmentos_ruas_qml())
        self.visualizacao.atualizar_previa_rua(
            self.editor.segmentos_previa_qml()
        )
        if self.rota_calculada is not None:
            self.visualizacao.atualizar_destaque_rota(
                segmentos_rota_qml(self.rota_calculada),
                marcadores_rota_qml(self.rota_calculada, self.projeto),
            )
        self._atualizar_campos_grafo()
        calibradas = sum(
            geometria.calibrada_manualmente
            and len(self.projeto.polilinha_rua(*chave)) >= 2
            for chave, geometria in self.projeto.ruas.items()
        )
        total_conexoes = len(self.grafo.listar_arestas())
        total_tracadas = len(self.projeto.ruas)
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
        for cliente in self.grafo.listar_clientes():
            item = QListWidgetItem(f"{cliente.identificador} — {cliente.nome}")
            item.setData(Qt.ItemDataRole.UserRole, cliente.identificador)
            selecionado = (
                cliente.identificador in clientes_selecionados
                or cliente.identificador not in clientes_anteriores
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
            self._definir_instrucao(
                "Nenhuma geometria foi atingida. Tente novamente sobre a cidade."
            )
            return
        posicao = (x, y, z)
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
            elif self.editor.operacao_rua.editando_aresta is not None:
                self._definir_instrucao(
                    "A conexão já existe no grafo. Adicione curvas ou confirme "
                    "para calibrar seu traçado e peso."
                )
            else:
                self._definir_instrucao(
                    "Adicione curvas clicando no asfalto ou confirme a conexão."
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
        self._definir_instrucao(
            f"Rua {origem} ↔ {destino} selecionada · peso oficial {peso:g} km."
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
            ModoEditor.REPOSICIONAR_VERTICE,
        }:
            self.editor.selecao = None
            self._sincronizar_cena()
            self._atualizar_botoes_selecao()
            return

        try:
            self.editor.validar_superficie_trafegavel(referencia)
        except ValueError as erro:
            self._definir_instrucao(
                f"Clique rejeitado: {erro}"
            )
            return

        if modo is ModoEditor.REPOSICIONAR_VERTICE:
            identificador = self.editor.vertice_reposicionado
            if identificador is None:
                return
            try:
                self.editor.reposicionar_vertice(identificador, posicao)
            except (TypeError, ValueError, KeyError) as erro:
                self._mostrar_erro(str(erro))
                return
            self._invalidar_rota_por_edicao()
            self._sincronizar_cena()
            self._modo_navegar()
            self._definir_instrucao(f"Ponto {identificador} reposicionado.")
            return

        if modo is ModoEditor.ADICIONAR_PONTO:
            self._criar_vertice_no_ponto(posicao, self.editor.tipo_sugerido)
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
        self._sincronizar_cena()
        self._definir_instrucao(
            f"Ponto {identificador} criado e associado ao grafo oficial."
        )
        if not permanecer_no_modo:
            self._modo_navegar()
        return identificador

    def _confirmar_operacao(self) -> None:
        if self.editor.modo is not ModoEditor.CRIAR_RUA:
            return
        operacao = self.editor.operacao_rua
        if operacao.origem is None or operacao.destino is None:
            return
        comprimento = self.editor.comprimento_operacao_rua()
        peso_atual = None
        if operacao.editando_aresta is not None:
            peso_atual = self.grafo.obter_distancia(
                operacao.origem, operacao.destino
            )
        dialogo = DialogoRua(
            operacao.origem,
            operacao.destino,
            comprimento,
            self.projeto.fator_km_por_unidade,
            self,
            peso_atual=peso_atual,
        )
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        peso, fator = dialogo.dados()
        try:
            self.editor.confirmar_rua(peso, fator)
        except (TypeError, ValueError, KeyError) as erro:
            self._mostrar_erro(str(erro))
            return
        self._invalidar_rota_por_edicao()
        self._sincronizar_cena()
        self._modo_navegar()
        self._definir_instrucao("Rua criada com sucesso.")

    def _desfazer_operacao(self) -> None:
        if self.editor.modo is ModoEditor.CRIAR_RUA:
            removido = self.editor.desfazer_ponto_rua()
            if removido is not None:
                self._definir_instrucao(f"Último {removido.replace('_', ' ')} removido.")
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
                self.editor.editar_vertice(identificador, nome=nome, tipo=tipo)
            except (TypeError, ValueError, KeyError) as erro:
                self._mostrar_erro(str(erro))
                return
            self._invalidar_rota_por_edicao()
            self._sincronizar_cena()
            self._definir_instrucao(f"Ponto {identificador} atualizado.")
            return
        origem, destino = selecao[1], selecao[2]
        self.editor.iniciar_rua(origem, destino, editar=True)
        self.visualizacao.definir_modo_interacao(ModoEditor.CRIAR_RUA.value)
        self._marcar_ferramenta(self.botao_criar_rua, "Editar rua")
        self._definir_instrucao(
            "Edite o traçado: adicione curvas, desfaça pontos ou confirme para alterar o peso."
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
        self._assinatura_campos_grafo = None
        self.caminho_projeto = Path(caminho)
        self.limpar_rota(status="Projeto carregado. Calcule uma nova rota.")
        self._atualizando_campos_rota = True
        self.lista_clientes.clear()
        self._atualizando_campos_rota = False
        self._inicializar_posicoes_legadas()
        self._sincronizar_cena()
        self._modo_navegar()
        self._definir_projeto_modificado(False)
        self._definir_instrucao(f"Projeto {self.caminho_projeto.name} carregado.")
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
            "◎", "Clientes atendidos", "0", "valorClientes"
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
                self._modo_navegar()
                if self.rota_calculada is None:
                    self.limpar_rota()
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
        if self.animacao_missao is not None:
            self.animacao_missao.timer.stop()
            if self.controlador_missao is not None:
                self.controlador_missao.encerrar()
            self.animacao_missao.deleteLater()
        self.animacao_missao = None
        self.controlador_missao = None
        self._sessao_missao_ativa = False
        evento.accept()


__all__ = ["CartaoInformacao", "JanelaPrincipal"]
