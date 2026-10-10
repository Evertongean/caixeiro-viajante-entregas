"""Ponto de entrada da interface gráfica do Delivery Route."""

from __future__ import annotations

import sys

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError as erro:  # Mensagem amigável para a primeira execução.
    raise SystemExit(
        "PySide6 não está instalado. Execute: "
        "python3 -m pip install -r requirements.txt"
    ) from erro

from ui.estilos import ESTILO_APLICACAO
from ui.janela_principal_3d import JanelaPrincipal3D


def main() -> int:
    """Inicializa o Qt e exibe a janela principal."""
    aplicacao = QApplication(sys.argv)
    aplicacao.setApplicationName("Delivery Route")
    aplicacao.setStyle("Fusion")
    aplicacao.setStyleSheet(ESTILO_APLICACAO)

    # A aplicação entregue é exclusivamente 3D. A janela histórica continua
    # importável para compatibilidade com projetos/testes antigos, mas não é
    # mais exposta pelo ponto de entrada.
    janela = JanelaPrincipal3D()
    janela.show()
    return aplicacao.exec()


if __name__ == "__main__":
    raise SystemExit(main())
