"""Enumeração exaustiva observável para demonstrações do TSP."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import permutations
from math import inf, isinf
from time import perf_counter

from algorithms.caixeiro_viajante import (
    ResultadoCaixeiroViajante,
    _concatenar_segmentos,
    _construir_segmentos,
    _selecionar_clientes,
    permutacoes_forca_bruta,
)
from algorithms.dijkstra import dijkstra_todos
from models.grafo import Grafo


LIMITE_DEMONSTRACAO_CLIENTES = 17
INTERVALO_PROGRESSO_SEGUNDOS = 0.10


@dataclass(frozen=True, slots=True)
class ProgressoForcaBruta:
    clientes: int
    total_permutacoes: int
    permutacoes_avaliadas: int
    tempo_decorrido: float
    melhor_custo: float | None
    melhor_ordem: tuple[str, ...]

    @property
    def taxa_por_segundo(self) -> float:
        if self.tempo_decorrido <= 0:
            return 0.0
        return self.permutacoes_avaliadas / self.tempo_decorrido


@dataclass(frozen=True, slots=True)
class ResultadoForcaBrutaTempoReal:
    deposito: str
    clientes: tuple[str, ...]
    total_permutacoes: int
    permutacoes_avaliadas: int
    tempo_decorrido: float
    concluida: bool
    motivo_interrupcao: str | None
    melhor_resultado: ResultadoCaixeiroViajante | None


def forca_bruta_tempo_real(
    grafo: Grafo,
    clientes: Iterable[str] | None = None,
    *,
    interromper: Callable[[], bool] | None = None,
    progresso: Callable[[ProgressoForcaBruta], None] | None = None,
    duracao_maxima_segundos: float | None = None,
    intervalo_progresso_segundos: float = INTERVALO_PROGRESSO_SEGUNDOS,
) -> ResultadoForcaBrutaTempoReal:
    """Avalia realmente cada permutação, sem poda ou contagem artificial."""
    if not isinstance(grafo, Grafo):
        raise TypeError("É necessário fornecer uma instância de Grafo.")
    if duracao_maxima_segundos is not None and duracao_maxima_segundos <= 0:
        raise ValueError("A duração máxima deve ser positiva.")
    if intervalo_progresso_segundos < 0:
        raise ValueError("O intervalo de progresso não pode ser negativo.")
    deposito = grafo.obter_deposito()
    if deposito is None:
        raise ValueError("O grafo não possui um depósito principal definido.")
    clientes_ids = _selecionar_clientes(grafo, clientes)
    quantidade = len(clientes_ids)
    if quantidade > LIMITE_DEMONSTRACAO_CLIENTES:
        raise ValueError(
            f"A demonstração aceita até {LIMITE_DEMONSTRACAO_CLIENTES} clientes."
        )

    deposito_id = deposito.identificador
    total = permutacoes_forca_bruta(quantidade)
    inicio = perf_counter()
    locais = [deposito_id, *clientes_ids]
    menores_caminhos = {origem: dijkstra_todos(grafo, origem) for origem in locais}
    inacessiveis = tuple(
        cliente
        for cliente in clientes_ids
        if isinf(menores_caminhos[deposito_id].distancias[cliente])
    )
    if inacessiveis:
        resultado_inviavel = ResultadoCaixeiroViajante(
            deposito=deposito_id,
            ordem_entregas=[],
            percurso_completo=[],
            distancia_total=inf,
            encontrada=False,
            sequencias_avaliadas=0,
            quantidade_clientes_atendidos=0,
            clientes_inacessiveis=inacessiveis,
        )
        return ResultadoForcaBrutaTempoReal(
            deposito_id,
            tuple(clientes_ids),
            total,
            0,
            perf_counter() - inicio,
            True,
            None,
            resultado_inviavel,
        )

    avaliadas = 0
    melhor_custo = inf
    melhor_ordem: tuple[str, ...] | None = None
    ultima_emissao = inicio
    motivo: str | None = None

    def emitir(agora: float) -> None:
        if progresso is None:
            return
        ordem = (
            (deposito_id, *melhor_ordem, deposito_id)
            if melhor_ordem is not None
            else ()
        )
        progresso(
            ProgressoForcaBruta(
                clientes=quantidade,
                total_permutacoes=total,
                permutacoes_avaliadas=avaliadas,
                tempo_decorrido=agora - inicio,
                melhor_custo=None if melhor_ordem is None else melhor_custo,
                melhor_ordem=ordem,
            )
        )

    emitir(inicio)
    for ordem in permutations(clientes_ids):
        agora = perf_counter()
        if interromper is not None and interromper():
            motivo = "usuario"
            break
        if (
            duracao_maxima_segundos is not None
            and agora - inicio >= duracao_maxima_segundos
        ):
            motivo = "tempo_limite"
            break

        paradas = (deposito_id, *ordem, deposito_id)
        custo = 0.0
        for origem, destino in zip(paradas, paradas[1:]):
            custo += menores_caminhos[origem].distancias[destino]
        avaliadas += 1
        if custo < melhor_custo:
            melhor_custo = custo
            melhor_ordem = ordem

        agora = perf_counter()
        if agora - ultima_emissao >= intervalo_progresso_segundos:
            emitir(agora)
            ultima_emissao = agora

    fim = perf_counter()
    concluida = avaliadas == total and motivo is None
    emitir(fim)

    melhor_resultado: ResultadoCaixeiroViajante | None = None
    if melhor_ordem is not None:
        ordem_entregas = [deposito_id, *melhor_ordem, deposito_id]
        segmentos = _construir_segmentos(ordem_entregas, menores_caminhos)
        melhor_resultado = ResultadoCaixeiroViajante(
            deposito=deposito_id,
            ordem_entregas=ordem_entregas,
            percurso_completo=_concatenar_segmentos(segmentos),
            distancia_total=melhor_custo,
            encontrada=True,
            sequencias_avaliadas=avaliadas,
            quantidade_clientes_atendidos=quantidade,
            segmentos=segmentos,
        )
    return ResultadoForcaBrutaTempoReal(
        deposito=deposito_id,
        clientes=tuple(clientes_ids),
        total_permutacoes=total,
        permutacoes_avaliadas=avaliadas,
        tempo_decorrido=fim - inicio,
        concluida=concluida,
        motivo_interrupcao=motivo,
        melhor_resultado=melhor_resultado,
    )


__all__ = [
    "INTERVALO_PROGRESSO_SEGUNDOS",
    "LIMITE_DEMONSTRACAO_CLIENTES",
    "ProgressoForcaBruta",
    "ResultadoForcaBrutaTempoReal",
    "forca_bruta_tempo_real",
]
