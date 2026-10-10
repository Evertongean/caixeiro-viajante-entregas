"""Projeto 3D versionado que estende, sem substituir, o JSON do grafo."""

from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

from models.grafo import Grafo
from models.persistencia import (
    ErroPersistencia,
    FORMATO_NOME,
    grafo_de_dados,
    grafo_para_dados,
)


FORMATO_PROJETO_CIDADE = "delivery-route-cidade-3d"
VERSAO_PROJETO_CIDADE = 1


class ClassificacaoSuperficie(str, Enum):
    NAO_CLASSIFICADA = "nao_classificada"
    RUA = "rua"
    CALCADA = "calcada"
    BLOQUEADA = "bloqueada"


@dataclass(slots=True)
class GeometriaRua:
    origem: str
    destino: str
    pontos_intermediarios: list[tuple[float, float, float]] = field(
        default_factory=list
    )
    calibrada_manualmente: bool = True


@dataclass(slots=True)
class ProjetoCidade:
    grafo: Grafo
    posicoes: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    ruas: dict[tuple[str, str], GeometriaRua] = field(default_factory=dict)
    superficies: dict[str, ClassificacaoSuperficie] = field(default_factory=dict)
    modelo_cidade: str = "assets/models/cidade.glb"
    modelo_carro: str = "assets/models/carro.glb"
    fator_km_por_unidade: float = 1.0

    @staticmethod
    def chave_aresta(origem: str, destino: str) -> tuple[str, str]:
        """Identidade canônica e sem colisões de uma aresta não direcionada."""
        return tuple(sorted((origem, destino)))  # type: ignore[return-value]

    def geometria_rua(self, origem: str, destino: str) -> GeometriaRua | None:
        return self.ruas.get(self.chave_aresta(origem, destino))

    def polilinha_rua(
        self, origem: str, destino: str
    ) -> tuple[tuple[float, float, float], ...]:
        """Retorna a geometria na orientação solicitada, sem mudar sua identidade."""
        geometria = self.geometria_rua(origem, destino)
        if geometria is None:
            return ()
        try:
            pontos = [
                self.posicoes[geometria.origem],
                *geometria.pontos_intermediarios,
                self.posicoes[geometria.destino],
            ]
        except KeyError:
            return ()
        if (origem, destino) == (geometria.origem, geometria.destino):
            return tuple(pontos)
        if (origem, destino) == (geometria.destino, geometria.origem):
            return tuple(reversed(pontos))
        return ()


def _vetor3(valor: Any, campo: str) -> tuple[float, float, float]:
    if not isinstance(valor, (list, tuple)) or len(valor) != 3:
        raise ErroPersistencia(f"'{campo}' deve possuir três coordenadas.")
    if any(
        isinstance(item, bool)
        or not isinstance(item, (int, float))
        or not math.isfinite(item)
        for item in valor
    ):
        raise ErroPersistencia(f"'{campo}' deve conter números finitos.")
    return tuple(float(item) for item in valor)  # type: ignore[return-value]


