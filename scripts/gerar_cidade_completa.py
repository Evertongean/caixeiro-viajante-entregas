#!/usr/bin/env python3
"""Reconstrói a malha viária completa e a valida diretamente no cidade.glb."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any, Sequence


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from models.grafo import Grafo, TipoVertice, Vertice  # noqa: E402
from models.projeto_cidade import (  # noqa: E402
    ClassificacaoSuperficie,
    GeometriaRua,
    ProjetoCidade,
    salvar_projeto_cidade,
)
from ui.assets_3d import (  # noqa: E402
    _identidade,
    _matriz_no,
    _multiplicar,
    _transformar,
    inspecionar_modelo,
)


ANOTACOES_PADRAO = RAIZ_PROJETO / "data/cidade_completa_vias.json"
DESTINO_PADRAO = RAIZ_PROJETO / "delivery-route-cidade-completa.json"
Ponto3D = tuple[float, float, float]
Triangulo2D = tuple[tuple[float, float], tuple[float, float], tuple[float, float]]


def _sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _ler_glb(caminho: Path) -> tuple[dict[str, Any], bytes]:
    bruto = caminho.read_bytes()
    if len(bruto) < 28:
        raise ValueError("O GLB não possui os blocos obrigatórios.")
    assinatura, versao, tamanho = struct.unpack_from("<4sII", bruto, 0)
    if assinatura != b"glTF" or versao != 2 or tamanho != len(bruto):
        raise ValueError("O modelo da cidade não é um GLB 2.0 válido.")
    tamanho_json, tipo_json = struct.unpack_from("<II", bruto, 12)
    if tipo_json != 0x4E4F534A:
        raise ValueError("O primeiro bloco do GLB não é JSON.")
    inicio_binario = 20 + tamanho_json
    documento = json.loads(
        bruto[20:inicio_binario].rstrip(b"\0 \t\r\n").decode("utf-8")
    )
    tamanho_binario, tipo_binario = struct.unpack_from(
        "<II", bruto, inicio_binario
    )
    if tipo_binario != 0x004E4942:
        raise ValueError("O segundo bloco do GLB não é BIN.")
    inicio_dados = inicio_binario + 8
    return documento, bruto[inicio_dados : inicio_dados + tamanho_binario]


def _ler_accessor(
    documento: dict[str, Any], binario: bytes, indice: int
) -> list[tuple[float | int, ...]]:
    accessor = documento["accessors"][indice]
    view = documento["bufferViews"][accessor["bufferView"]]
    componentes = {
        5120: ("b", 1),
        5121: ("B", 1),
        5122: ("h", 2),
        5123: ("H", 2),
        5125: ("I", 4),
        5126: ("f", 4),
    }
    dimensoes = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
    formato, tamanho = componentes[accessor["componentType"]]
    quantidade = dimensoes[accessor["type"]]
    passo = view.get("byteStride", quantidade * tamanho)
    inicio = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    return [
        struct.unpack_from(
            "<" + formato * quantidade,
            binario,
            inicio + item * passo,
        )
        for item in range(accessor["count"])
    ]


def _matriz_mundo(documento: dict[str, Any], indice_no: int):
    nos = documento["nodes"]
    pais = {
        filho: indice
        for indice, no in enumerate(nos)
        for filho in no.get("children", [])
    }
    cadeia = [indice_no]
    while cadeia[-1] in pais:
        cadeia.append(pais[cadeia[-1]])
    matriz = _identidade()
    for indice in reversed(cadeia):
        matriz = _multiplicar(matriz, _matriz_no(nos[indice]))
    return matriz


class SuperficieAsfalto:
    """Triângulos superiores trafegáveis extraídos da malha real do GLB."""

    def __init__(
        self,
        caminho: Path,
        *,
        nome_no: str,
        nome_material: str,
        escala_qml: float,
    ) -> None:
        documento, binario = _ler_glb(caminho)
        nos = documento["nodes"]
        candidatos = [
            (indice, no)
            for indice, no in enumerate(nos)
            if no.get("name") == nome_no and isinstance(no.get("mesh"), int)
        ]
        if len(candidatos) != 1:
            raise ValueError(f"Esperado um único nó de asfalto '{nome_no}'.")
        indice_no, no = candidatos[0]
        mesh = documento["meshes"][no["mesh"]]
        materiais = documento["materials"]
        primitivas = [
            primitiva
            for primitiva in mesh.get("primitives", [])
            if materiais[primitiva.get("material", -1)].get("name")
            == nome_material
        ]
        if len(primitivas) != 1:
            raise ValueError(
                f"Esperada uma única primitiva com material '{nome_material}'."
            )
        primitiva = primitivas[0]
        if primitiva.get("mode", 4) != 4 or "indices" not in primitiva:
            raise ValueError("A superfície de asfalto precisa usar triângulos indexados.")
        matriz = _matriz_mundo(documento, indice_no)
        posicoes = [
            tuple(
                coordenada * escala_qml
                for coordenada in _transformar(matriz, posicao)
            )
            for posicao in _ler_accessor(
                documento, binario, primitiva["attributes"]["POSITION"]
            )
        ]
        indices = [
            int(item[0])
            for item in _ler_accessor(documento, binario, primitiva["indices"])
        ]
        self.triangulos: list[Triangulo2D] = []
        alturas: list[float] = []
        for inicio in range(0, len(indices), 3):
            pontos = [posicoes[indices[inicio + deslocamento]] for deslocamento in range(3)]
            a, b, c = pontos
            ab = tuple(b[eixo] - a[eixo] for eixo in range(3))
            ac = tuple(c[eixo] - a[eixo] for eixo in range(3))
            normal = (
                ab[1] * ac[2] - ab[2] * ac[1],
                ab[2] * ac[0] - ab[0] * ac[2],
                ab[0] * ac[1] - ab[1] * ac[0],
            )
            norma = math.sqrt(sum(valor * valor for valor in normal))
            if norma == 0 or normal[1] / norma <= 0.9:
                continue
            self.triangulos.append(
                tuple((ponto[0], ponto[2]) for ponto in pontos)  # type: ignore[arg-type]
            )
            alturas.extend(ponto[1] for ponto in pontos)
        if not self.triangulos:
            raise ValueError("Nenhum triângulo superior foi encontrado no asfalto.")
        self.altura = sum(alturas) / len(alturas)
        self.nome_no = nome_no
        self.nome_material = nome_material

    @staticmethod
    def _ponto_no_triangulo(
        ponto: tuple[float, float], triangulo: Triangulo2D
    ) -> bool:
        x, z = ponto
        (x1, z1), (x2, z2), (x3, z3) = triangulo
        denominador = (z2 - z3) * (x1 - x3) + (x3 - x2) * (z1 - z3)
        if abs(denominador) < 1e-14:
            return False
        a = ((z2 - z3) * (x - x3) + (x3 - x2) * (z - z3)) / denominador
        b = ((z3 - z1) * (x - x3) + (x1 - x3) * (z - z3)) / denominador
        c = 1.0 - a - b
        tolerancia = 1e-8
        return a >= -tolerancia and b >= -tolerancia and c >= -tolerancia

    def contem(self, x: float, z: float) -> bool:
        return any(
            self._ponto_no_triangulo((x, z), triangulo)
            for triangulo in self.triangulos
        )

    def validar_segmento(
        self,
        inicio: Sequence[float],
        fim: Sequence[float],
        *,
        passo: float,
        meia_largura: float,
    ) -> int:
        dx = float(fim[0]) - float(inicio[0])
        dz = float(fim[2]) - float(inicio[2])
        comprimento = math.hypot(dx, dz)
        if comprimento <= 0:
            raise ValueError("Um segmento viário possui comprimento nulo.")
        amostras = max(2, math.ceil(comprimento / passo) + 1)
        normal = (-dz / comprimento, dx / comprimento)
        for indice in range(amostras):
            t = indice / (amostras - 1)
            x = float(inicio[0]) + dx * t
            z = float(inicio[2]) + dz * t
            for afastamento in (0.0, -meia_largura, meia_largura):
                lateral = (
                    x + normal[0] * afastamento,
                    z + normal[1] * afastamento,
                )
                if not self.contem(*lateral):
                    raise ValueError(
                        "O segmento sai do asfalto em "
                        f"({lateral[0]:.6f}, {lateral[1]:.6f})."
                    )
        return amostras * 3


def _distancia_ponto_segmento(
    ponto: tuple[float, float],
    inicio: tuple[float, float],
    fim: tuple[float, float],
) -> float:
    dx, dz = fim[0] - inicio[0], fim[1] - inicio[1]
    denominador = dx * dx + dz * dz
    t = 0.0 if denominador == 0 else (
        (ponto[0] - inicio[0]) * dx + (ponto[1] - inicio[1]) * dz
    ) / denominador
    t = max(0.0, min(1.0, t))
    return math.hypot(
        ponto[0] - (inicio[0] + t * dx),
        ponto[1] - (inicio[1] + t * dz),
    )


def _parametro_no_segmento(
    ponto: Sequence[float], inicio: Sequence[float], fim: Sequence[float]
) -> float:
    dx, dz = float(fim[0]) - float(inicio[0]), float(fim[2]) - float(inicio[2])
    denominador = dx * dx + dz * dz
    if denominador == 0:
        raise ValueError("Trecho de referência com comprimento nulo.")
    t = (
        (float(ponto[0]) - float(inicio[0])) * dx
        + (float(ponto[2]) - float(inicio[2])) * dz
    ) / denominador
    projetado = (
        float(inicio[0]) + t * dx,
        float(inicio[2]) + t * dz,
    )
    erro = math.hypot(float(ponto[0]) - projetado[0], float(ponto[2]) - projetado[1])
    if not 0.0 < t < 1.0 or erro > 1e-9:
        raise ValueError("Um ponto de serviço não subdivide corretamente seu trecho.")
    return t


def _carregar_anotacoes(caminho: Path) -> dict[str, Any]:
    with caminho.open("r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    if dados.get("formato") != "delivery-route-anotacao-viaria" or dados.get("versao") != 1:
        raise ValueError("Formato de anotações viárias incompatível.")
    return dados


def gerar_projeto(
    anotacoes_path: Path = ANOTACOES_PADRAO,
) -> tuple[ProjetoCidade, dict[str, Any]]:
    anotacoes = _carregar_anotacoes(anotacoes_path)
    origem = anotacoes["origem"]
    cidade = (RAIZ_PROJETO / origem["modelo_cidade"]).resolve()
    carro = (RAIZ_PROJETO / origem["modelo_carro"]).resolve()
    if _sha256(cidade) != origem["sha256_cidade"]:
        raise ValueError("O cidade.glb difere do modelo usado na anotação.")
    if _sha256(carro) != origem["sha256_carro"]:
        raise ValueError("O carro.glb difere do modelo usado na anotação.")
    superficie = SuperficieAsfalto(
        cidade,
        nome_no=origem["no_asfalto"],
        nome_material=origem["material_asfalto"],
        escala_qml=float(origem["escala_qml_cidade"]),
    )
    if len(superficie.triangulos) != origem["triangulos_superiores_asfalto"]:
        raise ValueError("A triangulação superior do asfalto foi alterada.")
    if not math.isclose(
        superficie.altura,
        float(origem["altura_pavimento"]),
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ValueError("A altura real do pavimento difere da anotação.")

    info_carro = inspecionar_modelo(carro)
    meia_largura_carro = (
        info_carro.limites.dimensoes[0]
        * float(origem["escala_qml_carro"])
        * 0.5
    )
    cruzamentos = {item["id"]: tuple(item["posicao"]) for item in anotacoes["cruzamentos"]}
    servicos = {item["id"]: item for item in anotacoes["pontos_servico"]}
    if len(cruzamentos) != len(anotacoes["cruzamentos"]):
        raise ValueError("Há cruzamentos duplicados nas anotações.")
    if set(cruzamentos) & set(servicos):
        raise ValueError("Há conflito entre IDs de cruzamentos e serviços.")

    grafo = Grafo()
    posicoes: dict[str, Ponto3D] = {}
    for item in anotacoes["pontos_servico"]:
        tipo = TipoVertice(item["tipo"])
        posicao = tuple(float(valor) for valor in item["posicao"])
        grafo.adicionar_vertice(
            Vertice(item["id"], item["nome"], tipo, posicao[0], posicao[2])
        )
        posicoes[item["id"]] = posicao  # type: ignore[assignment]
    for identificador, posicao_bruta in cruzamentos.items():
        posicao = tuple(float(valor) for valor in posicao_bruta)
        grafo.adicionar_vertice(
            Vertice(
                identificador,
                f"Cruzamento {identificador}",
                TipoVertice.CRUZAMENTO,
                posicao[0],
                posicao[2],
            )
        )
        posicoes[identificador] = posicao  # type: ignore[assignment]

    por_trecho: dict[str, list[dict[str, Any]]] = {}
    for item in anotacoes["pontos_servico"]:
        por_trecho.setdefault(item["trecho"], []).append(item)
    ruas: dict[tuple[str, str], GeometriaRua] = {}
    amostras_validadas = 0
    referencia_segmentos: list[tuple[tuple[float, float], tuple[float, float]]] = []
    ids_trechos: set[str] = set()
    for trecho in anotacoes["trechos_referencia"]:
        trecho_id = trecho["id"]
        if trecho_id in ids_trechos:
            raise ValueError(f"Trecho de referência duplicado: {trecho_id}.")
        ids_trechos.add(trecho_id)
        origem_id, destino_id = trecho["origem"], trecho["destino"]
        inicio, fim = posicoes[origem_id], posicoes[destino_id]
        referencia_segmentos.append(((inicio[0], inicio[2]), (fim[0], fim[2])))
        internos = sorted(
            por_trecho.get(trecho_id, []),
            key=lambda item: _parametro_no_segmento(item["posicao"], inicio, fim),
        )
        cadeia = [origem_id, *(item["id"] for item in internos), destino_id]
        for a, b in zip(cadeia, cadeia[1:]):
            ponto_a, ponto_b = posicoes[a], posicoes[b]
            amostras_validadas += superficie.validar_segmento(
                ponto_a,
                ponto_b,
                passo=0.005,
                meia_largura=meia_largura_carro,
            )
            peso = round(
                math.dist(ponto_a, ponto_b) * float(origem["fator_km_por_unidade"]),
                6,
            )
            grafo.adicionar_aresta(a, b, peso)
            chave = ProjetoCidade.chave_aresta(a, b)
            rua_origem, rua_destino = chave
            ruas[chave] = GeometriaRua(
                rua_origem,
                rua_destino,
                [],
                calibrada_manualmente=True,
            )
    trechos_inexistentes = set(por_trecho) - ids_trechos
    if trechos_inexistentes:
        raise ValueError(
            "Pontos de serviço referenciam trechos inexistentes: "
            + ", ".join(sorted(trechos_inexistentes))
        )

    pontos_cobertura: list[tuple[float, float]] = []
    for triangulo in superficie.triangulos:
        pontos_cobertura.extend(triangulo)
        pontos_cobertura.append(
            (
                sum(ponto[0] for ponto in triangulo) / 3.0,
                sum(ponto[1] for ponto in triangulo) / 3.0,
            )
        )
    maior_distancia_cobertura = max(
        min(
            _distancia_ponto_segmento(ponto, inicio, fim)
            for inicio, fim in referencia_segmentos
        )
        for ponto in pontos_cobertura
    )
    if maior_distancia_cobertura > 0.085:
        raise ValueError(
            "A referência de linhas centrais não cobre toda a superfície de asfalto."
        )

    projeto = ProjetoCidade(
        grafo=grafo,
        posicoes=posicoes,
        ruas=ruas,
        superficies={
            origem["superficie_asfalto"]: ClassificacaoSuperficie.RUA,
            origem["superficie_calcada"]: ClassificacaoSuperficie.CALCADA,
        },
        modelo_cidade=origem["modelo_cidade"],
        modelo_carro=origem["modelo_carro"],
        fator_km_por_unidade=float(origem["fator_km_por_unidade"]),
    )
    relatorio = {
        "triangulos_superiores_asfalto": len(superficie.triangulos),
        "altura_pavimento": superficie.altura,
        "trechos_reais_identificados": len(anotacoes["trechos_referencia"]),
        "trechos_reais_mapeados": len(referencia_segmentos),
        "arestas_apos_subdivisoes": len(grafo.listar_arestas()),
        "amostras_laterais_validadas": amostras_validadas,
        "meia_largura_carro": meia_largura_carro,
        "maior_distancia_asfalto_centrovia": maior_distancia_cobertura,
        "regioes_sem_cobertura": [],
        "trechos_pendentes": [],
    }
    return projeto, relatorio


def gerar_arquivo(
    destino: Path = DESTINO_PADRAO,
    anotacoes_path: Path = ANOTACOES_PADRAO,
) -> dict[str, Any]:
    projeto, relatorio = gerar_projeto(anotacoes_path)
    salvar_projeto_cidade(projeto, destino)
    return relatorio


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anotacoes", type=Path, default=ANOTACOES_PADRAO)
    parser.add_argument("--destino", type=Path, default=DESTINO_PADRAO)
    argumentos = parser.parse_args()
    relatorio = gerar_arquivo(
        argumentos.destino.resolve(), argumentos.anotacoes.resolve()
    )
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
