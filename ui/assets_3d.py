"""Validação dos GLBs e conversão reproduzível para Qt Quick 3D."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Sequence

from models.projeto_cidade import ClassificacaoSuperficie


ESCALA_CIDADE_PADRAO = 0.01
ESCALA_CARRO_PADRAO = 0.018


class ErroModelo3D(RuntimeError):
    """Falha explicada de validação ou preparação de um modelo 3D."""


@dataclass(frozen=True, slots=True)
class Limites3D:
    minimo: tuple[float, float, float]
    maximo: tuple[float, float, float]

    @property
    def centro(self) -> tuple[float, float, float]:
        return tuple(
            (self.minimo[i] + self.maximo[i]) * 0.5 for i in range(3)
        )  # type: ignore[return-value]

    @property
    def dimensoes(self) -> tuple[float, float, float]:
        return tuple(
            self.maximo[i] - self.minimo[i] for i in range(3)
        )  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class InformacoesModelo3D:
    caminho: Path
    tamanho_bytes: int
    malhas: int
    materiais: int
    texturas: int
    limites: Limites3D


@dataclass(frozen=True, slots=True)
class AssetConvertido:
    origem: Path
    qml: Path
    diretorio: Path
    veio_do_cache: bool


Triangulo3D = tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]


@dataclass(frozen=True, slots=True)
class AmostraSuperficie:
    referencia: str
    classificacao: ClassificacaoSuperficie
    altura: float


@dataclass(frozen=True, slots=True)
class TrianguloSuperficieGLB:
    """Triângulo renderizável com a semântica bruta disponível no GLB."""

    referencia: str
    nome_no: str
    nome_material: str
    cor_base: tuple[float, float, float, float]
    triangulo: Triangulo3D


@dataclass(frozen=True, slots=True)
class MapaSuperficies3D:
    """Triângulos reais das superfícies semanticamente classificadas do GLB."""

    triangulos: dict[str, tuple[Triangulo3D, ...]]
    classificacoes: dict[str, ClassificacaoSuperficie]

    @staticmethod
    def _altura_triangulo(
        triangulo: Triangulo3D, x: float, z: float
    ) -> float | None:
        a, b, c = triangulo
        abx, abz = b[0] - a[0], b[2] - a[2]
        acx, acz = c[0] - a[0], c[2] - a[2]
        apx, apz = x - a[0], z - a[2]
        denominador = abx * acz - abz * acx
        if abs(denominador) <= 1e-12:
            return None
        u = (apx * acz - apz * acx) / denominador
        v = (abx * apz - abz * apx) / denominador
        if u < -1e-8 or v < -1e-8 or u + v > 1.0 + 1e-8:
            return None
        return a[1] + u * (b[1] - a[1]) + v * (c[1] - a[1])

    def amostrar(self, x: float, z: float) -> AmostraSuperficie | None:
        """Retorna a superfície classificada visível mais alta nesse ponto."""
        melhor: AmostraSuperficie | None = None
        for referencia, triangulos in self.triangulos.items():
            alturas = (
                altura
                for triangulo in triangulos
                if (altura := self._altura_triangulo(triangulo, x, z)) is not None
            )
            altura = max(alturas, default=None)
            if altura is None:
                continue
            amostra = AmostraSuperficie(
                referencia, self.classificacoes[referencia], altura
            )
            if melhor is None or amostra.altura > melhor.altura:
                melhor = amostra
        return melhor


Matriz = tuple[tuple[float, float, float, float], ...]


def _identidade() -> Matriz:
    return (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )


def _multiplicar(a: Matriz, b: Matriz) -> Matriz:
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4))
        for i in range(4)
    )


def _matriz_no(no: dict[str, Any]) -> Matriz:
    matriz = no.get("matrix")
    if isinstance(matriz, list) and len(matriz) == 16:
        return tuple(
            tuple(float(matriz[coluna * 4 + linha]) for coluna in range(4))
            for linha in range(4)
        )

    tx, ty, tz = (float(v) for v in no.get("translation", (0, 0, 0)))
    sx, sy, sz = (float(v) for v in no.get("scale", (1, 1, 1)))
    x, y, z, w = (float(v) for v in no.get("rotation", (0, 0, 0, 1)))
    rotacao = (
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
    )
    return (
        (rotacao[0][0] * sx, rotacao[0][1] * sy, rotacao[0][2] * sz, tx),
        (rotacao[1][0] * sx, rotacao[1][1] * sy, rotacao[1][2] * sz, ty),
        (rotacao[2][0] * sx, rotacao[2][1] * sy, rotacao[2][2] * sz, tz),
        (0.0, 0.0, 0.0, 1.0),
    )


def _transformar(matriz: Matriz, ponto: Sequence[float]) -> tuple[float, float, float]:
    vetor = (float(ponto[0]), float(ponto[1]), float(ponto[2]), 1.0)
    return tuple(
        sum(matriz[linha][coluna] * vetor[coluna] for coluna in range(4))
        for linha in range(3)
    )  # type: ignore[return-value]


def _ler_documento_glb(caminho: Path) -> dict[str, Any]:
    try:
        dados = caminho.read_bytes()
    except OSError as erro:
        raise ErroModelo3D(f"Não foi possível ler {caminho}: {erro}") from erro
    if len(dados) < 20:
        raise ErroModelo3D(f"{caminho.name} não possui um cabeçalho GLB completo.")
    assinatura, versao, tamanho = struct.unpack_from("<4sII", dados, 0)
    if assinatura != b"glTF" or versao != 2 or tamanho != len(dados):
        raise ErroModelo3D(f"{caminho.name} não é um arquivo glTF 2.0 válido.")
    comprimento, tipo = struct.unpack_from("<II", dados, 12)
    if tipo != 0x4E4F534A or 20 + comprimento > len(dados):
        raise ErroModelo3D(f"{caminho.name} não possui o bloco JSON obrigatório.")
    try:
        documento = json.loads(
            dados[20 : 20 + comprimento].rstrip(b"\0 \t\r\n").decode("utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ErroModelo3D(f"O JSON interno de {caminho.name} é inválido.") from erro
    if not isinstance(documento, dict):
        raise ErroModelo3D(f"O documento interno de {caminho.name} é inválido.")
    return documento


def _ler_glb(caminho: Path) -> tuple[dict[str, Any], bytes]:
    documento = _ler_documento_glb(caminho)
    dados = caminho.read_bytes()
    comprimento_json = struct.unpack_from("<I", dados, 12)[0]
    inicio = 20 + comprimento_json
    inicio += (-inicio) % 4
    if inicio + 8 > len(dados):
        raise ErroModelo3D(f"{caminho.name} não possui bloco binário.")
    comprimento_binario, tipo = struct.unpack_from("<II", dados, inicio)
    if tipo != 0x004E4942 or inicio + 8 + comprimento_binario > len(dados):
        raise ErroModelo3D(f"O bloco binário de {caminho.name} é inválido.")
    return documento, dados[inicio + 8 : inicio + 8 + comprimento_binario]


_FORMATOS_COMPONENTE = {
    5120: "b",
    5121: "B",
    5122: "h",
    5123: "H",
    5125: "I",
    5126: "f",
}
_COMPONENTES_TIPO = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
}


def _ler_acessor(
    documento: dict[str, Any], bloco: bytes, indice: int
) -> list[tuple[float, ...]]:
    try:
        acessor = documento["accessors"][indice]
        vista = documento["bufferViews"][acessor["bufferView"]]
        formato = _FORMATOS_COMPONENTE[acessor["componentType"]]
        componentes = _COMPONENTES_TIPO[acessor["type"]]
        quantidade = int(acessor["count"])
    except (KeyError, IndexError, TypeError, ValueError) as erro:
        raise ErroModelo3D("Um acessor do GLB é incompatível.") from erro
    formato_item = "<" + formato * componentes
    tamanho_item = struct.calcsize(formato_item)
    passo = int(vista.get("byteStride", tamanho_item))
    inicio = int(vista.get("byteOffset", 0)) + int(acessor.get("byteOffset", 0))
    if passo < tamanho_item or inicio < 0:
        raise ErroModelo3D("Um acessor do GLB possui deslocamento inválido.")
    resultado: list[tuple[float, ...]] = []
    try:
        for item in range(quantidade):
            valores = struct.unpack_from(formato_item, bloco, inicio + item * passo)
            resultado.append(tuple(float(valor) for valor in valores))
    except struct.error as erro:
        raise ErroModelo3D("Um acessor ultrapassa o bloco binário do GLB.") from erro
    return resultado


def extrair_mapa_superficies(
    caminho: str | os.PathLike[str],
    classificacoes: dict[str, ClassificacaoSuperficie],
    *,
    escala: float = ESCALA_CIDADE_PADRAO,
) -> MapaSuperficies3D:
    """Extrai somente as malhas classificadas, com transformações reais dos nós."""
    if not isinstance(escala, (int, float)) or escala <= 0:
        raise ValueError("A escala da cidade deve ser positiva.")
    caminho_path = Path(caminho).expanduser().resolve()
    documento, bloco = _ler_glb(caminho_path)
    nos = documento.get("nodes", [])
    malhas = documento.get("meshes", [])
    materiais = documento.get("materials", [])
    pais = {
        filho: indice
        for indice, no in enumerate(nos)
        if isinstance(no, dict)
        for filho in no.get("children", [])
        if isinstance(filho, int)
    }

    def matriz_mundo(indice: int) -> Matriz:
        cadeia: list[int] = []
        atual = indice
        while True:
            cadeia.append(atual)
            if atual not in pais:
                break
            atual = pais[atual]
        matriz = _identidade()
        for item in reversed(cadeia):
            matriz = _multiplicar(matriz, _matriz_no(nos[item]))
        return matriz

    encontrados: dict[str, list[Triangulo3D]] = {
        referencia: [] for referencia in classificacoes
    }
    for indice_no, no in enumerate(nos):
        if not isinstance(no, dict) or not isinstance(no.get("mesh"), int):
            continue
        indice_malha = no["mesh"]
        if not 0 <= indice_malha < len(malhas):
            continue
        nome_no = str(no.get("name", ""))
        matriz = matriz_mundo(indice_no)
        for primitiva in malhas[indice_malha].get("primitives", []):
            if not isinstance(primitiva, dict) or primitiva.get("mode", 4) != 4:
                continue
            indice_material = primitiva.get("material")
            nome_material = ""
            if (
                isinstance(indice_material, int)
                and 0 <= indice_material < len(materiais)
                and isinstance(materiais[indice_material], dict)
            ):
                nome_material = str(materiais[indice_material].get("name", ""))
            referencia = f"{nome_no}|{nome_material}"
            if referencia not in encontrados:
                continue
            atributos = primitiva.get("attributes", {})
            indice_posicao = atributos.get("POSITION") if isinstance(atributos, dict) else None
            if not isinstance(indice_posicao, int):
                continue
            vertices = [
                tuple(coordenada * float(escala) for coordenada in _transformar(matriz, ponto))
                for ponto in _ler_acessor(documento, bloco, indice_posicao)
            ]
            if isinstance(primitiva.get("indices"), int):
                indices = [
                    int(item[0])
                    for item in _ler_acessor(documento, bloco, primitiva["indices"])
                ]
            else:
                indices = list(range(len(vertices)))
            for inicio in range(0, len(indices) - 2, 3):
                try:
                    triangulo = (
                        vertices[indices[inicio]],
                        vertices[indices[inicio + 1]],
                        vertices[indices[inicio + 2]],
                    )
                except IndexError as erro:
                    raise ErroModelo3D("Uma primitiva referencia vértice inexistente.") from erro
                encontrados[referencia].append(triangulo)
    ausentes = [referencia for referencia, itens in encontrados.items() if not itens]
    if ausentes:
        raise ErroModelo3D(
            "Superfícies classificadas não encontradas no GLB: " + ", ".join(ausentes)
        )
    return MapaSuperficies3D(
        triangulos={chave: tuple(valor) for chave, valor in encontrados.items()},
        classificacoes=dict(classificacoes),
    )


def extrair_triangulos_glb(
    caminho: str | os.PathLike[str],
    *,
    escala: float = ESCALA_CIDADE_PADRAO,
) -> tuple[TrianguloSuperficieGLB, ...]:
    """Extrai todos os triângulos do GLB no sistema de coordenadas da cena.

    Diferentemente de :func:`extrair_mapa_superficies`, não depende das antigas
    classificações manuais. Nomes e cor base são preservados apenas como pistas;
    a decisão final pode variar espacialmente em cada triângulo/célula.
    """
    if not isinstance(escala, (int, float)) or escala <= 0:
        raise ValueError("A escala da cidade deve ser positiva.")
    caminho_path = Path(caminho).expanduser().resolve()
    documento, bloco = _ler_glb(caminho_path)
    nos = documento.get("nodes", [])
    malhas = documento.get("meshes", [])
    materiais = documento.get("materials", [])
    pais = {
        filho: indice
        for indice, no in enumerate(nos)
        if isinstance(no, dict)
        for filho in no.get("children", [])
        if isinstance(filho, int)
    }

    matrizes: dict[int, Matriz] = {}

    def matriz_mundo(indice: int) -> Matriz:
        if indice in matrizes:
            return matrizes[indice]
        cadeia: list[int] = []
        atual = indice
        while True:
            cadeia.append(atual)
            if atual not in pais:
                break
            atual = pais[atual]
        matriz = _identidade()
        for item in reversed(cadeia):
            matriz = _multiplicar(matriz, _matriz_no(nos[item]))
        matrizes[indice] = matriz
        return matriz

    resultado: list[TrianguloSuperficieGLB] = []
    for indice_no, no in enumerate(nos):
        if not isinstance(no, dict) or not isinstance(no.get("mesh"), int):
            continue
        indice_malha = no["mesh"]
        if not 0 <= indice_malha < len(malhas):
            continue
        nome_no = str(no.get("name", ""))
        matriz = matriz_mundo(indice_no)
        primitivas = malhas[indice_malha].get("primitives", [])
        for primitiva in primitivas:
            if not isinstance(primitiva, dict) or primitiva.get("mode", 4) != 4:
                continue
            indice_material = primitiva.get("material")
            material: dict[str, Any] = {}
            if isinstance(indice_material, int) and 0 <= indice_material < len(materiais):
                candidato = materiais[indice_material]
                if isinstance(candidato, dict):
                    material = candidato
            nome_material = str(material.get("name", ""))
            fator = material.get("pbrMetallicRoughness", {}).get(
                "baseColorFactor", (0.5, 0.5, 0.5, 1.0)
            )
            if not isinstance(fator, list) or len(fator) != 4:
                fator = (0.5, 0.5, 0.5, 1.0)
            cor = tuple(float(componente) for componente in fator)
            referencia = f"{nome_no}|{nome_material}"
            atributos = primitiva.get("attributes", {})
            indice_posicao = atributos.get("POSITION") if isinstance(atributos, dict) else None
            if not isinstance(indice_posicao, int):
                continue
            vertices = [
                tuple(
                    coordenada * float(escala)
                    for coordenada in _transformar(matriz, ponto)
                )
                for ponto in _ler_acessor(documento, bloco, indice_posicao)
            ]
            if isinstance(primitiva.get("indices"), int):
                indices = [
                    int(item[0])
                    for item in _ler_acessor(documento, bloco, primitiva["indices"])
                ]
            else:
                indices = list(range(len(vertices)))
            for inicio in range(0, len(indices) - 2, 3):
                try:
                    triangulo = (
                        vertices[indices[inicio]],
                        vertices[indices[inicio + 1]],
                        vertices[indices[inicio + 2]],
                    )
                except IndexError as erro:
                    raise ErroModelo3D(
                        "Uma primitiva referencia vértice inexistente."
                    ) from erro
                resultado.append(
                    TrianguloSuperficieGLB(
                        referencia,
                        nome_no,
                        nome_material,
                        cor,  # type: ignore[arg-type]
                        triangulo,
                    )
                )
    if not resultado:
        raise ErroModelo3D(f"{caminho_path.name} não possui triângulos reconhecíveis.")
    return tuple(resultado)


def _limites_documento(documento: dict[str, Any]) -> Limites3D:
    acessores = documento.get("accessors", [])
    malhas = documento.get("meshes", [])
    nos = documento.get("nodes", [])
    if not all(isinstance(itens, list) for itens in (acessores, malhas, nos)):
        raise ErroModelo3D("A estrutura de malhas do GLB é inválida.")

    limites_por_malha: dict[int, list[tuple[float, float, float]]] = {}
    for indice_malha, malha in enumerate(malhas):
        if not isinstance(malha, dict):
            continue
        for primitiva in malha.get("primitives", []):
            atributos = primitiva.get("attributes", {}) if isinstance(primitiva, dict) else {}
            indice = atributos.get("POSITION") if isinstance(atributos, dict) else None
            if not isinstance(indice, int) or not 0 <= indice < len(acessores):
                continue
            acessor = acessores[indice]
            if not isinstance(acessor, dict):
                continue
            minimo, maximo = acessor.get("min"), acessor.get("max")
            if not (
                isinstance(minimo, list)
                and isinstance(maximo, list)
                and len(minimo) >= 3
                and len(maximo) >= 3
            ):
                continue
            for mascara in range(8):
                limites_por_malha.setdefault(indice_malha, []).append(
                    tuple(
                        float(maximo[eixo] if mascara & (1 << eixo) else minimo[eixo])
                        for eixo in range(3)
                    )
                )

    pontos: list[tuple[float, float, float]] = []
    visitados: set[int] = set()

    def visitar(indice: int, matriz_pai: Matriz) -> None:
        if indice in visitados or not 0 <= indice < len(nos):
            return
        visitados.add(indice)
        no = nos[indice]
        if not isinstance(no, dict):
            return
        matriz_mundo = _multiplicar(matriz_pai, _matriz_no(no))
        indice_malha = no.get("mesh")
        if isinstance(indice_malha, int):
            pontos.extend(
                _transformar(matriz_mundo, ponto)
                for ponto in limites_por_malha.get(indice_malha, ())
            )
        for filho in no.get("children", []):
            if isinstance(filho, int):
                visitar(filho, matriz_mundo)

    cenas = documento.get("scenes", [])
    indice_cena = documento.get("scene", 0)
    raizes: list[int] = []
    if isinstance(cenas, list) and isinstance(indice_cena, int) and 0 <= indice_cena < len(cenas):
        cena = cenas[indice_cena]
        if isinstance(cena, dict):
            raizes = [i for i in cena.get("nodes", []) if isinstance(i, int)]
    if not raizes:
        filhos = {
            filho
            for no in nos
            if isinstance(no, dict)
            for filho in no.get("children", [])
            if isinstance(filho, int)
        }
        raizes = [indice for indice in range(len(nos)) if indice not in filhos]
    for raiz in raizes:
        visitar(raiz, _identidade())
    for indice in range(len(nos)):
        if indice not in visitados:
            visitar(indice, _identidade())
    if not pontos:
        raise ErroModelo3D("O GLB não possui limites POSITION utilizáveis.")
    return Limites3D(
        minimo=tuple(min(ponto[eixo] for ponto in pontos) for eixo in range(3)),  # type: ignore[arg-type]
        maximo=tuple(max(ponto[eixo] for ponto in pontos) for eixo in range(3)),  # type: ignore[arg-type]
    )


def inspecionar_modelo(caminho: str | os.PathLike[str]) -> InformacoesModelo3D:
    """Valida o GLB e calcula sua caixa real considerando a árvore de nós."""
    caminho_path = Path(caminho).expanduser().resolve()
    if not caminho_path.is_file():
        raise ErroModelo3D(f"Modelo 3D não encontrado: {caminho_path}")
    documento = _ler_documento_glb(caminho_path)
    return InformacoesModelo3D(
        caminho=caminho_path,
        tamanho_bytes=caminho_path.stat().st_size,
        malhas=len(documento.get("meshes", [])),
        materiais=len(documento.get("materials", [])),
        texturas=len(documento.get("textures", [])),
        limites=_limites_documento(documento),
    )


def caminho_modelo(nome: str) -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "models" / nome


class ConversorBalsam:
    """Converte GLB para QML/.mesh uma vez e reutiliza o cache versionado."""

    def __init__(
        self,
        cache_dir: str | os.PathLike[str] | None = None,
        executavel: str | os.PathLike[str] | None = None,
    ) -> None:
        cache_configurado = os.environ.get("DELIVERY_ROUTE_CACHE_DIR")
        raiz_cache = Path(
            cache_dir
            or cache_configurado
            or Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            / "delivery-route"
        )
        self.cache_dir = raiz_cache.expanduser().resolve() / "balsam"
        self.executavel = Path(executavel).resolve() if executavel else self._localizar()

    @staticmethod
    def _localizar() -> Path:
        candidatos = (
            Path(sys.executable).with_name("pyside6-balsam"),
            Path(sys.executable).with_name("pyside6-balsam.exe"),
        )
        for candidato in candidatos:
            if candidato.is_file():
                return candidato
        encontrado = shutil.which("pyside6-balsam")
        if encontrado:
            return Path(encontrado)
        raise ErroModelo3D(
            "O conversor pyside6-balsam não foi encontrado na instalação do PySide6."
        )

    @staticmethod
    def _versao_qt() -> str:
        try:
            return version("PySide6")
        except PackageNotFoundError:
            return "desconhecida"

    def converter(self, caminho: str | os.PathLike[str]) -> AssetConvertido:
        origem = Path(caminho).expanduser().resolve()
        if not origem.is_file():
            raise ErroModelo3D(f"Modelo 3D não encontrado: {origem}")
        estatistica = origem.stat()
        chave = hashlib.sha256(
            (
                f"{origem}\0{estatistica.st_size}\0{estatistica.st_mtime_ns}"
                f"\0PySide6-{self._versao_qt()}"
            ).encode("utf-8")
        ).hexdigest()[:20]
        destino = self.cache_dir / f"{origem.stem}-{chave}"
        existentes = sorted(destino.glob("*.qml")) if destino.is_dir() else []
        if existentes:
            return AssetConvertido(origem, existentes[0], destino, True)

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        temporario = Path(
            tempfile.mkdtemp(prefix=f".{origem.stem}-", dir=self.cache_dir)
        )
        ambiente = os.environ.copy()
        ambiente.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            processo = subprocess.run(
                [str(self.executavel), "-o", str(temporario), str(origem)],
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
                env=ambiente,
            )
            if processo.returncode != 0:
                detalhe = (processo.stderr or processo.stdout or "sem detalhes").strip()
                raise ErroModelo3D(
                    f"Balsam falhou ao converter {origem.name}: {detalhe}"
                )
            gerados = sorted(temporario.glob("*.qml"))
            if not gerados:
                raise ErroModelo3D(
                    f"Balsam não gerou a cena QML de {origem.name}."
                )
            try:
                temporario.replace(destino)
            except FileExistsError:
                shutil.rmtree(temporario, ignore_errors=True)
            qml = sorted(destino.glob("*.qml"))
            if not qml:
                raise ErroModelo3D(f"O cache de {origem.name} ficou incompleto.")
            return AssetConvertido(origem, qml[0], destino, False)
        except Exception:
            if temporario.exists():
                shutil.rmtree(temporario, ignore_errors=True)
            raise


__all__ = [
    "AssetConvertido",
    "AmostraSuperficie",
    "ConversorBalsam",
    "ErroModelo3D",
    "ESCALA_CARRO_PADRAO",
    "ESCALA_CIDADE_PADRAO",
    "InformacoesModelo3D",
    "Limites3D",
    "MapaSuperficies3D",
    "caminho_modelo",
    "extrair_mapa_superficies",
    "inspecionar_modelo",
]
