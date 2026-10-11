#!/usr/bin/env python3
"""Validação reproduzível da cidade completa, algoritmos e missão 3D."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Any


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from algorithms.caixeiro_viajante import caixeiro_viajante  # noqa: E402
from models.grafo import TipoVertice  # noqa: E402
from models.missao import ControladorMissao, EstadoMissao  # noqa: E402
from models.projeto_cidade import (  # noqa: E402
    carregar_projeto_cidade,
    projeto_para_dados,
    salvar_projeto_cidade,
)
from models.rota import calcular_dijkstra, calcular_tsp  # noqa: E402
from scripts.gerar_cidade_completa import (  # noqa: E402
    ANOTACOES_PADRAO,
    DESTINO_PADRAO,
    gerar_projeto,
)


CLIENTES = ("A", "B", "C", "E", "F")
HASHES_PROTEGIDOS = {
    "delivery-route1.json": "c2fa263faac7301ee1d8c324d0084c18bf3fdedaaeef192e8c2b9398177abc85",
    "delivery-route-5-entregas.json": "d894cc9f4d3faf83429a81b841c0af6535818a8c342e8f0330529d83a0b0bc91",
    "assets/models/cidade.glb": "6af0a41563b1ad48ddb60b83edbb5d2ea6d58189ebcb093887620ee0ef851d35",
    "assets/models/carro.glb": "523a2d819178e36c053b61236947001666bf1cfe3231fe0b497e4951965a8292",
}


def _exigir(condicao: bool, mensagem: str) -> None:
    if not condicao:
        raise AssertionError(mensagem)


def _sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _alcancaveis(grafo, origem: str) -> set[str]:
    visitados: set[str] = set()
    pendentes = [origem]
    while pendentes:
        atual = pendentes.pop()
        if atual in visitados:
            continue
        visitados.add(atual)
        pendentes.extend(set(grafo.obter_vizinhos(atual)) - visitados)
    return visitados


def validar(
    cenario_path: Path = DESTINO_PADRAO,
    anotacoes_path: Path = ANOTACOES_PADRAO,
) -> dict[str, Any]:
    for referencia, esperado in HASHES_PROTEGIDOS.items():
        caminho = RAIZ_PROJETO / referencia
        _exigir(caminho.is_file(), f"Arquivo protegido ausente: {referencia}.")
        _exigir(_sha256(caminho) == esperado, f"Arquivo protegido alterado: {referencia}.")

    with cenario_path.open("r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    with anotacoes_path.open("r", encoding="utf-8") as arquivo:
        anotacoes = json.load(arquivo)
    projeto = carregar_projeto_cidade(cenario_path)
    reproduzido, cobertura = gerar_projeto(anotacoes_path)
    _exigir(
        projeto_para_dados(projeto) == dados,
        "O cenário perde informações ao ser carregado.",
    )
    _exigir(
        projeto_para_dados(reproduzido) == dados,
        "O JSON não é reproduzido deterministicamente pelo gerador.",
    )

    grafo = projeto.grafo
    vertices = grafo.listar_vertices()
    depositos = [v for v in vertices if v.tipo is TipoVertice.DEPOSITO]
    clientes = grafo.listar_clientes()
    cruzamentos = [v for v in vertices if v.tipo is TipoVertice.CRUZAMENTO]
    _exigir(len(depositos) == 1, "Deve existir exatamente um depósito.")
    _exigir(
        (depositos[0].identificador, depositos[0].nome)
        == ("D", "Depósito Central"),
        "Depósito principal inválido.",
    )
    _exigir(len(clientes) == 5, "Devem existir exatamente cinco clientes.")
    _exigir({v.identificador for v in clientes} == set(CLIENTES), "Clientes inválidos.")
    _exigir(len(cruzamentos) == 24, "Quantidade inesperada de cruzamentos.")
    _exigir(
        {v.identificador for v in cruzamentos}
        == {f"X{indice}" for indice in range(1, 25)},
        "Os cruzamentos não usam a sequência X1..X24.",
    )

    servicos = anotacoes["pontos_servico"]
    imoveis = [item["imovel_referencia"] for item in servicos if item["tipo"] == "cliente"]
    regioes = [item["regiao"] for item in servicos if item["tipo"] == "cliente"]
    _exigir(len(imoveis) == len(set(imoveis)) == 5, "Clientes não usam cinco imóveis distintos.")
    _exigir(len(regioes) == len(set(regioes)) == 5, "Clientes não cobrem cinco regiões distintas.")

    ids = [v.identificador for v in vertices]
    _exigir(len(ids) == len(set(ids)), "Há IDs de vértices duplicados.")
    _exigir(set(projeto.posicoes) == set(ids), "Há posições 3D ausentes ou excedentes.")
    _exigir(
        _alcancaveis(grafo, "D") == set(ids),
        "A rede não forma um único componente conectado.",
    )
    graus = {identificador: len(grafo.obter_vizinhos(identificador)) for identificador in ids}
    _exigir(all(grau > 0 for grau in graus.values()), "Há vértices isolados.")
    _exigir(
        {identificador for identificador, grau in graus.items() if grau == 1} == {"X20"},
        "Há términos de via inesperados; X20 é a única saída sudeste do modelo.",
    )

    arestas = grafo.listar_arestas()
    chaves = [
        tuple(sorted((aresta.origem.identificador, aresta.destino.identificador)))
        for aresta in arestas
    ]
    _exigir(len(arestas) == 39, "Quantidade inesperada de arestas subdivididas.")
    _exigir(len(chaves) == len(set(chaves)), "Há arestas duplicadas.")
    _exigir(set(chaves) == set(projeto.ruas), "Arestas e polilinhas não coincidem.")
    maior_trecho = 0.0
    for aresta in arestas:
        origem = aresta.origem.identificador
        destino = aresta.destino.identificador
        _exigir(math.isfinite(aresta.peso) and aresta.peso > 0, "Peso inválido.")
        direta = projeto.polilinha_rua(origem, destino)
        inversa = projeto.polilinha_rua(destino, origem)
        _exigir(len(direta) >= 2, f"Polilinha ausente em {origem} ↔ {destino}.")
        _exigir(direta == tuple(reversed(inversa)), "Geometria inversa inconsistente.")
        _exigir(direta[0] == projeto.posicoes[origem], "Extremo inicial incorreto.")
        _exigir(direta[-1] == projeto.posicoes[destino], "Extremo final incorreto.")
        comprimento = sum(math.dist(a, b) for a, b in zip(direta, direta[1:]))
        maior_trecho = max(maior_trecho, comprimento)
        _exigir(
            math.isclose(
                aresta.peso,
                comprimento * projeto.fator_km_por_unidade,
                rel_tol=2e-6,
                abs_tol=1e-6,
            ),
            "Peso não corresponde ao comprimento geométrico.",
        )
        geometria = projeto.geometria_rua(origem, destino)
        _exigir(
            geometria is not None and geometria.calibrada_manualmente,
            "Rua sem confirmação baseada na evidência geométrica.",
        )

    _exigir(cobertura["trechos_reais_identificados"] == 33, "Referência de cobertura inválida.")
    _exigir(cobertura["trechos_reais_mapeados"] == 33, "Há trecho real não mapeado.")
    _exigir(not cobertura["regioes_sem_cobertura"], "Há regiões sem cobertura.")
    _exigir(not cobertura["trechos_pendentes"], "Há trechos pendentes.")

    resultados_dijkstra: dict[str, Any] = {}
    for cliente in CLIENTES:
        rota = calcular_dijkstra(projeto, "D", cliente)
        _exigir(rota.calibracao_completa and not rota.arestas_pendentes, "Dijkstra pendente.")
        resultados_dijkstra[cliente] = {
            "percurso": list(rota.percurso_completo),
            "distancia_km": rota.distancia_total,
            "arestas": len(rota.segmentos_espaciais),
            "calibracao": rota.estado_espacial.value,
        }

    rota_tsp = calcular_tsp(projeto, CLIENTES)
    bruto_tsp = caixeiro_viajante(grafo, CLIENTES)
    _exigir(rota_tsp.calibracao_completa, "TSP usa ruas não calibradas.")
    _exigir(rota_tsp.ordem_atendimento[0] == rota_tsp.ordem_atendimento[-1] == "D", "TSP não retorna ao depósito.")
    _exigir(set(rota_tsp.ordem_atendimento[1:-1]) == set(CLIENTES), "TSP não atende todos os clientes.")
    _exigir(tuple(bruto_tsp.percurso_completo) == rota_tsp.percurso_completo, "TSP integrado divergente.")

    missao = ControladorMissao(
        rota_tsp,
        velocidade_base=10.0,
        tempo_parada_entrega=0.0,
        velocidade_rotacao=720.0,
    )
    quadro = missao.iniciar()
    for _ in range(10_000):
        if quadro.estado is EstadoMissao.CONCLUIDA:
            break
        quadro = missao.avancar(0.02)
    _exigir(quadro.estado is EstadoMissao.CONCLUIDA, "Missão não concluída.")
    _exigir(set(quadro.clientes_atendidos) == set(CLIENTES), "Missão não atingiu 5/5.")
    _exigir(quadro.posicao == projeto.posicoes["D"], "Missão não retornou ao depósito.")

    with tempfile.TemporaryDirectory() as pasta:
        copia = Path(pasta) / "cidade-completa.json"
        salvar_projeto_cidade(projeto, copia)
        _exigir(
            projeto_para_dados(carregar_projeto_cidade(copia)) == dados,
            "O ciclo salvar/carregar perde dados.",
        )

    return {
        "arquivo": str(cenario_path),
        "depositos": len(depositos),
        "clientes": len(clientes),
        "cruzamentos": len(cruzamentos),
        "trechos_reais_identificados": cobertura["trechos_reais_identificados"],
        "trechos_reais_mapeados": cobertura["trechos_reais_mapeados"],
        "arestas_apos_subdivisoes": len(arestas),
        "ruas_calibradas": len(projeto.ruas),
        "ruas_pendentes": 0,
        "triangulos_asfalto": cobertura["triangulos_superiores_asfalto"],
        "amostras_laterais_no_asfalto": cobertura["amostras_laterais_validadas"],
        "meia_largura_carro": cobertura["meia_largura_carro"],
        "maior_distancia_asfalto_centrovia": cobertura["maior_distancia_asfalto_centrovia"],
        "maior_trecho_sem_salto": maior_trecho,
        "regioes_sem_cobertura": cobertura["regioes_sem_cobertura"],
        "dijkstra": resultados_dijkstra,
        "tsp": {
            "ordem": list(rota_tsp.ordem_atendimento),
            "percurso": list(rota_tsp.percurso_completo),
            "distancia_km": rota_tsp.distancia_total,
            "arestas": len(rota_tsp.segmentos_espaciais),
            "sequencias_avaliadas": bruto_tsp.sequencias_avaliadas,
            "calibracao": rota_tsp.estado_espacial.value,
        },
        "missao": {
            "estado": quadro.estado.value,
            "entregas": f"{len(quadro.clientes_atendidos)}/5",
            "retornou_ao_deposito": quadro.posicao == projeto.posicoes["D"],
        },
        "persistencia_sem_perda": True,
        "geracao_deterministica": True,
        "arquivos_protegidos_intactos": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cenario", nargs="?", type=Path, default=DESTINO_PADRAO)
    parser.add_argument("--anotacoes", type=Path, default=ANOTACOES_PADRAO)
    argumentos = parser.parse_args()
    relatorio = validar(argumentos.cenario.resolve(), argumentos.anotacoes.resolve())
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
