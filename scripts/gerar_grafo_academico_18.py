#!/usr/bin/env python3
"""Gera o grafo acadêmico de 18 vértices sobre a malha viária aferida.

Os pesos abaixo foram transcritos da Figura 2 de Póvoa (2001). A distribuição
espacial é independente do desenho da figura: usa dispersão por distância na
rede para escolher 18 pontos distintos e Dijkstra geométrico para ligar cada
aresta somente por segmentos já confirmados da cidade atual.
"""

from __future__ import annotations

import argparse
import heapq
import math
import sys
from pathlib import Path


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from models.cenario_academico import CAMINHO_CENARIO_ACADEMICO_18  # noqa: E402
from models.grafo import Grafo, TipoVertice, Vertice  # noqa: E402
from models.projeto_cidade import (  # noqa: E402
    EstacionamentoVeiculo,
    GeometriaRua,
    ProjetoCidade,
    carregar_projeto_cidade,
    salvar_projeto_cidade,
)


ORIGEM_ESPACIAL = RAIZ_PROJETO / "delivery-route-cidade-completa-corrigida.json"
QUANTIDADE_VERTICES = 18

# Estrutura verificável e canônica: cada par aparece uma única vez, com o
# menor identificador numérico primeiro. São exatamente as 45 linhas da figura.
ARESTAS_ACADEMICAS_18 = (
    ("1", "2", 20.0),
    ("1", "8", 29.0),
    ("1", "12", 29.0),
    ("1", "13", 37.0),
    ("2", "3", 25.0),
    ("2", "8", 28.0),
    ("2", "12", 39.0),
    ("3", "4", 25.0),
    ("3", "8", 30.0),
    ("3", "13", 54.0),
    ("4", "5", 39.0),
    ("4", "6", 32.0),
    ("4", "7", 42.0),
    ("4", "9", 23.0),
    ("4", "10", 33.0),
    ("4", "14", 56.0),
    ("5", "6", 12.0),
    ("5", "7", 26.0),
    ("5", "10", 19.0),
    ("6", "7", 17.0),
    ("6", "10", 35.0),
    ("6", "11", 30.0),
    ("7", "11", 38.0),
    ("8", "12", 25.0),
    ("8", "13", 22.0),
    ("9", "10", 26.0),
    ("9", "13", 34.0),
    ("9", "14", 37.0),
    ("9", "16", 43.0),
    ("10", "11", 24.0),
    ("10", "14", 30.0),
    ("10", "15", 19.0),
    ("11", "15", 26.0),
    ("11", "18", 36.0),
    ("12", "13", 27.0),
    ("12", "16", 43.0),
    ("13", "14", 24.0),
    ("13", "16", 19.0),
    ("14", "15", 20.0),
    ("14", "16", 19.0),
    ("14", "17", 17.0),
    ("15", "17", 18.0),
    ("15", "18", 21.0),
    ("16", "17", 26.0),
    ("17", "18", 15.0),
)


def _comprimento(pontos: tuple[tuple[float, float, float], ...]) -> float:
    return sum(math.dist(a, b) for a, b in zip(pontos, pontos[1:]))


def _rede_espacial(
    base: ProjetoCidade,
) -> dict[str, list[tuple[str, float]]]:
    ids = [vertice.identificador for vertice in base.grafo.listar_vertices()]
    rede: dict[str, list[tuple[str, float]]] = {identificador: [] for identificador in ids}
    for aresta in base.grafo.listar_arestas():
        origem = aresta.origem.identificador
        destino = aresta.destino.identificador
        geometria = base.geometria_rua(origem, destino)
        pontos = base.polilinha_rua(origem, destino)
        if geometria is None or not geometria.calibrada_manualmente or len(pontos) < 2:
            raise ValueError(f"Trecho-base {origem} ↔ {destino} não está confirmado.")
        custo = _comprimento(pontos)
        rede[origem].append((destino, custo))
        rede[destino].append((origem, custo))
    return rede


def _dijkstra_rede(
    rede: dict[str, list[tuple[str, float]]], origem: str
) -> tuple[dict[str, float], dict[str, str]]:
    distancias = {identificador: math.inf for identificador in rede}
    anteriores: dict[str, str] = {}
    distancias[origem] = 0.0
    fila: list[tuple[float, str]] = [(0.0, origem)]
    while fila:
        distancia, atual = heapq.heappop(fila)
        if distancia != distancias[atual]:
            continue
        for vizinho, custo in rede[atual]:
            proposta = distancia + custo
            if proposta + 1e-12 < distancias[vizinho]:
                distancias[vizinho] = proposta
                anteriores[vizinho] = atual
                heapq.heappush(fila, (proposta, vizinho))
    return distancias, anteriores


