"""Algoritmo de Dijkstra para caminhos mínimos no Delivery Route.

A implementação usa somente a biblioteca padrão e lê o grafo pela sua API
pública. Nenhuma estrutura do grafo é modificada durante o cálculo.
"""

from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from math import inf, isinf

from models.grafo import Grafo


@dataclass(frozen=True, slots=True)
class ArestaAnalisada:
    """Aresta examinada durante uma iteração do algoritmo."""

    origem: str
    destino: str
    peso: float


@dataclass(frozen=True, slots=True)
class AtualizacaoDistancia:
    """Alteração feita durante o relaxamento de uma aresta."""

    vertice: str
    distancia_anterior: float
    nova_distancia: float
    predecessor: str


@dataclass(frozen=True, slots=True)
class EtapaDijkstra:
    """Fotografia de uma iteração, própria para visualização posterior."""

    vertice_atual: str
    distancia_atual: float
    distancias: dict[str, float]
    vertices_processados: frozenset[str]
    predecessores: dict[str, str]
    arestas_analisadas: tuple[ArestaAnalisada, ...]
    atualizacoes: tuple[AtualizacaoDistancia, ...]
    numero: int = 0
    fase: str = "iteracao"
    descricao: str = ""


@dataclass(frozen=True, slots=True)
class ResultadoDijkstra:
    """Resultado do menor caminho entre uma origem e um destino.

    Quando o destino é inalcançável, ``encontrado`` é falso, ``caminho`` é uma
    lista vazia e ``distancia_total`` é infinito.
    """

    origem: str
    destino: str
    caminho: list[str]
    distancia_total: float
    encontrado: bool
    etapas: tuple[EtapaDijkstra, ...] = ()


@dataclass(frozen=True, slots=True)
class ResultadoDijkstraTodos:
    """Menores distâncias e predecessores calculados a partir de uma origem."""

    origem: str
    distancias: dict[str, float]
    predecessores: dict[str, str]
    etapas: tuple[EtapaDijkstra, ...] = ()

    def reconstruir_caminho(self, destino: str) -> list[str]:
        """Reconstrói o caminho até um destino; retorna vazio se inalcançável."""
        if destino not in self.distancias:
            raise KeyError(f"Não existe vértice com o identificador '{destino}'.")
        if isinf(self.distancias[destino]):
            return []
        return _reconstruir_caminho(self.origem, destino, self.predecessores)

    def resultado_para(self, destino: str) -> ResultadoDijkstra:
        """Converte parte do cálculo completo em um resultado origem-destino."""
        caminho = self.reconstruir_caminho(destino)
        return ResultadoDijkstra(
            origem=self.origem,
            destino=destino,
            caminho=caminho,
            distancia_total=self.distancias[destino],
            encontrado=bool(caminho),
            etapas=self.etapas,
        )


@dataclass(frozen=True, slots=True)
class _ExecucaoDijkstra:
    """Dados internos compartilhados pelas duas formas de executar Dijkstra."""

    distancias: dict[str, float]
    predecessores: dict[str, str]
    etapas: tuple[EtapaDijkstra, ...]


def dijkstra(
    grafo: Grafo,
    origem: str,
    destino: str,
    *,
    registrar_etapas: bool = False,
) -> ResultadoDijkstra:
    """Calcula o menor caminho entre ``origem`` e ``destino``.

    A execução termina assim que o destino é retirado da fila com sua distância
    definitiva. Use :func:`dijkstra_todos` quando forem necessárias as menores
    distâncias para todos os vértices.
    """
    _validar_grafo(grafo)
    grafo.obter_vertice(origem)
    grafo.obter_vertice(destino)

    execucao = _executar(
        grafo,
        origem,
        destino=destino,
        registrar_etapas=registrar_etapas,
    )
    distancia = execucao.distancias[destino]
    caminho = (
        []
        if isinf(distancia)
        else _reconstruir_caminho(origem, destino, execucao.predecessores)
    )
    return ResultadoDijkstra(
        origem=origem,
        destino=destino,
        caminho=caminho,
        distancia_total=distancia,
        encontrado=bool(caminho),
        etapas=execucao.etapas,
    )


