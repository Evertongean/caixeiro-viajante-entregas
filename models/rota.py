"""Resultado de rota compartilhado pela visualização e pela missão 3D."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from algorithms.caixeiro_viajante import (
    LIMITE_PADRAO_CLIENTES,
    caixeiro_viajante,
)
from algorithms.dijkstra import dijkstra
from models.grafo import TipoVertice
from models.projeto_cidade import ProjetoCidade


Ponto3D = tuple[float, float, float]


class AlgoritmoRota(str, Enum):
    DIJKSTRA = "dijkstra"
    TSP = "tsp"


class EstadoEspacial(str, Enum):
    COMPLETO = "completo"
    PARCIAL = "parcial"
    INDISPONIVEL = "indisponivel"


class RotaInacessivel(ValueError):
    """O grafo é válido, mas não contém uma rota para a solicitação."""


@dataclass(frozen=True, slots=True)
class SegmentoEspacialRota:
    indice: int
    origem: str
    destino: str
    peso: float
    pontos: tuple[Ponto3D, ...]
    confirmado_manualmente: bool

    @property
    def disponivel(self) -> bool:
        return len(self.pontos) >= 2


@dataclass(frozen=True, slots=True)
class RotaCalculada:
    """Estado imutável consumido pelo destaque visual e pelo modo Missão 3D."""

    algoritmo: AlgoritmoRota
    origem: str
    destino: str | None
    ordem_atendimento: tuple[str, ...]
    percurso_completo: tuple[str, ...]
    distancia_total: float
    segmentos_espaciais: tuple[SegmentoEspacialRota, ...]
    estado_espacial: EstadoEspacial
    arestas_pendentes: tuple[tuple[str, str], ...]
    clientes_selecionados: tuple[str, ...]

    @property
    def calibracao_completa(self) -> bool:
        return self.estado_espacial is EstadoEspacial.COMPLETO

    @property
    def pontos_espaciais(self) -> tuple[Ponto3D, ...]:
        pontos: list[Ponto3D] = []
        for segmento in self.segmentos_espaciais:
            if not segmento.disponivel:
                continue
            if pontos and pontos[-1] == segmento.pontos[0]:
                pontos.extend(segmento.pontos[1:])
            else:
                pontos.extend(segmento.pontos)
        return tuple(pontos)


def _segmentos_espaciais(
    projeto: ProjetoCidade, percurso: tuple[str, ...]
) -> tuple[
    tuple[SegmentoEspacialRota, ...],
    EstadoEspacial,
    tuple[tuple[str, str], ...],
]:
    segmentos: list[SegmentoEspacialRota] = []
    pendentes: list[tuple[str, str]] = []
    chaves_pendentes: set[tuple[str, str]] = set()
    for indice, (origem, destino) in enumerate(zip(percurso, percurso[1:])):
        geometria = projeto.geometria_rua(origem, destino)
        pontos = projeto.polilinha_rua(origem, destino)
        confirmado = False
        if geometria is not None:
            confirmado = bool(geometria.calibrada_manualmente and len(pontos) >= 2)
        if not confirmado:
            chave = projeto.chave_aresta(origem, destino)
            if chave not in chaves_pendentes:
                pendentes.append(chave)
                chaves_pendentes.add(chave)
        segmentos.append(
            SegmentoEspacialRota(
                indice=indice,
                origem=origem,
                destino=destino,
                peso=projeto.grafo.obter_distancia(origem, destino),
                pontos=pontos,
                confirmado_manualmente=confirmado,
            )
        )

    if not pendentes:
        estado = EstadoEspacial.COMPLETO
    elif segmentos and any(segmento.disponivel for segmento in segmentos):
        estado = EstadoEspacial.PARCIAL
    else:
        estado = EstadoEspacial.INDISPONIVEL
    return tuple(segmentos), estado, tuple(pendentes)


def _clientes_no_percurso(
    projeto: ProjetoCidade, percurso: tuple[str, ...]
) -> tuple[str, ...]:
    clientes: list[str] = []
    for identificador in percurso:
        vertice = projeto.grafo.obter_vertice(identificador)
        if vertice.tipo is TipoVertice.CLIENTE and identificador not in clientes:
            clientes.append(identificador)
    return tuple(clientes)


def calcular_dijkstra(
    projeto: ProjetoCidade, origem: str, destino: str
) -> RotaCalculada:
    if not isinstance(projeto, ProjetoCidade):
        raise TypeError("É necessário fornecer um ProjetoCidade.")
    resultado = dijkstra(projeto.grafo, origem, destino)
    if not resultado.encontrado:
        raise RotaInacessivel(
            f"O destino '{destino}' é inacessível a partir de '{origem}'."
        )
    percurso = tuple(resultado.caminho)
    segmentos, estado, pendentes = _segmentos_espaciais(projeto, percurso)
    return RotaCalculada(
        algoritmo=AlgoritmoRota.DIJKSTRA,
        origem=origem,
        destino=destino,
        ordem_atendimento=(),
        percurso_completo=percurso,
        distancia_total=resultado.distancia_total,
        segmentos_espaciais=segmentos,
        estado_espacial=estado,
        arestas_pendentes=pendentes,
        clientes_selecionados=_clientes_no_percurso(projeto, percurso),
    )


def calcular_tsp(
    projeto: ProjetoCidade,
    clientes: Iterable[str],
    *,
    limite_clientes: int = LIMITE_PADRAO_CLIENTES,
) -> RotaCalculada:
    if not isinstance(projeto, ProjetoCidade):
        raise TypeError("É necessário fornecer um ProjetoCidade.")
    if isinstance(clientes, (str, bytes)):
        raise TypeError("Os clientes devem ser fornecidos em uma coleção.")
    selecionados = list(clientes)
    resultado = caixeiro_viajante(
        projeto.grafo,
        selecionados,
        limite_clientes=limite_clientes,
    )
    if not resultado.encontrada:
        inacessiveis = ", ".join(resultado.clientes_inacessiveis)
        detalhe = f": {inacessiveis}" if inacessiveis else ""
        raise RotaInacessivel(f"Há clientes inacessíveis no grafo{detalhe}.")
    percurso = tuple(resultado.percurso_completo)
    segmentos, estado, pendentes = _segmentos_espaciais(projeto, percurso)
    return RotaCalculada(
        algoritmo=AlgoritmoRota.TSP,
        origem=resultado.deposito,
        destino=None,
        ordem_atendimento=tuple(resultado.ordem_entregas),
        percurso_completo=percurso,
        distancia_total=resultado.distancia_total,
        segmentos_espaciais=segmentos,
        estado_espacial=estado,
        arestas_pendentes=pendentes,
        clientes_selecionados=tuple(sorted(selecionados)),
    )


__all__ = [
    "AlgoritmoRota",
    "EstadoEspacial",
    "RotaCalculada",
    "RotaInacessivel",
    "SegmentoEspacialRota",
    "calcular_dijkstra",
    "calcular_tsp",
]
