#!/usr/bin/env python3
"""Valida estrutura, proveniência, rotas e missão do cenário de cinco entregas."""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from itertools import combinations
from pathlib import Path


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from algorithms.caixeiro_viajante import caixeiro_viajante  # noqa: E402
from models.grafo import TipoVertice  # noqa: E402
from models.missao import ControladorMissao, EstadoMissao  # noqa: E402
from models.projeto_cidade import (  # noqa: E402
    ClassificacaoSuperficie,
    ProjetoCidade,
    carregar_projeto_cidade,
    projeto_para_dados,
    salvar_projeto_cidade,
)
from models.rota import calcular_dijkstra, calcular_tsp  # noqa: E402
from ui.assets_3d import ESCALA_CIDADE_PADRAO, inspecionar_modelo  # noqa: E402


CENARIO_PADRAO = RAIZ_PROJETO / "delivery-route-5-entregas.json"
ORIGEM_PADRAO = RAIZ_PROJETO / "delivery-route1.json"
CLIENTES = ("A", "B", "C", "E", "F")
NOMES_CLIENTES = {
    "A": "Cliente A",
    "B": "Cliente B",
    "C": "Cliente C",
    "E": "Cliente D",
    "F": "Cliente E",
}
ORIGEM_POR_ID = {
    "D": "D1",
    "A": "B",
    "B": "C1",
    "C": "C2",
    "E": "X2",
    "F": "X5",
}
ID_DESCARTADO_NA_ORIGEM = "A"


def _origem_id(identificador: str) -> str:
    return ORIGEM_POR_ID.get(identificador, identificador)


def _chave(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))  # type: ignore[return-value]


def _falhar(condicao: bool, mensagem: str) -> None:
    if not condicao:
        raise AssertionError(mensagem)


def _validar_proveniencia(projeto: ProjetoCidade, base: ProjetoCidade) -> None:
    ids = {vertice.identificador for vertice in projeto.grafo.listar_vertices()}
    ids_base_esperados = {
        _origem_id(identificador) for identificador in ids
    }
    ids_base_reais = {
        vertice.identificador
        for vertice in base.grafo.listar_vertices()
        if vertice.identificador != ID_DESCARTADO_NA_ORIGEM
    }
    _falhar(
        ids_base_esperados == ids_base_reais,
        "Os vértices não correspondem à cópia rastreável do cenário-base.",
    )
    for identificador in ids:
        _falhar(
            projeto.posicoes[identificador] == base.posicoes[_origem_id(identificador)],
            f"A posição de {identificador} não foi preservada do cenário-base.",
        )

    arestas_base: dict[tuple[str, str], float] = {}
    for aresta in base.grafo.listar_arestas():
        origem = aresta.origem.identificador
        destino = aresta.destino.identificador
        if ID_DESCARTADO_NA_ORIGEM in (origem, destino):
            continue
        arestas_base[_chave(origem, destino)] = aresta.peso
    _falhar(
        len(arestas_base) == len(projeto.grafo.listar_arestas()),
        "A quantidade de arestas difere da malha espacial aproveitável da origem.",
    )
    for aresta in projeto.grafo.listar_arestas():
        origem = aresta.origem.identificador
        destino = aresta.destino.identificador
        chave_base = _chave(_origem_id(origem), _origem_id(destino))
        _falhar(chave_base in arestas_base, f"A aresta {origem} ↔ {destino} foi inventada.")
        _falhar(
            aresta.peso == arestas_base[chave_base],
            f"O peso de {origem} ↔ {destino} foi alterado.",
        )
        pontos = projeto.polilinha_rua(origem, destino)
        pontos_base = base.polilinha_rua(
            _origem_id(origem), _origem_id(destino)
        )
        _falhar(
            pontos == pontos_base,
            f"A geometria de {origem} ↔ {destino} não veio do cenário-base.",
        )
        geometria = projeto.geometria_rua(origem, destino)
        geometria_base = base.geometria_rua(
            _origem_id(origem), _origem_id(destino)
        )
        _falhar(geometria is not None and geometria_base is not None, "Rua ausente.")
        _falhar(
            geometria.calibrada_manualmente
            == geometria_base.calibrada_manualmente,
            f"A confirmação de {origem} ↔ {destino} foi alterada.",
        )

    _falhar(projeto.superficies == base.superficies, "Superfícies foram alteradas.")
    _falhar(projeto.modelo_cidade == base.modelo_cidade, "Modelo da cidade alterado.")
    _falhar(projeto.modelo_carro == base.modelo_carro, "Modelo do carro alterado.")
    _falhar(
        projeto.fator_km_por_unidade == base.fator_km_por_unidade,
        "Fator de conversão alterado.",
    )


