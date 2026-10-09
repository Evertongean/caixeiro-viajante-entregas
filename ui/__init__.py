"""Interface gráfica desktop do Delivery Route."""

__all__ = ["JanelaPrincipal"]


def __getattr__(nome: str):
    """Adia a importação do Qt até a janela ser efetivamente solicitada."""
    if nome == "JanelaPrincipal":
        from .janela_principal import JanelaPrincipal

        return JanelaPrincipal
    raise AttributeError(nome)
