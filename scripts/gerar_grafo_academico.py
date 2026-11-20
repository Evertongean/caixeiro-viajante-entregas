#!/usr/bin/env python3
"""Gera o grafo acadêmico usando somente vias já aferidas no cidade.glb."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from models.cenario_academico import CAMINHO_CENARIO_ACADEMICO  # noqa: E402
from models.grafo import Grafo, TipoVertice, Vertice  # noqa: E402
from models.projeto_cidade import (  # noqa: E402
    EstacionamentoVeiculo,
    GeometriaRua,
    ProjetoCidade,
    carregar_projeto_cidade,
    salvar_projeto_cidade,
)


ORIGEM_ESPACIAL = RAIZ_PROJETO / "delivery-route-cidade-completa-corrigida.json"

# Os cinco pontos são serviços já aferidos sobre o asfalto do GLB. Os IDs do
# arquivo acadêmico permanecem exatamente 1..5; os IDs à direita existem
# somente na malha-base usada para reproduzir as polilinhas.
VERTICES_ACADEMICOS = {
    "1": ("D", "Depósito central", TipoVertice.DEPOSITO),
    "2": ("A", "Cliente 1", TipoVertice.CLIENTE),
    "3": ("B", "Cliente 2", TipoVertice.CLIENTE),
    "4": ("C", "Cliente 3", TipoVertice.CLIENTE),
    "5": ("E", "Cliente 4", TipoVertice.CLIENTE),
}

ARESTAS_ACADEMICAS = (
    ("1", "2", 2.0),
    ("1", "4", 3.0),
    ("1", "5", 6.0),
    ("2", "3", 4.0),
    ("2", "4", 3.0),
    ("3", "4", 7.0),
    ("3", "5", 3.0),
    ("4", "5", 3.0),
)

# Cada sequência percorre segmentos da malha viária aferida. Cruzamentos e o
# ponto F viram apenas controles geométricos: eles não são vértices do grafo
# matemático acadêmico e não criam atalhos ou novas arestas.
ROTAS_ESPACIAIS = {
    ("1", "2"): ("D", "X13", "X8", "X22", "X21", "X2", "A"),
    ("1", "4"): ("D", "X13", "X12", "C"),
    ("1", "5"): ("D", "X14", "X15", "X10", "X11", "E"),
    ("2", "3"): ("A", "X2", "X21", "X22", "X8", "X13", "D", "X14", "X19", "B"),
    ("2", "4"): ("A", "X1", "X7", "C"),
    ("3", "4"): ("B", "X19", "X18", "X17", "X12", "C"),
    ("3", "5"): ("B", "X19", "X14", "X15", "X16", "X11", "E"),
    ("4", "5"): ("C", "X7", "X8", "F", "X9", "X10", "X11", "E"),
}


def _polilinha_base(
    base: ProjetoCidade, caminho: tuple[str, ...]
) -> tuple[tuple[float, float, float], ...]:
    pontos: list[tuple[float, float, float]] = []
    for origem, destino in zip(caminho, caminho[1:]):
        geometria = base.geometria_rua(origem, destino)
        trecho = base.polilinha_rua(origem, destino)
        if geometria is None or not geometria.calibrada_manualmente or len(trecho) < 2:
            raise ValueError(
                f"O trecho espacial {origem} ↔ {destino} não está confirmado."
            )
        if pontos and pontos[-1] != trecho[0]:
            raise ValueError(f"A rota espacial se desconecta antes de {destino}.")
        pontos.extend(trecho[1:] if pontos else trecho)
    return tuple(pontos)


def criar_projeto_academico(
    origem_espacial: Path = ORIGEM_ESPACIAL,
) -> ProjetoCidade:
    """Constrói os cinco vértices e as oito arestas com pesos independentes."""
    base = carregar_projeto_cidade(origem_espacial)
    grafo = Grafo()
    posicoes: dict[str, tuple[float, float, float]] = {}

    for identificador, (id_base, nome, tipo) in VERTICES_ACADEMICOS.items():
        try:
            posicao = base.posicoes[id_base]
        except KeyError as erro:
            raise ValueError(
                f"A malha-base não contém a posição espacial de {id_base}."
            ) from erro
        grafo.adicionar_vertice(
            Vertice(identificador, nome, tipo, posicao[0], posicao[2])
        )
        posicoes[identificador] = posicao

    ruas: dict[tuple[str, str], GeometriaRua] = {}
    for origem, destino, peso in ARESTAS_ACADEMICAS:
        grafo.adicionar_aresta(origem, destino, peso)
        caminho = ROTAS_ESPACIAIS[(origem, destino)]
        pontos = _polilinha_base(base, caminho)
        if pontos[0] != posicoes[origem] or pontos[-1] != posicoes[destino]:
            raise ValueError(
                f"A rota espacial de {origem} ↔ {destino} possui extremos incorretos."
            )
        chave = ProjetoCidade.chave_aresta(origem, destino)
        ruas[chave] = GeometriaRua(
            origem=chave[0],
            destino=chave[1],
            pontos_intermediarios=list(pontos[1:-1]),
            calibrada_manualmente=True,
        )

    estacionamento_base = base.estacionamento_inicial
    if estacionamento_base is None or estacionamento_base.deposito != "D":
        raise ValueError("A malha-base não contém a vaga validada do depósito.")
    estacionamento = EstacionamentoVeiculo(
        deposito="1",
        # A vaga e o depósito têm o mesmo ponto horizontal. Usar a altura já
        # normalizada da malha evita uma diferença numérica subatômica no fim
        # da missão, sem alterar a localização aferida da vaga.
        posicao=posicoes["1"],
        orientacao_graus=estacionamento_base.orientacao_graus,
        superficie=estacionamento_base.superficie,
        validado=estacionamento_base.validado,
    )
    return ProjetoCidade(
        grafo=grafo,
        posicoes=posicoes,
        ruas=ruas,
        superficies=dict(base.superficies),
        modelo_cidade=base.modelo_cidade,
        modelo_carro=base.modelo_carro,
        # Mantido apenas por compatibilidade do formato. Os pesos acadêmicos
        # acima não são calculados nem sobrescritos por este fator.
        fator_km_por_unidade=1.0,
        escala_km_validada=False,
        estacionamento_inicial=estacionamento,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origem", type=Path, default=ORIGEM_ESPACIAL)
    parser.add_argument("--destino", type=Path, default=CAMINHO_CENARIO_ACADEMICO)
    argumentos = parser.parse_args()
    projeto = criar_projeto_academico(argumentos.origem.resolve())
    destino = salvar_projeto_cidade(projeto, argumentos.destino.resolve())
    print(f"Cenário acadêmico criado em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
