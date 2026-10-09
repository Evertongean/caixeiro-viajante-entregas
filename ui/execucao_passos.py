"""Adapta os históricos dos algoritmos para a navegação manual da interface.

Este módulo não recalcula Dijkstra nem TSP. Ele cria uma fotografia do grafo,
solicita o histórico estruturado aos módulos de algoritmo e transforma cada
registro em um passo visual comum às duas representações da cidade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import inf, isinf

from algorithms.caixeiro_viajante import (
    ResultadoCaixeiroViajante,
    caixeiro_viajante,
)
from algorithms.dijkstra import ResultadoDijkstra, dijkstra
from models.grafo import Grafo
from models.persistencia import grafo_de_dados, grafo_para_dados


@dataclass(frozen=True, slots=True)
class PassoExecucao:
    """Estado visual independente da implementação gráfica específica."""

    numero: int
    descricao: str
    vertice_atual: str | None = None
    vertices_processados: frozenset[str] = frozenset()
    arestas_avaliadas: tuple[tuple[str, str], ...] = ()
    caminho_final: tuple[str, ...] = ()
    distancias: dict[str, float] = field(default_factory=dict)
    predecessores: dict[str, str] = field(default_factory=dict)
    ordem_avaliada: tuple[str, ...] = ()
    distancia_avaliada: float | None = None
    melhor_ordem: tuple[str, ...] = ()
    melhor_distancia: float = inf
    concluido: bool = False


class SessaoPassoAPasso:
    """Histórico navegável calculado sobre uma fotografia imutável do grafo."""

    def __init__(
        self,
        algoritmo: str,
        grafo_snapshot: Grafo,
        assinatura: dict,
        resultado: ResultadoDijkstra | ResultadoCaixeiroViajante,
        passos: tuple[PassoExecucao, ...],
    ) -> None:
        self.algoritmo = algoritmo
        self.grafo_snapshot = grafo_snapshot
        self._assinatura = assinatura
        self.resultado = resultado
        self.passos = passos
        self.indice_atual = 0 if passos else -1

    @classmethod
    def criar_dijkstra(
        cls, grafo: Grafo, origem: str, destino: str
    ) -> "SessaoPassoAPasso":
        snapshot, assinatura = _fotografar(grafo)
        resultado = dijkstra(snapshot, origem, destino, registrar_etapas=True)
        passos = _passos_dijkstra(snapshot, resultado)
        return cls("dijkstra", snapshot, assinatura, resultado, passos)

    @classmethod
    def criar_tsp(
        cls, grafo: Grafo, clientes: list[str]
    ) -> "SessaoPassoAPasso":
        snapshot, assinatura = _fotografar(grafo)
        resultado = caixeiro_viajante(
            snapshot, clientes, registrar_etapas=True
        )
        passos = _passos_tsp(resultado)
        return cls("tsp", snapshot, assinatura, resultado, passos)

    @property
    def total(self) -> int:
        return len(self.passos)

    @property
    def passo_atual(self) -> PassoExecucao | None:
        if 0 <= self.indice_atual < self.total:
            return self.passos[self.indice_atual]
        return None

    @property
    def finalizada(self) -> bool:
        passo = self.passo_atual
        return passo is not None and passo.concluido

    def avancar(self) -> PassoExecucao | None:
        if self.total:
            self.indice_atual = min(self.indice_atual + 1, self.total - 1)
        return self.passo_atual

    def retroceder(self) -> PassoExecucao | None:
        if self.total:
            self.indice_atual = max(self.indice_atual - 1, 0)
        return self.passo_atual

    def ir_para_primeiro(self) -> PassoExecucao | None:
        self.indice_atual = 0 if self.total else -1
        return self.passo_atual

    def ir_para_ultimo(self) -> PassoExecucao | None:
        self.indice_atual = self.total - 1 if self.total else -1
        return self.passo_atual

    def grafo_foi_alterado(self, grafo: Grafo) -> bool:
        """Detecta alteração externa mesmo que ela não passe pelo editor."""
        try:
            return grafo_para_dados(grafo) != self._assinatura
        except (TypeError, ValueError, KeyError):
            return True


def _fotografar(grafo: Grafo) -> tuple[Grafo, dict]:
    assinatura = grafo_para_dados(grafo)
    return grafo_de_dados(assinatura), assinatura


def _passos_dijkstra(
    grafo: Grafo, resultado: ResultadoDijkstra
) -> tuple[PassoExecucao, ...]:
    identificadores = [vertice.identificador for vertice in grafo.listar_vertices()]
    iniciais = {identificador: inf for identificador in identificadores}
    iniciais[resultado.origem] = 0.0
    passos = [
        PassoExecucao(
            numero=1,
            descricao=(
                f"Inicialização: distância de {resultado.origem} = 0; "
                "as demais distâncias começam como infinitas. "
                f"{_resumir_distancias(iniciais, {})}"
            ),
            distancias=iniciais,
        )
    ]
    for etapa in resultado.etapas:
        passos.append(
            PassoExecucao(
                numero=len(passos) + 1,
                descricao=(
                    f"{etapa.descricao} "
                    f"{_resumir_distancias(etapa.distancias, etapa.predecessores)}"
                ),
                vertice_atual=etapa.vertice_atual,
                vertices_processados=etapa.vertices_processados,
                arestas_avaliadas=tuple(
                    (aresta.origem, aresta.destino)
                    for aresta in etapa.arestas_analisadas
                ),
                distancias=etapa.distancias,
                predecessores=etapa.predecessores,
            )
        )

    processados = (
        resultado.etapas[-1].vertices_processados
        if resultado.etapas
        else frozenset()
    )
    distancias = resultado.etapas[-1].distancias if resultado.etapas else iniciais
    predecessores = resultado.etapas[-1].predecessores if resultado.etapas else {}
    if resultado.encontrado:
        descricao = (
            f"Conclusão: caminho reconstruído "
            f"{' → '.join(resultado.caminho)} "
            f"({resultado.distancia_total:g} km). "
            f"{_resumir_distancias(distancias, predecessores)}"
        )
        caminho = tuple(resultado.caminho)
    else:
        descricao = (
            f"Conclusão: {resultado.destino} está inalcançável; "
            f"nenhum caminho foi reconstruído. "
            f"{_resumir_distancias(distancias, predecessores)}"
        )
        caminho = ()
    passos.append(
        PassoExecucao(
            numero=len(passos) + 1,
            descricao=descricao,
            vertices_processados=processados,
            caminho_final=caminho,
            distancias=distancias,
            predecessores=predecessores,
            concluido=True,
        )
    )
    return tuple(passos)


def _resumir_distancias(
    distancias: dict[str, float], predecessores: dict[str, str]
) -> str:
    """Formata o estado de Dijkstra para leitura no painel didático."""
    itens = []
    for identificador in distancias:
        distancia = distancias[identificador]
        distancia_texto = "∞" if isinf(distancia) else f"{distancia:g}"
        predecessor = predecessores.get(identificador, "—")
        itens.append(f"{identificador}={distancia_texto} (pred.: {predecessor})")
    return "Distâncias/predecessores: " + "; ".join(itens) + "."


def _passos_tsp(resultado: ResultadoCaixeiroViajante) -> tuple[PassoExecucao, ...]:
    passos: list[PassoExecucao] = []
    for etapa in resultado.etapas:
        ordem = etapa.ordem_avaliada
        passos.append(
            PassoExecucao(
                numero=len(passos) + 1,
                descricao=etapa.descricao,
                vertice_atual=ordem[-1] if ordem else resultado.deposito,
                vertices_processados=frozenset(ordem),
                arestas_avaliadas=tuple(zip(ordem, ordem[1:])),
                ordem_avaliada=ordem,
                distancia_avaliada=etapa.distancia_avaliada,
                melhor_ordem=etapa.melhor_ordem,
                melhor_distancia=etapa.melhor_distancia,
                concluido=etapa.fase == "conclusao",
            )
        )

    if not passos:
        # Proteção para resultados produzidos por versões antigas do algoritmo
        # que não registravam histórico.
        passos.append(
            PassoExecucao(
                numero=1,
                descricao="Nenhum histórico passo a passo foi produzido.",
                concluido=True,
            )
        )
    final = passos[-1]
    if resultado.encontrada and final.caminho_final == ():
        passos[-1] = PassoExecucao(
            numero=final.numero,
            descricao=final.descricao,
            vertice_atual=final.vertice_atual,
            vertices_processados=final.vertices_processados,
            arestas_avaliadas=final.arestas_avaliadas,
            caminho_final=tuple(resultado.percurso_completo),
            ordem_avaliada=final.ordem_avaliada,
            distancia_avaliada=final.distancia_avaliada,
            melhor_ordem=final.melhor_ordem,
            melhor_distancia=final.melhor_distancia,
            concluido=True,
        )
    return tuple(passos)

