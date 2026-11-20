"""Acesso ao cenário acadêmico opcional distribuído com a aplicação."""

from __future__ import annotations

from pathlib import Path

from models.projeto_cidade import ProjetoCidade, carregar_projeto_cidade


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
CAMINHO_CENARIO_ACADEMICO = (
    RAIZ_PROJETO / "assets" / "config" / "grafo-academico-5-vertices.json"
)
CAMINHO_CENARIO_ACADEMICO_18 = (
    RAIZ_PROJETO / "assets" / "config" / "grafo-academico-18-vertices.json"
)


def carregar_cenario_academico() -> ProjetoCidade:
    """Carrega uma nova instância do exemplo, sem alterar o cenário inicial."""
    return carregar_projeto_cidade(CAMINHO_CENARIO_ACADEMICO)


def carregar_cenario_academico_18() -> ProjetoCidade:
    """Carrega o grafo de Póvoa com 18 vértices sobre a cidade existente."""
    return carregar_projeto_cidade(CAMINHO_CENARIO_ACADEMICO_18)


__all__ = [
    "CAMINHO_CENARIO_ACADEMICO",
    "CAMINHO_CENARIO_ACADEMICO_18",
    "carregar_cenario_academico",
    "carregar_cenario_academico_18",
]
