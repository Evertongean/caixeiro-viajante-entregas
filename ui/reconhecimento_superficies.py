"""Reconhecimento automático das regiões navegáveis do modelo real da cidade."""

from __future__ import annotations

from dataclasses import dataclass
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Callable

from models.trafegabilidade import (
    AmostraTrafegabilidade,
    MapaTrafegabilidade,
    TipoRegiao,
)
from ui.assets_3d import (
    ESCALA_CIDADE_PADRAO,
    ErroModelo3D,
    MapaSuperficies3D,
    TrianguloSuperficieGLB,
    extrair_triangulos_glb,
)


VERSAO_RECONHECEDOR = "cidade-glb-v2"
RESOLUCAO_PADRAO = 0.01


@dataclass(frozen=True, slots=True)
class ResultadoReconhecimento:
    mapa: MapaTrafegabilidade
    veio_do_cache: bool
    chave_cache: str
    estatisticas: dict[TipoRegiao, int]
    avisos: tuple[str, ...] = ()


def _diretorio_cache_padrao() -> Path:
    raiz = os.environ.get("XDG_CACHE_HOME")
    if raiz:
        return Path(raiz) / "delivery-route" / "trafegabilidade"
    return Path.home() / ".cache" / "delivery-route" / "trafegabilidade"