def dijkstra_todos(
    grafo: Grafo,
    origem: str,
    *,
    registrar_etapas: bool = False,
) -> ResultadoDijkstraTodos:
    """Calcula os menores caminhos da origem para todos os vértices.

    O dicionário de distâncias inclui também vértices inalcançáveis, associados
    a ``math.inf``. Seus caminhos reconstruídos são listas vazias.
    """
    _validar_grafo(grafo)
    grafo.obter_vertice(origem)
    execucao = _executar(
        grafo,
        origem,
        destino=None,
        registrar_etapas=registrar_etapas,
    )
    return ResultadoDijkstraTodos(
        origem=origem,
        distancias=execucao.distancias,
        predecessores=execucao.predecessores,
        etapas=execucao.etapas,
    )


def _executar(
    grafo: Grafo,
    origem: str,
    *,
    destino: str | None,
    registrar_etapas: bool,
) -> _ExecucaoDijkstra:
    identificadores = [
        vertice.identificador for vertice in grafo.listar_vertices()
    ]
    distancias = {identificador: inf for identificador in identificadores}
    distancias[origem] = 0.0
    predecessores: dict[str, str] = {}
    processados: set[str] = set()
    fila: list[tuple[float, str]] = [(0.0, origem)]
    etapas: list[EtapaDijkstra] = []

    while fila:
        distancia_atual, atual = heappop(fila)

        # Entradas antigas permanecem no heap após uma melhora e são ignoradas.
        if atual in processados or distancia_atual > distancias[atual]:
            continue

        processados.add(atual)
        arestas_analisadas: list[ArestaAnalisada] = []
        atualizacoes: list[AtualizacaoDistancia] = []

        for vizinho, peso in grafo.obter_vizinhos(atual).items():
            arestas_analisadas.append(ArestaAnalisada(atual, vizinho, peso))
            nova_distancia = distancia_atual + peso
            if nova_distancia >= distancias[vizinho]:
                continue

            distancia_anterior = distancias[vizinho]
            distancias[vizinho] = nova_distancia
            predecessores[vizinho] = atual
            heappush(fila, (nova_distancia, vizinho))
            atualizacoes.append(
                AtualizacaoDistancia(
                    vertice=vizinho,
                    distancia_anterior=distancia_anterior,
                    nova_distancia=nova_distancia,
                    predecessor=atual,
                )
            )

        if registrar_etapas:
            descricao = _descrever_etapa(
                atual, distancia_atual, arestas_analisadas, atualizacoes
            )
            etapas.append(
                EtapaDijkstra(
                    vertice_atual=atual,
                    distancia_atual=distancia_atual,
                    distancias=distancias.copy(),
                    vertices_processados=frozenset(processados),
                    predecessores=predecessores.copy(),
                    arestas_analisadas=tuple(arestas_analisadas),
                    atualizacoes=tuple(atualizacoes),
                    numero=len(etapas) + 1,
                    fase="iteracao",
                    descricao=descricao,
                )
            )

        if atual == destino:
            break

    return _ExecucaoDijkstra(
        distancias=distancias,
        predecessores=predecessores,
        etapas=tuple(etapas),
    )


def _reconstruir_caminho(
    origem: str, destino: str, predecessores: dict[str, str]
) -> list[str]:
    caminho = [destino]
    atual = destino
    while atual != origem:
        atual = predecessores[atual]
        caminho.append(atual)
    caminho.reverse()
    return caminho


def _validar_grafo(grafo: Grafo) -> None:
    if not isinstance(grafo, Grafo):
        raise TypeError("É necessário fornecer uma instância de Grafo.")


def _descrever_etapa(
    atual: str,
    distancia: float,
    arestas: list[ArestaAnalisada],
    atualizacoes: list[AtualizacaoDistancia],
) -> str:
    """Produz uma explicação curta sem mover a lógica do algoritmo para a UI."""
    distancia_texto = "infinita" if isinf(distancia) else f"{distancia:g}"
    if atualizacoes:
        melhorias = ", ".join(
            f"{atualizacao.vertice}={atualizacao.nova_distancia:g}"
            for atualizacao in atualizacoes
        )
        return (
            f"Processando {atual} (distância {distancia_texto}). "
            f"Relaxamento: {melhorias}."
        )
    if arestas:
        return (
            f"Processando {atual} (distância {distancia_texto}); "
            "nenhuma distância foi melhorada."
        )
    return f"Processando {atual} (distância {distancia_texto}); sem vizinhos novos."
