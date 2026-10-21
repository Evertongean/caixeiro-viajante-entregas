"""Diálogos compactos usados pelo editor no painel principal."""

from __future__ import annotations

from math import isfinite

from PySide6.QtCore import QLocale, Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from models.grafo import TipoVertice, Vertice
from models.projeto_cidade import ClassificacaoSuperficie
from .formatacao import arredondar_para_exibicao


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
        parent=None,
        *,
        peso_atual: float | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirmar rua")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        formulario = QFormLayout()
        formulario.addRow("Conexão", QLabel(f"{origem} ↔ {destino}"))
        self.peso = QDoubleSpinBox()
        self.peso.setLocale(
            QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil)
        )
        self.peso.setDecimals(1)
        self.peso.setRange(0.0, 1_000_000_000_000)
        self.peso.setSuffix(" km")
        self.peso.setKeyboardTracking(False)
        self.peso.setCorrectionMode(
            QAbstractSpinBox.CorrectionMode.CorrectToPreviousValue
        )
        self._peso_original = float(peso_atual) if peso_atual is not None else None
        if self._peso_original is not None and (
            not isfinite(self._peso_original) or self._peso_original <= 0
        ):
            raise ValueError("A distância oficial atual deve ser positiva e finita.")
        self._peso_modificado = False
        valor_inicial = self._peso_original if self._peso_original is not None else 0.0
        self.peso.setValue(arredondar_para_exibicao(valor_inicial))
        self.peso.valueChanged.connect(self._marcar_peso_modificado)
        self.peso.lineEdit().textChanged.connect(self._marcar_peso_modificado)
        formulario.addRow("Distância da rua (km)", self.peso)
        layout.addLayout(formulario)
        self.erro_distancia = QLabel()
        self.erro_distancia.setStyleSheet("color: #FCA5A5;")
        self.erro_distancia.setWordWrap(True)
        layout.addWidget(self.erro_distancia)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.botao_salvar = botoes.button(QDialogButtonBox.StandardButton.Save)
        self.botao_cancelar = botoes.button(QDialogButtonBox.StandardButton.Cancel)
        self.botao_salvar.setText("Salvar")
        self.botao_cancelar.setText("Cancelar")
        botoes.accepted.connect(self._validar)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    def _marcar_peso_modificado(self, *_args) -> None:
        self._peso_modificado = True

    def _validar(self) -> None:
        try:
            self.dados()
        except ValueError:
            if self.peso.hasAcceptableInput() and self.peso.value() <= 0:
                mensagem = (
                    "A distância deve ser positiva. Informe ao menos 0,1 km."
                )
            else:
                mensagem = "Informe uma distância numérica válida."
            self.erro_distancia.setText(mensagem)
            self.peso.setFocus()
            return
        self.erro_distancia.clear()
        self.accept()

    def dados(self) -> float:
        if self._peso_original is not None and not self._peso_modificado:
            return self._peso_original
        if not self.peso.hasAcceptableInput():
            raise ValueError("A distância da rua deve ser um número válido.")
        self.peso.interpretText()
        valor = self.peso.value()
        if not isfinite(valor) or valor <= 0:
            raise ValueError("A distância da rua deve ser positiva e finita.")
        return valor


__all__ = [
    "DialogoRua",
    "DialogoSuperficie",
    "DialogoVertice",
]
