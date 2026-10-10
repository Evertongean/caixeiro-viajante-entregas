"""Cálculo testável da câmera de perseguição da missão 3D."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, exp, isfinite, radians, sin
from typing import Sequence


Ponto3D = tuple[float, float, float]


def _vetor3(valor: Sequence[float]) -> Ponto3D:
    if len(valor) != 3:
        raise ValueError("Uma posição deve possuir três coordenadas.")
    resultado = tuple(float(item) for item in valor)
    if not all(isfinite(item) for item in resultado):
        raise ValueError("As coordenadas devem ser finitas.")
    return resultado  # type: ignore[return-value]


def _suavizar(atual: Ponto3D, alvo: Ponto3D, fator: float) -> Ponto3D:
    return tuple(
        atual[eixo] + (alvo[eixo] - atual[eixo]) * fator for eixo in range(3)
    )  # type: ignore[return-value]


@dataclass(slots=True)
class CameraSeguidora:
    distancia: float = 0.34
    altura: float = 0.18
    antecipacao: float = 0.07
    suavidade: float = 7.0
    posicao: Ponto3D = (0.0, 0.0, 0.0)
    alvo: Ponto3D = (0.0, 0.0, 0.0)
    inicializada: bool = False

    def configurar(self, *, distancia: float, altura: float) -> None:
        if not isfinite(distancia) or distancia <= 0:
            raise ValueError("A distância da câmera deve ser positiva e finita.")
        if not isfinite(altura) or altura <= 0:
            raise ValueError("A altura da câmera deve ser positiva e finita.")
        self.distancia = float(distancia)
        self.altura = float(altura)

    def reiniciar(self) -> None:
        self.inicializada = False

    def atualizar(
        self,
        posicao_carro: Sequence[float],
        orientacao_graus: float,
        delta_segundos: float,
        *,
        imediato: bool = False,
    ) -> tuple[Ponto3D, Ponto3D]:
        carro = _vetor3(posicao_carro)
        if not isfinite(orientacao_graus):
            raise ValueError("A orientação deve ser finita.")
        if not isfinite(delta_segundos) or delta_segundos < 0:
            raise ValueError("O delta deve ser não negativo e finito.")
        angulo = radians(orientacao_graus)
        frente_x, frente_z = sin(angulo), cos(angulo)
        desejada = (
            carro[0] - frente_x * self.distancia,
            carro[1] + self.altura,
            carro[2] - frente_z * self.distancia,
        )
        alvo = (
            carro[0] + frente_x * self.antecipacao,
            carro[1] + self.altura * 0.18,
            carro[2] + frente_z * self.antecipacao,
        )
        if imediato or not self.inicializada:
            self.posicao, self.alvo = desejada, alvo
            self.inicializada = True
        else:
            fator = 1.0 - exp(-self.suavidade * delta_segundos)
            self.posicao = _suavizar(self.posicao, desejada, fator)
            self.alvo = _suavizar(self.alvo, alvo, fator)
        return self.posicao, self.alvo


__all__ = ["CameraSeguidora"]
