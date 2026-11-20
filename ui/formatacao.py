"""Formatação brasileira de distâncias sem reduzir a precisão do domínio."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP, localcontext
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


def formatar_inteiro_br(valor: int) -> str:
    """Formata inteiros com ponto como separador brasileiro de milhares."""
    if not isinstance(valor, int) or isinstance(valor, bool):
        raise TypeError("O valor deve ser um número inteiro.")
    return f"{valor:,}".replace(",", ".")


def formatar_percentual_progresso(avaliadas: int, total: int) -> str:
    """Percentual preciso inclusive para avanços minúsculos sobre 17!."""
    if avaliadas < 0 or total <= 0 or avaliadas > total:
        raise ValueError("O progresso deve estar entre zero e o total positivo.")
    if avaliadas == 0:
        return "0,000000%"
    if avaliadas == total:
        return "100,000000%"
    with localcontext() as contexto:
        contexto.prec = 40
        percentual = Decimal(avaliadas) * Decimal(100) / Decimal(total)
    if percentual < Decimal("0.000001"):
        return "menos de 0,000001%"
    return f"{percentual:.6f}%".replace(".", ",")


def formatar_duracao(segundos: float) -> str:
    if not isfinite(segundos) or segundos < 0:
        raise ValueError("A duração deve ser não negativa e finita.")
    if segundos < 60:
        return f"{segundos:.1f} s".replace(".", ",")
    total = int(segundos)
    dias, resto = divmod(total, 86_400)
    horas, resto = divmod(resto, 3_600)
    minutos, segundos_inteiros = divmod(resto, 60)
    partes: list[str] = []
    if dias:
        partes.append(f"{dias} d")
    if horas or dias:
        partes.append(f"{horas} h")
    partes.append(f"{minutos} min")
    partes.append(f"{segundos_inteiros} s")
    return " ".join(partes)


__all__ = [
    "arredondar_para_exibicao",
    "formatar_distancia_km",
    "formatar_inteiro_br",
    "formatar_percentual_progresso",
    "formatar_duracao",
    "formatar_numero_br",
]
