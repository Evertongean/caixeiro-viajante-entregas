"""Diálogos compactos usados pelo editor no painel principal."""

from __future__ import annotations

from math import isfinite

from PySide6.QtCore import QLocale, Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from models.grafo import TipoVertice, Vertice
from models.projeto_cidade import ClassificacaoSuperficie


class DialogoVertice(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        vertice: Vertice | None = None,
        tipo_sugerido: TipoVertice | None = None,
        identificador_sugerido: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar ponto" if vertice else "Adicionar ponto")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        texto = QLabel(
            "A posição será obtida diretamente do ponto selecionado na cidade 3D."
        )
        texto.setWordWrap(True)
        layout.addWidget(texto)
        formulario = QFormLayout()
        self.identificador = QLineEdit(
            vertice.identificador if vertice else identificador_sugerido
        )
        self.identificador.setEnabled(vertice is None)
        self.nome = QLineEdit(vertice.nome if vertice else "")
        self.tipo = QComboBox()
        for item in TipoVertice:
            self.tipo.addItem(item.value.capitalize(), item.value)
        tipo = vertice.tipo if vertice else tipo_sugerido
        if tipo is not None:
            self.tipo.setCurrentIndex(self.tipo.findData(tipo.value))
        formulario.addRow("Identificador", self.identificador)
        formulario.addRow("Nome", self.nome)
        formulario.addRow("Tipo", self.tipo)
        layout.addLayout(formulario)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.accepted.connect(self._validar)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    def _validar(self) -> None:
        if not self.identificador.text().strip():
            self.identificador.setFocus()
            return
        if not self.nome.text().strip():
            self.nome.setFocus()
            return
        self.accept()

    def dados(self) -> tuple[str, str, TipoVertice]:
        try:
            tipo = TipoVertice(self.tipo.currentData())
        except (TypeError, ValueError) as erro:
            raise ValueError("O tipo de ponto selecionado é inválido.") from erro
        return (
            self.identificador.text().strip(),
            self.nome.text().strip(),
            tipo,
        )


class DialogoSuperficie(QDialog):
    def __init__(
        self,
        referencia: str,
        atual: ClassificacaoSuperficie,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Classificar superfície")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        explicacao = QLabel(
            "O modelo não identifica ruas de forma confiável. Confirme manualmente "
            "a classe desta malha antes de cadastrar pontos."
        )
        explicacao.setWordWrap(True)
        layout.addWidget(explicacao)
        referencia_label = QLabel(referencia)
        referencia_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        referencia_label.setWordWrap(True)
        layout.addWidget(referencia_label)
        self.classificacao = QComboBox()
        for valor, texto in (
            (ClassificacaoSuperficie.RUA, "Rua trafegável"),
            (ClassificacaoSuperficie.CALCADA, "Calçada"),
            (ClassificacaoSuperficie.BLOQUEADA, "Área bloqueada / edifício"),
            (ClassificacaoSuperficie.NAO_CLASSIFICADA, "Ainda não classificada"),
        ):
            # QVariant normaliza enums que herdam de str para str puro. O dado
            # armazenado é deliberadamente o valor serializável e valor() faz a
            # conversão explícita de volta ao contrato do domínio.
            self.classificacao.addItem(texto, valor.value)
        indice_atual = self.classificacao.findData(atual.value)
        self.classificacao.setCurrentIndex(max(indice_atual, 0))
        layout.addWidget(self.classificacao)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    def valor(self) -> ClassificacaoSuperficie:
        try:
            return ClassificacaoSuperficie(self.classificacao.currentData())
        except (TypeError, ValueError) as erro:
            raise ValueError("A classificação selecionada é inválida.") from erro


