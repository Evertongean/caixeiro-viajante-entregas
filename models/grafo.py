"""Estruturas para representar um grafo não direcionado e ponderado.

O módulo não contém algoritmos de busca de caminhos. Ele é responsável apenas
por manter vértices, conexões e as invariantes do grafo do Delivery Route.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from numbers import Real


class TipoVertice(str, Enum):
    """Papéis que um vértice pode desempenhar no cenário de entregas."""

    DEPOSITO = "depósito"
    CLIENTE = "cliente"
    CRUZAMENTO = "cruzamento"


@dataclass(frozen=True, slots=True)
class Vertice:
    """Um local do mapa e sua posição na visualização."""

    identificador: str
    nome: str
    tipo: TipoVertice
    x: float
    y: float

    def __post_init__(self) -> None:
        if not isinstance(self.identificador, str) or not self.identificador.strip():
            raise ValueError("O identificador do vértice deve ser um texto não vazio.")
        if not isinstance(self.nome, str) or not self.nome.strip():
            raise ValueError("O nome do vértice deve ser um texto não vazio.")
        if not isinstance(self.tipo, TipoVertice):
            raise TypeError("O tipo do vértice deve ser um valor de TipoVertice.")
        if not _numero_finito(self.x) or not _numero_finito(self.y):
            raise ValueError("As coordenadas do vértice devem ser números finitos.")


@dataclass(frozen=True, slots=True)
class Aresta:
    """Uma conexão direta entre dois vértices, medida em quilômetros."""

    origem: Vertice
    destino: Vertice
    peso: float

    def __post_init__(self) -> None:
        if not isinstance(self.origem, Vertice) or not isinstance(
            self.destino, Vertice
        ):
            raise TypeError("A origem e o destino da aresta devem ser vértices.")
        if self.origem.identificador == self.destino.identificador:
            raise ValueError("Uma aresta não pode ligar um vértice a ele mesmo.")
        object.__setattr__(self, "peso", _validar_peso(self.peso))


class Grafo:
    """Grafo não direcionado e ponderado baseado em listas de adjacência."""

    def __init__(self) -> None:
        self._vertices: dict[str, Vertice] = {}
        self._adjacencias: dict[str, dict[str, float]] = {}
        self._deposito_id: str | None = None

    def adicionar_vertice(self, vertice: Vertice) -> None:
        """Adiciona um vértice ainda não cadastrado."""
        if not isinstance(vertice, Vertice):
            raise TypeError("É necessário fornecer uma instância de Vertice.")
        if vertice.identificador in self._vertices:
            raise ValueError(
                f"Já existe um vértice com o identificador '{vertice.identificador}'."
            )
        if any(cadastrado.nome == vertice.nome for cadastrado in self._vertices.values()):
            raise ValueError(f"Já existe um vértice com o nome '{vertice.nome}'.")
        if vertice.tipo is TipoVertice.DEPOSITO and any(
            cadastrado.tipo is TipoVertice.DEPOSITO
            for cadastrado in self._vertices.values()
        ):
            raise ValueError("O grafo pode ter no máximo um depósito.")

        self._vertices[vertice.identificador] = vertice
        self._adjacencias[vertice.identificador] = {}
        if vertice.tipo is TipoVertice.DEPOSITO:
            self._deposito_id = vertice.identificador

    def atualizar_vertice(
        self,
        identificador: str,
        *,
        nome: str,
        tipo: TipoVertice,
        x: float,
        y: float,
    ) -> Vertice:
        """Atualiza os dados de um vértice mantendo seu identificador.

        Como as arestas usam o identificador como chave, preservá-lo mantém
        todas as conexões consistentes durante a edição.
        """
        atual = self._obter_vertice_ou_falhar(identificador)
        novo = Vertice(identificador, nome, tipo, x, y)
        if any(
            cadastrado.identificador != identificador
            and cadastrado.nome == novo.nome
            for cadastrado in self._vertices.values()
        ):
            raise ValueError(f"Já existe um vértice com o nome '{novo.nome}'.")
        if novo.tipo is TipoVertice.DEPOSITO and any(
            cadastrado.identificador != identificador
            and cadastrado.tipo is TipoVertice.DEPOSITO
            for cadastrado in self._vertices.values()
        ):
            raise ValueError("O grafo pode ter no máximo um depósito.")

        self._vertices[identificador] = novo
        if atual.tipo is TipoVertice.DEPOSITO and novo.tipo is not TipoVertice.DEPOSITO:
            self._deposito_id = None
        elif novo.tipo is TipoVertice.DEPOSITO:
            self._deposito_id = identificador
        return novo

    # Nome alternativo explícito para código de edição e futuras integrações.
    editar_vertice = atualizar_vertice

    def remover_vertice(self, identificador: str) -> Vertice:
        """Remove um vértice e todas as arestas ligadas a ele."""
        vertice = self._obter_vertice_ou_falhar(identificador)

        for vizinho_id in tuple(self._adjacencias[identificador]):
            del self._adjacencias[vizinho_id][identificador]

        del self._adjacencias[identificador]
        del self._vertices[identificador]
        if self._deposito_id == identificador:
            self._deposito_id = None
        return vertice

    def adicionar_aresta(
        self, origem_id: str, destino_id: str, peso: float
    ) -> None:
        """Cria uma conexão simétrica entre dois vértices existentes."""
        self._obter_vertice_ou_falhar(origem_id)
        self._obter_vertice_ou_falhar(destino_id)
        if origem_id == destino_id:
            raise ValueError("Uma aresta não pode ligar um vértice a ele mesmo.")
        peso_validado = _validar_peso(peso)
        if destino_id in self._adjacencias[origem_id]:
            raise ValueError(
                f"A aresta entre '{origem_id}' e '{destino_id}' já existe."
            )

        self._adjacencias[origem_id][destino_id] = peso_validado
        self._adjacencias[destino_id][origem_id] = peso_validado

    def remover_aresta(self, origem_id: str, destino_id: str) -> None:
        """Remove uma conexão nos dois sentidos."""
        self._obter_vertice_ou_falhar(origem_id)
        self._obter_vertice_ou_falhar(destino_id)
        if destino_id not in self._adjacencias[origem_id]:
            raise ValueError(
                f"Não existe aresta entre '{origem_id}' e '{destino_id}'."
            )

        del self._adjacencias[origem_id][destino_id]
        del self._adjacencias[destino_id][origem_id]

    def obter_vizinhos(self, identificador: str) -> dict[str, float]:
        """Retorna uma cópia do mapa ``identificador do vizinho -> peso``."""
        self._obter_vertice_ou_falhar(identificador)
        return self._adjacencias[identificador].copy()

    def obter_distancia(self, origem_id: str, destino_id: str) -> float:
        """Consulta o peso de uma conexão direta."""
        self._obter_vertice_ou_falhar(origem_id)
        self._obter_vertice_ou_falhar(destino_id)
        try:
            return self._adjacencias[origem_id][destino_id]
        except KeyError as erro:
            raise ValueError(
                f"Não existe aresta entre '{origem_id}' e '{destino_id}'."
            ) from erro

    def listar_vertices(self) -> list[Vertice]:
        """Lista os vértices na ordem em que foram cadastrados."""
        return list(self._vertices.values())

    def listar_arestas(self) -> list[Aresta]:
        """Lista cada aresta não direcionada uma única vez."""
        arestas: list[Aresta] = []
        visitadas: set[frozenset[str]] = set()

        for origem_id, vizinhos in self._adjacencias.items():
            for destino_id, peso in vizinhos.items():
                chave = frozenset((origem_id, destino_id))
                if chave in visitadas:
                    continue
                visitadas.add(chave)
                arestas.append(
                    Aresta(
                        origem=self._vertices[origem_id],
                        destino=self._vertices[destino_id],
                        peso=peso,
                    )
                )
        return arestas

    def atualizar_peso_aresta(
        self, origem_id: str, destino_id: str, novo_peso: float
    ) -> None:
        """Atualiza o peso de uma conexão existente nos dois sentidos."""
        self._obter_vertice_ou_falhar(origem_id)
        self._obter_vertice_ou_falhar(destino_id)
        if destino_id not in self._adjacencias[origem_id]:
            raise ValueError(
                f"Não existe aresta entre '{origem_id}' e '{destino_id}'."
            )
        peso_validado = _validar_peso(novo_peso)

        self._adjacencias[origem_id][destino_id] = peso_validado
        self._adjacencias[destino_id][origem_id] = peso_validado

    # Alias semântico usado pelo editor, mantendo a API original disponível.
    editar_aresta = atualizar_peso_aresta

    def definir_deposito(self, identificador: str) -> None:
        """Define o único depósito principal do cenário.

        Repetir a definição para o mesmo vértice é permitido, mas a troca para
        outro depósito exige que o depósito atual seja removido do grafo.
        """
        vertice = self._obter_vertice_ou_falhar(identificador)
        if vertice.tipo is not TipoVertice.DEPOSITO:
            raise ValueError(
                f"O vértice '{identificador}' não possui o tipo depósito."
            )
        if self._deposito_id is not None and self._deposito_id != identificador:
            raise ValueError(
                f"O depósito principal já foi definido como '{self._deposito_id}'."
            )
        self._deposito_id = identificador

    def obter_deposito(self) -> Vertice | None:
        """Retorna o depósito principal ou ``None`` quando não foi definido."""
        if self._deposito_id is None:
            return None
        return self._vertices[self._deposito_id]

    def listar_clientes(self) -> list[Vertice]:
        """Lista somente os vértices que representam clientes."""
        return [
            vertice
            for vertice in self._vertices.values()
            if vertice.tipo is TipoVertice.CLIENTE
        ]

    def existe_aresta(self, origem_id: str, destino_id: str) -> bool:
        """Informa se há conexão direta entre dois vértices existentes."""
        self._obter_vertice_ou_falhar(origem_id)
        self._obter_vertice_ou_falhar(destino_id)
        return destino_id in self._adjacencias[origem_id]

    def obter_vertice(self, identificador: str) -> Vertice:
        """Consulta um vértice pelo identificador."""
        return self._obter_vertice_ou_falhar(identificador)

    def _obter_vertice_ou_falhar(self, identificador: str) -> Vertice:
        try:
            return self._vertices[identificador]
        except (KeyError, TypeError) as erro:
            raise KeyError(
                f"Não existe vértice com o identificador '{identificador}'."
            ) from erro


def _numero_finito(valor: object) -> bool:
    """Evita aceitar booleanos, infinitos e valores que não sejam números reais."""
    return isinstance(valor, Real) and not isinstance(valor, bool) and isfinite(valor)


def _validar_peso(peso: float) -> float:
    if not _numero_finito(peso) or peso <= 0:
        raise ValueError("O peso da aresta deve ser um número positivo e finito.")
    return float(peso)


def criar_cenario_exemplo() -> Grafo:
    """Cria o pequeno cenário fictício compartilhado pela demo e pelos testes."""
    grafo = Grafo()
    vertices = (
        Vertice("D", "Depósito Central", TipoVertice.DEPOSITO, 0, 0),
        Vertice("X", "Cruzamento", TipoVertice.CRUZAMENTO, 2, 1),
        Vertice("A", "Cliente A", TipoVertice.CLIENTE, 3, 0),
        Vertice("B", "Cliente B", TipoVertice.CLIENTE, 5, 2),
        Vertice("C", "Cliente C", TipoVertice.CLIENTE, 2, 4),
    )
    for vertice in vertices:
        grafo.adicionar_vertice(vertice)

    grafo.definir_deposito("D")
    for origem, destino, peso in (
        ("D", "X", 2),
        ("X", "A", 1),
        ("A", "B", 3),
        ("B", "C", 2),
        ("C", "D", 7),
        ("X", "B", 5),
        ("A", "C", 6),
    ):
        grafo.adicionar_aresta(origem, destino, peso)
    return grafo
