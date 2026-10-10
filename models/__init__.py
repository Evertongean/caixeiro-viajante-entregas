"""Modelos de domínio do Delivery Route."""

from .grafo import Aresta, Grafo, TipoVertice, Vertice, criar_cenario_exemplo
from .persistencia import (
    ErroPersistencia,
    carregar_grafo,
    grafo_de_dados,
    grafo_para_dados,
    salvar_grafo,
    validar_grafo,
)
from .projeto_cidade import (
    ClassificacaoSuperficie,
    GeometriaRua,
    ProjetoCidade,
    carregar_projeto_cidade,
    salvar_projeto_cidade,
)

__all__ = [
    "Aresta",
    "Grafo",
    "TipoVertice",
    "Vertice",
    "criar_cenario_exemplo",
    "ErroPersistencia",
    "carregar_grafo",
    "grafo_de_dados",
    "grafo_para_dados",
    "salvar_grafo",
    "validar_grafo",
    "ClassificacaoSuperficie",
    "GeometriaRua",
    "ProjetoCidade",
    "carregar_projeto_cidade",
    "salvar_projeto_cidade",
]
