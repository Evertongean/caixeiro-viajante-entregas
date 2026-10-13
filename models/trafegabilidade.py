"""Mapa espacial de trafegabilidade derivado automaticamente da cidade 3D.

Este módulo é deliberadamente independente de Qt e do formato GLB.  Ele contém
as operações de domínio usadas pelo editor: consultas pontuais, validação da
largura do veículo, validação contínua de ruas e busca de um caminho viável.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import heapq
import math
from typing import Iterable, Sequence, TypeAlias

from models.projeto_cidade import ClassificacaoSuperficie


Posicao3D: TypeAlias = tuple[float, float, float]


class TipoRegiao(str, Enum):
    RUA = "rua"
    CALCADA = "calcada"
    EDIFICIO = "edificio"
    VERDE = "verde"
    DESCONHECIDA = "desconhecida"


@dataclass(frozen=True)
class AmostraTrafegabilidade:
    tipo: TipoRegiao
    altura: float
    referencia: str = ""
    confianca: float = 0.0

    @property
    def trafegavel(self) -> bool:
        return self.tipo == TipoRegiao.RUA

    @property
    def classificacao(self) -> ClassificacaoSuperficie:
        """Compatibilidade com consumidores do mapa de superfícies antigo."""
        return (
            ClassificacaoSuperficie.RUA
            if self.trafegavel
            else ClassificacaoSuperficie.BLOQUEADA
        )


@dataclass(frozen=True)
class ResultadoValidacaoTrajeto:
    valido: bool
    conclusivo: bool
    motivo: str
    posicao_problema: Posicao3D | None = None


class MapaTrafegabilidade:
    """Grade regular da superfície visível da cidade.

    A grade mantém a classificação por célula, em vez de associá-la ao nome de
    uma malha inteira. Isso permite distinguir regiões diferentes de uma mesma
    malha e impede que cor/nome sejam tratados como verdade global.
    """

    def __init__(
        self,
        origem_x: float,
        origem_z: float,
        resolucao: float,
        largura: int,
        profundidade: int,
        celulas: Sequence[AmostraTrafegabilidade | None],
    ) -> None:
        if resolucao <= 0 or largura <= 0 or profundidade <= 0:
            raise ValueError("Dimensões inválidas para o mapa de trafegabilidade.")
        if len(celulas) != largura * profundidade:
            raise ValueError("Quantidade de células incompatível com a grade.")
        self.origem_x = float(origem_x)
        self.origem_z = float(origem_z)
        self.resolucao = float(resolucao)
        self.largura = int(largura)
        self.profundidade = int(profundidade)
        self._celulas = tuple(celulas)

    @property
    def limite_x(self) -> float:
        return self.origem_x + self.largura * self.resolucao

    @property
    def limite_z(self) -> float:
        return self.origem_z + self.profundidade * self.resolucao

    def _indice(self, coluna: int, linha: int) -> int:
        return linha * self.largura + coluna

    def celula(self, coluna: int, linha: int) -> AmostraTrafegabilidade | None:
        if not (0 <= coluna < self.largura and 0 <= linha < self.profundidade):
            return None
        return self._celulas[self._indice(coluna, linha)]

    def coordenada_celula(self, x: float, z: float) -> tuple[int, int] | None:
        coluna = math.floor((x - self.origem_x) / self.resolucao)
        linha = math.floor((z - self.origem_z) / self.resolucao)
        if not (0 <= coluna < self.largura and 0 <= linha < self.profundidade):
            return None
        return coluna, linha

    def centro_celula(self, coluna: int, linha: int) -> tuple[float, float]:
        return (
            self.origem_x + (coluna + 0.5) * self.resolucao,
            self.origem_z + (linha + 0.5) * self.resolucao,
        )

    def amostrar(self, x: float, z: float) -> AmostraTrafegabilidade | None:
        coordenada = self.coordenada_celula(x, z)
        return self.celula(*coordenada) if coordenada is not None else None

    def _area_livre(self, x: float, z: float, meia_largura: float) -> bool:
        centro = self.amostrar(x, z)
        if centro is None or not centro.trafegavel:
            return False
        if meia_largura <= self.resolucao * 0.25:
            return True

        alcance = max(1, math.ceil(meia_largura / self.resolucao))
        coordenada = self.coordenada_celula(x, z)
        if coordenada is None:
            return False
        coluna_centro, linha_centro = coordenada
        raio_quadrado = (meia_largura + self.resolucao * 0.35) ** 2
        for dz in range(-alcance, alcance + 1):
            for dx in range(-alcance, alcance + 1):
                distancia_x = dx * self.resolucao
                distancia_z = dz * self.resolucao
                if distancia_x * distancia_x + distancia_z * distancia_z > raio_quadrado:
                    continue
                amostra = self.celula(coluna_centro + dx, linha_centro + dz)
                if amostra is None or not amostra.trafegavel:
                    return False
        return True

    def validar_posicao(
        self, posicao: Posicao3D, meia_largura: float = 0.0
    ) -> ResultadoValidacaoTrajeto:
        amostra = self.amostrar(posicao[0], posicao[2])
        if amostra is None:
            return ResultadoValidacaoTrajeto(
                False, False, "Posição fora da área reconhecida.", posicao
            )
        if not amostra.trafegavel:
            nome = {
                TipoRegiao.CALCADA: "calçada",
                TipoRegiao.EDIFICIO: "edificação/obstáculo",
                TipoRegiao.VERDE: "área verde",
                TipoRegiao.DESCONHECIDA: "região não reconhecida",
            }.get(amostra.tipo, amostra.tipo.value)
            return ResultadoValidacaoTrajeto(
                False,
                amostra.tipo != TipoRegiao.DESCONHECIDA,
                f"A posição está sobre {nome}, não sobre uma rua.",
                posicao,
            )
        if not self._area_livre(posicao[0], posicao[2], meia_largura):
            return ResultadoValidacaoTrajeto(
                False,
                True,
                "A rua não oferece largura livre suficiente para o veículo.",
                posicao,
            )
        return ResultadoValidacaoTrajeto(True, True, "Posição trafegável.")

    def validar_segmento(
        self,
        inicio: Posicao3D,
        fim: Posicao3D,
        meia_largura: float = 0.0,
    ) -> ResultadoValidacaoTrajeto:
        dx = fim[0] - inicio[0]
        dz = fim[2] - inicio[2]
        distancia = math.hypot(dx, dz)
        quantidade = max(1, math.ceil(distancia / (self.resolucao * 0.45)))
        encontrou_desconhecida = False
        for indice in range(quantidade + 1):
            fator = indice / quantidade
            posicao = (
                inicio[0] + dx * fator,
                inicio[1] + (fim[1] - inicio[1]) * fator,
                inicio[2] + dz * fator,
            )
            resultado = self.validar_posicao(posicao, meia_largura)
            if resultado.valido:
                continue
            if not resultado.conclusivo:
                encontrou_desconhecida = True
            else:
                return resultado
        if encontrou_desconhecida:
            return ResultadoValidacaoTrajeto(
                False,
                False,
                "O segmento atravessa uma região que não pôde ser reconhecida.",
            )
        return ResultadoValidacaoTrajeto(True, True, "Segmento trafegável.")

    def validar_polilinha(
        self,
        pontos: Sequence[Posicao3D],
        meia_largura: float = 0.0,
    ) -> ResultadoValidacaoTrajeto:
        if len(pontos) < 2:
            return ResultadoValidacaoTrajeto(
                False, False, "Uma rua precisa de pelo menos dois pontos."
            )
        for inicio, fim in zip(pontos, pontos[1:]):
            resultado = self.validar_segmento(inicio, fim, meia_largura)
            if not resultado.valido:
                return resultado
        return ResultadoValidacaoTrajeto(True, True, "Rua validada automaticamente.")

    def _rua_mais_proxima(
        self, posicao: Posicao3D, meia_largura: float, alcance: int = 5
    ) -> tuple[int, int] | None:
        origem = self.coordenada_celula(posicao[0], posicao[2])
        if origem is None:
            return None
        melhor: tuple[float, tuple[int, int]] | None = None
        for raio in range(alcance + 1):
            for dz in range(-raio, raio + 1):
                for dx in range(-raio, raio + 1):
                    if raio and max(abs(dx), abs(dz)) != raio:
                        continue
                    celula = (origem[0] + dx, origem[1] + dz)
                    amostra = self.celula(*celula)
                    if amostra is None or not amostra.trafegavel:
                        continue
                    x, z = self.centro_celula(*celula)
                    if not self._area_livre(x, z, meia_largura):
                        continue
                    distancia = (x - posicao[0]) ** 2 + (z - posicao[2]) ** 2
                    if melhor is None or distancia < melhor[0]:
                        melhor = distancia, celula
            if melhor is not None:
                return melhor[1]
        return None

    def sugerir_caminho(
        self,
        inicio: Posicao3D,
        fim: Posicao3D,
        meia_largura: float = 0.0,
        maximo_celulas: int = 80_000,
    ) -> list[Posicao3D] | None:
        """Encontra e simplifica um caminho inteiramente contido em ruas."""
        origem = self._rua_mais_proxima(inicio, meia_largura)
        destino = self._rua_mais_proxima(fim, meia_largura)
        if origem is None or destino is None:
            return None

        def heuristica(celula: tuple[int, int]) -> float:
            return math.hypot(celula[0] - destino[0], celula[1] - destino[1])

        fronteira: list[tuple[float, float, tuple[int, int]]] = [(heuristica(origem), 0.0, origem)]
        anterior: dict[tuple[int, int], tuple[int, int] | None] = {origem: None}
        custos = {origem: 0.0}
        visitadas = 0
        vizinhas = (
            (-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
            (-1, -1, math.sqrt(2)), (1, -1, math.sqrt(2)),
            (-1, 1, math.sqrt(2)), (1, 1, math.sqrt(2)),
        )
        while fronteira and visitadas < maximo_celulas:
            _, custo, atual = heapq.heappop(fronteira)
            if custo != custos.get(atual):
                continue
            visitadas += 1
            if atual == destino:
                break
            for dx, dz, adicional in vizinhas:
                proxima = (atual[0] + dx, atual[1] + dz)
                amostra = self.celula(*proxima)
                if amostra is None or not amostra.trafegavel:
                    continue
                x, z = self.centro_celula(*proxima)
                if not self._area_livre(x, z, meia_largura):
                    continue
                novo_custo = custo + adicional
                if novo_custo >= custos.get(proxima, math.inf):
                    continue
                custos[proxima] = novo_custo
                anterior[proxima] = atual
                heapq.heappush(
                    fronteira,
                    (novo_custo + heuristica(proxima), novo_custo, proxima),
                )
        if destino not in anterior:
            return None

        caminho_celulas: list[tuple[int, int]] = []
        atual: tuple[int, int] | None = destino
        while atual is not None:
            caminho_celulas.append(atual)
            atual = anterior[atual]
        caminho_celulas.reverse()
        caminho = [inicio]
        for coluna, linha in caminho_celulas[1:-1]:
            x, z = self.centro_celula(coluna, linha)
            amostra = self.celula(coluna, linha)
            caminho.append((x, amostra.altura if amostra else inicio[1], z))
        caminho.append(fim)
        return self._simplificar_caminho(caminho, meia_largura)

    def _simplificar_caminho(
        self, pontos: Sequence[Posicao3D], meia_largura: float
    ) -> list[Posicao3D]:
        if len(pontos) <= 2:
            return list(pontos)
        resultado = [pontos[0]]
        indice = 0
        while indice < len(pontos) - 1:
            proximo = len(pontos) - 1
            while proximo > indice + 1:
                if self.validar_segmento(
                    pontos[indice], pontos[proximo], meia_largura
                ).valido:
                    break
                proximo -= 1
            resultado.append(pontos[proximo])
            indice = proximo
        return resultado

    def iterar_celulas(
        self,
    ) -> Iterable[tuple[int, int, AmostraTrafegabilidade | None]]:
        for linha in range(self.profundidade):
            for coluna in range(self.largura):
                yield coluna, linha, self.celula(coluna, linha)

    def para_dados(self) -> dict:
        """Representação compacta com sequências iguais por linha."""
        linhas: list[list[list]] = []
        for linha in range(self.profundidade):
            sequencias: list[list] = []
            atual: tuple | None = None
            repeticoes = 0
            for coluna in range(self.largura):
                celula = self.celula(coluna, linha)
                valor = None if celula is None else (
                    celula.tipo.value,
                    round(celula.altura, 6),
                    celula.referencia,
                    round(celula.confianca, 3),
                )
                if coluna == 0 or valor != atual:
                    if coluna:
                        sequencias.append([repeticoes, atual])
                    atual = valor
                    repeticoes = 1
                else:
                    repeticoes += 1
            sequencias.append([repeticoes, atual])
            linhas.append(sequencias)
        return {
            "origem": [self.origem_x, self.origem_z],
            "resolucao": self.resolucao,
            "dimensoes": [self.largura, self.profundidade],
            "linhas": linhas,
        }

    @classmethod
    def de_dados(cls, dados: dict) -> "MapaTrafegabilidade":
        celulas: list[AmostraTrafegabilidade | None] = []
        for sequencias in dados["linhas"]:
            for quantidade, valor in sequencias:
                if valor is None:
                    celula = None
                else:
                    celula = AmostraTrafegabilidade(
                        TipoRegiao(valor[0]), float(valor[1]), str(valor[2]), float(valor[3])
                    )
                celulas.extend([celula] * int(quantidade))
        return cls(
            float(dados["origem"][0]),
            float(dados["origem"][1]),
            float(dados["resolucao"]),
            int(dados["dimensoes"][0]),
            int(dados["dimensoes"][1]),
            celulas,
        )
