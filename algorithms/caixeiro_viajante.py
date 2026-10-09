"""Solução exata do Caixeiro Viajante por força bruta.

As permutações definem somente a ordem das entregas. O deslocamento real entre
duas paradas é obtido com Dijkstra, podendo incluir cruzamentos e outros
clientes como pontos intermediários.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import permutations
from math import inf, isinf

from .dijkstra import ResultadoDijkstraTodos, dijkstra_todos
from models.grafo import Grafo, TipoVertice


LIMITE_PADRAO_CLIENTES = 8


@dataclass(frozen=True, slots=True)
class SegmentoRota:
    """Menor caminho percorrido entre duas paradas de atendimento."""

    origem: str
    destino: str
    caminho: list[str]
    distancia: float


@dataclass(frozen=True, slots=True)
class ResultadoCaixeiroViajante:
    """Resultado estruturado de uma execução exata do TSP.

    Se não houver rota viável, ``encontrada`` será falso, a ordem e o percurso
    serão vazios e a distância será infinita.
    """

    deposito: str
    ordem_entregas: list[str]
    percurso_completo: list[str]
    distancia_total: float
    encontrada: bool
    sequencias_avaliadas: int
    quantidade_clientes_atendidos: int
    segmentos: tuple[SegmentoRota, ...] = ()
    clientes_inacessiveis: tuple[str, ...] = ()


def caixeiro_viajante(
    grafo: Grafo,
    clientes: Iterable[str] | None = None,
    *,
    limite_clientes: int = LIMITE_PADRAO_CLIENTES,
) -> ResultadoCaixeiroViajante:
    """Encontra a rota ótima para todos ou para alguns clientes.

    ``clientes=None`` seleciona todos os vértices do tipo cliente. Uma coleção
    vazia seleciona explicitamente zero clientes. O limite é verificado antes
    de qualquer cálculo fatorial e pode ser configurado por chamada.
    """
    if not isinstance(grafo, Grafo):
        raise TypeError("É necessário fornecer uma instância de Grafo.")
    if (
        not isinstance(limite_clientes, int)
        or isinstance(limite_clientes, bool)
        or limite_clientes < 0
    ):
        raise ValueError("O limite de clientes deve ser um inteiro não negativo.")

    deposito = grafo.obter_deposito()
    if deposito is None:
        raise ValueError("O grafo não possui um depósito principal definido.")

    clientes_ids = _selecionar_clientes(grafo, clientes)
    if len(clientes_ids) > limite_clientes:
        raise ValueError(
            f"O limite de {limite_clientes} clientes para a solução exata "
            f"foi ultrapassado: {len(clientes_ids)} selecionados."
        )

    deposito_id = deposito.identificador
    if not clientes_ids:
        return ResultadoCaixeiroViajante(
            deposito=deposito_id,
            ordem_entregas=[deposito_id],
            percurso_completo=[deposito_id],
            distancia_total=0.0,
            encontrada=True,
            sequencias_avaliadas=1,
            quantidade_clientes_atendidos=0,
        )

    # Uma execução por local relevante fornece todas as distâncias e caminhos
    # necessários, sem recalcular Dijkstra para cada permutação.
    locais_relevantes = [deposito_id, *clientes_ids]
    menores_caminhos = {
        origem: dijkstra_todos(grafo, origem) for origem in locais_relevantes
    }
    clientes_inacessiveis = tuple(
        cliente
        for cliente in clientes_ids
        if isinf(menores_caminhos[deposito_id].distancias[cliente])
    )
    if clientes_inacessiveis:
        return ResultadoCaixeiroViajante(
            deposito=deposito_id,
            ordem_entregas=[],
            percurso_completo=[],
            distancia_total=inf,
            encontrada=False,
            sequencias_avaliadas=0,
            quantidade_clientes_atendidos=0,
            clientes_inacessiveis=clientes_inacessiveis,
        )

    melhor_ordem: tuple[str, ...] | None = None
    melhor_distancia = inf
    sequencias_avaliadas = 0

    # A lista de clientes é ordenada previamente; em empates, a primeira
    # permutação lexicográfica permanece como resultado determinístico.
    for ordem_clientes in permutations(clientes_ids):
        sequencias_avaliadas += 1
        paradas = (deposito_id, *ordem_clientes, deposito_id)
        distancia = sum(
            menores_caminhos[origem].distancias[destino]
            for origem, destino in zip(paradas, paradas[1:])
        )
        if distancia < melhor_distancia:
            melhor_distancia = distancia
            melhor_ordem = ordem_clientes

    # Com clientes alcançáveis, permutations sempre produz ao menos uma ordem.
    if melhor_ordem is None:  # pragma: no cover - proteção defensiva
        return ResultadoCaixeiroViajante(
            deposito=deposito_id,
            ordem_entregas=[],
            percurso_completo=[],
            distancia_total=inf,
            encontrada=False,
            sequencias_avaliadas=sequencias_avaliadas,
            quantidade_clientes_atendidos=0,
        )

    ordem_entregas = [deposito_id, *melhor_ordem, deposito_id]
    segmentos = _construir_segmentos(ordem_entregas, menores_caminhos)
    percurso_completo = _concatenar_segmentos(segmentos)

    return ResultadoCaixeiroViajante(
        deposito=deposito_id,
        ordem_entregas=ordem_entregas,
        percurso_completo=percurso_completo,
        distancia_total=melhor_distancia,
        encontrada=True,
        sequencias_avaliadas=sequencias_avaliadas,
        quantidade_clientes_atendidos=len(clientes_ids),
        segmentos=segmentos,
    )


def _selecionar_clientes(
    grafo: Grafo, clientes: Iterable[str] | None
) -> list[str]:
    if clientes is None:
        selecionados = [cliente.identificador for cliente in grafo.listar_clientes()]
    else:
        if isinstance(clientes, (str, bytes)):
            raise TypeError("Os clientes devem ser fornecidos em uma coleção.")
        try:
            selecionados = list(clientes)
        except TypeError as erro:
            raise TypeError("Os clientes devem ser fornecidos em uma coleção.") from erro

    if any(
        not isinstance(identificador, str) or not identificador.strip()
        for identificador in selecionados
    ):
        raise TypeError("Os identificadores dos clientes devem ser textos não vazios.")
    if len(selecionados) != len(set(selecionados)):
        raise ValueError("A seleção contém identificadores de clientes duplicados.")

    for identificador in selecionados:
        vertice = grafo.obter_vertice(identificador)
        if vertice.tipo is not TipoVertice.CLIENTE:
            raise ValueError(
                f"O vértice '{identificador}' não possui o tipo cliente."
            )
    return sorted(selecionados)


def _construir_segmentos(
    ordem_entregas: list[str],
    menores_caminhos: dict[str, ResultadoDijkstraTodos],
) -> tuple[SegmentoRota, ...]:
    segmentos: list[SegmentoRota] = []
    for origem, destino in zip(ordem_entregas, ordem_entregas[1:]):
        resultado_origem = menores_caminhos[origem]
        segmentos.append(
            SegmentoRota(
                origem=origem,
                destino=destino,
                caminho=resultado_origem.reconstruir_caminho(destino),
                distancia=resultado_origem.distancias[destino],
            )
        )
    return tuple(segmentos)


def _concatenar_segmentos(segmentos: tuple[SegmentoRota, ...]) -> list[str]:
    percurso = list(segmentos[0].caminho)
    for segmento in segmentos[1:]:
        # O primeiro vértice já é o último do segmento anterior.
        percurso.extend(segmento.caminho[1:])
    return percurso