def distribuir_vertices_automaticamente(
    base: ProjetoCidade,
    *,
    quantidade: int = QUANTIDADE_VERTICES,
) -> tuple[str, ...]:
    """Seleciona candidatos espalhados pela rede, mantendo D como depósito."""
    if quantidade < 1:
        raise ValueError("A quantidade de vértices deve ser positiva.")
    rede = _rede_espacial(base)
    if "D" not in rede:
        raise ValueError("A malha-base não possui o depósito espacial D.")
    if quantidade > len(rede):
        raise ValueError("A malha-base não possui candidatos suficientes.")
    distancias = {
        identificador: _dijkstra_rede(rede, identificador)[0]
        for identificador in rede
    }
    selecionados = ["D"]
    while len(selecionados) < quantidade:
        candidatos = [item for item in rede if item not in selecionados]
        candidatos.sort(
            key=lambda item: (
                -min(distancias[escolhido][item] for escolhido in selecionados),
                item,
            )
        )
        escolhido = candidatos[0]
        if math.isinf(min(distancias[item][escolhido] for item in selecionados)):
            raise ValueError("A malha-base possui componentes viários desconectados.")
        selecionados.append(escolhido)
    return tuple(selecionados)


def _caminho_rede(
    rede: dict[str, list[tuple[str, float]]], origem: str, destino: str
) -> tuple[str, ...]:
    distancias, anteriores = _dijkstra_rede(rede, origem)
    if math.isinf(distancias[destino]):
        raise ValueError(f"Não existe caminho viário entre {origem} e {destino}.")
    caminho = [destino]
    while caminho[-1] != origem:
        caminho.append(anteriores[caminho[-1]])
    caminho.reverse()
    return tuple(caminho)


def _polilinha_base(
    base: ProjetoCidade, caminho: tuple[str, ...]
) -> tuple[tuple[float, float, float], ...]:
    pontos: list[tuple[float, float, float]] = []
    for origem, destino in zip(caminho, caminho[1:]):
        trecho = base.polilinha_rua(origem, destino)
        if len(trecho) < 2:
            raise ValueError(f"Trecho-base ausente: {origem} ↔ {destino}.")
        for ponto in trecho:
            if not pontos or ponto != pontos[-1]:
                pontos.append(ponto)
    return tuple(pontos)


def _geometria_canonica(
    origem: str,
    destino: str,
    pontos: tuple[tuple[float, float, float], ...],
) -> tuple[tuple[str, str], GeometriaRua]:
    chave = ProjetoCidade.chave_aresta(origem, destino)
    orientados = pontos if origem == chave[0] else tuple(reversed(pontos))
    return chave, GeometriaRua(
        origem=chave[0],
        destino=chave[1],
        pontos_intermediarios=list(orientados[1:-1]),
        calibrada_manualmente=True,
    )


def criar_projeto_academico_18(
    origem_espacial: Path = ORIGEM_ESPACIAL,
) -> ProjetoCidade:
    """Constrói o grafo oficial e todas as 45 geometrias viárias."""
    base = carregar_projeto_cidade(origem_espacial)
    rede = _rede_espacial(base)
    candidatos = distribuir_vertices_automaticamente(base)
    vinculos = {
        str(indice): identificador_base
        for indice, identificador_base in enumerate(candidatos, start=1)
    }

    grafo = Grafo()
    posicoes: dict[str, tuple[float, float, float]] = {}
    for indice in range(1, QUANTIDADE_VERTICES + 1):
        identificador = str(indice)
        posicao = base.posicoes[vinculos[identificador]]
        tipo = TipoVertice.DEPOSITO if indice == 1 else TipoVertice.CLIENTE
        nome = "Depósito central" if indice == 1 else f"Cliente {indice}"
        grafo.adicionar_vertice(
            Vertice(identificador, nome, tipo, posicao[0], posicao[2])
        )
        posicoes[identificador] = posicao

    ruas: dict[tuple[str, str], GeometriaRua] = {}
    for origem, destino, peso in ARESTAS_ACADEMICAS_18:
        grafo.adicionar_aresta(origem, destino, peso)
        caminho_base = _caminho_rede(
            rede, vinculos[origem], vinculos[destino]
        )
        pontos = _polilinha_base(base, caminho_base)
        if pontos[0] != posicoes[origem] or pontos[-1] != posicoes[destino]:
            raise ValueError(f"Extremos espaciais incorretos em {origem} ↔ {destino}.")
        chave, geometria = _geometria_canonica(origem, destino, pontos)
        ruas[chave] = geometria

    estacionamento_base = base.estacionamento_inicial
    if estacionamento_base is None or estacionamento_base.deposito != "D":
        raise ValueError("A malha-base não contém a vaga validada do depósito D.")
    estacionamento = EstacionamentoVeiculo(
        deposito="1",
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
        fator_km_por_unidade=1.0,
        escala_km_validada=False,
        estacionamento_inicial=estacionamento,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origem", type=Path, default=ORIGEM_ESPACIAL)
    parser.add_argument("--destino", type=Path, default=CAMINHO_CENARIO_ACADEMICO_18)
    argumentos = parser.parse_args()
    projeto = criar_projeto_academico_18(argumentos.origem.resolve())
    destino = salvar_projeto_cidade(projeto, argumentos.destino.resolve())
    print(
        f"Cenário de 18 vértices criado em {destino} "
        f"({len(projeto.grafo.listar_arestas())} arestas validadas)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