def validar(cenario: Path, origem: Path = ORIGEM_PADRAO) -> dict[str, object]:
    with cenario.open("r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    projeto = carregar_projeto_cidade(cenario)
    base = carregar_projeto_cidade(origem)
    grafo = projeto.grafo

    _falhar(dados.get("formato") == "delivery-route-cidade-3d", "Formato inválido.")
    _falhar(dados.get("versao") == 1, "Versão inválida.")
    _falhar(projeto_para_dados(projeto) == dados, "O JSON perde dados no carregamento.")

    vertices = grafo.listar_vertices()
    ids = [vertice.identificador for vertice in vertices]
    _falhar(len(ids) == len(set(ids)), "Há identificadores de vértices duplicados.")
    depositos = [v for v in vertices if v.tipo is TipoVertice.DEPOSITO]
    clientes = grafo.listar_clientes()
    cruzamentos = [v for v in vertices if v.tipo is TipoVertice.CRUZAMENTO]
    _falhar(len(depositos) == 1, "O cenário deve possuir um único depósito.")
    _falhar(depositos[0].identificador == "D", "O depósito deve usar o ID D.")
    _falhar(depositos[0].nome == "Depósito Central", "Nome do depósito inválido.")
    _falhar(len(clientes) == 5, "O cenário deve possuir exatamente cinco clientes.")
    _falhar({v.identificador for v in clientes} == set(CLIENTES), "IDs de clientes inválidos.")
    for cliente in clientes:
        _falhar(cliente.nome == NOMES_CLIENTES[cliente.identificador], "Nome de cliente inválido.")
    _falhar(len(cruzamentos) == 19, "Quantidade inesperada de cruzamentos.")
    _falhar(set(projeto.posicoes) == set(ids), "Nem todo vértice possui posição 3D.")

    # Confere que as coordenadas 2D seguem a projeção oficial (x, z) do editor.
    for vertice in vertices:
        x, _, z = projeto.posicoes[vertice.identificador]
        _falhar(
            math.isclose(vertice.x, x) and math.isclose(vertice.y, z),
            f"Coordenadas 2D/3D inconsistentes em {vertice.identificador}.",
        )

    arestas = grafo.listar_arestas()
    chaves_arestas = [
        _chave(aresta.origem.identificador, aresta.destino.identificador)
        for aresta in arestas
    ]
    _falhar(len(arestas) == 32, "Quantidade inesperada de ruas.")
    _falhar(len(chaves_arestas) == len(set(chaves_arestas)), "Há ruas duplicadas.")
    _falhar(set(projeto.ruas) == set(chaves_arestas), "Arestas e geometrias divergem.")

    confirmadas = 0
    pendentes: list[tuple[str, str]] = []
    maior_erro_relativo = 0.0
    for aresta in arestas:
        origem_id = aresta.origem.identificador
        destino_id = aresta.destino.identificador
        _falhar(math.isfinite(aresta.peso) and aresta.peso > 0, "Peso inválido.")
        geometria = projeto.geometria_rua(origem_id, destino_id)
        pontos = projeto.polilinha_rua(origem_id, destino_id)
        _falhar(geometria is not None and len(pontos) >= 2, "Polilinha ausente.")
        comprimento = sum(math.dist(a, b) for a, b in zip(pontos, pontos[1:]))
        _falhar(comprimento > 0, "Polilinha de comprimento nulo.")
        esperado = comprimento * projeto.fator_km_por_unidade
        erro_relativo = abs(aresta.peso - esperado) / esperado
        maior_erro_relativo = max(maior_erro_relativo, erro_relativo)
        _falhar(erro_relativo < 1e-4, "Peso incompatível com a geometria espacial.")
        if geometria.calibrada_manualmente:
            confirmadas += 1
        else:
            pendentes.append(_chave(origem_id, destino_id))

    _falhar(
        sum(c is ClassificacaoSuperficie.RUA for c in projeto.superficies.values()) == 2,
        "As duas superfícies trafegáveis da origem devem ser preservadas.",
    )
    _validar_proveniencia(projeto, base)

    # Os clientes precisam estar visualmente distribuídos, não sobrepostos.
    separacoes = [
        math.dist(
            (projeto.posicoes[a][0], projeto.posicoes[a][2]),
            (projeto.posicoes[b][0], projeto.posicoes[b][2]),
        )
        for a, b in combinations(CLIENTES, 2)
    ]
    _falhar(min(separacoes) > 0.30, "Há clientes praticamente sobrepostos.")

    modelos = {}
    for nome, referencia in (
        ("cidade", projeto.modelo_cidade),
        ("carro", projeto.modelo_carro),
    ):
        caminho_modelo = (RAIZ_PROJETO / referencia).resolve()
        _falhar(caminho_modelo.is_file(), f"Modelo {nome} não encontrado.")
        info = inspecionar_modelo(caminho_modelo)
        modelos[nome] = {
            "arquivo": referencia,
            "malhas": info.malhas,
            "materiais": info.materiais,
        }
    limites = inspecionar_modelo((RAIZ_PROJETO / projeto.modelo_cidade).resolve()).limites
    minimo = tuple(valor * ESCALA_CIDADE_PADRAO for valor in limites.minimo)
    maximo = tuple(valor * ESCALA_CIDADE_PADRAO for valor in limites.maximo)
    for identificador, posicao in projeto.posicoes.items():
        _falhar(
            all(minimo[eixo] <= posicao[eixo] <= maximo[eixo] for eixo in range(3)),
            f"{identificador} está fora dos limites da cidade escalada.",
        )

    resultados_dijkstra: dict[str, object] = {}
    for cliente in CLIENTES:
        rota = calcular_dijkstra(projeto, "D", cliente)
        _falhar(rota.calibracao_completa, f"Rota D → {cliente} não está calibrada.")
        resultados_dijkstra[cliente] = {
            "percurso": list(rota.percurso_completo),
            "distancia_km": rota.distancia_total,
        }

    rota_tsp = calcular_tsp(projeto, CLIENTES)
    resultado_tsp = caixeiro_viajante(grafo, CLIENTES)
    _falhar(rota_tsp.calibracao_completa, "O TSP usa ruas pendentes.")
    _falhar(rota_tsp.ordem_atendimento[0] == "D", "TSP não inicia no depósito.")
    _falhar(rota_tsp.ordem_atendimento[-1] == "D", "TSP não retorna ao depósito.")
    _falhar(set(rota_tsp.ordem_atendimento[1:-1]) == set(CLIENTES), "TSP incompleto.")
    _falhar(not rota_tsp.arestas_pendentes, "O TSP possui pendências espaciais.")
    _falhar(
        tuple(resultado_tsp.ordem_entregas) == rota_tsp.ordem_atendimento
        and tuple(resultado_tsp.percurso_completo) == rota_tsp.percurso_completo
        and resultado_tsp.distancia_total == rota_tsp.distancia_total,
        "O resultado integrado diverge do TSP exato oficial.",
    )

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
    _falhar(quadro.estado is EstadoMissao.CONCLUIDA, "A missão não foi concluída.")
    _falhar(set(quadro.clientes_atendidos) == set(CLIENTES), "A missão não entregou 5/5.")
    _falhar(quadro.posicao == projeto.posicoes["D"], "A missão não retornou ao depósito.")

    with tempfile.TemporaryDirectory() as pasta:
        copia = Path(pasta) / "cenario.json"
        salvar_projeto_cidade(projeto, copia)
        recarregado = carregar_projeto_cidade(copia)
        _falhar(
            projeto_para_dados(recarregado) == dados,
            "O ciclo salvar/carregar causa perda de dados.",
        )

    return {
        "arquivo": str(cenario),
        "origem_dos_dados": str(origem),
        "depositos": len(depositos),
        "clientes": len(clientes),
        "cruzamentos": len(cruzamentos),
        "ruas": len(arestas),
        "ruas_confirmadas": confirmadas,
        "ruas_pendentes": len(pendentes),
        "maior_erro_relativo_peso_geometria": maior_erro_relativo,
        "menor_separacao_entre_clientes": min(separacoes),
        "modelos": modelos,
        "dijkstra": resultados_dijkstra,
        "tsp": {
            "ordem": list(rota_tsp.ordem_atendimento),
            "percurso_completo": list(rota_tsp.percurso_completo),
            "distancia_km": rota_tsp.distancia_total,
            "sequencias_avaliadas": resultado_tsp.sequencias_avaliadas,
        },
        "missao": {
            "estado": quadro.estado.value,
            "entregas": f"{len(quadro.clientes_atendidos)}/5",
            "retornou_ao_deposito": quadro.posicao == projeto.posicoes["D"],
        },
        "persistencia_sem_perda": True,
        "proveniencia_integral": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cenario", nargs="?", type=Path, default=CENARIO_PADRAO)
    parser.add_argument("--origem", type=Path, default=ORIGEM_PADRAO)
    argumentos = parser.parse_args()
    relatorio = validar(argumentos.cenario.resolve(), argumentos.origem.resolve())
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