class DialogoRua(QDialog):
    def __init__(
        self,
        origem: str,
        destino: str,
        distancia_sugerida_km: float,
        parent=None,
        *,
        peso_atual: float | None = None,
        escala_validada: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirmar rua")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        aviso = QLabel(
            "Confira a sugestão calculada pelo traçado ou informe a distância "
            "real da rua. A distância oficial será utilizada pelos algoritmos "
            "de otimização."
        )
        aviso.setWordWrap(True)
        layout.addWidget(aviso)
        formulario = QFormLayout()
        formulario.addRow("Conexão", QLabel(f"{origem} ↔ {destino}"))
        self._distancia_sugerida = float(distancia_sugerida_km)
        if not isfinite(self._distancia_sugerida) or self._distancia_sugerida <= 0:
            raise ValueError("A distância sugerida deve ser positiva e finita.")
        self.sugestao = QLabel(self._texto_distancia(self._distancia_sugerida))
        formulario.addRow("Distância sugerida", self.sugestao)
        if not escala_validada:
            estimativa = QLabel(
                "Estimativa baseada na escala geral configurada para o cenário."
            )
            estimativa.setObjectName("textoSecundario")
            estimativa.setWordWrap(True)
            formulario.addRow("", estimativa)
        self.peso = QDoubleSpinBox()
        self.peso.setLocale(
            QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil)
        )
        self.peso.setDecimals(9)
        self.peso.setRange(0.000000001, 1_000_000_000_000)
        self.peso.setSuffix(" km")
        self.peso.setKeyboardTracking(False)
        self.peso.setCorrectionMode(
            QAbstractSpinBox.CorrectionMode.CorrectToPreviousValue
        )
        self.peso.setValue(
            peso_atual if peso_atual is not None else self._distancia_sugerida
        )
        formulario.addRow("Distância oficial (km)", self.peso)
        layout.addLayout(formulario)
        self.erro_distancia = QLabel()
        self.erro_distancia.setStyleSheet("color: #FCA5A5;")
        self.erro_distancia.setWordWrap(True)
        layout.addWidget(self.erro_distancia)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botao_usar_sugestao = QPushButton("Usar sugestão")
        botoes.addButton(
            self.botao_usar_sugestao, QDialogButtonBox.ButtonRole.ActionRole
        )
        self.botao_salvar = botoes.button(QDialogButtonBox.StandardButton.Save)
        self.botao_cancelar = botoes.button(QDialogButtonBox.StandardButton.Cancel)
        self.botao_salvar.setText("Salvar")
        self.botao_cancelar.setText("Cancelar")
        self.botao_usar_sugestao.clicked.connect(self.usar_sugestao)
        botoes.accepted.connect(self._validar)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    @staticmethod
    def _texto_distancia(valor: float) -> str:
        locale = QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil)
        return f"{locale.toString(valor, 'f', 6)} km"

    def usar_sugestao(self) -> None:
        self.peso.setValue(self._distancia_sugerida)
        self.erro_distancia.clear()

    def _validar(self) -> None:
        if not self.peso.hasAcceptableInput():
            self.erro_distancia.setText("Informe uma distância numérica válida.")
            self.peso.setFocus()
            return
        self.peso.interpretText()
        valor = self.peso.value()
        if not isfinite(valor) or valor <= 0:
            self.erro_distancia.setText("A distância deve ser maior que zero.")
            self.peso.setFocus()
            return
        self.erro_distancia.clear()
        self.accept()

    def dados(self) -> float:
        if not self.peso.hasAcceptableInput():
            raise ValueError("A distância oficial deve ser um número válido.")
        self.peso.interpretText()
        valor = self.peso.value()
        if not isfinite(valor) or valor <= 0:
            raise ValueError("A distância oficial deve ser positiva e finita.")
        return valor


class DialogoEscalaCenario(QDialog):
    """Configuração geral, deliberadamente separada da confirmação de ruas."""

    def __init__(
        self,
        fator_atual: float,
        escala_validada: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Escala de distância do cenário")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        explicacao = QLabel(
            "Defina quantos quilômetros reais correspondem a uma unidade da "
            "cidade 3D. Essa escala será usada apenas para sugerir distâncias; "
            "as distâncias oficiais já salvas não serão alteradas."
        )
        explicacao.setWordWrap(True)
        layout.addWidget(explicacao)
        formulario = QFormLayout()
        self.escala = QDoubleSpinBox()
        self.escala.setLocale(
            QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil)
        )
        self.escala.setDecimals(9)
        self.escala.setRange(0.000000001, 1_000_000_000)
        self.escala.setSuffix(" km/unidade")
        self.escala.setValue(fator_atual)
        formulario.addRow("Escala geral", self.escala)
        layout.addLayout(formulario)
        self.validada = QCheckBox("Escala conferida para este cenário")
        self.validada.setChecked(escala_validada)
        layout.addWidget(self.validada)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    def dados(self) -> tuple[float, bool]:
        valor = self.escala.value()
        if not isfinite(valor) or valor <= 0:
            raise ValueError("A escala geral deve ser positiva e finita.")
        return valor, self.validada.isChecked()


__all__ = [
    "DialogoEscalaCenario",
    "DialogoRua",
    "DialogoSuperficie",
    "DialogoVertice",
]
