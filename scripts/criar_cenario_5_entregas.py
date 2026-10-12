#!/usr/bin/env python3
"""Gera o cenário de demonstração somente a partir de dados espaciais existentes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from models.grafo import Grafo, TipoVertice, Vertice  # noqa: E402
from models.projeto_cidade import (  # noqa: E402
    GeometriaRua,
    ProjetoCidade,
    carregar_projeto_cidade,
    salvar_projeto_cidade,
)


ORIGEM_PADRAO = RAIZ_PROJETO / "delivery-route1.json"
DESTINO_PADRAO = RAIZ_PROJETO / "delivery-route-5-entregas.json"

# O antigo A é o único ponto excluído: sua aresta A-B não possui geometria 3D.
ID_DESCARTADO = "A"
MAPEAMENTO_IDS = {
    "D1": "D",
    "B": "A",
    "C1": "B",
    "C2": "C",
    "X2": "E",
    "X5": "F",
}
NOMES_DESTINO = {
    "D": "Depósito Central",
    "A": "Cliente A",
    "B": "Cliente B",
    "C": "Cliente C",
    "E": "Cliente D",
    "F": "Cliente E",
}
TIPOS_DESTINO = {
    "D": TipoVertice.DEPOSITO,
    "A": TipoVertice.CLIENTE,
    "B": TipoVertice.CLIENTE,
    "C": TipoVertice.CLIENTE,
    "E": TipoVertice.CLIENTE,
    "F": TipoVertice.CLIENTE,
}


def _novo_id(identificador: str) -> str:
    return MAPEAMENTO_IDS.get(identificador, identificador)


def criar_cenario(origem: Path = ORIGEM_PADRAO) -> ProjetoCidade:
    """Cria uma cópia organizada sem inventar posições, arestas ou pesos."""
    base = carregar_projeto_cidade(origem)
    ids_base = {vertice.identificador for vertice in base.grafo.listar_vertices()}
    esperados = set(MAPEAMENTO_IDS) | {ID_DESCARTADO}
    ausentes = sorted(esperados - ids_base)
    if ausentes:
        raise ValueError(
            "O cenário-base não contém os vértices esperados: " + ", ".join(ausentes)
        )

    grafo = Grafo()
    posicoes: dict[str, tuple[float, float, float]] = {}
    for vertice in base.grafo.listar_vertices():
        if vertice.identificador == ID_DESCARTADO:
            continue
        identificador = _novo_id(vertice.identificador)
        posicao = base.posicoes.get(vertice.identificador)
        if posicao is None:
            raise ValueError(
                f"O vértice-base '{vertice.identificador}' não possui posição 3D."
            )
        tipo = TIPOS_DESTINO.get(identificador, TipoVertice.CRUZAMENTO)
        nome = NOMES_DESTINO.get(identificador, f"Cruzamento {identificador}")
        # O editor oficial projeta a posição da cena no plano (x, z) do grafo.
        grafo.adicionar_vertice(
            Vertice(identificador, nome, tipo, posicao[0], posicao[2])
        )
        posicoes[identificador] = posicao

    for aresta in base.grafo.listar_arestas():
        origem_id = aresta.origem.identificador
        destino_id = aresta.destino.identificador
        if ID_DESCARTADO in (origem_id, destino_id):
            continue
        if base.geometria_rua(origem_id, destino_id) is None:
            raise ValueError(
                f"A aresta-base {origem_id} ↔ {destino_id} não possui geometria."
            )
        grafo.adicionar_aresta(
            _novo_id(origem_id), _novo_id(destino_id), aresta.peso
        )

    ruas: dict[tuple[str, str], GeometriaRua] = {}
    for geometria in base.ruas.values():
        if ID_DESCARTADO in (geometria.origem, geometria.destino):
            continue
        origem_id = _novo_id(geometria.origem)
        destino_id = _novo_id(geometria.destino)
        pontos = list(geometria.pontos_intermediarios)
        # Persiste cada rua com a mesma identidade canônica usada pelo carregador.
        if origem_id > destino_id:
            origem_id, destino_id = destino_id, origem_id
            pontos.reverse()
        chave = ProjetoCidade.chave_aresta(origem_id, destino_id)
        ruas[chave] = GeometriaRua(
            origem=origem_id,
            destino=destino_id,
            pontos_intermediarios=pontos,
            calibrada_manualmente=geometria.calibrada_manualmente,
        )

    projeto = ProjetoCidade(
        grafo=grafo,
        posicoes=posicoes,
        ruas=ruas,
        superficies=dict(base.superficies),
        modelo_cidade=base.modelo_cidade,
        modelo_carro=base.modelo_carro,
        fator_km_por_unidade=base.fator_km_por_unidade,
    )
    if len(projeto.grafo.listar_clientes()) != 5:
        raise ValueError("A transformação não produziu exatamente cinco clientes.")
    if projeto.grafo.obter_deposito() is None:
        raise ValueError("A transformação não produziu o depósito principal.")
    return projeto


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origem", type=Path, default=ORIGEM_PADRAO)
    parser.add_argument("--destino", type=Path, default=DESTINO_PADRAO)
    argumentos = parser.parse_args()
    origem = argumentos.origem.resolve()
    destino = argumentos.destino.resolve()
    if origem == destino:
        parser.error("o arquivo de destino deve ser diferente do cenário-base")
    projeto = criar_cenario(origem)
    salvar_projeto_cidade(projeto, destino)
    print(f"Cenário criado em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
