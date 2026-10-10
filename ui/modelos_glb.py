"""Inspeção, configuração e alinhamento dos modelos GLB da missão 3D.

Este módulo não é um renderizador. Ele valida os arquivos glTF binário, coleta
metadados úteis para a cena e mantém o transform entre as coordenadas do
grafo (2D) e o espaço da cidade importada. O grafo continua sendo a fonte
única de ruas, pesos e ordem da rota.

O renderizador Panda3D é opcional (ver :mod:`ui.renderizador_panda3d`). Mesmo
quando ele não está instalado, o programa consegue diagnosticar o modelo e
manter a simulação legada de forma explícita, sem desenhar o GLB com
``QPainter``.
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from models.grafo import Grafo


class ErroGLB(ValueError):
    """Arquivo GLB inválido ou incompatível com glTF 2.0."""


@dataclass(frozen=True, slots=True)
class CaixaGLB:
    minimo: tuple[float, float, float]
    maximo: tuple[float, float, float]

    @property
    def dimensoes(self) -> tuple[float, float, float]:
        return tuple(self.maximo[i] - self.minimo[i] for i in range(3))

    @property
    def centro(self) -> tuple[float, float, float]:
        return tuple((self.minimo[i] + self.maximo[i]) / 2 for i in range(3))

    @property
    def valida(self) -> bool:
        return all(math.isfinite(v) for v in (*self.minimo, *self.maximo)) and all(
            self.maximo[i] >= self.minimo[i] for i in range(3)
        )


@dataclass(frozen=True, slots=True)
class InformacoesGLB:
    """Diagnóstico estável de um arquivo GLB."""

    caminho: Path
    valido: bool
    versao: int | None = None
    tamanho_bytes: int = 0
    cenas: int = 0
    nos: int = 0
    malhas: int = 0
    materiais: int = 0
    texturas: int = 0
    imagens: int = 0
    caixa: CaixaGLB | None = None
    eixo_vertical: str = "Y"
    eixo_frente: str = "+Z"
    titulo: str = ""
    autor: str = ""
    gerador: str = ""
    mensagens: tuple[str, ...] = ()

    @property
    def dimensoes(self) -> tuple[float, float, float] | None:
        return None if self.caixa is None else self.caixa.dimensoes

    @property
    def tem_texturas(self) -> bool:
        return self.texturas > 0 or self.imagens > 0

    @property
    def resumo(self) -> str:
        if not self.valido:
            return f"{self.caminho.name}: GLB inválido"
        dimensoes = "—"
        if self.dimensoes:
            dimensoes = " × ".join(f"{v:.2f}" for v in self.dimensoes)
        return (
            f"{self.caminho.name}: {self.malhas} malhas, {self.materiais} materiais, "
            f"dimensões {dimensoes}"
        )

    # Vocabulário em inglês útil para ferramentas externas que consomem o
    # diagnóstico, sem duplicar o objeto ou perder a API em português.
    @property
    def valid(self) -> bool:
        return self.valido

    @property
    def bounds(self) -> CaixaGLB | None:
        return self.caixa

    @property
    def mesh_count(self) -> int:
        return self.malhas

    @property
    def material_count(self) -> int:
        return self.materiais


def _erro_info(caminho: Path, mensagem: str, *, tamanho: int = 0) -> InformacoesGLB:
    return InformacoesGLB(
        caminho=caminho,
        valido=False,
        tamanho_bytes=tamanho,
        mensagens=(mensagem,),
    )


def _matriz_multiplicar(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> list[list[float]]:
    return [
        [sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
        for i in range(4)
    ]


def _matriz_identidade() -> list[list[float]]:
    return [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]


def _matriz_no(no: Mapping[str, object]) -> list[list[float]]:
    """Lê matrix/TRS glTF e devolve matriz coluna-vetor em ordem matemática."""

    matriz = no.get("matrix")
    if isinstance(matriz, list) and len(matriz) == 16:
        # glTF serializa matrizes em column-major.
        return [[float(matriz[c * 4 + r]) for c in range(4)] for r in range(4)]
    trans = [float(v) for v in no.get("translation", [0, 0, 0])]
    escala = [float(v) for v in no.get("scale", [1, 1, 1])]
    quat = [float(v) for v in no.get("rotation", [0, 0, 0, 1])]
    x, y, z, w = quat
    rot = [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]
    return [
        [rot[0][0] * escala[0], rot[0][1] * escala[1], rot[0][2] * escala[2], trans[0]],
        [rot[1][0] * escala[0], rot[1][1] * escala[1], rot[1][2] * escala[2], trans[1]],
        [rot[2][0] * escala[0], rot[2][1] * escala[1], rot[2][2] * escala[2], trans[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _transformar_ponto(matriz: Sequence[Sequence[float]], ponto: Sequence[float]) -> tuple[float, float, float]:
    return tuple(
        sum(matriz[i][j] * (float(ponto[j]) if j < 3 else 1.0) for j in range(4))
        for i in range(3)
    )


def _carregar_chunks(caminho: Path) -> tuple[dict, bytes, int]:
    dados = caminho.read_bytes()
    if len(dados) < 12:
        raise ErroGLB("arquivo menor que o cabeçalho GLB")
    magic, versao, tamanho = struct.unpack_from("<4sII", dados, 0)
    if magic != b"glTF":
        raise ErroGLB("assinatura GLB ausente")
    if versao != 2:
        raise ErroGLB(f"versão glTF não suportada: {versao}")
    if tamanho != len(dados):
        raise ErroGLB("tamanho declarado no cabeçalho não corresponde ao arquivo")
    offset = 12
    documento: dict | None = None
    binario = b""
    while offset < len(dados):
        if offset + 8 > len(dados):
            raise ErroGLB("chunk GLB truncado")
        comprimento, tipo = struct.unpack_from("<II", dados, offset)
        offset += 8
        fim = offset + comprimento
        if fim > len(dados):
            raise ErroGLB("chunk GLB excede o tamanho do arquivo")
        chunk = dados[offset:fim]
        offset = fim
        if tipo == 0x4E4F534A:  # JSON
            try:
                documento = json.loads(chunk.rstrip(b" \t\r\n\0").decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as erro:
                raise ErroGLB("chunk JSON inválido") from erro
        elif tipo == 0x004E4942:  # BIN
            binario = chunk
    if not isinstance(documento, dict):
        raise ErroGLB("chunk JSON não encontrado")
    if documento.get("asset", {}).get("version") != "2.0":
        raise ErroGLB("o asset não declara glTF 2.0")
    buffers = documento.get("buffers", [])
    if buffers and isinstance(buffers[0], dict):
        declarado = buffers[0].get("byteLength")
        if isinstance(declarado, int) and declarado > len(binario):
            raise ErroGLB("buffer BIN truncado")
    return documento, binario, versao


def _caixa_documento(documento: Mapping[str, object], binario: bytes = b"") -> CaixaGLB | None:
    """Calcula a caixa das posições POSITION aplicando transforms dos nós."""

    accessors = documento.get("accessors", [])
    meshes = documento.get("meshes", [])
    nodes = documento.get("nodes", [])
    if not isinstance(accessors, list) or not isinstance(meshes, list) or not isinstance(nodes, list):
        return None
    pontos: list[tuple[float, float, float]] = []
    mesh_bounds: dict[int, list[tuple[float, float, float]]] = {}
    for mesh_index, mesh in enumerate(meshes):
        if not isinstance(mesh, dict):
            continue
        for prim in mesh.get("primitives", []):
            if not isinstance(prim, dict):
                continue
            indice = prim.get("attributes", {}).get("POSITION") if isinstance(prim.get("attributes"), dict) else None
            if not isinstance(indice, int) or indice >= len(accessors):
                continue
            accessor = accessors[indice]
            minimo = accessor.get("min") if isinstance(accessor, dict) else None
            maximo = accessor.get("max") if isinstance(accessor, dict) else None
            if not (
                isinstance(minimo, list)
                and isinstance(maximo, list)
                and len(minimo) >= 3
                and len(maximo) >= 3
            ) and isinstance(accessor, dict):
                # min/max são opcionais no glTF. Os assets do projeto já os
                # fornecem, mas este caminho mantém o inspetor correto para
                # GLBs pequenos gerados por ferramentas acadêmicas.
                view_index = accessor.get("bufferView")
                count = accessor.get("count")
                views = documento.get("bufferViews", [])
                if (
                    isinstance(view_index, int)
                    and isinstance(count, int)
                    and 0 <= view_index < len(views)
                    and accessor.get("componentType") == 5126
                    and accessor.get("type") == "VEC3"
                ):
                    view = views[view_index]
                    if isinstance(view, dict):
                        inicio = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
                        passo = int(view.get("byteStride", 12))
                        pontos_acessor = []
                        try:
                            for item in range(count):
                                pontos_acessor.append(struct.unpack_from("<3f", binario, inicio + item * passo))
                            if pontos_acessor:
                                minimo = [min(p[i] for p in pontos_acessor) for i in range(3)]
                                maximo = [max(p[i] for p in pontos_acessor) for i in range(3)]
                        except (struct.error, ValueError):
                            minimo = maximo = None
            if not (isinstance(minimo, list) and isinstance(maximo, list) and len(minimo) >= 3 and len(maximo) >= 3):
                continue
            minimo3 = tuple(float(minimo[i]) for i in range(3))
            maximo3 = tuple(float(maximo[i]) for i in range(3))
            mesh_bounds.setdefault(mesh_index, []).extend(
                tuple(
                    minimo3[i] if (mascara & (1 << i)) == 0 else maximo3[i]
                    for i in range(3)
                )
                for mascara in range(8)
            )
    if not mesh_bounds:
        return None
    filhos: dict[int, list[int]] = {}
    referenciados: set[int] = set()
    for indice, no in enumerate(nodes):
        if not isinstance(no, dict):
            continue
        for filho in no.get("children", []):
            if isinstance(filho, int) and 0 <= filho < len(nodes):
                filhos.setdefault(indice, []).append(filho)
                referenciados.add(filho)
    roots = [i for i in range(len(nodes)) if i not in referenciados]
    if not roots:
        roots = list(range(len(nodes)))
    visitados: set[int] = set()

    def visitar(indice: int, pai: list[list[float]]) -> None:
        if indice in visitados:
            return
        visitados.add(indice)
        no = nodes[indice]
        if not isinstance(no, dict):
            return
        mundo = _matriz_multiplicar(pai, _matriz_no(no))
        mesh = no.get("mesh")
        if isinstance(mesh, int):
            for ponto in mesh_bounds.get(mesh, []):
                pontos.append(_transformar_ponto(mundo, ponto))
        for filho in filhos.get(indice, []):
            visitar(filho, mundo)

    for raiz in roots:
        visitar(raiz, _matriz_identidade())
    # Alguns arquivos possuem nós não conectados à cena; ainda são geometria
    # válida e devem aparecer no diagnóstico.
    for indice, no in enumerate(nodes):
        if indice not in visitados and isinstance(no, dict) and isinstance(no.get("mesh"), int):
            visitar(indice, _matriz_identidade())
    if not pontos:
        return None
    return CaixaGLB(
        tuple(min(p[i] for p in pontos) for i in range(3)),
        tuple(max(p[i] for p in pontos) for i in range(3)),
    )


@lru_cache(maxsize=16)
def _inspecionar_glb_cache(caminho: str) -> InformacoesGLB:
    """Valida e inspeciona um GLB sem depender de um motor gráfico."""

    caminho = Path(caminho).expanduser()
    try:
        tamanho = caminho.stat().st_size
    except OSError as erro:
        return _erro_info(caminho, f"não foi possível acessar o arquivo: {erro}")
    try:
        documento, binario, versao = _carregar_chunks(caminho)
    except (OSError, ErroGLB) as erro:
        return _erro_info(caminho, str(erro), tamanho=tamanho)
    asset = documento.get("asset", {})
    extras = asset.get("extras", {}) if isinstance(asset, dict) else {}
    if not isinstance(extras, dict):
        extras = {}
    mensagens: list[str] = []
    caixa = _caixa_documento(documento, binario)
    if caixa is None or not caixa.valida:
        mensagens.append("nenhuma geometria POSITION com limites válidos foi encontrada")
    elif any(d <= 0 for d in caixa.dimensoes):
        mensagens.append("a caixa da geometria possui dimensão zero em algum eixo")
    valido = caixa is not None and caixa.valida and not any(d <= 0 for d in caixa.dimensoes)
    return InformacoesGLB(
        caminho=caminho,
        valido=valido,
        versao=versao,
        tamanho_bytes=tamanho,
        cenas=len(documento.get("scenes", [])),
        nos=len(documento.get("nodes", [])),
        malhas=len(documento.get("meshes", [])),
        materiais=len(documento.get("materials", [])),
        texturas=len(documento.get("textures", [])),
        imagens=len(documento.get("images", [])),
        caixa=caixa,
        # Os assets usados pelo projeto são exportados pelo Sketchfab com
        # conversão Z-up -> Y-up na raiz. Mantemos essa informação explícita.
        eixo_vertical="Y",
        eixo_frente="+Z",
        titulo=str(extras.get("title", "")),
        autor=str(extras.get("author", "")),
        gerador=str(asset.get("generator", "")) if isinstance(asset, dict) else "",
        mensagens=tuple(mensagens),
    )


def inspecionar_glb(caminho: str | Path) -> InformacoesGLB:
    """Valida e inspeciona um GLB, reutilizando diagnósticos imutáveis."""

    return _inspecionar_glb_cache(str(Path(caminho).expanduser().resolve()))


# Nomes alternativos para integrações e para manter a API legível em português.
validar_glb = inspecionar_glb
carregar_info_glb = inspecionar_glb


def carregar_glb(caminho: str | Path) -> InformacoesGLB:
    """Versão estrita: retorna o diagnóstico ou lança ``ErroGLB``."""

    info = inspecionar_glb(caminho)
    if not info.valido:
        raise ErroGLB("; ".join(info.mensagens) or "GLB inválido")
    return info


def _tripla(valor: Iterable[float], nome: str) -> tuple[float, float, float]:
    try:
        itens = tuple(float(v) for v in valor)
    except (TypeError, ValueError) as erro:
        raise ValueError(f"{nome} deve conter três números finitos") from erro
    if len(itens) != 3 or not all(math.isfinite(v) for v in itens):
        raise ValueError(f"{nome} deve conter três números finitos")
    return itens


@dataclass(frozen=True, slots=True)
class ConfiguracaoModelos3D:
    """Parâmetros ajustáveis no painel ``Modelos 3D``."""

    caminho_cidade: Path = field(default_factory=lambda: caminho_modelo_padrao("cidade.glb"))
    caminho_carro: Path = field(default_factory=lambda: caminho_modelo_padrao("carro.glb"))
    escala_cidade: float = 0.01
    posicao_cidade: tuple[float, float, float] = (0.0, 0.0, 0.0)
    escala_carro: float = 0.018
    orientacao_carro: float = 0.0
    altura_carro: float = 0.0
    eixo_frente_carro: str = "+Z"

    # Aliases usados por código externo e por versões anteriores do protótipo.
    @property
    def cidade_glb(self) -> Path:
        return self.caminho_cidade

    @property
    def carro_glb(self) -> Path:
        return self.caminho_carro

    def validar(self) -> "ConfiguracaoModelos3D":
        cidade = Path(self.caminho_cidade).expanduser()
        carro = Path(self.caminho_carro).expanduser()
        valores = (self.escala_cidade, self.escala_carro, self.orientacao_carro, self.altura_carro)
        if not all(math.isfinite(float(v)) for v in valores):
            raise ValueError("as configurações 3D devem ser finitas")
        if self.escala_cidade <= 0 or self.escala_carro <= 0:
            raise ValueError("as escalas dos modelos devem ser positivas")
        if self.eixo_frente_carro not in {"+X", "-X", "+Y", "-Y", "+Z", "-Z"}:
            raise ValueError("eixo_frente_carro inválido")
        return replace(self, caminho_cidade=cidade, caminho_carro=carro, posicao_cidade=_tripla(self.posicao_cidade, "posicao_cidade"))

    # Nomes de leitura convenientes para a UI.
    @property
    def escala_modelo_cidade(self) -> float:
        return self.escala_cidade

    @property
    def escala_modelo_carro(self) -> float:
        return self.escala_carro

    @property
    def city_path(self) -> Path:
        return self.caminho_cidade

    @property
    def car_path(self) -> Path:
        return self.caminho_carro

    @property
    def city_scale(self) -> float:
        return self.escala_cidade

    @property
    def car_scale(self) -> float:
        return self.escala_carro


def caminho_modelo_padrao(nome: str) -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "models" / nome


@dataclass(frozen=True, slots=True)
class MapeamentoCidadeGLB:
    """Alinhamento espacial do grafo com a cidade importada.

    ``posicoes`` continua sendo a única fonte das coordenadas dos vértices;
    ``pontos_intermediarios`` é apenas uma polilinha visual para uma aresta
    já existente no :class:`Grafo`.  Assim, calibrar uma rua nunca cria,
    remove ou altera conexões e pesos do algoritmo.
    """

    posicoes: dict[str, tuple[float, float, float]]
    escala: float
    deslocamento: tuple[float, float, float]
    valido: bool
    mensagens: tuple[str, ...] = ()
    pontos_intermediarios: dict[tuple[str, str], tuple[tuple[float, float, float], ...]] = field(
        default_factory=dict
    )
    calibrado: bool = False

    @property
    def positions(self) -> dict[str, tuple[float, float, float]]:
        return self.posicoes

    @property
    def valid(self) -> bool:
        return self.valido

    @property
    def viario_calibrado(self) -> bool:
        """Indica que o usuário confirmou posições/curvas sobre as ruas."""

        return self.calibrado

    @property
    def pontos_arestas(self) -> dict[tuple[str, str], tuple[tuple[float, float, float], ...]]:
        return self.pontos_intermediarios

    @staticmethod
    def _chave_aresta(origem: str, destino: str) -> tuple[str, str]:
        return (str(origem), str(destino))

    def pontos_da_aresta(
        self, origem: str, destino: str
    ) -> tuple[tuple[float, float, float], ...]:
        """Retorna origem, pontos calibrados e destino na direção solicitada."""

        if origem not in self.posicoes or destino not in self.posicoes:
            return ()
        inicio = self.posicoes[origem]
        fim = self.posicoes[destino]
        pontos = self.pontos_intermediarios.get(self._chave_aresta(origem, destino))
        if pontos is None:
            pontos_reversos = self.pontos_intermediarios.get(self._chave_aresta(destino, origem))
            pontos = tuple(reversed(pontos_reversos)) if pontos_reversos is not None else ()
        return (inicio, *tuple(pontos), fim)

    def expandir_percurso(self, percurso: Iterable[str]) -> tuple[tuple[float, float, float], ...]:
        """Expande uma rota de vértices em uma polilinha 3D sem duplicar nós."""

        rota = tuple(percurso)
        if not rota:
            return ()
        resultado: list[tuple[float, float, float]] = []
        for origem, destino in zip(rota, rota[1:]):
            segmento = self.pontos_da_aresta(origem, destino)
            if not segmento:
                continue
            if resultado:
                resultado.extend(segmento[1:])
            else:
                resultado.extend(segmento)
        if not resultado and rota[0] in self.posicoes:
            resultado.append(self.posicoes[rota[0]])
        return tuple(resultado)

    percurso_3d = expandir_percurso
    trajeto_calibrado = expandir_percurso

    def com_posicao(self, identificador: str, posicao: Sequence[float]) -> "MapeamentoCidadeGLB":
        """Retorna uma cópia com um único vértice reposicionado."""

        if identificador not in self.posicoes:
            raise KeyError(f"vértice não mapeado: {identificador}")
        atualizado = dict(self.posicoes)
        atualizado[identificador] = _tripla(posicao, f"posição de {identificador}")
        return replace(self, posicoes=atualizado, valido=True, calibrado=True)

    def com_ponto_intermediario(
        self,
        origem: str,
        destino: str,
        ponto: Sequence[float],
        *,
        indice: int | None = None,
    ) -> "MapeamentoCidadeGLB":
        """Insere/atualiza um ponto de curva para uma aresta visual."""

        if origem not in self.posicoes or destino not in self.posicoes:
            raise KeyError("a aresta deve usar vértices mapeados")
        chave = self._chave_aresta(origem, destino)
        pontos = list(self.pontos_intermediarios.get(chave, ()))
        valor = _tripla(ponto, f"ponto intermediário {origem}–{destino}")
        if indice is None:
            pontos.append(valor)
        else:
            indice = int(indice)
            if indice < 0 or indice > len(pontos):
                raise IndexError("índice do ponto intermediário fora do intervalo")
            if indice == len(pontos):
                pontos.append(valor)
            else:
                pontos[indice] = valor
        intermediarios = dict(self.pontos_intermediarios)
        intermediarios[chave] = tuple(pontos)
        return replace(self, pontos_intermediarios=intermediarios, valido=True, calibrado=True)

    def remover_pontos_intermediarios(self, origem: str, destino: str) -> "MapeamentoCidadeGLB":
        intermediarios = dict(self.pontos_intermediarios)
        intermediarios.pop(self._chave_aresta(origem, destino), None)
        intermediarios.pop(self._chave_aresta(destino, origem), None)
        return replace(self, pontos_intermediarios=intermediarios)

    def validar_rota(self, grafo: Grafo, percurso: Iterable[str]) -> tuple[bool, str]:
        rota = tuple(percurso)
        faltantes = [v for v in rota if v not in self.posicoes]
        if faltantes:
            return False, f"mapeamento sem posição para: {', '.join(faltantes)}"
        ids = {v.identificador for v in grafo.listar_vertices()}
        if any(v not in ids for v in rota):
            return False, "a rota contém vértice que não pertence ao grafo"
        for origem, destino in zip(rota, rota[1:]):
            if origem != destino and not grafo.existe_aresta(origem, destino):
                return False, f"a rota contém conexão inexistente: {origem}–{destino}"
        if not self.valido:
            return False, "; ".join(self.mensagens) or "mapeamento 3D inválido"
        return True, ""


def mapear_grafo_cidade_glb(
    grafo: Grafo,
    cidade: InformacoesGLB,
    configuracao: ConfiguracaoModelos3D | None = None,
    *,
    posicoes_manuais: Mapping[str, Sequence[float]] | None = None,
) -> MapeamentoCidadeGLB:
    """Converte coordenadas do grafo para o espaço da cidade importada.

    O cálculo é apenas uma transformação afim para visualização. Arestas e
    pesos nunca são criados, removidos ou recalculados aqui.
    """

    config = (configuracao or ConfiguracaoModelos3D()).validar()
    if not cidade.valido or cidade.caixa is None:
        return MapeamentoCidadeGLB({}, config.escala_cidade, config.posicao_cidade, False, ("modelo de cidade inválido",))
    vertices = grafo.listar_vertices()
    if not vertices:
        return MapeamentoCidadeGLB({}, config.escala_cidade, config.posicao_cidade, False, ("grafo vazio",))
    if posicoes_manuais is not None:
        faltantes = [v.identificador for v in vertices if v.identificador not in posicoes_manuais]
        if faltantes:
            return MapeamentoCidadeGLB({}, config.escala_cidade, config.posicao_cidade, False, (f"mapeamento manual incompleto: {', '.join(faltantes)}",))
        try:
            posicoes = {v.identificador: _tripla(posicoes_manuais[v.identificador], f"posição de {v.identificador}") for v in vertices}
        except ValueError as erro:
            return MapeamentoCidadeGLB({}, config.escala_cidade, config.posicao_cidade, False, (str(erro),))
        return MapeamentoCidadeGLB(posicoes, 1.0, (0.0, 0.0, 0.0), True, (), {}, True)
    xs = [float(v.x) for v in vertices]
    ys = [float(v.y) for v in vertices]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    dimensoes = cidade.caixa.dimensoes
    # Grafo 2D é projetado no plano XZ do modelo (Y é altura).
    largura = max(dimensoes[0], 1e-9) * config.escala_cidade
    profundidade = max(dimensoes[2], 1e-9) * config.escala_cidade
    escala = min(largura / max(maxx - minx, 1e-9), profundidade / max(maxy - miny, 1e-9)) * 0.82
    centro = cidade.caixa.centro
    centro_mundo = (
        centro[0] * config.escala_cidade + config.posicao_cidade[0],
        # Os vértices representam a rua, não o centro vertical dos prédios.
        # Usar a base real do GLB evita que o carro flutue quando o pivô do
        # modelo contém vários andares acima do solo.
        float(cidade.caixa.minimo[1]) * config.escala_cidade + config.posicao_cidade[1],
        centro[2] * config.escala_cidade + config.posicao_cidade[2],
    )
    posicoes = {
        v.identificador: (
            centro_mundo[0] + ((float(v.x) - (minx + maxx) / 2) * escala),
            centro_mundo[1],
            centro_mundo[2] + ((float(v.y) - (miny + maxy) / 2) * escala),
        )
        for v in vertices
    }
    return MapeamentoCidadeGLB(posicoes, escala, config.posicao_cidade, True)


def mapear_grafo_para_glb(*args, **kwargs) -> MapeamentoCidadeGLB:
    return mapear_grafo_cidade_glb(*args, **kwargs)


def validar_mapeamento_rota(
    grafo: Grafo, mapeamento: MapeamentoCidadeGLB, percurso: Iterable[str]
) -> tuple[bool, str]:
    return mapeamento.validar_rota(grafo, percurso)


FORMATO_MAPEAMENTO_3D = "delivery-route-mapeamento-3d"
VERSAO_MAPEAMENTO_3D = 1


def mapeamento_cidade_glb_para_dados(mapeamento: MapeamentoCidadeGLB) -> dict:
    """Converte uma calibração espacial para JSON legível e versionado."""

    if not isinstance(mapeamento, MapeamentoCidadeGLB):
        raise TypeError("É necessário fornecer um MapeamentoCidadeGLB.")
    return {
        "formato": FORMATO_MAPEAMENTO_3D,
        "versao": VERSAO_MAPEAMENTO_3D,
        "escala": float(mapeamento.escala),
        "deslocamento": list(mapeamento.deslocamento),
        "valido": bool(mapeamento.valido),
        "calibrado": bool(mapeamento.calibrado),
        "posicoes": {identificador: list(posicao) for identificador, posicao in mapeamento.posicoes.items()},
        "pontos_intermediarios": [
            {
                "origem": origem,
                "destino": destino,
                "pontos": [list(ponto) for ponto in pontos],
            }
            for (origem, destino), pontos in sorted(mapeamento.pontos_intermediarios.items())
        ],
    }


def mapeamento_cidade_glb_de_dados(dados: object) -> MapeamentoCidadeGLB:
    """Valida e reconstrói uma calibração sem tocar no grafo atual."""

    if not isinstance(dados, dict) or dados.get("formato") != FORMATO_MAPEAMENTO_3D:
        raise ValueError("Formato de mapeamento 3D desconhecido.")
    if dados.get("versao") != VERSAO_MAPEAMENTO_3D:
        raise ValueError(f"Versão de mapeamento incompatível: {dados.get('versao')!r}.")
    posicoes_brutas = dados.get("posicoes")
    if not isinstance(posicoes_brutas, dict):
        raise ValueError("'posicoes' deve ser um objeto JSON.")
    posicoes = {
        str(identificador): _tripla(posicao, f"posição de {identificador}")
        for identificador, posicao in posicoes_brutas.items()
    }
    escala = float(dados.get("escala", 1.0))
    deslocamento = _tripla(dados.get("deslocamento", (0, 0, 0)), "deslocamento")
    if not math.isfinite(escala) or escala <= 0:
        raise ValueError("escala do mapeamento deve ser positiva e finita")
    intermediarios_brutos = dados.get("pontos_intermediarios", [])
    if not isinstance(intermediarios_brutos, list):
        raise ValueError("'pontos_intermediarios' deve ser uma lista.")
    intermediarios: dict[tuple[str, str], tuple[tuple[float, float, float], ...]] = {}
    for indice, item in enumerate(intermediarios_brutos):
        if not isinstance(item, dict) or not isinstance(item.get("origem"), str) or not isinstance(item.get("destino"), str):
            raise ValueError(f"ponto intermediário {indice + 1} inválido")
        pontos = item.get("pontos", [])
        if not isinstance(pontos, list):
            raise ValueError(f"pontos da aresta {indice + 1} devem ser uma lista")
        intermediarios[(item["origem"], item["destino"])] = tuple(
            _tripla(ponto, f"ponto intermediário {indice + 1}") for ponto in pontos
        )
    return MapeamentoCidadeGLB(
        posicoes,
        escala,
        deslocamento,
        bool(dados.get("valido", True)),
        (),
        intermediarios,
        bool(dados.get("calibrado", True)),
    )


def salvar_mapeamento_cidade_glb(mapeamento: MapeamentoCidadeGLB, caminho: str | Path) -> Path:
    """Salva uma calibração por substituição atômica."""

    destino = Path(caminho).expanduser()
    if not destino.name:
        raise ValueError("o caminho do mapeamento não pode ser vazio")
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(f".{destino.name}.tmp")
    try:
        temporario.write_text(
            json.dumps(mapeamento_cidade_glb_para_dados(mapeamento), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporario.replace(destino)
    finally:
        if temporario.exists():
            temporario.unlink()
    return destino


def carregar_mapeamento_cidade_glb(caminho: str | Path) -> MapeamentoCidadeGLB:
    caminho_path = Path(caminho).expanduser()
    try:
        dados = json.loads(caminho_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        raise ValueError(f"JSON de mapeamento inválido na linha {erro.lineno}: {erro.msg}.") from erro
    return mapeamento_cidade_glb_de_dados(dados)


# Aliases de API para scripts de calibração e integrações externas.
serializar_mapeamento_3d = mapeamento_cidade_glb_para_dados
desserializar_mapeamento_3d = mapeamento_cidade_glb_de_dados
salvar_mapeamento_3d = salvar_mapeamento_cidade_glb
carregar_mapeamento_3d = carregar_mapeamento_cidade_glb


# Aliases de integração para evitar que consumidores dependam de nomes de uma
# única versão da interface.
GLBModelInfo = InformacoesGLB
GLBBounds = CaixaGLB
ModelConfig3D = ConfiguracaoModelos3D
CityGLBMapping = MapeamentoCidadeGLB
validate_glb = inspecionar_glb
load_glb = carregar_glb
map_graph_to_glb = mapear_grafo_cidade_glb

