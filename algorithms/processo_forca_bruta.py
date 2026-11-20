"""Ponto de entrada serializável do processo da demonstração exaustiva."""

from __future__ import annotations

from queue import Full

from algorithms.forca_bruta_tempo_real import forca_bruta_tempo_real


def executar_forca_bruta_processo(
    grafo,
    clientes: tuple[str, ...],
    duracao_maxima_segundos: float | None,
    evento_interrupcao,
    fila,
) -> None:
    """Executa fora do processo Qt e publica progresso em baixa frequência."""

    def publicar_progresso(progresso) -> None:
        try:
            fila.put_nowait(("progresso", progresso))
        except Full:
            # O cálculo nunca espera a interface; a próxima fotografia substitui
            # naturalmente uma atualização intermediária descartada.
            pass

    try:
        resultado = forca_bruta_tempo_real(
            grafo,
            clientes,
            interromper=evento_interrupcao.is_set,
            progresso=publicar_progresso,
            duracao_maxima_segundos=duracao_maxima_segundos,
        )
        fila.put(("resultado", resultado))
    except BaseException as erro:  # pragma: no cover - fronteira do subprocesso
        fila.put(("erro", f"{type(erro).__name__}: {erro}"))


__all__ = ["executar_forca_bruta_processo"]
