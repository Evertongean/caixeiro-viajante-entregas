"""Ponto de entrada da nova interface desktop do Delivery Route."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError:
        print(
            "PySide6 não está instalado. Execute: "
            "python3 -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    from ui.janela_principal import JanelaPrincipal

    aplicacao = QApplication.instance() or QApplication(sys.argv)
    aplicacao.setApplicationName("Delivery Route")
    aplicacao.setOrganizationName("Delivery Route")
    janela = JanelaPrincipal()
    janela.show()
    return aplicacao.exec()


if __name__ == "__main__":
    raise SystemExit(main())
