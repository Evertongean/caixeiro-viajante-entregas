"""Diálogos pequenos e reutilizáveis para editar o cenário do grafo."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from models.grafo import Grafo, TipoVertice


class DialogoVertice(QDialog):
    """Formulário para inserir ou alterar um vértice."""

    def __init__(self, *, vertice=None, posicao: tuple[float, float] = (0, 0), parent=None):
        super().__init__(parent)
        self._editando = vertice is not None
        self.setWindowTitle("Editar local" if self._editando else "Adicionar local")
        self.setModal(True)

        formulario = QFormLayout()
        self.identificador = QLineEdit()
        self.identificador.setPlaceholderText("Ex.: D, A ou CRZ1")
        if vertice is not None:
            self.identificador.setText(vertice.identificador)
            self.identificador.setReadOnly(True)
        formulario.addRow("Identificador", self.identificador)

        self.nome = QLineEdit()
        self.nome.setPlaceholderText("Nome exibido na cidade")
        formulario.addRow("Nome", self.nome)

        self.tipo = QComboBox()
        for tipo in TipoVertice:
            self.tipo.addItem(tipo.value.capitalize(), tipo)
        formulario.addRow("Tipo", self.tipo)

        self.x = self._coordenada()
        self.y = self._coordenada()
        formulario.addRow("Coordenada X", self.x)
        formulario.addRow("Coordenada Y", self.y)

        if vertice is not None:
            self.nome.setText(vertice.nome)
            self.tipo.setCurrentIndex(self.tipo.findData(vertice.tipo))
            self.x.setValue(vertice.x)
            self.y.setValue(vertice.y)
        else:
            self.x.setValue(posicao[0])
            self.y.setValue(posicao[1])

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        caixa = QVBoxLayout(self)
        caixa.addLayout(formulario)
        caixa.addWidget(botoes)

    @staticmethod
    def _coordenada() -> QDoubleSpinBox:
        campo = QDoubleSpinBox()
        campo.setRange(-1_000_000, 1_000_000)
        campo.setDecimals(2)
        campo.setSingleStep(1)
        return campo

    def dados(self) -> dict:
        tipo = self.tipo.currentData()
        if not isinstance(tipo, TipoVertice):
            try:
                tipo = TipoVertice(tipo)
            except (TypeError, ValueError):
                tipo = None
        return {
            "identificador": self.identificador.text().strip(),
            "nome": self.nome.text().strip(),
            "tipo": tipo,
            "x": self.x.value(),
            "y": self.y.value(),
        }

    def accept(self) -> None:  # noqa: D401 - contrato Qt
        dados = self.dados()
        if not dados["identificador"] or not dados["nome"]:
            QMessageBox.warning(self, "Dados inválidos", "Informe identificador e nome.")
            return
        if not isinstance(dados["tipo"], TipoVertice):
            QMessageBox.warning(self, "Dados inválidos", "Selecione um tipo válido.")
            return
        super().accept()


class DialogoAresta(QDialog):
    """Formulário para inserir ou alterar o peso de uma aresta."""

    def __init__(self, grafo: Grafo, *, aresta=None, parent=None):
        super().__init__(parent)
        self._editando = aresta is not None
        self.setWindowTitle("Editar rua" if self._editando else "Criar rua")
        self.setModal(True)
        vertices = grafo.listar_vertices()

        formulario = QFormLayout()
        self.origem = QComboBox()
        self.destino = QComboBox()
        for vertice in vertices:
            texto = f"{vertice.identificador} — {vertice.nome}"
            self.origem.addItem(texto, vertice.identificador)
            self.destino.addItem(texto, vertice.identificador)
        formulario.addRow("Origem", self.origem)
        formulario.addRow("Destino", self.destino)

        self.peso = QDoubleSpinBox()
        self.peso.setRange(0.0001, 1_000_000_000)
        self.peso.setDecimals(4)
        self.peso.setValue(1.0)
        self.peso.setSuffix(" km")
        formulario.addRow("Distância", self.peso)

        if aresta is not None:
            self.origem.setCurrentIndex(self.origem.findData(aresta.origem.identificador))
            self.destino.setCurrentIndex(self.destino.findData(aresta.destino.identificador))
            self.peso.setValue(aresta.peso)
            self.origem.setEnabled(False)
            self.destino.setEnabled(False)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        caixa = QVBoxLayout(self)
        caixa.addLayout(formulario)
        caixa.addWidget(botoes)

    def dados(self) -> dict:
        return {
            "origem": self.origem.currentData(),
            "destino": self.destino.currentData(),
            "peso": self.peso.value(),
        }

    def accept(self) -> None:  # noqa: D401 - contrato Qt
        dados = self.dados()
        if not dados["origem"] or not dados["destino"]:
            QMessageBox.warning(self, "Dados inválidos", "Selecione as duas pontas da rua.")
            return
        if dados["origem"] == dados["destino"]:
            QMessageBox.warning(self, "Dados inválidos", "Uma rua não pode ligar o local a ele mesmo.")
            return
        if dados["peso"] <= 0:
            QMessageBox.warning(self, "Dados inválidos", "A distância deve ser positiva.")
            return
        super().accept()


class DialogoArestaExistente(QDialog):
    """Seleciona uma aresta já cadastrada para alterar ou remover."""

    def __init__(self, grafo: Grafo, *, titulo: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setModal(True)
        self._arestas = grafo.listar_arestas()

        formulario = QFormLayout()
        self.aresta = QComboBox()
        for aresta in self._arestas:
            self.aresta.addItem(
                f"{aresta.origem.identificador} — {aresta.destino.identificador}  "
                f"({aresta.peso:g} km)",
                (aresta.origem.identificador, aresta.destino.identificador),
            )
        formulario.addRow("Rua", self.aresta)

        self.peso = QDoubleSpinBox()
        self.peso.setRange(0.0001, 1_000_000_000)
        self.peso.setDecimals(4)
        self.peso.setSuffix(" km")
        if self._arestas:
            self.peso.setValue(self._arestas[0].peso)
        self.aresta.currentIndexChanged.connect(self._aresta_alterada)
        formulario.addRow("Distância", self.peso)

        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        caixa = QVBoxLayout(self)
        caixa.addLayout(formulario)
        caixa.addWidget(botoes)

    def _aresta_alterada(self, indice: int) -> None:
        if 0 <= indice < len(self._arestas):
            self.peso.setValue(self._arestas[indice].peso)

    def dados(self) -> dict:
        extremos = self.aresta.currentData()
        origem, destino = extremos if extremos else (None, None)
        return {"origem": origem, "destino": destino, "peso": self.peso.value()}


