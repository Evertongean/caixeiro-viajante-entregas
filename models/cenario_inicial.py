"""Configuração mínima e versionada usada somente ao abrir a interface."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from models.grafo import Grafo, TipoVertice, Vertice
from models.persistencia import ErroPersistencia
from models.projeto_cidade import EstacionamentoVeiculo, ProjetoCidade


FORMATO_CENARIO_INICIAL = "delivery-route-cidade-inicial"
VERSAO_CENARIO_INICIAL = 1
RAIZ_PROJETO = Path(__file__).resolve().parents[1]
CAMINHO_CONFIGURACAO_INICIAL = RAIZ_PROJETO / "assets" / "config" / "cidade-inicial.json"


@dataclass(frozen=True, slots=True)
class ConfiguracaoCidadeInicial:
    modelo_cidade: str
    sha256_cidade: str
    deposito_id: str
    deposito_nome: str
    posicao_deposito: tuple[float, float, float]
    posicao_estacionamento: tuple[float, float, float]
    orientacao_estacionamento: float
    superficie_estacionamento: str

    def modelo_corresponde(self, caminho: str | Path | None = None) -> bool:
        modelo = (
            Path(caminho).expanduser().resolve()
            if caminho is not None
            else (RAIZ_PROJETO / self.modelo_cidade).resolve()
        )
        resumo = hashlib.sha256()
        try:
            with modelo.open("rb") as arquivo:
                while bloco := arquivo.read(1024 * 1024):
                    resumo.update(bloco)
        except OSError:
            return False
        return resumo.hexdigest() == self.sha256_cidade


def _vetor3(valor: Any, campo: str) -> tuple[float, float, float]:
    if not isinstance(valor, list) or len(valor) != 3:
        raise ErroPersistencia(f"'{campo}' deve possuir três coordenadas.")
    if any(
        isinstance(item, bool)
        or not isinstance(item, (int, float))
        or not math.isfinite(item)
        for item in valor
    ):
        raise ErroPersistencia(f"'{campo}' deve conter números finitos.")
    return tuple(float(item) for item in valor)  # type: ignore[return-value]


def carregar_configuracao_inicial(
    caminho: str | Path = CAMINHO_CONFIGURACAO_INICIAL,
) -> ConfiguracaoCidadeInicial:
    origem = Path(caminho).expanduser()
    try:
        dados = json.loads(origem.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as erro:
        raise ErroPersistencia(
            f"Não foi possível carregar a configuração inicial: {erro}"
        ) from erro
    if not isinstance(dados, dict):
        raise ErroPersistencia("A configuração inicial deve ser um objeto JSON.")
    if dados.get("formato") != FORMATO_CENARIO_INICIAL:
        raise ErroPersistencia("Formato da configuração inicial desconhecido.")
    if dados.get("versao") != VERSAO_CENARIO_INICIAL:
        raise ErroPersistencia("Versão da configuração inicial incompatível.")
    deposito = dados.get("deposito")
    estacionamento = dados.get("estacionamento")
    if not isinstance(deposito, dict) or not isinstance(estacionamento, dict):
        raise ErroPersistencia("Depósito e estacionamento iniciais são obrigatórios.")

    modelo = dados.get("modelo_cidade")
    resumo = dados.get("sha256_cidade")
    identificador = deposito.get("identificador")
    nome = deposito.get("nome")
    superficie = estacionamento.get("superficie")
    orientacao = estacionamento.get("orientacao_graus")
    if not isinstance(modelo, str) or not modelo:
        raise ErroPersistencia("O modelo da cidade inicial é inválido.")
    if (
        not isinstance(resumo, str)
        or len(resumo) != 64
        or any(caractere not in "0123456789abcdef" for caractere in resumo)
    ):
        raise ErroPersistencia("A identidade SHA-256 da cidade é inválida.")
    if not isinstance(identificador, str) or not identificador:
        raise ErroPersistencia("O identificador do depósito é inválido.")
    if not isinstance(nome, str) or not nome:
        raise ErroPersistencia("O nome do depósito é inválido.")
    if not isinstance(superficie, str) or not superficie:
        raise ErroPersistencia("A superfície de estacionamento é inválida.")
    if (
        isinstance(orientacao, bool)
        or not isinstance(orientacao, (int, float))
        or not math.isfinite(orientacao)
    ):
        raise ErroPersistencia("A orientação de estacionamento é inválida.")
    return ConfiguracaoCidadeInicial(
        modelo,
        resumo,
        identificador,
        nome,
        _vetor3(deposito.get("posicao"), "deposito.posicao"),
        _vetor3(estacionamento.get("posicao"), "estacionamento.posicao"),
        float(orientacao),
        superficie,
    )


def criar_projeto_inicial(
    configuracao: ConfiguracaoCidadeInicial | None = None,
) -> ProjetoCidade:
    """Cria um projeto sem demonstração: um depósito e nenhum outro vértice."""
    config = configuracao or carregar_configuracao_inicial()
    x, _, z = config.posicao_deposito
    grafo = Grafo()
    grafo.adicionar_vertice(
        Vertice(
            config.deposito_id,
            config.deposito_nome,
            TipoVertice.DEPOSITO,
            x,
            z,
        )
    )
    grafo.definir_deposito(config.deposito_id)
    return ProjetoCidade(
        grafo=grafo,
        posicoes={config.deposito_id: config.posicao_deposito},
        modelo_cidade=config.modelo_cidade,
        estacionamento_inicial=EstacionamentoVeiculo(
            deposito=config.deposito_id,
            posicao=config.posicao_estacionamento,
            orientacao_graus=config.orientacao_estacionamento,
            superficie=config.superficie_estacionamento,
            validado=False,
        ),
    )


__all__ = [
    "CAMINHO_CONFIGURACAO_INICIAL",
    "ConfiguracaoCidadeInicial",
    "carregar_configuracao_inicial",
    "criar_projeto_inicial",
]