def projeto_para_dados(projeto: ProjetoCidade) -> dict[str, Any]:
    if not isinstance(projeto, ProjetoCidade):
        raise TypeError("É necessário fornecer uma instância de ProjetoCidade.")
    if (
        not isinstance(projeto.fator_km_por_unidade, (int, float))
        or isinstance(projeto.fator_km_por_unidade, bool)
        or not math.isfinite(projeto.fator_km_por_unidade)
        or projeto.fator_km_por_unidade <= 0
    ):
        raise ValueError("O fator de conversão deve ser positivo e finito.")
    vertices = {vertice.identificador for vertice in projeto.grafo.listar_vertices()}
    if not set(projeto.posicoes).issubset(vertices):
        raise ValueError("Existem posições associadas a vértices inexistentes.")
    posicoes = {
        identificador: _vetor3(posicao, f"posicoes.{identificador}")
        for identificador, posicao in projeto.posicoes.items()
    }
    if not isinstance(projeto.modelo_cidade, str) or not projeto.modelo_cidade:
        raise ValueError("A referência do modelo da cidade deve ser um texto não vazio.")
    if not isinstance(projeto.modelo_carro, str) or not projeto.modelo_carro:
        raise ValueError("A referência do modelo do carro deve ser um texto não vazio.")
    for superficie, classificacao in projeto.superficies.items():
        if not isinstance(superficie, str) or not superficie:
            raise ValueError("Uma referência de superfície é inválida.")
        if not isinstance(classificacao, ClassificacaoSuperficie):
            raise TypeError("Uma classificação de superfície é inválida.")

    ruas = []
    for chave, geometria in sorted(projeto.ruas.items()):
        if chave != projeto.chave_aresta(geometria.origem, geometria.destino):
            raise ValueError("A chave de uma geometria de rua é inconsistente.")
        if not projeto.grafo.existe_aresta(geometria.origem, geometria.destino):
            raise ValueError("Existe geometria para uma aresta inexistente.")
        pontos = [
            _vetor3(ponto, "ruas.pontos_intermediarios")
            for ponto in geometria.pontos_intermediarios
        ]
        ruas.append(
            {
                "origem": geometria.origem,
                "destino": geometria.destino,
                "pontos_intermediarios": [list(ponto) for ponto in pontos],
                "calibrada_manualmente": geometria.calibrada_manualmente,
            }
        )
    return {
        "formato": FORMATO_PROJETO_CIDADE,
        "versao": VERSAO_PROJETO_CIDADE,
        "modelos": {
            "cidade": projeto.modelo_cidade,
            "carro": projeto.modelo_carro,
        },
        "grafo": grafo_para_dados(projeto.grafo),
        "editor_3d": {
            "posicoes": {
                identificador: list(posicao)
                for identificador, posicao in sorted(posicoes.items())
            },
            "ruas": ruas,
            "superficies": {
                superficie: classificacao.value
                for superficie, classificacao in sorted(projeto.superficies.items())
            },
            "fator_km_por_unidade": float(projeto.fator_km_por_unidade),
        },
    }


