"""Estado puro do editor visual de ruas sobre a cidade importada.

O módulo não conhece widgets nem algoritmos. Ele recebe pontos em coordenadas
de cena produzidos por ``View3D.pick`` e valida uma polilinha antes de o
controlador alterar o :class:`models.grafo.Grafo`. Essa separação evita que um
clique acidental em um prédio vire uma aresta oficial.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import dist, isfinite
from typing import Iterable, Sequence


def _ponto(valor: Sequence[float]) -> tuple[float, float, float]:
    try:
        itens = tuple(float(item) for item in valor)
    except (TypeError, ValueError) as erro:
        raise ValueError("o ponto 3D deve conter três números") from erro
    if len(itens) != 3 or not all(isfinite(item) for item in itens):
        raise ValueError("o ponto 3D deve conter três números finitos")
    return itens  # type: ignore[return-value]


class ModoEdicaoRua(str, Enum):
    NAVEGACAO = "navegacao"
    CRIAR_RUA = "criar_rua"
    MARCAR_SUPERFICIE = "marcar_superficie"


@dataclass(frozen=True, slots=True)
class SuperficieTrafegavel3D:
    """Região explicitamente confirmada pelo usuário como pavimento."""

    pontos: tuple[tuple[float, float, float], ...]
    nome: str = "superfície trafegável"
    raio_tolerancia: float = 0.75

    def __post_init__(self) -> None:
        pontos = tuple(_ponto(ponto) for ponto in self.pontos)
        if not pontos:
            raise ValueError("uma superfície precisa de ao menos um ponto")
        if not isfinite(float(self.raio_tolerancia)) or self.raio_tolerancia <= 0:
            raise ValueError("a tolerância da superfície deve ser positiva")
        object.__setattr__(self, "pontos", pontos)

    def contem(self, ponto: Sequence[float]) -> bool:
        alvo = _ponto(ponto)
        # Superfícies marcadas com um ponto funcionam como uma área circular
        # de tolerância. Com três ou mais pontos, usa-se o polígono XZ e uma
        # margem vertical pequena, adequado ao pavimento da cidade.
        if len(self.pontos) < 3:
            return any(dist(alvo, origem) <= self.raio_tolerancia for origem in self.pontos)
        x, z = alvo[0], alvo[2]
        if abs(alvo[1] - sum(p[1] for p in self.pontos) / len(self.pontos)) > max(
            self.raio_tolerancia, 1.0
        ):
            return False
        dentro = False
        for atual, proximo in zip(self.pontos, (*self.pontos[1:], self.pontos[0])):
            ax, az = atual[0], atual[2]
            bx, bz = proximo[0], proximo[2]
            cruza = (az > z) != (bz > z)
            if cruza and x < (bx - ax) * (z - az) / ((bz - az) or 1e-12) + ax:
                dentro = not dentro
        return dentro or any(dist(alvo, origem) <= self.raio_tolerancia for origem in self.pontos)


@dataclass(frozen=True, slots=True)
class RuaEmEdicao3D:
    pontos: tuple[tuple[float, float, float], ...] = ()
    origem_id: str | None = None
    destino_id: str | None = None

    @property
    def pronta(self) -> bool:
        return len(self.pontos) >= 2

    @property
    def comprimento_visual(self) -> float:
        return sum(dist(a, b) for a, b in zip(self.pontos, self.pontos[1:]))


@dataclass
class EditorRuas3D:
    """Máquina de estados determinística para criação e calibração de ruas."""

    fator_distancia: float = 1.0
    modo: ModoEdicaoRua = ModoEdicaoRua.NAVEGACAO
    superficies: list[SuperficieTrafegavel3D] = field(default_factory=list)
    rua: RuaEmEdicao3D = field(default_factory=RuaEmEdicao3D)
    ruas_configuradas: set[tuple[str, str]] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.definir_fator_distancia(self.fator_distancia)

    @property
    def pontos_pendentes(self) -> tuple[tuple[float, float, float], ...]:
        return self.rua.pontos

    @property
    def ponto_inicial(self) -> tuple[float, float, float] | None:
        return self.rua.pontos[0] if self.rua.pontos else None

    @property
    def ponto_final(self) -> tuple[float, float, float] | None:
        return self.rua.pontos[-1] if self.rua.pontos else None

    def definir_fator_distancia(self, valor: float) -> None:
        valor = float(valor)
        if not isfinite(valor) or valor <= 0:
            raise ValueError("o fator de conversão da distância deve ser positivo")
        self.fator_distancia = valor

    def iniciar_rua(self, ponto: Sequence[float], *, vertice_id: str | None = None) -> None:
        self.modo = ModoEdicaoRua.CRIAR_RUA
        self.rua = RuaEmEdicao3D((_ponto(ponto),), vertice_id, None)

    def selecionar_fim(self, ponto: Sequence[float], *, vertice_id: str | None = None) -> None:
        if not self.rua.pontos:
            self.iniciar_rua(ponto, vertice_id=vertice_id)
            return
        pontos = self.rua.pontos
        self.rua = RuaEmEdicao3D((*pontos, _ponto(ponto)), self.rua.origem_id, vertice_id)

    def adicionar_curva(self, ponto: Sequence[float]) -> None:
        if not self.rua.pontos:
            raise ValueError("selecione o início da rua antes de adicionar uma curva")
        if self.rua.destino_id is not None:
            raise ValueError("a rua já possui um ponto final")
        self.rua = RuaEmEdicao3D((*self.rua.pontos, _ponto(ponto)), self.rua.origem_id, None)

    def adicionar_ponto(self, ponto: Sequence[float], *, vertice_id: str | None = None) -> None:
        """Atalho para o fluxo de cliques início → fim → curvas."""

        if not self.rua.pontos:
            self.iniciar_rua(ponto, vertice_id=vertice_id)
        elif self.rua.destino_id is None:
            self.selecionar_fim(ponto, vertice_id=vertice_id)
        else:
            self.adicionar_curva(ponto)

    def desfazer_ultimo_ponto(self) -> None:
        if not self.rua.pontos:
            return
        self.rua = RuaEmEdicao3D(self.rua.pontos[:-1], self.rua.origem_id, None)

    def cancelar_rua(self) -> None:
        self.rua = RuaEmEdicao3D()
        self.modo = ModoEdicaoRua.NAVEGACAO

    def marcar_superficie(
        self,
        pontos: Iterable[Sequence[float]],
        *,
        nome: str = "superfície trafegável",
        raio_tolerancia: float = 0.75,
    ) -> SuperficieTrafegavel3D:
        superficie = SuperficieTrafegavel3D(
            tuple(_ponto(ponto) for ponto in pontos), nome, raio_tolerancia
        )
        self.superficies.append(superficie)
        self.modo = ModoEdicaoRua.NAVEGACAO
        return superficie

    def limpar_superficies(self) -> None:
        self.superficies.clear()

    def ponto_trafegavel(self, ponto: Sequence[float], objeto: str = "") -> bool:
        if any(superficie.contem(ponto) for superficie in self.superficies):
            return True
        # Só aceitamos nomes semânticos quando o importador realmente os
        # forneceu. Nomes genéricos de malha (mesh_001, Object_12, …) exigem a
        # confirmação manual acima e nunca são tratados como asfalto.
        texto = str(objeto).casefold()
        return any(token in texto for token in ("asphalt", "asfalto", "road", "street", "rua", "pavement"))

    def validar_rua(self, *, objeto: str = "") -> tuple[bool, str]:
        if not self.rua.pronta:
            return False, "informe início e fim da rua"
        if any(not self.ponto_trafegavel(ponto, objeto) for ponto in self.rua.pontos):
            return False, "a rua contém ponto sem superfície trafegável classificada"
        if self.rua.comprimento_visual <= 0:
            return False, "a rua não pode ter comprimento zero"
        return True, ""

    def peso_sugerido(self) -> float:
        comprimento = self.rua.comprimento_visual * self.fator_distancia
        if comprimento <= 0:
            raise ValueError("a rua precisa de comprimento positivo")
        return float(comprimento)

    def comprimento_polilinha(self) -> float:
        return self.rua.comprimento_visual

    validar_conexao = validar_rua

    def registrar_rua(self, origem: str, destino: str) -> None:
        if not origem or not destino or origem == destino:
            raise ValueError("uma rua precisa ligar dois vértices distintos")
        self.ruas_configuradas.add((str(origem), str(destino)))
        self.ruas_configuradas.add((str(destino), str(origem)))

    def rota_configurada(self, percurso: Iterable[str]) -> tuple[str, ...]:
        faltantes = [
            f"{origem}–{destino}"
            for origem, destino in zip(tuple(percurso), tuple(percurso)[1:])
            if origem != destino and (str(origem), str(destino)) not in self.ruas_configuradas
        ]
        return tuple(faltantes)

    def dados(self) -> dict:
        return {
            "fator_distancia": self.fator_distancia,
            "superficies": [
                {
                    "nome": superficie.nome,
                    "raio_tolerancia": superficie.raio_tolerancia,
                    "pontos": [list(ponto) for ponto in superficie.pontos],
                }
                for superficie in self.superficies
            ],
            "ruas_configuradas": [list(rua) for rua in sorted(self.ruas_configuradas)],
        }

    @classmethod
    def de_dados(cls, dados: object) -> "EditorRuas3D":
        if not isinstance(dados, dict):
            raise ValueError("dados do editor 3D devem ser um objeto")
        editor = cls(float(dados.get("fator_distancia", 1.0)))
        superficies = dados.get("superficies", [])
        if not isinstance(superficies, list):
            raise ValueError("superficies do editor 3D devem ser uma lista")
        for item in superficies:
            if not isinstance(item, dict):
                raise ValueError("superfície inválida")
            editor.marcar_superficie(
                item.get("pontos", []),
                nome=str(item.get("nome", "superfície trafegável")),
                raio_tolerancia=float(item.get("raio_tolerancia", 0.75)),
            )
        ruas = dados.get("ruas_configuradas", [])
        if not isinstance(ruas, list):
            raise ValueError("ruas_configuradas deve ser uma lista")
        for item in ruas:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise ValueError("conexão viária inválida")
            editor.registrar_rua(str(item[0]), str(item[1]))
        editor.modo = ModoEdicaoRua.NAVEGACAO
        return editor


__all__ = [
    "EditorRuas3D",
    "ModoEdicaoRua",
    "RuaEmEdicao3D",
    "SuperficieTrafegavel3D",
]
