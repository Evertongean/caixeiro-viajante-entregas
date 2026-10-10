"""Serialização e validação de projetos do Delivery Route.

O formato é deliberadamente pequeno e não contém estado da interface ou
resultados temporários dos algoritmos::

    {
      "formato": "delivery-route-grafo",
      "versao": 1,
      "deposito": "D",
      "vertices": [{"identificador": "D", "nome": "...",
                    "tipo": "depósito", "x": 0, "y": 0}],
      "arestas": [{"origem": "D", "destino": "X", "peso": 2}]
    }

Cada aresta não direcionada aparece uma única vez. O carregamento sempre
reconstrói um ``Grafo`` temporário; o chamador só deve substituir seu projeto
depois que esta função terminar sem erro.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from models.grafo import Grafo, TipoVertice, Vertice


FORMATO_NOME = "delivery-route-grafo"
FORMATO_VERSAO = 1

__all__ = [
    "ErroPersistencia",
    "FORMATO_NOME",
    "FORMATO_VERSAO",
    "grafo_para_dados",
    "grafo_de_dados",
    "validar_grafo",
    "salvar_grafo",
    "carregar_grafo",
    "serializar_grafo",
    "desserializar_grafo",
    "salvar_projeto",
    "carregar_projeto",
]


class ErroPersistencia(ValueError):
    """Indica que um arquivo não pertence ao formato válido do projeto."""


def grafo_para_dados(grafo: Grafo) -> dict[str, Any]:
    """Converte um grafo para o dicionário serializável do formato versão 1."""
    if not isinstance(grafo, Grafo):
        raise TypeError("É necessário fornecer uma instância de Grafo.")

    deposito = grafo.obter_deposito()
    return {
        "formato": FORMATO_NOME,
        "versao": FORMATO_VERSAO,
        "deposito": deposito.identificador if deposito is not None else None,
        "vertices": [
            {
                "identificador": vertice.identificador,
                "nome": vertice.nome,
                "tipo": vertice.tipo.value,
                "x": vertice.x,
                "y": vertice.y,
            }
            for vertice in grafo.listar_vertices()
        ],
        "arestas": [
            {
                "origem": aresta.origem.identificador,
                "destino": aresta.destino.identificador,
                "peso": aresta.peso,
            }
            for aresta in grafo.listar_arestas()
        ],
    }


def grafo_de_dados(dados: Any) -> Grafo:
    """Valida ``dados`` e reconstrói um novo grafo sem tocar em outro objeto."""
    if not isinstance(dados, dict):
        raise ErroPersistencia("A raiz do projeto deve ser um objeto JSON.")
    if dados.get("formato") != FORMATO_NOME:
        raise ErroPersistencia("Formato de projeto desconhecido.")
    versao = dados.get("versao")
    if type(versao) is not int or versao != FORMATO_VERSAO:
        raise ErroPersistencia(
            f"Versão de projeto incompatível: {versao!r}. "
            f"Esperada: {FORMATO_VERSAO}."
        )

    vertices = dados.get("vertices")
    arestas = dados.get("arestas")
    if not isinstance(vertices, list) or not isinstance(arestas, list):
        raise ErroPersistencia("'vertices' e 'arestas' devem ser listas.")

    deposito_informado = dados.get("deposito", _CAMPO_AUSENTE)
    if deposito_informado is not _CAMPO_AUSENTE and deposito_informado is not None:
        _exigir_texto(deposito_informado, "deposito")

    temporario = Grafo()
    for indice, dados_vertice in enumerate(vertices):
        vertice = _vertice_a_partir_de_dados(dados_vertice, indice)
        try:
            temporario.adicionar_vertice(vertice)
        except (TypeError, ValueError) as erro:
            raise ErroPersistencia(f"Vértice {indice + 1} inválido: {erro}") from erro

    for indice, dados_aresta in enumerate(arestas):
        origem, destino, peso = _aresta_a_partir_de_dados(dados_aresta, indice)
        try:
            temporario.adicionar_aresta(origem, destino, peso)
        except (KeyError, TypeError, ValueError) as erro:
            raise ErroPersistencia(f"Aresta {indice + 1} inválida: {erro}") from erro

    deposito_real = temporario.obter_deposito()
    if deposito_informado is not _CAMPO_AUSENTE:
        if deposito_informado is None:
            if deposito_real is not None:
                raise ErroPersistencia(
                    "O campo 'deposito' não pode ser nulo quando há um depósito."
                )
        elif deposito_real is None or deposito_real.identificador != deposito_informado:
            raise ErroPersistencia(
                "O depósito informado não corresponde ao único depósito do grafo."
            )

    return temporario


def carregar_grafo(caminho: str | os.PathLike[str]) -> Grafo:
    """Lê, valida e reconstrói um projeto JSON em uma estrutura temporária."""
    caminho_path = _caminho(caminho)
    try:
        with caminho_path.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except json.JSONDecodeError as erro:
        raise ErroPersistencia(f"JSON inválido na linha {erro.lineno}: {erro.msg}.") from erro
    except UnicodeDecodeError as erro:
        raise ErroPersistencia("O arquivo não está codificado em UTF-8.") from erro
    return grafo_de_dados(dados)


def salvar_grafo(grafo: Grafo, caminho: str | os.PathLike[str]) -> Path:
    """Grava um projeto com substituição atômica para evitar arquivos parciais."""
    dados = grafo_para_dados(grafo)
    validar_grafo(grafo)
    caminho_path = _caminho(caminho)
    temporario: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=caminho_path.parent,
            prefix=f".{caminho_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as arquivo:
            temporario = Path(arquivo.name)
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho_path)
        temporario = None
    finally:
        if temporario is not None:
            try:
                temporario.unlink()
            except FileNotFoundError:
                pass
    return caminho_path


def validar_grafo(grafo: Grafo) -> None:
    """Confirma que o grafo atual também é aceito pelo formato de persistência."""
    grafo_de_dados(grafo_para_dados(grafo))


_CAMPO_AUSENTE = object()


def _caminho(caminho: str | os.PathLike[str]) -> Path:
    if not isinstance(caminho, (str, os.PathLike)):
        raise TypeError("O caminho deve ser texto ou os.PathLike.")
    caminho_path = Path(caminho).expanduser()
    if not caminho_path.name:
        raise ValueError("O caminho do projeto não pode ser vazio.")
    return caminho_path


def _vertice_a_partir_de_dados(dados: Any, indice: int) -> Vertice:
    if not isinstance(dados, dict):
        raise ErroPersistencia(f"Vértice {indice + 1} deve ser um objeto.")
    identificador = _exigir_texto(dados.get("identificador"), "identificador")
    nome = _exigir_texto(dados.get("nome"), "nome")
    tipo_bruto = dados.get("tipo")
    tipo_texto = _exigir_texto(tipo_bruto, "tipo")
    try:
        tipo = TipoVertice(tipo_texto)
    except ValueError as erro:
        raise ErroPersistencia(f"Tipo de vértice desconhecido: {tipo_texto!r}.") from erro
    x = _exigir_numero(dados.get("x"), "x")
    y = _exigir_numero(dados.get("y"), "y")
    try:
        return Vertice(identificador, nome, tipo, x, y)
    except (TypeError, ValueError) as erro:
        raise ErroPersistencia(f"Dados inválidos do vértice: {erro}") from erro


def _aresta_a_partir_de_dados(dados: Any, indice: int) -> tuple[str, str, float]:
    if not isinstance(dados, dict):
        raise ErroPersistencia(f"Aresta {indice + 1} deve ser um objeto.")
    origem = _exigir_texto(dados.get("origem"), "origem")
    destino = _exigir_texto(dados.get("destino"), "destino")
    peso = _exigir_numero(dados.get("peso"), "peso")
    return origem, destino, peso


def _exigir_texto(valor: Any, campo: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErroPersistencia(f"O campo '{campo}' deve ser um texto não vazio.")
    return valor.strip()


def _exigir_numero(valor: Any, campo: str) -> float:
    # Vertice/Aresta farão a validação de finitude e positividade quando
    # aplicável; aqui rejeitamos bool e valores que o JSON não trouxe.
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        raise ErroPersistencia(f"O campo '{campo}' deve ser numérico.")
    return float(valor)


# Nomes alternativos úteis para consumidores que preferem a terminologia de
# serialização/desserialização ou de projeto, sem duplicar a implementação.
serializar_grafo = grafo_para_dados
desserializar_grafo = grafo_de_dados
salvar_projeto = salvar_grafo
carregar_projeto = carregar_grafo