def projeto_de_dados(dados: Any) -> ProjetoCidade:
    """Carrega o formato novo ou promove um JSON de grafo versão 1."""
    if not isinstance(dados, dict):
        raise ErroPersistencia("A raiz do projeto deve ser um objeto JSON.")
    if dados.get("formato") == FORMATO_NOME:
        return ProjetoCidade(grafo=grafo_de_dados(dados))
    if dados.get("formato") != FORMATO_PROJETO_CIDADE:
        raise ErroPersistencia("Formato de projeto 3D desconhecido.")
    if dados.get("versao") != VERSAO_PROJETO_CIDADE:
        raise ErroPersistencia("Versão de projeto 3D incompatível.")

    grafo = grafo_de_dados(dados.get("grafo"))
    modelos = dados.get("modelos", {})
    editor = dados.get("editor_3d", {})
    if not isinstance(modelos, dict) or not isinstance(editor, dict):
        raise ErroPersistencia("As seções 'modelos' e 'editor_3d' são obrigatórias.")
    cidade = modelos.get("cidade", "assets/models/cidade.glb")
    carro = modelos.get("carro", "assets/models/carro.glb")
    if not isinstance(cidade, str) or not cidade or not isinstance(carro, str) or not carro:
        raise ErroPersistencia("As referências dos modelos devem ser textos não vazios.")

    vertices = {vertice.identificador for vertice in grafo.listar_vertices()}
    posicoes_brutas = editor.get("posicoes", {})
    if not isinstance(posicoes_brutas, dict):
        raise ErroPersistencia("'posicoes' deve ser um objeto.")
    posicoes: dict[str, tuple[float, float, float]] = {}
    for identificador, posicao in posicoes_brutas.items():
        if identificador not in vertices:
            raise ErroPersistencia(
                f"A posição referencia o vértice inexistente '{identificador}'."
            )
        posicoes[identificador] = _vetor3(posicao, f"posicoes.{identificador}")

    superficies_brutas = editor.get("superficies", {})
    if not isinstance(superficies_brutas, dict):
        raise ErroPersistencia("'superficies' deve ser um objeto.")
    superficies: dict[str, ClassificacaoSuperficie] = {}
    for superficie, classificacao in superficies_brutas.items():
        if not isinstance(superficie, str) or not superficie:
            raise ErroPersistencia("Uma referência de superfície é inválida.")
        try:
            superficies[superficie] = ClassificacaoSuperficie(classificacao)
        except ValueError as erro:
            raise ErroPersistencia(
                f"Classificação desconhecida para a superfície '{superficie}'."
            ) from erro

    fator = editor.get("fator_km_por_unidade", 1.0)
    if (
        isinstance(fator, bool)
        or not isinstance(fator, (int, float))
        or not math.isfinite(fator)
        or fator <= 0
    ):
        raise ErroPersistencia("O fator de conversão deve ser positivo e finito.")

    ruas_brutas = editor.get("ruas", [])
    if not isinstance(ruas_brutas, list):
        raise ErroPersistencia("'ruas' deve ser uma lista.")
    ruas: dict[tuple[str, str], GeometriaRua] = {}
    for indice, item in enumerate(ruas_brutas):
        if not isinstance(item, dict):
            raise ErroPersistencia(f"Rua {indice + 1} deve ser um objeto.")
        origem, destino = item.get("origem"), item.get("destino")
        if not isinstance(origem, str) or not isinstance(destino, str):
            raise ErroPersistencia(f"Rua {indice + 1} possui extremos inválidos.")
        try:
            grafo.obter_distancia(origem, destino)
        except (KeyError, ValueError) as erro:
            raise ErroPersistencia(
                f"Rua {indice + 1} não corresponde a uma aresta do grafo."
            ) from erro
        pontos_brutos = item.get("pontos_intermediarios", [])
        if not isinstance(pontos_brutos, list):
            raise ErroPersistencia(
                f"Pontos intermediários da rua {indice + 1} devem ser uma lista."
            )
        calibrada = item.get("calibrada_manualmente", False)
        if not isinstance(calibrada, bool):
            raise ErroPersistencia(
                f"A calibração manual da rua {indice + 1} deve ser booleana."
            )
        chave = ProjetoCidade.chave_aresta(origem, destino)
        pontos = [
            _vetor3(ponto, f"ruas[{indice}].pontos_intermediarios")
            for ponto in pontos_brutos
        ]
        if origem != chave[0]:
            pontos.reverse()
        geometria = GeometriaRua(
            origem=chave[0],
            destino=chave[1],
            pontos_intermediarios=pontos,
            calibrada_manualmente=calibrada,
        )
        if chave in ruas:
            existente = ruas[chave]
            if existente.pontos_intermediarios != geometria.pontos_intermediarios:
                raise ErroPersistencia(
                    f"A rua {chave[0]} ↔ {chave[1]} possui geometrias duplicadas "
                    "e conflitantes; a migração automática não é segura."
                )
            existente.calibrada_manualmente = bool(
                existente.calibrada_manualmente
                or geometria.calibrada_manualmente
            )
            continue
        ruas[chave] = geometria

    return ProjetoCidade(
        grafo=grafo,
        posicoes=posicoes,
        ruas=ruas,
        superficies=superficies,
        modelo_cidade=cidade,
        modelo_carro=carro,
        fator_km_por_unidade=float(fator),
    )


def salvar_projeto_cidade(
    projeto: ProjetoCidade, caminho: str | os.PathLike[str]
) -> Path:
    dados = projeto_para_dados(projeto)
    destino = Path(caminho).expanduser()
    temporario: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destino.parent,
            prefix=f".{destino.name}.",
            suffix=".tmp",
            delete=False,
        ) as arquivo:
            temporario = Path(arquivo.name)
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, destino)
        temporario = None
    finally:
        if temporario is not None:
            temporario.unlink(missing_ok=True)
    return destino


def carregar_projeto_cidade(caminho: str | os.PathLike[str]) -> ProjetoCidade:
    caminho_path = Path(caminho).expanduser()
    try:
        with caminho_path.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except json.JSONDecodeError as erro:
        raise ErroPersistencia(
            f"JSON inválido na linha {erro.lineno}: {erro.msg}."
        ) from erro
    except UnicodeDecodeError as erro:
        raise ErroPersistencia("O arquivo não está codificado em UTF-8.") from erro
    return projeto_de_dados(dados)


__all__ = [
    "ClassificacaoSuperficie",
    "FORMATO_PROJETO_CIDADE",
    "GeometriaRua",
    "ProjetoCidade",
    "VERSAO_PROJETO_CIDADE",
    "carregar_projeto_cidade",
    "projeto_de_dados",
    "projeto_para_dados",
    "salvar_projeto_cidade",
]
