"""Seleção e validação geométrica da pose inicial do veículo."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, pi, radians, sin
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


def _orientacoes_candidatas(
    projeto: ProjetoCidade, deposito: str
) -> tuple[float, ...]:
    orientacoes: list[float] = []
    for direcao_x, direcao_z in _direcoes_de_saida(projeto, deposito):
        orientacoes.append(degrees(atan2(direcao_x, direcao_z)))
    # O eixo do veículo é simétrico para a validação da ocupação. Passos
    # de 15° cobrem também vias diagonais sem atrelar a busca ao grafo lógico.
    orientacoes.extend(float(angulo) for angulo in range(-180, 0, 15))
    unicas: list[float] = []
    for orientacao in orientacoes:
        normalizada = ((orientacao + 180.0) % 180.0) - 180.0
        if all(abs(normalizada - existente) > 1e-6 for existente in unicas):
            unicas.append(normalizada)
    return tuple(unicas)


def _alcance_longitudinal(
    mapa: MapaSuperficies,
    posicao: Ponto3D,
    orientacao_graus: float,
    *,
    limite: float = 0.20,
    passo: float = 0.01,
) -> float:
    """Mede o eixo contínuo de rua para preferir o alinhamento da via."""
    angulo = radians(orientacao_graus)
    frente = (sin(angulo), cos(angulo))
    alcance = 0.0
    for sentido in (-1.0, 1.0):
        distancia = passo
        while distancia <= limite + 1e-9:
            amostra = mapa.amostrar(
                posicao[0] + frente[0] * distancia * sentido,
                posicao[2] + frente[1] * distancia * sentido,
            )
            if (
                amostra is None
                or amostra.classificacao is not ClassificacaoSuperficie.RUA
            ):
                break
            alcance += passo
            distancia += passo
    return alcance


def _posicoes_proximas(
    origem: Ponto3D,
    distancia_maxima: float,
    *,
    passo: float = 0.01,
) -> tuple[tuple[float, Ponto3D], ...]:
    """Gera anéis determinísticos ao redor do depósito, do mais perto ao longe."""
    resultado = [(0.0, origem)]
    quantidade_raios = max(1, int(distancia_maxima / passo))
    for indice in range(1, quantidade_raios + 1):
        raio = min(indice * passo, distancia_maxima)
        # Vinte e quatro direções mantêm o erro lateral abaixo da resolução
        # do mapa mesmo no limite da busca.
        for setor in range(24):
            angulo = 2.0 * pi * setor / 24.0
            resultado.append(
                (
                    raio,
                    (
                        origem[0] + cos(angulo) * raio,
                        origem[1],
                        origem[2] + sin(angulo) * raio,
                    ),
                )
            )
    return tuple(resultado)


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
    orientacoes = _orientacoes_candidatas(projeto, deposito.identificador)
    distancia_atual: float | None = None
    candidatos_validos: list[
        tuple[float, float, ResultadoValidacaoEstacionamento]
    ] = []
    for distancia, posicao in _posicoes_proximas(
        origem, distancia_maxima_deposito
    ):
        if distancia_atual is not None and distancia > distancia_atual + 1e-9:
            if candidatos_validos:
                break
            candidatos_validos.clear()
        distancia_atual = distancia
        amostra = mapa.amostrar(posicao[0], posicao[2])
        if (
            amostra is None
            or amostra.classificacao is not ClassificacaoSuperficie.RUA
        ):
            continue
        posicao_pavimento = (posicao[0], amostra.altura, posicao[2])
        for orientacao in orientacoes:
            candidato = EstacionamentoVeiculo(
                deposito=deposito.identificador,
                posicao=posicao_pavimento,
                orientacao_graus=orientacao,
            )
            validacao = validar_estacionamento(candidato, mapa, dimensoes)
            if validacao.valido:
                candidatos_validos.append(
                    (
                        _alcance_longitudinal(
                            mapa, validacao.posicao_pavimento, orientacao
                        ),
                        orientacao,
                        validacao,
                    )
                )
    if candidatos_validos:
        _, orientacao, validacao = max(
            candidatos_validos,
            key=lambda item: (
                item[0],
                -abs(item[1] - round(item[1] / 90.0) * 90.0),
                -abs(item[1]),
            ),
        )
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
