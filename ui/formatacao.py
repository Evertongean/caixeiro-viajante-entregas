"""Formatação brasileira de distâncias sem reduzir a precisão do domínio."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from math import isfinite


UMA_CASA = Decimal("0.1")


def arredondar_para_exibicao(valor: float) -> float:
    """Arredonda para uma casa somente quando um controle exige esse valor."""
    numero = float(valor)
    if not isfinite(numero):
        raise ValueError("A distância exibida deve ser finita.")
    arredondado = float(Decimal(str(numero)).quantize(UMA_CASA, ROUND_HALF_UP))
    return 0.0 if arredondado == 0 else arredondado


def formatar_numero_br(valor: float) -> str:
    """Apresenta uma casa decimal com vírgula, sem modificar ``valor``."""
    return f"{arredondar_para_exibicao(valor):.1f}".replace(".", ",")


def formatar_distancia_km(valor: float) -> str:
    return f"{formatar_numero_br(valor)} km"


__all__ = [
    "arredondar_para_exibicao",
    "formatar_distancia_km",
    "formatar_numero_br",
]
