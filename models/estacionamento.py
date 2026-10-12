"""Seleção e validação geométrica da pose inicial do veículo."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, radians, sin
from typing import Protocol

from models.projeto_cidade import (
    ClassificacaoSuperficie,
    EstacionamentoVeiculo,
    ProjetoCidade,
)


Ponto3D = tuple[float, float, float]


class AmostraSuperficie(Protocol):
    referencia: str
    classificacao: ClassificacaoSuperficie
    altura: float


class MapaSuperficies(Protocol):
    def amostrar(self, x: float, z: float) -> AmostraSuperficie | None: ...


@dataclass(frozen=True, slots=True)
class DimensoesVeiculo:
    largura: float
    altura: float
    comprimento: float

    def __post_init__(self) -> None:
        if min(self.largura, self.altura, self.comprimento) <= 0:
            raise ValueError("As dimensões do veículo devem ser positivas.")


@dataclass(frozen=True, slots=True)
class ResultadoValidacaoEstacionamento:
    valido: bool
    posicao_pavimento: Ponto3D
    superficie: str | None
    motivo: str


def pontos_ocupacao_veiculo(
    posicao: Ponto3D,
    orientacao_graus: float,
    dimensoes: DimensoesVeiculo,
    *,
    margem: float = 0.006,
) -> tuple[Ponto3D, ...]:
    """Amostra centro, bordas e cantos da carroceria projetada no pavimento."""
    angulo = radians(orientacao_graus)
    frente = (sin(angulo), cos(angulo))
    direita = (cos(angulo), -sin(angulo))
    metade_largura = dimensoes.largura * 0.5 + margem
    metade_comprimento = dimensoes.comprimento * 0.5 + margem
    fracoes = (-1.0, -0.5, 0.0, 0.5, 1.0)
    pontos: list[Ponto3D] = []
    for lateral in fracoes:
        for longitudinal in fracoes:
            deslocamento_lateral = lateral * metade_largura
            deslocamento_frontal = longitudinal * metade_comprimento
            pontos.append(
                (
                    posicao[0]
                    + direita[0] * deslocamento_lateral
                    + frente[0] * deslocamento_frontal,
                    posicao[1],
                    posicao[2]
                    + direita[1] * deslocamento_lateral
                    + frente[1] * deslocamento_frontal,
                )
            )
    return tuple(pontos)


def validar_estacionamento(
    estacionamento: EstacionamentoVeiculo,
    mapa: MapaSuperficies,
    dimensoes: DimensoesVeiculo,
    *,
    margem: float = 0.006,
    tolerancia_altura: float = 0.004,
) -> ResultadoValidacaoEstacionamento:
    alturas: list[float] = []
    referencias: list[str] = []
    for ponto in pontos_ocupacao_veiculo(
        estacionamento.posicao,
        estacionamento.orientacao_graus,
        dimensoes,
        margem=margem,
    ):
        amostra = mapa.amostrar(ponto[0], ponto[2])
        if amostra is None:
            return ResultadoValidacaoEstacionamento(
                False,
                estacionamento.posicao,
                None,
                "Parte da carroceria fica fora de uma superfície classificada.",
            )
        if amostra.classificacao is not ClassificacaoSuperficie.RUA:
            return ResultadoValidacaoEstacionamento(
                False,
                estacionamento.posicao,
                amostra.referencia,
                "Parte da carroceria invade uma superfície não trafegável.",
            )
        alturas.append(amostra.altura)
        referencias.append(amostra.referencia)
    if max(alturas) - min(alturas) > tolerancia_altura:
        return ResultadoValidacaoEstacionamento(
            False,
            estacionamento.posicao,
            referencias[0],
            "A área de estacionamento possui desnível excessivo.",
        )
    altura = sum(alturas) / len(alturas)
    superficie = max(set(referencias), key=referencias.count)
    return ResultadoValidacaoEstacionamento(
        True,
        (estacionamento.posicao[0], altura, estacionamento.posicao[2]),
        superficie,
        "A carroceria inteira está sobre a pista de rolamento.",
    )


def _direcoes_de_saida(
    projeto: ProjetoCidade, deposito: str
) -> tuple[tuple[float, float], ...]:
    origem = projeto.posicoes.get(deposito)
    if origem is None:
        return ()
    direcoes: list[tuple[float, float]] = []
    for vizinho in sorted(projeto.grafo.obter_vizinhos(deposito)):
        pontos = projeto.polilinha_rua(deposito, vizinho)
        for ponto in pontos[1:]:
            dx, dz = ponto[0] - origem[0], ponto[2] - origem[2]
            comprimento = hypot(dx, dz)
            if comprimento > 1e-9:
                direcoes.append((dx / comprimento, dz / comprimento))
                break
    return tuple(direcoes)


def resolver_estacionamento(
    projeto: ProjetoCidade,
    mapa: MapaSuperficies,
    dimensoes: DimensoesVeiculo,
    *,
    distancia_maxima_deposito: float = 0.25,
) -> EstacionamentoVeiculo:
    """Valida a pose persistida ou procura uma pose alinhada às ruas do depósito."""
    deposito = projeto.grafo.obter_deposito()
    if deposito is None or deposito.identificador not in projeto.posicoes:
        raise ValueError("O projeto não possui depósito com posição espacial.")

    persistido = projeto.estacionamento_inicial
    if persistido is not None and persistido.deposito == deposito.identificador:
        distancia = hypot(
            persistido.posicao[0] - projeto.posicoes[deposito.identificador][0],
            persistido.posicao[2] - projeto.posicoes[deposito.identificador][2],
        )
        if distancia <= distancia_maxima_deposito:
            validacao = validar_estacionamento(persistido, mapa, dimensoes)
            if validacao.valido:
                return EstacionamentoVeiculo(
                    deposito=deposito.identificador,
                    posicao=validacao.posicao_pavimento,
                    orientacao_graus=persistido.orientacao_graus,
                    superficie=validacao.superficie,
                    validado=True,
                )

    origem = projeto.posicoes[deposito.identificador]
    direcoes = _direcoes_de_saida(projeto, deposito.identificador)
    if not direcoes:
        raise ValueError("O depósito não possui rua espacial calibrada para estacionar.")
    # Primeiro tenta o ponto lógico do depósito. Os deslocamentos seguintes
    # permanecem sobre a própria polilinha e servem para depósitos em esquinas.
    deslocamentos = (0.0, 0.025, -0.025, 0.05, -0.05, 0.075, -0.075)
    for direcao_x, direcao_z in direcoes:
        orientacao = degrees(atan2(direcao_x, direcao_z))
        for deslocamento in deslocamentos:
            candidato = EstacionamentoVeiculo(
                deposito=deposito.identificador,
                posicao=(
                    origem[0] + direcao_x * deslocamento,
                    origem[1],
                    origem[2] + direcao_z * deslocamento,
                ),
                orientacao_graus=orientacao,
            )
            validacao = validar_estacionamento(candidato, mapa, dimensoes)
            if validacao.valido:
                return EstacionamentoVeiculo(
                    deposito=deposito.identificador,
                    posicao=validacao.posicao_pavimento,
                    orientacao_graus=orientacao,
                    superficie=validacao.superficie,
                    validado=True,
                )
    raise ValueError(
        "Não foi encontrada uma área de asfalto com espaço para toda a carroceria."
    )


__all__ = [
    "DimensoesVeiculo",
    "ResultadoValidacaoEstacionamento",
    "pontos_ocupacao_veiculo",
    "resolver_estacionamento",
    "validar_estacionamento",
]
