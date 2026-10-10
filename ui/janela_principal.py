"""Janela principal nova, sem dependências da interface descartada."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
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
from models.persistencia import ErroPersistencia
from models.projeto_cidade import (
    ProjetoCidade,
    carregar_projeto_cidade,
    salvar_projeto_cidade,
)

from .assets_3d import ConversorBalsam
from .dialogos_editor import DialogoRua, DialogoSuperficie, DialogoVertice
from .editor_cidade import EditorCidade3D, ModoEditor
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
        self._editor_inicializado = False
        self.projeto = ProjetoCidade(grafo=criar_cenario_exemplo())
        self.editor = EditorCidade3D(self.projeto)
        self.grafo = self.projeto.grafo
        self.caminho_projeto: Path | None = None

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
        self.visualizacao.ponto_selecionado.connect(self._processar_pick)

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
        for botao in self.botoes_edicao:
            botao.setEnabled(False)
            layout.addWidget(botao)

        self.instrucao_editor = QLabel("Aguarde o carregamento da cidade 3D.")
        self.instrucao_editor.setObjectName("instrucaoEditor")
        self.instrucao_editor.setWordWrap(True)
        layout.addWidget(self.instrucao_editor)

        operacao = QHBoxLayout()
        self.botao_confirmar_edicao = QPushButton("Confirmar")
        self.botao_confirmar_edicao.setObjectName("botaoMissao")
        self.botao_desfazer_edicao = QPushButton("Desfazer")
        self.botao_cancelar_edicao = QPushButton("Cancelar")
        for botao in (
            self.botao_confirmar_edicao,
            self.botao_desfazer_edicao,
            self.botao_cancelar_edicao,
        ):
            botao.setEnabled(False)
            operacao.addWidget(botao)
        layout.addLayout(operacao)

        selecao = QHBoxLayout()
        self.botao_editar_selecao = QPushButton("Editar")
        self.botao_reposicionar = QPushButton("Reposicionar")
        self.botao_excluir_selecao = QPushButton("Excluir")
        for botao in (
            self.botao_editar_selecao,
            self.botao_reposicionar,
            self.botao_excluir_selecao,
        ):
            botao.setEnabled(False)
            selecao.addWidget(botao)
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

    def _definir_instrucao(self, texto: str) -> None:
        self.instrucao_editor.setText(texto)
        self.cartao_status.definir(texto)

    def _modo_navegar(self) -> None:
        self.editor.definir_modo(ModoEditor.NAVEGAR)
        self.visualizacao.definir_modo_interacao(ModoEditor.NAVEGAR.value)
        self.visualizacao.mostrar_marcador_temporario(None)
        self.visualizacao.atualizar_previa_rua([])
        self._definir_instrucao(
            "Navegação ativa. Clique em um marcador ou rua para selecioná-lo."
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
        self._definir_instrucao(
            f"Selecione sobre uma superfície classificada como rua para adicionar {descricao}."
        )
        self._atualizar_botoes_operacao()

    def _ativar_criacao_rua(self) -> None:
        self.editor.iniciar_rua()
        self.visualizacao.definir_modo_interacao(ModoEditor.CRIAR_RUA.value)
        self._definir_instrucao(
            "Selecione o ponto inicial da rua ou clique no asfalto para criá-lo."
        )
        self._sincronizar_cena()
        self._atualizar_botoes_operacao()

    def _ativar_classificacao(self) -> None:
        self.editor.definir_modo(ModoEditor.CLASSIFICAR_SUPERFICIE)
        self.visualizacao.definir_modo_interacao(
            ModoEditor.CLASSIFICAR_SUPERFICIE.value
        )
        self._definir_instrucao(
            "Clique em uma malha para classificá-la como rua, calçada ou área bloqueada."
        )
        self._atualizar_botoes_operacao()

    def _cancelar_operacao(self) -> None:
        self._modo_navegar()

    def _atualizar_botoes_operacao(self) -> None:
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
        self._atualizar_campos_grafo()

    def _atualizar_campos_grafo(self) -> None:
        origem_atual = self.origem.currentData() if self.origem.count() else None
        destino_atual = self.destino.currentData() if self.destino.count() else None
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
            item.setCheckState(Qt.CheckState.Checked)
            self.lista_clientes.addItem(item)

    def _processar_pick(
        self,
        x: float,
        y: float,
        z: float,
        objeto: str,
        material: str,
        encontrado: bool,
    ) -> None:
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
                self.editor.classificar_superficie(referencia, dialogo.valor())
                self._definir_instrucao(
                    f"Superfície classificada como {dialogo.valor().value}."
                )
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
            self._sincronizar_cena()
            self._definir_instrucao(f"Ponto {identificador} atualizado.")
            return
        origem, destino = selecao[1], selecao[2]
        self.editor.iniciar_rua(origem, destino, editar=True)
        self.visualizacao.definir_modo_interacao(ModoEditor.CRIAR_RUA.value)
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
        self._definir_instrucao(f"Projeto salvo em {self.caminho_projeto.name}.")
        return True

    def abrir_projeto(self, caminho: str | Path | None = None) -> bool:
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
        self.caminho_projeto = Path(caminho)
        self._inicializar_posicoes_legadas()
        self._sincronizar_cena()
        self._modo_navegar()
        self._definir_instrucao(f"Projeto {self.caminho_projeto.name} carregado.")
        return True

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
            for botao in self.botoes_edicao:
                botao.setEnabled(True)
            if not self._editor_inicializado:
                self._editor_inicializado = True
                self._inicializar_posicoes_legadas()
                self._sincronizar_cena()
                self._modo_navegar()

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
