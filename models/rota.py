"""Resultado de rota compartilhado pela visualização e pela missão 3D."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable

from algorithms.caixeiro_viajante import (
    CalculoTSPCancelado,
    LIMITE_HELD_KARP_CLIENTES,
    LIMITE_PADRAO_CLIENTES,
    caixeiro_viajante,
    held_karp,
    permutacoes_forca_bruta,
)
from algorithms.dijkstra import dijkstra
from algorithms.forca_bruta_tempo_real import (
    ProgressoForcaBruta,
    ResultadoForcaBrutaTempoReal,
    forca_bruta_tempo_real,
)
from models.grafo import TipoVertice
from models.projeto_cidade import ProjetoCidade


Ponto3D = tuple[float, float, float]


class AlgoritmoRota(str, Enum):
    DIJKSTRA = "dijkstra"
    TSP = "tsp"


class MetodoTSP(str, Enum):
    FORCA_BRUTA = "forca_bruta"
    FORCA_BRUTA_DEMONSTRACAO = "forca_bruta_demonstracao"
    HELD_KARP = "held_karp"

    @property
    def nome_exibicao(self) -> str:
        return {
            MetodoTSP.FORCA_BRUTA: "Força bruta (exato)",
            MetodoTSP.FORCA_BRUTA_DEMONSTRACAO: (
                "Força Bruta — Demonstração em Tempo Real"
            ),
            MetodoTSP.HELD_KARP: "Held–Karp (exato)",
        }[self]


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
    metodo_tsp: MetodoTSP | None = None
    permutacoes_teoricas: int = 0
    total_vertices_grafo: int = 0
    tempo_processamento_segundos: float | None = None
    permutacoes_avaliadas: int = 0
    busca_tsp_completa: bool = True

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
    metodo: MetodoTSP | str = MetodoTSP.FORCA_BRUTA,
    limite_clientes: int = LIMITE_PADRAO_CLIENTES,
    cancelado: Callable[[], bool] | None = None,
    progresso: Callable[[ProgressoForcaBruta], None] | None = None,
    duracao_maxima_segundos: float | None = None,
) -> RotaCalculada:
    if not isinstance(projeto, ProjetoCidade):
        raise TypeError("É necessário fornecer um ProjetoCidade.")
    if isinstance(clientes, (str, bytes)):
        raise TypeError("Os clientes devem ser fornecidos em uma coleção.")
    selecionados = list(clientes)
    try:
        metodo_tsp = MetodoTSP(metodo)
    except ValueError as erro:
        raise ValueError("Selecione um método TSP válido.") from erro
    resultado_demonstracao: ResultadoForcaBrutaTempoReal | None = None
    if metodo_tsp is MetodoTSP.FORCA_BRUTA:
        resultado = caixeiro_viajante(
            projeto.grafo,
            selecionados,
            limite_clientes=limite_clientes,
        )
    elif metodo_tsp is MetodoTSP.HELD_KARP:
        resultado = held_karp(
            projeto.grafo,
            selecionados,
            limite_clientes=LIMITE_HELD_KARP_CLIENTES,
            cancelado=cancelado,
        )
    else:
        resultado_demonstracao = forca_bruta_tempo_real(
            projeto.grafo,
            selecionados,
            interromper=cancelado,
            progresso=progresso,
            duracao_maxima_segundos=duracao_maxima_segundos,
        )
        resultado = resultado_demonstracao.melhor_resultado
        if resultado is None:
            raise CalculoTSPCancelado(
                "A busca foi interrompida antes de avaliar a primeira permutação."
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
        metodo_tsp=metodo_tsp,
        permutacoes_teoricas=permutacoes_forca_bruta(len(selecionados)),
        total_vertices_grafo=len(projeto.grafo.listar_vertices()),
        tempo_processamento_segundos=(
            resultado_demonstracao.tempo_decorrido
            if resultado_demonstracao is not None
            else None
        ),
        permutacoes_avaliadas=(
            resultado_demonstracao.permutacoes_avaliadas
            if resultado_demonstracao is not None
            else resultado.sequencias_avaliadas
            if metodo_tsp is MetodoTSP.FORCA_BRUTA
            else 0
        ),
        busca_tsp_completa=(
            resultado_demonstracao.concluida
            if resultado_demonstracao is not None
            else True
        ),
    )


def rota_de_resultado_forca_bruta(
    projeto: ProjetoCidade,
    resultado: ResultadoForcaBrutaTempoReal,
) -> RotaCalculada | None:
    """Converte o melhor resultado de um processo de demonstração para a UI."""
    if resultado.melhor_resultado is None:
        return None
    base = resultado.melhor_resultado
    percurso = tuple(base.percurso_completo)
    segmentos, estado, pendentes = _segmentos_espaciais(projeto, percurso)
    return RotaCalculada(
        algoritmo=AlgoritmoRota.TSP,
        origem=base.deposito,
        destino=None,
        ordem_atendimento=tuple(base.ordem_entregas),
        percurso_completo=percurso,
        distancia_total=base.distancia_total,
        segmentos_espaciais=segmentos,
        estado_espacial=estado,
        arestas_pendentes=pendentes,
        clientes_selecionados=resultado.clientes,
        metodo_tsp=MetodoTSP.FORCA_BRUTA_DEMONSTRACAO,
        permutacoes_teoricas=resultado.total_permutacoes,
        total_vertices_grafo=len(projeto.grafo.listar_vertices()),
        tempo_processamento_segundos=resultado.tempo_decorrido,
        permutacoes_avaliadas=resultado.permutacoes_avaliadas,
        busca_tsp_completa=resultado.concluida,
    )


__all__ = [
    "AlgoritmoRota",
    "MetodoTSP",
    "EstadoEspacial",
    "RotaCalculada",
    "RotaInacessivel",
    "SegmentoEspacialRota",
    "calcular_dijkstra",
    "calcular_tsp",
    "rota_de_resultado_forca_bruta",
    "CalculoTSPCancelado",
]
