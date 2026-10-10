"""Converte uma rota matemática validada em dados declarativos para o QML."""

from __future__ import annotations

from models.projeto_cidade import ProjetoCidade
from models.rota import RotaCalculada


def segmentos_rota_qml(
    rota: RotaCalculada,
    indice_atual: int | None = None,
    *,
    concluida: bool = False,
) -> list[dict[str, object]]:
    segmentos: list[dict[str, object]] = []
    for trecho in rota.segmentos_espaciais:
        if not trecho.disponivel:
            continue
        estado = "restante"
        if concluida or (indice_atual is not None and trecho.indice < indice_atual):
            estado = "percorrido"
        elif indice_atual is not None and trecho.indice == indice_atual:
            estado = "atual"
        if estado == "percorrido":
            cor = "#64748B"
        elif estado == "atual":
            cor = "#FBBF24"
        else:
            cor = "#22D3EE" if trecho.confirmado_manualmente else "#F59E0B"
        for curva, (inicio, fim) in enumerate(zip(trecho.pontos, trecho.pontos[1:])):
            segmentos.append(
                {
                    "id": f"rota:{trecho.indice}:{curva}",
                    "sequencia": trecho.indice,
                    "origem": trecho.origem,
                    "destino": trecho.destino,
                    "confirmado": trecho.confirmado_manualmente,
                    "estado": estado,
                    "cor": cor,
                    "ax": inicio[0],
                    "ay": inicio[1] + 0.034,
                    "az": inicio[2],
                    "bx": fim[0],
                    "by": fim[1] + 0.034,
                    "bz": fim[2],
                }
            )
    return segmentos


def marcadores_rota_qml(
    rota: RotaCalculada,
    projeto: ProjetoCidade,
    clientes_atendidos: set[str] | frozenset[str] | None = None,
    proximo_cliente: str | None = None,
) -> list[dict[str, object]]:
    atendidos = clientes_atendidos or set()
    destaques: dict[str, dict[str, object]] = {}

    def adicionar(identificador: str, texto: str, cor: str) -> None:
        posicao = projeto.posicoes.get(identificador)
        if posicao is None:
            return
        existente = destaques.get(identificador)
        if existente is not None:
            rotulo = str(existente["texto"])
            if texto not in rotulo:
                existente["texto"] = f"{rotulo} / {texto}"
            return
        destaques[identificador] = {
            "id": identificador,
            "texto": texto,
            "cor": cor,
            "x": posicao[0],
            "y": posicao[1],
            "z": posicao[2],
        }

    if rota.percurso_completo:
        adicionar(rota.percurso_completo[0], "INÍCIO", "#38BDF8")
        adicionar(rota.percurso_completo[-1], "FIM", "#F59E0B")

    ordem_clientes = [
        identificador
        for identificador in rota.ordem_atendimento
        if identificador in rota.clientes_selecionados
    ]
    for indice, identificador in enumerate(ordem_clientes, start=1):
        if identificador in atendidos:
            texto, cor = f"ENTREGA {indice} · OK", "#64748B"
        elif identificador == proximo_cliente:
            texto, cor = f"PRÓXIMA · ENTREGA {indice}", "#FBBF24"
        else:
            texto, cor = f"ENTREGA {indice}", "#2DD4BF"
        adicionar(identificador, texto, cor)
    if not ordem_clientes:
        for identificador in rota.clientes_selecionados:
            adicionar(identificador, "CLIENTE", "#2DD4BF")
    return list(destaques.values())


def pontos_para_enquadrar(
    rota: RotaCalculada, projeto: ProjetoCidade
) -> list[tuple[float, float, float]]:
    pontos = list(rota.pontos_espaciais)
    for identificador in rota.percurso_completo:
        posicao = projeto.posicoes.get(identificador)
        if posicao is not None and posicao not in pontos:
            pontos.append(posicao)
    return pontos


__all__ = [
    "marcadores_rota_qml",
    "pontos_para_enquadrar",
    "segmentos_rota_qml",
]
