"""Janela principal enxuta do Delivery Route, exclusivamente 3D.

Esta tela é uma composição fina: ``Grafo``, Dijkstra, TSP, persistência e o
renderizador continuam nos módulos existentes. A janela apenas coordena os
três fluxos pedidos pelo usuário (editar cidade, calcular rota e missão).
``JanelaPrincipal`` permanece disponível para compatibilidade com projetos e
testes legados; o ponto de entrada da aplicação usa esta versão 3D.
"""

from __future__ import annotations

from math import dist
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QDoubleSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from algorithms.caixeiro_viajante import ResultadoCaixeiroViajante, caixeiro_viajante
from algorithms.dijkstra import ResultadoDijkstra, dijkstra
from models.grafo import Grafo, TipoVertice, Vertice, criar_cenario_exemplo
from models.persistencia import ErroPersistencia, carregar_grafo
from models.projeto_3d import carregar_projeto_3d, projeto_3d_para_dados, salvar_projeto_3d

from .cidade_3d import Cidade3DWidget
from .editor_ruas_3d import EditorRuas3D, ModoEdicaoRua
from .estilos import ESTILO_APLICACAO
from .modelos_glb import ConfiguracaoModelos3D
from .painel_resultados import PainelResultados


class JanelaPrincipal3D(QMainWindow):
    """Aplicação final: a cidade GLB ocupa o centro e o painel é contextual."""

    def __init__(self, grafo: Grafo | None = None) -> None:
        super().__init__()
        self._grafo = grafo if grafo is not None else criar_cenario_exemplo()
        self._resultado_atual: ResultadoDijkstra | ResultadoCaixeiroViajante | None = None
        self._algoritmo_resultado: str | None = None
        self._calculando = False
        self._caminho_projeto: Path | None = None
        self._modo_ponto: TipoVertice | None = None
        self._esperando_curva = False
        self._objeto_hit_atual = ""
        self._editor_ruas = EditorRuas3D()
        self._rota_pendente: tuple[str, ...] = ()

        self.setObjectName("janelaPrincipal3D")
        self.setWindowTitle("Delivery Route — Cidade 3D")
        self.resize(1440, 900)
        self.setMinimumSize(980, 640)
        self.setStyleSheet(ESTILO_APLICACAO)
        self._construir_interface()
        self._atualizar_dados()
        QTimer.singleShot(0, self._inicializar_cena)

    @property
    def grafo(self) -> Grafo:
        return self._grafo

    @property
    def cidade_3d(self) -> Cidade3DWidget:
        return self._cidade_3d

    @property
    def resultado_atual(self):
        return self._resultado_atual

    @property
    def editor_ruas(self) -> EditorRuas3D:
        return self._editor_ruas

    @property
    def modo_atual(self) -> str:
        return "cidade3d"

    def _construir_interface(self) -> None:
        raiz = QWidget()
        raiz.setObjectName("raizCidade3D")
        layout_raiz = QVBoxLayout(raiz)
        layout_raiz.setContentsMargins(0, 0, 0, 0)
        layout_raiz.setSpacing(0)
        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.setChildrenCollapsible(False)
        self._cidade_3d = Cidade3DWidget(self._grafo)
        self._cidade_3d.setObjectName("cidade3DPrincipal")
        self._cidade_3d.ponto_clicado_3d.connect(self._ponto_clicado)
        self._cidade_3d.missao_concluida.connect(self._missao_concluida)
        layout_raiz.addWidget(self._criar_barra())
        divisor.addWidget(self._cidade_3d)
        divisor.addWidget(self._criar_painel_lateral())
        divisor.setStretchFactor(0, 1)
        divisor.setStretchFactor(1, 0)
        divisor.setSizes([1100, 330])
        layout_raiz.addWidget(divisor, 1)
        self.setCentralWidget(raiz)

    def _criar_barra(self) -> QWidget:
        barra = QWidget()
        barra.setObjectName("barraSuperior3D")
        layout = QHBoxLayout(barra)
        layout.setContentsMargins(16, 9, 16, 9)
        marca = QLabel("DR  ·  DELIVERY ROUTE")
        marca.setObjectName("tituloAplicacao")
        layout.addWidget(marca)
        subtitulo = QLabel("Editor de ruas e missão de entregas")
        subtitulo.setObjectName("textoSecundario")
        layout.addWidget(subtitulo)
        layout.addStretch(1)
        self.rotulo_status = QLabel("Cidade 3D pronta")
        self.rotulo_status.setObjectName("aviso")
        layout.addWidget(self.rotulo_status)
        self.botao_enquadrar = QPushButton("Enquadrar cidade")
        self.botao_enquadrar.clicked.connect(self._cidade_3d.enquadrar_cidade)
        layout.addWidget(self.botao_enquadrar)
        self.botao_foco_carro = QPushButton("Foco carro")
        self.botao_foco_carro.clicked.connect(self._cidade_3d.focar_carro)
        layout.addWidget(self.botao_foco_carro)
        menu = self.menuBar().addMenu("Projeto")
        abrir = QAction("Abrir projeto 3D…", self)
        abrir.triggered.connect(lambda: self.abrir_projeto())
        menu.addAction(abrir)
        salvar = QAction("Salvar projeto 3D", self)
        salvar.triggered.connect(lambda: self.salvar_projeto())
        menu.addAction(salvar)
        salvar_como = QAction("Salvar projeto 3D como…", self)
        salvar_como.triggered.connect(lambda: self.salvar_projeto_como())
        menu.addAction(salvar_como)
        return barra

    def _criar_painel_lateral(self) -> QWidget:
        painel = QWidget()
        painel.setObjectName("painelLateral3D")
        painel.setMinimumWidth(300)
        painel.setMaximumWidth(400)
        layout = QVBoxLayout(painel)
        layout.setContentsMargins(8, 8, 8, 8)
        abas = QTabWidget()
        abas.setObjectName("abasCidade3D")
        abas.addTab(self._criar_aba_edicao(), "Editar cidade")
        abas.addTab(self._criar_aba_rota(), "Calcular rota")
        abas.addTab(self._criar_aba_missao(), "Missão 3D")
        layout.addWidget(abas, 1)
        self.abas = abas
        return painel

    @staticmethod
    def _grupo(titulo: str, conteudo: QWidget) -> QGroupBox:
        grupo = QGroupBox(titulo)
        layout = QVBoxLayout(grupo)
        layout.addWidget(conteudo)
        return grupo

    def _criar_aba_edicao(self) -> QWidget:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        instrucoes = QLabel(
            "Navegue com o mouse. Para editar, classifique primeiro uma região "
            "do pavimento e depois crie a rua por cliques."
        )
        instrucoes.setWordWrap(True)
        instrucoes.setObjectName("textoSecundario")
        layout.addWidget(instrucoes)
        self.botao_navegar = QPushButton("Navegar")
        self.botao_navegar.clicked.connect(self._modo_navegacao)
        layout.addWidget(self.botao_navegar)
        self.botao_marcar_superficie = QPushButton("Marcar superfície trafegável")
        self.botao_marcar_superficie.clicked.connect(self._modo_superficie)
        self.botao_marcar_superficie.setToolTip("Clique em um ponto/área de asfalto para autorizar o tráfego")
        layout.addWidget(self.botao_marcar_superficie)
        self.combo_tipo_ponto = QComboBox()
        self.combo_tipo_ponto.addItem("Cruzamento", TipoVertice.CRUZAMENTO)
        self.combo_tipo_ponto.addItem("Cliente", TipoVertice.CLIENTE)
        self.combo_tipo_ponto.addItem("Depósito", TipoVertice.DEPOSITO)
        layout.addWidget(self.combo_tipo_ponto)
        self.botao_adicionar_ponto = QPushButton("Adicionar ponto por clique")
        self.botao_adicionar_ponto.clicked.connect(self._modo_adicionar_ponto)
        layout.addWidget(self.botao_adicionar_ponto)
        self.botao_criar_rua = QPushButton("Criar rua")
        self.botao_criar_rua.clicked.connect(self._modo_criar_rua)
        layout.addWidget(self.botao_criar_rua)
        self.botao_adicionar_curva = QPushButton("Adicionar curva")
        self.botao_adicionar_curva.clicked.connect(self._modo_curva)
        layout.addWidget(self.botao_adicionar_curva)
        self.botao_desfazer_ponto = QPushButton("Desfazer último ponto")
        self.botao_desfazer_ponto.clicked.connect(self._editor_ruas.desfazer_ultimo_ponto)
        layout.addWidget(self.botao_desfazer_ponto)
        formulario = QFormLayout()
        self.controle_fator_distancia = QDoubleSpinBox()
        self.controle_fator_distancia.setRange(0.0001, 100000.0)
        self.controle_fator_distancia.setValue(1.0)
        self.controle_fator_distancia.valueChanged.connect(self._fator_alterado)
        formulario.addRow("Fator distância", self.controle_fator_distancia)
        self.controle_peso_manual = QDoubleSpinBox()
        self.controle_peso_manual.setRange(0.0, 100000.0)
        self.controle_peso_manual.setValue(0.0)
        self.controle_peso_manual.setSpecialValueText("automático")
        formulario.addRow("Peso oficial", self.controle_peso_manual)
        layout.addLayout(formulario)
        self.botao_confirmar_rua = QPushButton("Confirmar rua")
        self.botao_confirmar_rua.clicked.connect(self._confirmar_rua)
        layout.addWidget(self.botao_confirmar_rua)
        self.botao_cancelar_rua = QPushButton("Cancelar edição")
        self.botao_cancelar_rua.clicked.connect(self._cancelar_edicao)
        layout.addWidget(self.botao_cancelar_rua)
        self.rotulo_rua = QLabel("Nenhuma rua em edição")
        self.rotulo_rua.setWordWrap(True)
        self.rotulo_rua.setObjectName("aviso")
        layout.addWidget(self.rotulo_rua)
        self.lista_vertices_3d = QListWidget()
        self.lista_vertices_3d.itemClicked.connect(self._selecionar_item_vertice)
        layout.addWidget(self.lista_vertices_3d, 1)
        self.botao_salvar_editor = QPushButton("Salvar cidade")
        self.botao_salvar_editor.clicked.connect(lambda: self.salvar_projeto())
        layout.addWidget(self.botao_salvar_editor)
        return aba

    def _criar_aba_rota(self) -> QWidget:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        self.combo_algoritmo = QComboBox()
        self.combo_algoritmo.addItem("Dijkstra — Menor caminho", "dijkstra")
        self.combo_algoritmo.addItem("Caixeiro Viajante — Entregas", "tsp")
        self.combo_algoritmo.currentIndexChanged.connect(self._algoritmo_alterado)
        layout.addWidget(self.combo_algoritmo)
        self.combo_origem = QComboBox()
        self.combo_destino = QComboBox()
        self.formulario_dijkstra = QFormLayout()
        self.formulario_dijkstra.addRow("Origem", self.combo_origem)
        self.formulario_dijkstra.addRow("Destino", self.combo_destino)
        container_dijkstra = QWidget()
        container_dijkstra.setLayout(self.formulario_dijkstra)
        layout.addWidget(container_dijkstra)
        self.lista_clientes = QListWidget()
        self.lista_clientes.setMinimumHeight(110)
        layout.addWidget(QLabel("Clientes do TSP"))
        layout.addWidget(self.lista_clientes)
        self.botao_calcular = QPushButton("Calcular rota")
        self.botao_calcular.clicked.connect(self.calcular_rota)
        self.botao_calcular.setObjectName("botaoPrimario")
        layout.addWidget(self.botao_calcular)
        self.botao_limpar_rota = QPushButton("Limpar rota")
        self.botao_limpar_rota.clicked.connect(self.limpar_rota)
        layout.addWidget(self.botao_limpar_rota)
        self.rotulo_resultado = QLabel("Nenhuma rota calculada")
        self.rotulo_resultado.setWordWrap(True)
        self.rotulo_resultado.setObjectName("detalhesLocal")
        layout.addWidget(self.rotulo_resultado)
        self.painel_resultados = PainelResultados()
        self.painel_resultados.limpar_solicitado.connect(self.limpar_rota)
        layout.addWidget(self.painel_resultados)
        layout.addStretch(1)
        return aba

    def _criar_aba_missao(self) -> QWidget:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        self.botao_iniciar_missao = QPushButton("Iniciar missão 3D")
        self.botao_iniciar_missao.clicked.connect(self.iniciar_missao)
        self.botao_iniciar_missao.setObjectName("botaoPrimario")
        layout.addWidget(self.botao_iniciar_missao)
        self.botao_iniciar_percurso = QPushButton("Iniciar percurso")
        self.botao_iniciar_percurso.clicked.connect(self._cidade_3d.iniciar_percurso)
        layout.addWidget(self.botao_iniciar_percurso)
        self.botao_pausar = QPushButton("Pausar")
        self.botao_pausar.clicked.connect(self._cidade_3d.pausar_percurso)
        layout.addWidget(self.botao_pausar)
        self.botao_continuar = QPushButton("Continuar")
        self.botao_continuar.clicked.connect(self._cidade_3d.continuar_percurso)
        layout.addWidget(self.botao_continuar)
        self.botao_reiniciar = QPushButton("Reiniciar")
        self.botao_reiniciar.clicked.connect(lambda: self._cidade_3d.reiniciar_missao())
        layout.addWidget(self.botao_reiniciar)
        self.botao_camera_missao = QPushButton("Câmera atrás do carro")
        self.botao_camera_missao.clicked.connect(self._alternar_camera_missao)
        layout.addWidget(self.botao_camera_missao)
        self.rotulo_missao = QLabel("Calcule uma rota e configure as ruas para iniciar.")
        self.rotulo_missao.setWordWrap(True)
        self.rotulo_missao.setObjectName("aviso")
        layout.addWidget(self.rotulo_missao)
        layout.addStretch(1)
        return aba

    def _inicializar_cena(self) -> None:
        try:
            if self._cidade_3d.backend_glb_disponivel:
                self._cidade_3d.iniciar_renderizador_glb()
                self._cidade_3d.enquadrar_cidade()
                self.rotulo_status.setText("Cidade e carro GLB carregados")
            else:
                self.rotulo_status.setText("GLB disponível, backend 3D não encontrado")
        except Exception as erro:  # pragma: no cover - depende do desktop
            self.rotulo_status.setText(f"Falha na renderização 3D: {erro}")
        self._atualizar_dados()

    def _atualizar_dados(self) -> None:
        if not hasattr(self, "combo_origem"):
            return
        combos = (self.combo_origem, self.combo_destino)
        for combo in combos:
            atual = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for vertice in self._grafo.listar_vertices():
                combo.addItem(f"{vertice.identificador} · {vertice.nome}", vertice.identificador)
            if atual is not None:
                indice = combo.findData(atual)
                if indice >= 0:
                    combo.setCurrentIndex(indice)
            combo.blockSignals(False)
        self.lista_clientes.clear()
        for cliente in self._grafo.listar_clientes():
            item = QListWidgetItem(f"{cliente.identificador} · {cliente.nome}")
            item.setData(Qt.ItemDataRole.UserRole, cliente.identificador)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.lista_clientes.addItem(item)
        self.lista_vertices_3d.clear()
        for vertice in self._grafo.listar_vertices():
            self.lista_vertices_3d.addItem(f"{vertice.identificador} · {vertice.nome} ({vertice.tipo.value})")
        self._atualizar_modo_rota()

    def _algoritmo_alterado(self) -> None:
        self._atualizar_modo_rota()

    def _atualizar_modo_rota(self) -> None:
        dijkstra_ativo = self.combo_algoritmo.currentData() == "dijkstra"
        self.combo_origem.setVisible(dijkstra_ativo)
        self.combo_destino.setVisible(dijkstra_ativo)
        for indice in range(self.formulario_dijkstra.rowCount()):
            label = self.formulario_dijkstra.itemAt(indice, QFormLayout.ItemRole.LabelRole)
            campo = self.formulario_dijkstra.itemAt(indice, QFormLayout.ItemRole.FieldRole)
            if label and label.widget():
                label.widget().setVisible(dijkstra_ativo)
            if campo and campo.widget():
                campo.widget().setVisible(dijkstra_ativo)
        self.lista_clientes.setVisible(not dijkstra_ativo)

    def _modo_navegacao(self) -> None:
        self._editor_ruas.modo = ModoEdicaoRua.NAVEGACAO
        self._esperando_curva = False
        self.rotulo_rua.setText("Navegação livre: arraste e use a rodinha do mouse.")

    def _modo_superficie(self) -> None:
        self._editor_ruas.modo = ModoEdicaoRua.MARCAR_SUPERFICIE
        self.rotulo_rua.setText("Clique no asfalto para marcar uma superfície trafegável.")

    def _modo_adicionar_ponto(self) -> None:
        self._modo_ponto = self.combo_tipo_ponto.currentData()
        self._editor_ruas.modo = ModoEdicaoRua.CRIAR_RUA
        self._esperando_curva = False
        self.rotulo_rua.setText("Clique na rua para posicionar o novo local.")

    def _modo_criar_rua(self) -> None:
        self._modo_ponto = None
        self._esperando_curva = False
        self._editor_ruas.modo = ModoEdicaoRua.CRIAR_RUA
        self._editor_ruas.cancelar_rua()
        self._editor_ruas.modo = ModoEdicaoRua.CRIAR_RUA
        self.rotulo_rua.setText("Clique no início e no fim da rua; use Adicionar curva se necessário.")

    def _modo_curva(self) -> None:
        if not self._editor_ruas.pontos_pendentes:
            self.rotulo_rua.setText("Selecione o início da rua antes de adicionar curvas.")
            return
        self._esperando_curva = True
        self.rotulo_rua.setText("Clique no próximo ponto intermediário da curva.")

    def _fator_alterado(self, valor: float) -> None:
        self._editor_ruas.definir_fator_distancia(valor)

    def _ponto_clicado(self, x: float, y: float, z: float, objeto: str, encontrado: bool) -> None:
        if not encontrado:
            self.rotulo_status.setText("Nenhuma geometria foi atingida; clique sobre o modelo.")
            return
        self._objeto_hit_atual = objeto
        ponto = (x, y, z)
        modo = self._editor_ruas.modo
        if modo is ModoEdicaoRua.MARCAR_SUPERFICIE:
            self._editor_ruas.marcar_superficie((ponto,), raio_tolerancia=1.2)
            self.rotulo_status.setText("Superfície trafegável marcada manualmente.")
            self._modo_navegacao()
            return
        if self._modo_ponto is not None:
            self._adicionar_vertice_por_ponto(ponto, self._modo_ponto, objeto)
            return
        if modo is not ModoEdicaoRua.CRIAR_RUA:
            return
        if self._esperando_curva:
            self._editor_ruas.adicionar_curva(ponto)
            self._esperando_curva = False
        elif not self._editor_ruas.pontos_pendentes:
            self._editor_ruas.iniciar_rua(ponto, vertice_id=self._vertice_proximo(ponto))
        elif self._editor_ruas.rua.destino_id is None:
            self._editor_ruas.selecionar_fim(ponto, vertice_id=self._vertice_proximo(ponto))
        else:
            self._editor_ruas.adicionar_curva(ponto)
        self._atualizar_rotulo_rua()

    def _vertice_proximo(self, ponto: tuple[float, float, float]) -> str | None:
        mapeamento = self._cidade_3d.mapeamento_cidade_glb
        if mapeamento is None:
            return None
        candidatos = [(dist(ponto, pos), ident) for ident, pos in mapeamento.posicoes.items()]
        if not candidatos:
            return None
        distancia, ident = min(candidatos)
        return ident if distancia <= 0.20 else None

    def _adicionar_vertice_por_ponto(self, ponto: tuple[float, float, float], tipo: TipoVertice, objeto: str) -> None:
        if not self._editor_ruas.ponto_trafegavel(ponto, objeto):
            self.rotulo_status.setText("Ponto recusado: classifique manualmente o pavimento antes de criar locais.")
            return
        proximo = len(self._grafo.listar_vertices()) + 1
        identificador = f"V{proximo}"
        while any(v.identificador == identificador for v in self._grafo.listar_vertices()):
            proximo += 1
            identificador = f"V{proximo}"
        if tipo is TipoVertice.DEPOSITO and self._grafo.obter_deposito() is not None:
            self.rotulo_status.setText("O grafo já possui um depósito; remova-o antes de criar outro.")
            return
        try:
            self._grafo.adicionar_vertice(Vertice(identificador, identificador, tipo, ponto[0], ponto[2]))
        except (TypeError, ValueError) as erro:
            self.rotulo_status.setText(str(erro))
            return
        self._atualizar_mapeamento({identificador: ponto})
        self._invalidar_rota("Local criado; recalcule a rota.")
        self._modo_navegacao()

    def _atualizar_mapeamento(self, novos: dict[str, tuple[float, float, float]] | None = None) -> None:
        renderizador_ativo = self._cidade_3d.renderizador_qtquick3d is not None
        anterior = dict(self._cidade_3d.mapeamento_cidade_glb.posicoes) if self._cidade_3d.mapeamento_cidade_glb else {}
        if novos:
            anterior.update(novos)
        self._cidade_3d.carregar_grafo(self._grafo)
        if set(anterior) == {v.identificador for v in self._grafo.listar_vertices()}:
            self._cidade_3d.configurar_mapeamento_manual(anterior)
            if self._editor_ruas.superficies:
                self._cidade_3d._mapeamento_glb = self._cidade_3d.mapeamento_cidade_glb
        # ``Cidade3DWidget.carregar_grafo`` encerra a cena para evitar assets
        # antigos. Em uma edição interativa precisamos reabri-la antes do
        # próximo clique, mantendo a janela responsiva e o picking ativo.
        if renderizador_ativo and self._cidade_3d.backend_glb_disponivel:
            try:
                self._cidade_3d.iniciar_renderizador_glb()
            except Exception as erro:  # pragma: no cover - backend gráfico
                self.rotulo_status.setText(f"Cena 3D aguardando recarga: {erro}")

    def _atualizar_rotulo_rua(self) -> None:
        if not self._editor_ruas.pontos_pendentes:
            self.rotulo_rua.setText("Nenhuma rua em edição")
            return
        comprimento = self._editor_ruas.rua.comprimento_visual
        self.rotulo_rua.setText(
            f"Rua: {len(self._editor_ruas.pontos_pendentes)} pontos · "
            f"distância visual {comprimento:.3f} · peso sugerido {comprimento * self._editor_ruas.fator_distancia:.3f}"
        )

    def _confirmar_rua(self) -> None:
        ok, mensagem = self._editor_ruas.validar_rua(objeto=self._objeto_hit_atual)
        if not ok:
            self.rotulo_status.setText(mensagem)
            return
        inicio = self._editor_ruas.rua.origem_id or self._criar_vertice_automatico(self._editor_ruas.pontos_pendentes[0])
        fim = self._editor_ruas.rua.destino_id or self._criar_vertice_automatico(self._editor_ruas.pontos_pendentes[-1])
        if inicio == fim:
            self.rotulo_status.setText("Início e fim precisam ser vértices diferentes.")
            return
        peso = self.controle_peso_manual.value() or self._editor_ruas.peso_sugerido()
        try:
            self._grafo.adicionar_aresta(inicio, fim, peso)
        except ValueError as erro:
            self.rotulo_status.setText(str(erro))
            return
        self._editor_ruas.registrar_rua(inicio, fim)
        pontos = self._editor_ruas.pontos_pendentes[1:-1]
        self._atualizar_mapeamento()
        for ponto in pontos:
            self._cidade_3d.adicionar_ponto_intermediario_3d(inicio, fim, ponto)
        self._editor_ruas.cancelar_rua()
        self._invalidar_rota("Rua criada no grafo oficial; recalcule a rota.")
        self.rotulo_rua.setText(f"Rua {inicio}–{fim} confirmada.")

    def _criar_vertice_automatico(self, ponto: tuple[float, float, float]) -> str:
        proximo = len(self._grafo.listar_vertices()) + 1
        identificador = f"V{proximo}"
        while any(v.identificador == identificador for v in self._grafo.listar_vertices()):
            proximo += 1
            identificador = f"V{proximo}"
        self._grafo.adicionar_vertice(Vertice(identificador, identificador, TipoVertice.CRUZAMENTO, ponto[0], ponto[2]))
        self._atualizar_mapeamento({identificador: ponto})
        return identificador

    def _cancelar_edicao(self) -> None:
        self._editor_ruas.cancelar_rua()
        self._modo_ponto = None
        self._esperando_curva = False
        self.rotulo_rua.setText("Edição cancelada.")

    def _selecionar_item_vertice(self, item: QListWidgetItem) -> None:
        ident = item.text().split(" · ", 1)[0]
        self._cidade_3d.selecionar_vertice(ident, emitir_sinal=False)

    def _invalidar_rota(self, mensagem: str) -> None:
        self._resultado_atual = None
        self._algoritmo_resultado = None
        self._rota_pendente = ()
        self._cidade_3d.limpar_destaque_rota()
        self.painel_resultados.exibir_grafo_alterado(mensagem)
        self.rotulo_resultado.setText(mensagem)
        self.rotulo_status.setText(mensagem)
        self._atualizar_dados()

    def _clientes_selecionados(self) -> list[str]:
        return [
            self.lista_clientes.item(indice).data(Qt.ItemDataRole.UserRole)
            for indice in range(self.lista_clientes.count())
            if self.lista_clientes.item(indice).checkState() == Qt.CheckState.Checked
        ]

    def calcular_rota(self) -> None:
        if self._calculando:
            return
        self._calculando = True
        self.botao_calcular.setEnabled(False)
        self._cidade_3d.limpar_destaque_rota()
        try:
            if self.combo_algoritmo.currentData() == "tsp":
                resultado = caixeiro_viajante(self._grafo, self._clientes_selecionados())
                percurso = tuple(resultado.percurso_completo) if resultado.encontrada else ()
                self._algoritmo_resultado = "tsp"
                texto = (
                    f"TSP: {resultado.distancia_total:g} km · "
                    f"{' → '.join(resultado.percurso_completo) if resultado.encontrada else 'rota inviável'}"
                )
                self.painel_resultados.exibir_tsp(self._grafo, resultado)
            else:
                origem = self.combo_origem.currentData()
                destino = self.combo_destino.currentData()
                resultado = dijkstra(self._grafo, origem, destino)
                percurso = tuple(resultado.caminho) if resultado.encontrado else ()
                self._algoritmo_resultado = "dijkstra"
                texto = f"Dijkstra: {resultado.distancia_total:g} km · {' → '.join(resultado.caminho) if resultado.encontrado else 'destino inalcançável'}"
                self.painel_resultados.exibir_dijkstra(self._grafo, resultado)
            self._resultado_atual = resultado
            self._rota_pendente = percurso
            if percurso:
                self._cidade_3d.definir_rota(percurso)
            else:
                self._cidade_3d.limpar_destaque_rota()
            self.rotulo_resultado.setText(texto)
            self.rotulo_status.setText("Rota destacada na cidade 3D." if percurso else "Nenhuma rota foi destacada.")
        except (KeyError, TypeError, ValueError) as erro:
            self._resultado_atual = None
            self._rota_pendente = ()
            self._cidade_3d.limpar_destaque_rota()
            self.painel_resultados.exibir_erro(str(erro))
            self.rotulo_resultado.setText(str(erro))
        finally:
            self._calculando = False
            self.botao_calcular.setEnabled(True)
            self._atualizar_botao_missao()

    def limpar_rota(self) -> None:
        if self._calculando:
            return
        self._resultado_atual = None
        self._algoritmo_resultado = None
        self._rota_pendente = ()
        self._cidade_3d.limpar_destaque_rota()
        self.painel_resultados.limpar()
        self.rotulo_resultado.setText("Nenhuma rota calculada")
        self.rotulo_status.setText("Rota e destaques removidos.")
        self._atualizar_botao_missao()

    def _atualizar_botao_missao(self) -> None:
        self.botao_iniciar_missao.setEnabled(bool(self._rota_pendente) and not self._calculando)

    def iniciar_missao(self) -> bool:
        if not self._rota_pendente:
            self.rotulo_missao.setText("Calcule uma rota válida antes de iniciar.")
            return False
        mapeamento = self._cidade_3d.mapeamento_cidade_glb
        faltantes = self._editor_ruas.rota_configurada(self._rota_pendente)
        if mapeamento is None or not mapeamento.calibrado or faltantes:
            detalhes = ", ".join(faltantes) if faltantes else "mapeamento espacial não calibrado"
            self.rotulo_missao.setText(f"Missão bloqueada: configure as ruas ({detalhes}).")
            return False
        if not self._cidade_3d.entrar_missao(self._rota_pendente):
            self.rotulo_missao.setText("A rota não possui mapeamento espacial válido.")
            return False
        self.abas.setCurrentIndex(2)
        self.rotulo_missao.setText("Missão pronta. Use Iniciar percurso para mover o carro.")
        return True

    def _alternar_camera_missao(self) -> None:
        modo = self._cidade_3d.alternar_camera()
        self.botao_camera_missao.setText("Câmera livre" if modo == "aerea" else "Câmera atrás do carro")

    def _missao_concluida(self) -> None:
        self.rotulo_missao.setText(self._cidade_3d.resumo_missao or "Missão concluída.")

    def carregar_grafo(self, grafo: Grafo) -> None:
        """Troca o grafo oficial mantendo a janela e os modelos GLB."""

        if not isinstance(grafo, Grafo):
            raise TypeError("É necessário fornecer uma instância de Grafo.")
        self._grafo = grafo
        self._editor_ruas = EditorRuas3D()
        self._resultado_atual = None
        self._algoritmo_resultado = None
        self._rota_pendente = ()
        self._cidade_3d.carregar_grafo(grafo)
        self._atualizar_dados()
        self.rotulo_status.setText("Grafo atualizado; configure as ruas 3D antes da missão.")

    def salvar_projeto(self, caminho: str | Path | None = None) -> bool:
        if caminho is None:
            if self._caminho_projeto is None:
                return self.salvar_projeto_como()
            caminho = self._caminho_projeto
        try:
            dados = projeto_3d_para_dados(
                self._grafo,
                caminho_cidade=self._cidade_3d.caminho_cidade_glb,
                caminho_carro=self._cidade_3d.caminho_carro_glb,
                mapeamento=self._cidade_3d.mapeamento_cidade_glb,
                editor=self._editor_ruas,
            )
            destino = salvar_projeto_3d(dados, caminho)
        except (OSError, TypeError, ValueError) as erro:
            self.rotulo_status.setText(f"Não foi possível salvar: {erro}")
            return False
        self._caminho_projeto = destino
        self.rotulo_status.setText(f"Projeto salvo: {destino.name}")
        return True

    def salvar_projeto_como(self, caminho: str | Path | None = None) -> bool:
        if caminho is None:
            caminho, _ = QFileDialog.getSaveFileName(self, "Salvar projeto 3D", "cidade-3d.json", "Projeto 3D (*.json)")
        return bool(caminho) and self.salvar_projeto(caminho)

    def abrir_projeto(self, caminho: str | Path | None = None) -> bool:
        if caminho is None:
            selecionado, _ = QFileDialog.getOpenFileName(self, "Abrir projeto 3D", "", "Projeto 3D (*.json)")
            caminho = selecionado
        if not caminho:
            return False
        caminho = Path(caminho).expanduser()
        try:
            projeto = carregar_projeto_3d(caminho)
        except (OSError, TypeError, ValueError, ErroPersistencia) as erro:
            # Compatibilidade: um projeto JSON antigo ainda pode ser aberto
            # como grafo e receber o mapeamento 3D durante a edição.
            try:
                grafo_legado = carregar_grafo(caminho)
            except (OSError, TypeError, ValueError, ErroPersistencia):
                self.rotulo_status.setText(f"Não foi possível carregar: {erro}")
                return False
            self._grafo = grafo_legado
            self._resultado_atual = None
            self._rota_pendente = ()
            self._cidade_3d.carregar_grafo(self._grafo)
            self._atualizar_dados()
            self._caminho_projeto = Path(caminho)
            self.rotulo_status.setText(f"Grafo legado carregado: {Path(caminho).name}")
            return True
        self._grafo = projeto["grafo"]
        self._editor_ruas = projeto["editor"]
        self._cidade_3d.configurar_modelos_3d(
            ConfiguracaoModelos3D(
                caminho_cidade=projeto["caminho_cidade"],
                caminho_carro=projeto["caminho_carro"],
            ).validar()
        )
        self._cidade_3d.carregar_grafo(self._grafo)
        if projeto["mapeamento"] is not None:
            try:
                self._cidade_3d._mapeamento_glb = projeto["mapeamento"]
            except Exception:
                pass
        try:
            if self._cidade_3d.backend_glb_disponivel:
                self._cidade_3d.iniciar_renderizador_glb()
                self._cidade_3d.enquadrar_cidade()
        except Exception as erro:  # pragma: no cover - backend gráfico
            self.rotulo_status.setText(f"Projeto carregado; cena aguardando renderização: {erro}")
        self._caminho_projeto = Path(caminho)
        self._resultado_atual = None
        self._rota_pendente = ()
        self._atualizar_dados()
        self.rotulo_status.setText(f"Projeto carregado: {Path(caminho).name}")
        return True

    def closeEvent(self, evento: QCloseEvent) -> None:  # noqa: N802 - contrato Qt
        self._cidade_3d.close()
        super().closeEvent(evento)


__all__ = ["JanelaPrincipal3D"]
