"""Painel de apresentação dos resultados dos algoritmos de rotas."""

from __future__ import annotations

from html import escape
from math import isinf

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from algorithms.caixeiro_viajante import ResultadoCaixeiroViajante
from algorithms.dijkstra import ResultadoDijkstra
from models.grafo import Grafo


class PainelResultados(QFrame):
    """Exibe resultados estruturados em cartões responsivos."""

    limpar_solicitado = Signal()
    _MENSAGEM_VAZIA = "Configure uma rota e clique em calcular para visualizar os resultados."

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("painelResultados")
        self.setMinimumHeight(148)
        self.setMaximumHeight(190)
        self._construir()
        self.limpar()

    def _construir(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        coluna_titulo = QVBoxLayout()
        titulo = QLabel("RESULTADOS DA ROTA")
        titulo.setObjectName("tituloPainel")
        coluna_titulo.addWidget(titulo)
        coluna_titulo.addStretch(1)
        self.botao_limpar = QPushButton("Limpar rota")
        self.botao_limpar.clicked.connect(self.limpar_solicitado.emit)
        coluna_titulo.addWidget(self.botao_limpar)
        layout.addLayout(coluna_titulo)

        separador = QFrame()
        separador.setFrameShape(QFrame.Shape.VLine)
        separador.setStyleSheet("color: #374151;")
        layout.addWidget(separador)

        self.pilha = QStackedWidget()
        self.estado_vazio = QLabel(self._MENSAGEM_VAZIA)
        self.estado_vazio.setObjectName("estadoVazio")
        self.estado_vazio.setWordWrap(True)
        self.pilha.addWidget(self.estado_vazio)

        conteudo = QWidget()
        layout_cartoes = QHBoxLayout(conteudo)
        layout_cartoes.setContentsMargins(0, 0, 0, 0)
        layout_cartoes.setSpacing(9)
        self.rotulo_status = self._criar_cartao(layout_cartoes, 1)
        self.rotulo_rota = self._criar_cartao(layout_cartoes, 3)
        self.rotulo_metricas = self._criar_cartao(layout_cartoes, 1)
        self.pilha.addWidget(conteudo)
        layout.addWidget(self.pilha, 1)

    @staticmethod
    def _criar_cartao(layout: QHBoxLayout, proporcao: int) -> QLabel:
        cartao = QFrame()
        cartao.setObjectName("cartaoResultado")
        layout_cartao = QVBoxLayout(cartao)
        layout_cartao.setContentsMargins(10, 8, 10, 8)
        rotulo = QLabel()
        rotulo.setWordWrap(True)
        rotulo.setTextFormat(Qt.TextFormat.RichText)
        layout_cartao.addWidget(rotulo)
        layout.addWidget(cartao, proporcao)
        return rotulo

    def limpar(self) -> None:
        self.pilha.setCurrentIndex(0)
        self.estado_vazio.setText(self._MENSAGEM_VAZIA)
        self.botao_limpar.setEnabled(False)
        self.rotulo_status.clear()
        self.rotulo_rota.clear()
        self.rotulo_metricas.clear()

    def exibir_calculando(self) -> None:
        self._mostrar_cartoes()
        self.rotulo_status.setText("<b>Processando</b><br>Calculando a melhor rota…")
        self.rotulo_rota.setText("Aguarde enquanto as possibilidades são avaliadas.")
        self.rotulo_metricas.clear()
        self.botao_limpar.setEnabled(False)

    def exibir_dijkstra(self, grafo: Grafo, resultado: ResultadoDijkstra) -> None:
        self._mostrar_cartoes()
        origem = grafo.obter_vertice(resultado.origem)
        destino = grafo.obter_vertice(resultado.destino)
        status = "Caminho encontrado" if resultado.encontrado else "Destino inalcançável"
        cor = "#10B981" if resultado.encontrado else "#F97316"
        caminho = " → ".join(resultado.caminho) if resultado.caminho else "Nenhum"
        distancia = (
            "Infinita"
            if isinf(resultado.distancia_total)
            else f"{resultado.distancia_total:g} km"
        )
        self.rotulo_status.setText(
            f"<b>Algoritmo</b><br>Dijkstra<br><br>"
            f"<font color='{cor}'><b>{status}</b></font>"
        )
        self.rotulo_rota.setText(
            f"<b>Origem / destino</b><br>"
            f"{escape(origem.nome)} ({escape(resultado.origem)}) → "
            f"{escape(destino.nome)} ({escape(resultado.destino)})<br><br>"
            f"<b>Caminho</b><br>{escape(caminho)}"
        )
        self.rotulo_metricas.setText(
            f"<b>Distância total</b><br><font size='+2'>{distancia}</font>"
        )
        self.botao_limpar.setEnabled(True)

    def exibir_tsp(
        self, grafo: Grafo, resultado: ResultadoCaixeiroViajante
    ) -> None:
        self._mostrar_cartoes()
        deposito = grafo.obter_vertice(resultado.deposito)
        status = "Rota ótima encontrada" if resultado.encontrada else "Rota inviável"
        cor = "#10B981" if resultado.encontrada else "#F97316"
        ordem = " → ".join(resultado.ordem_entregas) or "Nenhuma"
        percurso = " → ".join(resultado.percurso_completo) or "Nenhum"
        distancia = (
            "Infinita"
            if isinf(resultado.distancia_total)
            else f"{resultado.distancia_total:g} km"
        )
        self.rotulo_status.setText(
            f"<b>Algoritmo</b><br>Caixeiro Viajante<br>"
            f"Depósito: {escape(deposito.nome)}<br><br>"
            f"<font color='{cor}'><b>{status}</b></font>"
        )
        self.rotulo_rota.setText(
            f"<b>Ordem das entregas</b><br>{escape(ordem)}<br><br>"
            f"<b>Percurso completo</b><br>{escape(percurso)}"
            + (
                "<br><br><font color='#F97316'><b>Clientes inacessíveis:</b> "
                f"{escape(', '.join(resultado.clientes_inacessiveis))}</font>"
                if resultado.clientes_inacessiveis
                else ""
            )
        )
        self.rotulo_metricas.setText(
            f"<b>Distância total</b><br><font size='+2'>{distancia}</font><br><br>"
            f"Clientes: {resultado.quantidade_clientes_atendidos}<br>"
            f"Sequências: {resultado.sequencias_avaliadas}"
        )
        self.botao_limpar.setEnabled(True)

    def exibir_erro(self, mensagem: str) -> None:
        self._mostrar_cartoes()
        self.rotulo_status.setText(
            "<b>Não foi possível calcular</b><br>"
            "<font color='#F97316'>Verifique os dados da rota.</font>"
        )
        self.rotulo_rota.setText(escape(mensagem))
        self.rotulo_metricas.clear()
        self.botao_limpar.setEnabled(True)

    def exibir_grafo_alterado(self, mensagem: str = "Grafo alterado. Recalcule a rota.") -> None:
        """Informa que um resultado antigo deixou de ser válido."""
        self.pilha.setCurrentIndex(0)
        self.estado_vazio.setText(mensagem)
        self.rotulo_status.clear()
        self.rotulo_rota.clear()
        self.rotulo_metricas.clear()
        self.botao_limpar.setEnabled(False)

    def _mostrar_cartoes(self) -> None:
        self.pilha.setCurrentIndex(1)
