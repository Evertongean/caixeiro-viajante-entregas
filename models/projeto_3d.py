"""Persistência versionada do projeto 3D sem duplicar o formato do grafo.

O JSON contém o grafo oficial (compatível com ``models.persistencia``), a
referência aos GLBs, o alinhamento espacial e as regiões de pavimento
confirmadas. A geometria binária nunca é copiada para o projeto.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from models.grafo import Grafo
from models.persistencia import ErroPersistencia, grafo_de_dados, grafo_para_dados
from ui.editor_ruas_3d import EditorRuas3D
from ui.modelos_glb import MapeamentoCidadeGLB, mapeamento_cidade_glb_de_dados, mapeamento_cidade_glb_para_dados


FORMATO_PROJETO_3D = "delivery-route-projeto-3d"
VERSAO_PROJETO_3D = 1


def projeto_3d_para_dados(
    grafo: Grafo,
    *,
    caminho_cidade: str | Path,
    caminho_carro: str | Path,
    mapeamento: MapeamentoCidadeGLB | None = None,
    editor: EditorRuas3D | None = None,
) -> dict[str, Any]:
    if not isinstance(grafo, Grafo):
        raise TypeError("grafo deve ser uma instância de Grafo")
    return {
        "formato": FORMATO_PROJETO_3D,
        "versao": VERSAO_PROJETO_3D,
        "grafo": grafo_para_dados(grafo),
        "modelos": {
            "cidade": str(Path(caminho_cidade).expanduser()),
            "carro": str(Path(caminho_carro).expanduser()),
        },
        "mapeamento_3d": (
            mapeamento_cidade_glb_para_dados(mapeamento) if mapeamento is not None else None
        ),
        "editor_ruas": editor.dados() if editor is not None else EditorRuas3D().dados(),
    }


def projeto_3d_de_dados(dados: object) -> dict[str, Any]:
    if not isinstance(dados, dict) or dados.get("formato") != FORMATO_PROJETO_3D:
        raise ErroPersistencia("Formato de projeto 3D desconhecido.")
    if dados.get("versao") != VERSAO_PROJETO_3D:
        raise ErroPersistencia("Versão de projeto 3D incompatível.")
    grafo = grafo_de_dados(dados.get("grafo"))
    modelos = dados.get("modelos")
    if not isinstance(modelos, dict) or not isinstance(modelos.get("cidade"), str) or not isinstance(modelos.get("carro"), str):
        raise ErroPersistencia("O projeto 3D precisa referenciar cidade e carro.")
    for nome in ("cidade", "carro"):
        referencia = Path(modelos[nome]).expanduser()
        if referencia.suffix.casefold() != ".glb":
            raise ErroPersistencia(f"A referência do modelo {nome} deve apontar para um arquivo .glb.")
        if not referencia.is_file():
            raise ErroPersistencia(f"Modelo {nome} não encontrado: {referencia}")
    bruto_mapeamento = dados.get("mapeamento_3d")
    mapeamento = mapeamento_cidade_glb_de_dados(bruto_mapeamento) if bruto_mapeamento is not None else None
    editor = EditorRuas3D.de_dados(dados.get("editor_ruas", {}))
    return {
        "grafo": grafo,
        "caminho_cidade": Path(modelos["cidade"]).expanduser(),
        "caminho_carro": Path(modelos["carro"]).expanduser(),
        "mapeamento": mapeamento,
        "editor": editor,
    }


def salvar_projeto_3d(dados: dict[str, Any], caminho: str | Path) -> Path:
    destino = Path(caminho).expanduser()
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destino.parent,
            prefix=f".{destino.name}.", suffix=".tmp", delete=False
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
            try:
                temporario.unlink()
            except FileNotFoundError:
                pass
    return destino


def carregar_projeto_3d(caminho: str | Path) -> dict[str, Any]:
    arquivo = Path(caminho).expanduser()
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        raise ErroPersistencia(f"JSON 3D inválido na linha {erro.lineno}: {erro.msg}.") from erro
    if isinstance(dados, dict) and isinstance(dados.get("modelos"), dict):
        # Referências relativas são resolvidas em relação ao projeto, não ao
        # diretório de onde o processo foi iniciado.
        dados = dict(dados)
        modelos = dict(dados["modelos"])
        for nome in ("cidade", "carro"):
            if isinstance(modelos.get(nome), str):
                referencia = Path(modelos[nome]).expanduser()
                if not referencia.is_absolute():
                    relativa_ao_projeto = (arquivo.parent / referencia).resolve()
                    # Projetos antigos podem ter sido gravados com caminho
                    # relativo ao diretório de execução. Preservar esse
                    # fallback mantém a compatibilidade sem aceitar caminhos
                    # inexistentes silenciosamente.
                    if relativa_ao_projeto.is_file():
                        modelos[nome] = str(relativa_ao_projeto)
        dados["modelos"] = modelos
    return projeto_3d_de_dados(dados)


__all__ = [
    "FORMATO_PROJETO_3D",
    "VERSAO_PROJETO_3D",
    "carregar_projeto_3d",
    "projeto_3d_de_dados",
    "projeto_3d_para_dados",
    "salvar_projeto_3d",
]