def _hash_arquivo(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        while bloco := arquivo.read(1024 * 1024):
            resumo.update(bloco)
    return resumo.hexdigest()


def chave_cache_reconhecimento(
    caminho: Path, escala: float, resolucao: float
) -> str:
    parametros = json.dumps(
        {
            "modelo": _hash_arquivo(caminho),
            "versao": VERSAO_RECONHECEDOR,
            "escala": escala,
            "resolucao": resolucao,
            "inclinacao_maxima_graus": 35.0,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(parametros).hexdigest()


def _normal_e_area(
    item: TrianguloSuperficieGLB,
) -> tuple[float, float, float, float]:
    a, b, c = item.triangulo
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    nx = ab[1] * ac[2] - ab[2] * ac[1]
    ny = ab[2] * ac[0] - ab[0] * ac[2]
    nz = ab[0] * ac[1] - ab[1] * ac[0]
    norma = math.sqrt(nx * nx + ny * ny + nz * nz)
    return nx, ny, nz, norma


def _mediana_ponderada(valores: list[tuple[float, float]]) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    total = sum(peso for _, peso in ordenados)
    acumulado = 0.0
    for valor, peso in ordenados:
        acumulado += peso
        if acumulado >= total * 0.5:
            return valor
    return ordenados[-1][0]


def _tipo_triangulo(
    item: TrianguloSuperficieGLB,
    altura: float,
    nivel_solo: float,
) -> tuple[TipoRegiao, float]:
    """Combina geometria e pistas locais, sem regra global de cor escura."""
    material = item.nome_material.casefold().strip()
    nome_no = item.nome_no.casefold().strip()
    vermelho, verde, azul, _ = item.cor_base
    elevado = altura > nivel_solo + 0.014

    # Materiais verdes são inequívocos neste asset e continuam bloqueados mesmo
    # em copas elevadas. A cor só reforça a pista semântica do material.
    if (
        "green" in material
        or "gree" in material
        or (verde > vermelho * 1.55 and verde > azul * 1.35)
    ):
        return TipoRegiao.VERDE, 0.96 if "gree" in material else 0.78
    if elevado:
        return TipoRegiao.EDIFICIO, 0.94

    # Assinaturas verificadas no cidade.glb. Elas são usadas por triângulo/célula,
    # nunca para liberar a malha inteira caso exista outra superfície acima.
    if material == "plane" and nome_no.startswith("wh_plane"):
        return TipoRegiao.RUA, 0.99
    if material == "white.001" and nome_no.startswith("wh_white"):
        return TipoRegiao.CALCADA, 0.99

    # Superfícies horizontais de objetos/casas próximas ao chão não devem ser
    # promovidas a rua por mera aparência. Permanecem conservadoramente incertas.
    return TipoRegiao.DESCONHECIDA, 0.35


def _construir_mapa(
    triangulos: tuple[TrianguloSuperficieGLB, ...],
    resolucao: float,
    progresso: Callable[[str], None] | None,
) -> tuple[MapaTrafegabilidade, tuple[str, ...]]:
    coseno_limite = math.cos(math.radians(35.0))
    candidatos: list[tuple[TrianguloSuperficieGLB, float]] = []
    niveis: list[tuple[float, float]] = []
    for item in triangulos:
        _, ny, _, norma = _normal_e_area(item)
        if norma <= 1e-12 or abs(ny) / norma < coseno_limite:
            continue
        area_projetada = abs(ny) * 0.5
        if area_projetada <= 1e-10:
            continue
        altura_media = sum(ponto[1] for ponto in item.triangulo) / 3.0
        candidatos.append((item, altura_media))
        niveis.append((altura_media, area_projetada))
    if not candidatos:
        raise ErroModelo3D("O modelo não possui superfícies horizontais reconhecíveis.")

    nivel_solo = _mediana_ponderada(niveis)
    xs = [ponto[0] for item, _ in candidatos for ponto in item.triangulo]
    zs = [ponto[2] for item, _ in candidatos for ponto in item.triangulo]
    margem = resolucao
    origem_x = math.floor((min(xs) - margem) / resolucao) * resolucao
    origem_z = math.floor((min(zs) - margem) / resolucao) * resolucao
    limite_x = math.ceil((max(xs) + margem) / resolucao) * resolucao
    limite_z = math.ceil((max(zs) + margem) / resolucao) * resolucao
    largura = max(1, round((limite_x - origem_x) / resolucao))
    profundidade = max(1, round((limite_z - origem_z) / resolucao))
    celulas: list[AmostraTrafegabilidade | None] = [None] * (largura * profundidade)
    prioridades = {
        TipoRegiao.DESCONHECIDA: 0,
        TipoRegiao.RUA: 1,
        TipoRegiao.VERDE: 2,
        TipoRegiao.CALCADA: 3,
        TipoRegiao.EDIFICIO: 4,
    }

    if progresso:
        progresso(
            f"Analisando {len(candidatos):,} faces em uma grade "
            f"{largura} × {profundidade}..."
        )
    total_candidatos = len(candidatos)
    for indice_candidato, (item, altura_media) in enumerate(candidatos):
        if progresso and indice_candidato and indice_candidato % 5_000 == 0:
            percentual = round(indice_candidato * 100 / total_candidatos)
            progresso(f"Reconhecendo superfícies viárias… {percentual}%")
        pontos = item.triangulo
        min_x, max_x = min(p[0] for p in pontos), max(p[0] for p in pontos)
        min_z, max_z = min(p[2] for p in pontos), max(p[2] for p in pontos)
        coluna_inicial = max(0, math.floor((min_x - origem_x) / resolucao))
        coluna_final = min(largura - 1, math.floor((max_x - origem_x) / resolucao))
        linha_inicial = max(0, math.floor((min_z - origem_z) / resolucao))
        linha_final = min(profundidade - 1, math.floor((max_z - origem_z) / resolucao))
        tipo, confianca = _tipo_triangulo(item, altura_media, nivel_solo)
        for linha in range(linha_inicial, linha_final + 1):
            z = origem_z + (linha + 0.5) * resolucao
            for coluna in range(coluna_inicial, coluna_final + 1):
                x = origem_x + (coluna + 0.5) * resolucao
                altura = MapaSuperficies3D._altura_triangulo(item.triangulo, x, z)
                if altura is None:
                    continue
                indice = linha * largura + coluna
                anterior = celulas[indice]
                if anterior is not None:
                    diferenca = altura - anterior.altura
                    if diferenca < -1e-5:
                        continue
                    if abs(diferenca) <= 1e-5 and prioridades[tipo] <= prioridades[anterior.tipo]:
                        continue
                celulas[indice] = AmostraTrafegabilidade(
                    tipo, altura, item.referencia, confianca
                )

    # Buracos internos continuam explicitamente desconhecidos: a ausência de
    # evidência nunca é convertida em rua.
    desconhecida = AmostraTrafegabilidade(
        TipoRegiao.DESCONHECIDA, nivel_solo, "", 0.0
    )
    celulas = [celula if celula is not None else desconhecida for celula in celulas]
    mapa = MapaTrafegabilidade(
        origem_x, origem_z, resolucao, largura, profundidade, celulas
    )
    avisos: list[str] = []
    if not any(celula and celula.tipo == TipoRegiao.RUA for celula in celulas):
        avisos.append("Nenhuma região de rua foi reconhecida no modelo.")
    return mapa, tuple(avisos)


def _estatisticas(mapa: MapaTrafegabilidade) -> dict[TipoRegiao, int]:
    resultado = {tipo: 0 for tipo in TipoRegiao}
    for _, _, celula in mapa.iterar_celulas():
        if celula is not None:
            resultado[celula.tipo] += 1
    return resultado


def reconhecer_superficies(
    caminho: str | os.PathLike[str],
    *,
    escala: float = ESCALA_CIDADE_PADRAO,
    resolucao: float = RESOLUCAO_PADRAO,
    diretorio_cache: str | os.PathLike[str] | None = None,
    progresso: Callable[[str], None] | None = None,
) -> ResultadoReconhecimento:
    """Reconhece rua/calçada/edificação/verde diretamente do conteúdo do GLB."""
    if escala <= 0 or resolucao <= 0:
        raise ValueError("Escala e resolução devem ser positivas.")
    arquivo = Path(caminho).expanduser().resolve()
    if progresso:
        progresso("Calculando a identidade do modelo 3D...")
    chave = chave_cache_reconhecimento(arquivo, escala, resolucao)
    raiz_cache = (
        Path(diretorio_cache).expanduser().resolve()
        if diretorio_cache is not None
        else _diretorio_cache_padrao()
    )
    arquivo_cache = raiz_cache / f"{chave}.json.gz"
    try:
        with gzip.open(arquivo_cache, "rt", encoding="utf-8") as arquivo_json:
            dados = json.load(arquivo_json)
        if dados.get("versao") == VERSAO_RECONHECEDOR:
            mapa = MapaTrafegabilidade.de_dados(dados["mapa"])
            if progresso:
                progresso("Mapa de trafegabilidade carregado do cache.")
            return ResultadoReconhecimento(
                mapa, True, chave, _estatisticas(mapa), tuple(dados.get("avisos", ()))
            )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        pass

    if progresso:
        progresso("Lendo a geometria e os materiais do cidade.glb...")
    triangulos = extrair_triangulos_glb(arquivo, escala=escala)
    mapa, avisos = _construir_mapa(triangulos, resolucao, progresso)
    dados = {
        "versao": VERSAO_RECONHECEDOR,
        "chave": chave,
        "mapa": mapa.para_dados(),
        "avisos": list(avisos),
    }
    try:
        raiz_cache.mkdir(parents=True, exist_ok=True)
        descritor, temporario = tempfile.mkstemp(
            prefix=f".{chave}-", suffix=".tmp", dir=raiz_cache
        )
        os.close(descritor)
        try:
            with gzip.open(temporario, "wt", encoding="utf-8") as arquivo_json:
                json.dump(dados, arquivo_json, ensure_ascii=False, separators=(",", ":"))
            os.replace(temporario, arquivo_cache)
        finally:
            try:
                os.unlink(temporario)
            except FileNotFoundError:
                pass
    except OSError:
        # O mapa em memória continua válido mesmo se o ambiente não permitir cache.
        avisos = (*avisos, "Não foi possível persistir o cache de trafegabilidade.")
    if progresso:
        progresso("Reconhecimento automático concluído.")
    return ResultadoReconhecimento(
        mapa, False, chave, _estatisticas(mapa), tuple(avisos)
    )
