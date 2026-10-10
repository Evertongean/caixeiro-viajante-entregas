"""Diálogos compactos usados pelo editor no painel principal."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
            self.tipo.addItem(item.value.capitalize(), item)
        tipo = vertice.tipo if vertice else tipo_sugerido
        if tipo is not None:
            self.tipo.setCurrentIndex(self.tipo.findData(tipo))
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
        return (
            self.identificador.text().strip(),
            self.nome.text().strip(),
            self.tipo.currentData(),
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
            self.classificacao.addItem(texto, valor)
        self.classificacao.setCurrentIndex(self.classificacao.findData(atual))
        layout.addWidget(self.classificacao)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    def valor(self) -> ClassificacaoSuperficie:
        return self.classificacao.currentData()


class DialogoRua(QDialog):
    def __init__(
        self,
        origem: str,
        destino: str,
        comprimento: float,
        fator_atual: float,
        parent=None,
        *,
        peso_atual: float | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirmar rua")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        aviso = QLabel(
            "A conexão requer calibração manual: o editor valida cada ponto "
            "clicado, mas não toda a faixa entre eles. Confira se a polilinha "
            "não atravessa prédios e adicione curvas quando necessário. O "
            "comprimento visual é apenas uma sugestão; o peso abaixo é o valor "
            "oficial usado por Dijkstra e TSP."
        )
        aviso.setWordWrap(True)
        layout.addWidget(aviso)
        formulario = QFormLayout()
        formulario.addRow("Extremos", QLabel(f"{origem} ↔ {destino}"))
        formulario.addRow("Comprimento 3D", QLabel(f"{comprimento:.4f} unidades"))
        self.fator = QDoubleSpinBox()
        self.fator.setDecimals(6)
        self.fator.setRange(0.000001, 1_000_000)
        self.fator.setValue(fator_atual)
        self.fator.setSuffix(" km/unidade")
        self.peso = QDoubleSpinBox()
        self.peso.setDecimals(6)
        self.peso.setRange(0.000001, 1_000_000_000)
        self.peso.setSuffix(" km")
        self.peso.setValue(
            peso_atual if peso_atual is not None else comprimento * fator_atual
        )
        self.sugestao = QLabel()
        self.fator.valueChanged.connect(self._atualizar_sugestao)
        self._comprimento = comprimento
        self._atualizar_sugestao()
        formulario.addRow("Fator", self.fator)
        formulario.addRow("Sugestão geométrica", self.sugestao)
        formulario.addRow("Peso oficial", self.peso)
        layout.addLayout(formulario)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    def _atualizar_sugestao(self) -> None:
        self.sugestao.setText(
            f"{self._comprimento * self.fator.value():.6f} km"
        )

    def dados(self) -> tuple[float, float]:
        return self.peso.value(), self.fator.value()


__all__ = ["DialogoRua", "DialogoSuperficie", "DialogoVertice"]
