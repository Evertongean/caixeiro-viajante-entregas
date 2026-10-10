"""Painel de configuração dos assets da missão 3D."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .modelos_glb import ConfiguracaoModelos3D


class PainelModelos3D(QGroupBox):
    """Controles pequenos e independentes para os dois modelos GLB."""

    configuracao_alterada = Signal(object)
    visualizar_solicitado = Signal()
    enquadrar_solicitado = Signal()
    calibrar_solicitado = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Modelos 3D", parent)
        self.setObjectName("painelModelos3D")
        self._configuracao = ConfiguracaoModelos3D().validar()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(6)

        self.rotulo_cidade = QLabel()
        self.rotulo_cidade.setObjectName("textoSecundario")
        self.rotulo_cidade.setWordWrap(True)
        self.rotulo_carro = QLabel()
        self.rotulo_carro.setObjectName("textoSecundario")
        self.rotulo_carro.setWordWrap(True)
        self.botao_selecionar_cidade = QPushButton("Selecionar cidade.glb…")
        self.botao_selecionar_cidade.setObjectName("botaoSelecionarCidadeGLB")
        self.botao_selecionar_cidade.setObjectName("botaoFerramenta")
        self.botao_selecionar_cidade.clicked.connect(self._selecionar_cidade)
        self.botao_selecionar_carro = QPushButton("Selecionar carro.glb…")
        self.botao_selecionar_carro.setObjectName("botaoSelecionarCarroGLB")
        self.botao_selecionar_carro.setObjectName("botaoFerramenta")
        self.botao_selecionar_carro.clicked.connect(self._selecionar_carro)
        layout.addWidget(self.rotulo_cidade)
        layout.addWidget(self.botao_selecionar_cidade)
        layout.addWidget(self.rotulo_carro)
        layout.addWidget(self.botao_selecionar_carro)

        formulario = QFormLayout()
        formulario.setContentsMargins(0, 0, 0, 0)
        self.controle_escala_cidade = self._numero(0.0001, 100.0, 0.01, 0.001)
        self.controle_escala_cidade.setObjectName("escalaCidadeGLB")
        self.controle_posicao_cidade_x = self._numero(-100000, 100000, 0.0, 1.0)
        self.controle_posicao_cidade_x.setObjectName("posicaoCidadeXGLB")
        self.controle_posicao_cidade_y = self._numero(-100000, 100000, 0.0, 1.0)
        self.controle_posicao_cidade_y.setObjectName("posicaoCidadeYGLB")
        self.controle_posicao_cidade_z = self._numero(-100000, 100000, 0.0, 1.0)
        self.controle_posicao_cidade_z.setObjectName("posicaoCidadeZGLB")
        self.controle_escala_carro = self._numero(0.0001, 100.0, 0.018, 0.001)
        self.controle_escala_carro.setObjectName("escalaCarroGLB")
        self.controle_orientacao_carro = self._numero(-360.0, 360.0, 0.0, 5.0)
        self.controle_orientacao_carro.setObjectName("orientacaoCarroGLB")
        self.controle_altura_carro = self._numero(-1000.0, 1000.0, 0.0, 0.1)
        self.controle_altura_carro.setObjectName("alturaCarroGLB")
        formulario.addRow("Escala cidade", self.controle_escala_cidade)
        formulario.addRow("Cidade X", self.controle_posicao_cidade_x)
        formulario.addRow("Cidade Y", self.controle_posicao_cidade_y)
        formulario.addRow("Cidade Z", self.controle_posicao_cidade_z)
        formulario.addRow("Escala carro", self.controle_escala_carro)
        formulario.addRow("Orientação carro", self.controle_orientacao_carro)
        formulario.addRow("Altura carro", self.controle_altura_carro)
        layout.addLayout(formulario)

        self.botao_restaurar = QPushButton("Restaurar modelos padrão")
        self.botao_restaurar.setObjectName("botaoRestaurarModelos3D")
        self.botao_restaurar.setObjectName("botaoFerramenta")
        self.botao_restaurar.clicked.connect(self.restaurar_padrao)
        self.botao_visualizar = QPushButton("Visualizar modelos")
        self.botao_visualizar.setObjectName("botaoVisualizarModelos3D")
        self.botao_visualizar.setObjectName("botaoPrimario")
        self.botao_visualizar.setToolTip("Validar e visualizar a configuração 3D")
        self.botao_visualizar.clicked.connect(self.visualizar_solicitado.emit)
        self.botao_enquadrar = QPushButton("Enquadrar cidade")
        self.botao_enquadrar.setObjectName("botaoEnquadrarCidade3D")
        self.botao_enquadrar.setToolTip("Posicionar a câmera usando os limites reais da cidade importada")
        self.botao_enquadrar.clicked.connect(self.enquadrar_solicitado.emit)
        layout.addWidget(self.botao_restaurar)
        layout.addWidget(self.botao_visualizar)
        layout.addWidget(self.botao_enquadrar)
        self.botao_calibrar = QPushButton("Calibrar ruas 3D")
        self.botao_calibrar.setObjectName("botaoCalibrarRuas3D")
        self.botao_calibrar.setToolTip("Ajustar vértices e curvas das arestas sobre o modelo importado")
        self.botao_calibrar.clicked.connect(self.calibrar_solicitado.emit)
        layout.addWidget(self.botao_calibrar)
        for controle in self._controles_numericos():
            controle.valueChanged.connect(self._emitir_configuracao)
        self._atualizar_rotulos()

        # Aliases compatíveis com integrações que incluem o sufixo GLB no nome.
        self.botao_selecionar_cidade_glb = self.botao_selecionar_cidade
        self.botao_selecionar_carro_glb = self.botao_selecionar_carro
        self.botao_restaurar_modelos_3d = self.botao_restaurar

    @staticmethod
    def _numero(minimo: float, maximo: float, valor: float, passo: float) -> QDoubleSpinBox:
        controle = QDoubleSpinBox()
        controle.setRange(minimo, maximo)
        controle.setDecimals(4)
        controle.setSingleStep(passo)
        controle.setValue(valor)
        return controle

    def _controles_numericos(self) -> tuple[QDoubleSpinBox, ...]:
        return (
            self.controle_escala_cidade,
            self.controle_posicao_cidade_x,
            self.controle_posicao_cidade_y,
            self.controle_posicao_cidade_z,
            self.controle_escala_carro,
            self.controle_orientacao_carro,
            self.controle_altura_carro,
        )

    @property
    def configuracao(self) -> ConfiguracaoModelos3D:
        return self._configuracao

    def _configuracao_dos_controles(self) -> ConfiguracaoModelos3D:
        atual = self._configuracao
        return ConfiguracaoModelos3D(
            caminho_cidade=atual.caminho_cidade,
            caminho_carro=atual.caminho_carro,
            escala_cidade=self.controle_escala_cidade.value(),
            posicao_cidade=(
                self.controle_posicao_cidade_x.value(),
                self.controle_posicao_cidade_y.value(),
                self.controle_posicao_cidade_z.value(),
            ),
            escala_carro=self.controle_escala_carro.value(),
            orientacao_carro=self.controle_orientacao_carro.value(),
            altura_carro=self.controle_altura_carro.value(),
            eixo_frente_carro=atual.eixo_frente_carro,
        ).validar()

    def _emitir_configuracao(self) -> None:
        self._configuracao = self._configuracao_dos_controles()
        self.configuracao_alterada.emit(self._configuracao)

    def aplicar_configuracao(self, configuracao: ConfiguracaoModelos3D) -> None:
        self._configuracao = configuracao.validar()
        self._atualizar_controles()
        self.configuracao_alterada.emit(self._configuracao)

    def selecionar_cidade(self, caminho: str | Path) -> None:
        self._configuracao = ConfiguracaoModelos3D(
            caminho_cidade=Path(caminho), caminho_carro=self._configuracao.caminho_carro,
            escala_cidade=self._configuracao.escala_cidade, posicao_cidade=self._configuracao.posicao_cidade,
            escala_carro=self._configuracao.escala_carro, orientacao_carro=self._configuracao.orientacao_carro,
            altura_carro=self._configuracao.altura_carro, eixo_frente_carro=self._configuracao.eixo_frente_carro,
        ).validar()
        self._atualizar_rotulos()
        self.configuracao_alterada.emit(self._configuracao)

    def selecionar_carro(self, caminho: str | Path) -> None:
        atual = self._configuracao
        self._configuracao = ConfiguracaoModelos3D(
            caminho_cidade=atual.caminho_cidade, caminho_carro=Path(caminho), escala_cidade=atual.escala_cidade,
            posicao_cidade=atual.posicao_cidade, escala_carro=atual.escala_carro,
            orientacao_carro=atual.orientacao_carro, altura_carro=atual.altura_carro,
            eixo_frente_carro=atual.eixo_frente_carro,
        ).validar()
        self._atualizar_rotulos()
        self.configuracao_alterada.emit(self._configuracao)

    def restaurar_padrao(self) -> None:
        self.aplicar_configuracao(ConfiguracaoModelos3D().validar())

    def _atualizar_controles(self) -> None:
        config = self._configuracao
        valores = (
            config.escala_cidade,
            *config.posicao_cidade,
            config.escala_carro,
            config.orientacao_carro,
            config.altura_carro,
        )
        for controle, valor in zip(self._controles_numericos(), valores):
            controle.blockSignals(True)
            controle.setValue(valor)
            controle.blockSignals(False)
        self._atualizar_rotulos()

    def _atualizar_rotulos(self) -> None:
        self.rotulo_cidade.setText(f"Cidade: {self._configuracao.caminho_cidade.name}")
        self.rotulo_carro.setText(f"Carro: {self._configuracao.caminho_carro.name}")
        self.rotulo_cidade.setToolTip(str(self._configuracao.caminho_cidade))
        self.rotulo_carro.setToolTip(str(self._configuracao.caminho_carro))

    def _selecionar_cidade(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar cidade.glb", str(self._configuracao.caminho_cidade), "Modelos GLB (*.glb)")
        if caminho:
            self.selecionar_cidade(caminho)

    def _selecionar_carro(self) -> None:
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar carro.glb", str(self._configuracao.caminho_carro), "Modelos GLB (*.glb)")
        if caminho:
            self.selecionar_carro(caminho)

