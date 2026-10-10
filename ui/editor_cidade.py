"""Controlador testável do editor visual sobre a cidade 3D."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import dist, isfinite
from typing import Sequence

from models.grafo import TipoVertice, Vertice
from models.projeto_cidade import (
    ClassificacaoSuperficie,
    GeometriaRua,
    ProjetoCidade,
)


class ModoEditor(str, Enum):
    NAVEGAR = "navegar"
    ADICIONAR_PONTO = "adicionar_ponto"
    CRIAR_RUA = "criar_rua"
    CLASSIFICAR_SUPERFICIE = "classificar_superficie"
    REPOSICIONAR_VERTICE = "reposicionar_vertice"


@dataclass(slots=True)
class OperacaoRua:
    origem: str | None = None
    destino: str | None = None
    pontos_intermediarios: list[tuple[float, float, float]] = field(
        default_factory=list
    )
    editando_aresta: tuple[str, str] | None = None


class EditorCidade3D:
    """Aplica operações espaciais sempre sobre o grafo oficial do projeto."""

    CORES_TIPOS = {
        TipoVertice.DEPOSITO: "#2388FF",
        TipoVertice.CLIENTE: "#2DD4BF",
        TipoVertice.CRUZAMENTO: "#94A3B8",
    }

    def __init__(self, projeto: ProjetoCidade) -> None:
        if not isinstance(projeto, ProjetoCidade):
            raise TypeError("É necessário fornecer um ProjetoCidade.")
        self.projeto = projeto
        self.modo = ModoEditor.NAVEGAR
        self.tipo_sugerido: TipoVertice | None = None
        self.operacao_rua = OperacaoRua()
        self.vertice_reposicionado: str | None = None
        self.selecao: tuple[str, ...] | None = None

    @staticmethod
    def referencia_superficie(objeto: str, material: str = "") -> str:
        objeto = objeto.strip() or "malha-sem-nome"
        material = material.strip() or "material-sem-nome"
        return f"{objeto}|{material}"

    def classificacao_superficie(self, referencia: str) -> ClassificacaoSuperficie:
        return self.projeto.superficies.get(
            referencia, ClassificacaoSuperficie.NAO_CLASSIFICADA
        )

    def classificar_superficie(
        self, referencia: str, classificacao: ClassificacaoSuperficie
    ) -> None:
        if not referencia.strip():
            raise ValueError("A referência da superfície não pode ser vazia.")
        if not isinstance(classificacao, ClassificacaoSuperficie):
            raise TypeError("Classificação de superfície inválida.")
        if classificacao is ClassificacaoSuperficie.NAO_CLASSIFICADA:
            self.projeto.superficies.pop(referencia, None)
        else:
            self.projeto.superficies[referencia] = classificacao

    def superficie_trafegavel(self, referencia: str) -> bool:
        return self.classificacao_superficie(referencia) is ClassificacaoSuperficie.RUA

    def validar_superficie_trafegavel(self, referencia: str) -> None:
        classificacao = self.classificacao_superficie(referencia)
        if classificacao is ClassificacaoSuperficie.RUA:
            return
        nome = {
            ClassificacaoSuperficie.NAO_CLASSIFICADA: "não classificada",
            ClassificacaoSuperficie.CALCADA: "calçada",
            ClassificacaoSuperficie.BLOQUEADA: "área bloqueada",
        }[classificacao]
        raise ValueError(
            f"A superfície é {nome}; classifique o asfalto como rua trafegável."
        )

    def definir_modo(
        self,
        modo: ModoEditor,
        *,
        tipo_sugerido: TipoVertice | None = None,
    ) -> None:
        if not isinstance(modo, ModoEditor):
            raise TypeError("Modo de edição inválido.")
        self.cancelar_operacao()
        self.modo = modo
        self.tipo_sugerido = tipo_sugerido

    def cancelar_operacao(self) -> None:
        self.operacao_rua = OperacaoRua()
        self.vertice_reposicionado = None
        self.tipo_sugerido = None

    @staticmethod
    def _posicao(posicao: Sequence[float]) -> tuple[float, float, float]:
        if len(posicao) != 3:
            raise ValueError("Uma posição espacial deve possuir três coordenadas.")
        posicao3 = tuple(float(valor) for valor in posicao)
        if not all(isfinite(valor) for valor in posicao3):
            raise ValueError("As coordenadas espaciais devem ser finitas.")
        return posicao3  # type: ignore[return-value]

    @staticmethod
    def coordenadas_grafo(
        posicao: Sequence[float],
    ) -> tuple[float, float]:
        x, _, z = EditorCidade3D._posicao(posicao)
        return x, z

    def criar_vertice(
        self,
        identificador: str,
        nome: str,
        tipo: TipoVertice,
        posicao: Sequence[float],
    ) -> Vertice:
        posicao3 = self._posicao(posicao)
        x, y = self.coordenadas_grafo(posicao3)
        vertice = Vertice(identificador, nome, tipo, x, y)
        self.projeto.grafo.adicionar_vertice(vertice)
        self.projeto.posicoes[identificador] = posicao3
        return vertice

    def editar_vertice(
        self,
        identificador: str,
        *,
        nome: str,
        tipo: TipoVertice,
    ) -> Vertice:
        atual = self.projeto.grafo.obter_vertice(identificador)
        return self.projeto.grafo.atualizar_vertice(
            identificador,
            nome=nome,
            tipo=tipo,
            x=atual.x,
            y=atual.y,
        )

    def reposicionar_vertice(
        self, identificador: str, posicao: Sequence[float]
    ) -> Vertice:
        posicao3 = self._posicao(posicao)
        atual = self.projeto.grafo.obter_vertice(identificador)
        x, y = self.coordenadas_grafo(posicao3)
        atualizado = self.projeto.grafo.atualizar_vertice(
            identificador,
            nome=atual.nome,
            tipo=atual.tipo,
            x=x,
            y=y,
        )
        self.projeto.posicoes[identificador] = posicao3
        return atualizado

    def remover_vertice(self, identificador: str) -> Vertice:
        removido = self.projeto.grafo.remover_vertice(identificador)
        self.projeto.posicoes.pop(identificador, None)
        for chave in list(self.projeto.ruas):
            if identificador in chave:
                del self.projeto.ruas[chave]
        if self.selecao == ("vertice", identificador):
            self.selecao = None
        return removido

    def vertice_proximo(
        self, posicao: Sequence[float], tolerancia: float = 0.07
    ) -> str | None:
        posicao3 = self._posicao(posicao)
        candidatos = (
            (dist(posicao3, existente), identificador)
            for identificador, existente in self.projeto.posicoes.items()
        )
        proximos = [item for item in candidatos if item[0] <= tolerancia]
        return min(proximos, default=(0.0, None))[1]

    def iniciar_rua(
        self,
        origem: str | None = None,
        destino: str | None = None,
        *,
        editar: bool = False,
    ) -> None:
        self.cancelar_operacao()
        self.modo = ModoEditor.CRIAR_RUA
        intermediarios: list[tuple[float, float, float]] = []
        chave = None
        if origem is not None:
            self.projeto.grafo.obter_vertice(origem)
        if destino is not None:
            self.projeto.grafo.obter_vertice(destino)
        if editar and origem is not None and destino is not None:
            self.projeto.grafo.obter_distancia(origem, destino)
            chave = self.projeto.chave_aresta(origem, destino)
            geometria = self.projeto.ruas.get(chave)
            if geometria is not None:
                intermediarios = list(geometria.pontos_intermediarios)
        self.operacao_rua = OperacaoRua(origem, destino, intermediarios, chave)

    def selecionar_extremo_rua(self, identificador: str) -> str:
        self.projeto.grafo.obter_vertice(identificador)
        operacao = self.operacao_rua
        if operacao.origem is None:
            operacao.origem = identificador
            return "origem"
        if operacao.destino is None:
            if identificador == operacao.origem:
                raise ValueError("O início e o fim da rua devem ser diferentes.")
            operacao.destino = identificador
            if self.projeto.grafo.existe_aresta(operacao.origem, identificador):
                operacao.editando_aresta = self.projeto.chave_aresta(
                    operacao.origem, identificador
                )
            else:
                operacao.editando_aresta = None
            return "destino"
        raise ValueError("Os extremos já foram selecionados; adicione curvas ou confirme.")

    def adicionar_ponto_intermediario(self, posicao: Sequence[float]) -> None:
        if self.operacao_rua.origem is None or self.operacao_rua.destino is None:
            raise ValueError("Selecione o início e o fim antes de adicionar curvas.")
        self.operacao_rua.pontos_intermediarios.append(self._posicao(posicao))

    def desfazer_ponto_rua(self) -> str | None:
        operacao = self.operacao_rua
        if operacao.pontos_intermediarios:
            operacao.pontos_intermediarios.pop()
            return "ponto_intermediario"
        if operacao.destino is not None:
            operacao.destino = None
            operacao.editando_aresta = None
            return "destino"
        if operacao.origem is not None:
            operacao.origem = None
            return "origem"
        return None

    def pontos_rua(
        self,
        origem: str,
        destino: str,
        intermediarios: Sequence[Sequence[float]] = (),
    ) -> list[tuple[float, float, float]]:
        try:
            inicio = self.projeto.posicoes[origem]
            fim = self.projeto.posicoes[destino]
        except KeyError as erro:
            raise ValueError("Os extremos da rua precisam de posições 3D.") from erro
        return [inicio, *(self._posicao(p) for p in intermediarios), fim]

    @staticmethod
    def comprimento_geometrico(pontos: Sequence[Sequence[float]]) -> float:
        pontos3 = [EditorCidade3D._posicao(ponto) for ponto in pontos]
        return sum(dist(a, b) for a, b in zip(pontos3, pontos3[1:]))

    def comprimento_operacao_rua(self) -> float:
        operacao = self.operacao_rua
        if operacao.origem is None or operacao.destino is None:
            return 0.0
        return self.comprimento_geometrico(
            self.pontos_rua(
                operacao.origem,
                operacao.destino,
                operacao.pontos_intermediarios,
            )
        )

    def confirmar_rua(self, peso: float, fator_km_por_unidade: float) -> None:
        operacao = self.operacao_rua
        if operacao.origem is None or operacao.destino is None:
            raise ValueError("Selecione os dois extremos da rua.")
        if fator_km_por_unidade <= 0:
            raise ValueError("O fator de conversão deve ser positivo.")
        chave = self.projeto.chave_aresta(operacao.origem, operacao.destino)
        if operacao.editando_aresta is None:
            self.projeto.grafo.adicionar_aresta(
                operacao.origem, operacao.destino, peso
            )
        else:
            self.projeto.grafo.atualizar_peso_aresta(
                operacao.origem, operacao.destino, peso
            )
        self.projeto.ruas[chave] = GeometriaRua(
            operacao.origem,
            operacao.destino,
            list(operacao.pontos_intermediarios),
            True,
        )
        self.projeto.fator_km_por_unidade = float(fator_km_por_unidade)
        self.cancelar_operacao()
        self.modo = ModoEditor.NAVEGAR

    def editar_peso_aresta(self, origem: str, destino: str, peso: float) -> None:
        self.projeto.grafo.atualizar_peso_aresta(origem, destino, peso)

    def remover_aresta(self, origem: str, destino: str) -> None:
        self.projeto.grafo.remover_aresta(origem, destino)
        self.projeto.ruas.pop(self.projeto.chave_aresta(origem, destino), None)
        if self.selecao == ("aresta", *self.projeto.chave_aresta(origem, destino)):
            self.selecao = None

    def inicializar_posicoes_legadas(
        self,
        minimo_cidade: Sequence[float],
        maximo_cidade: Sequence[float],
        escala: float,
    ) -> None:
        """Projeta somente vértices sem posição de arquivos antigos."""
        ausentes = [
            vertice
            for vertice in self.projeto.grafo.listar_vertices()
            if vertice.identificador not in self.projeto.posicoes
        ]
        if not ausentes:
            return
        minimo = self._posicao(minimo_cidade)
        maximo = self._posicao(maximo_cidade)
        vertices = self.projeto.grafo.listar_vertices()
        xs = [vertice.x for vertice in vertices] or [0.0]
        ys = [vertice.y for vertice in vertices] or [0.0]
        largura_grafo = max(max(xs) - min(xs), 1.0)
        altura_grafo = max(max(ys) - min(ys), 1.0)
        largura = (maximo[0] - minimo[0]) * escala * 0.70
        profundidade = (maximo[2] - minimo[2]) * escala * 0.70
        centro_x = (minimo[0] + maximo[0]) * escala * 0.5
        centro_z = (minimo[2] + maximo[2]) * escala * 0.5
        solo = (minimo[1] + (maximo[1] - minimo[1]) * 0.062) * escala
        for vertice in ausentes:
            x = centro_x + ((vertice.x - (min(xs) + max(xs)) / 2) / largura_grafo) * largura
            z = centro_z + ((vertice.y - (min(ys) + max(ys)) / 2) / altura_grafo) * profundidade
            self.projeto.posicoes[vertice.identificador] = (x, solo, z)

    def marcadores_qml(self) -> list[dict[str, object]]:
        marcadores = []
        for vertice in self.projeto.grafo.listar_vertices():
            posicao = self.projeto.posicoes.get(vertice.identificador)
            if posicao is None:
                continue
            selecionado = (
                self.selecao == ("vertice", vertice.identificador)
                or self.vertice_reposicionado == vertice.identificador
                or (
                    self.modo is ModoEditor.CRIAR_RUA
                    and vertice.identificador
                    in (self.operacao_rua.origem, self.operacao_rua.destino)
                )
            )
            marcadores.append(
                {
                    "id": vertice.identificador,
                    "nome": vertice.nome,
                    "tipo": vertice.tipo.value,
                    "cor": (
                        "#F59E0B"
                        if selecionado
                        else self.CORES_TIPOS[vertice.tipo]
                    ),
                    "x": posicao[0],
                    "y": posicao[1],
                    "z": posicao[2],
                }
            )
        return marcadores

    @staticmethod
    def _segmentos(
        pontos: Sequence[Sequence[float]], identificador: str, cor: str
    ) -> list[dict[str, object]]:
        segmentos = []
        for indice, (inicio, fim) in enumerate(zip(pontos, pontos[1:])):
            a = EditorCidade3D._posicao(inicio)
            b = EditorCidade3D._posicao(fim)
            segmentos.append(
                {
                    "id": f"{identificador}:{indice}",
                    "aresta": identificador,
                    "cor": cor,
                    "ax": a[0],
                    "ay": a[1] + 0.004,
                    "az": a[2],
                    "bx": b[0],
                    "by": b[1] + 0.004,
                    "bz": b[2],
                }
            )
        return segmentos

    def segmentos_ruas_qml(self) -> list[dict[str, object]]:
        segmentos: list[dict[str, object]] = []
        for chave, geometria in self.projeto.ruas.items():
            pontos = self.pontos_rua(
                geometria.origem,
                geometria.destino,
                geometria.pontos_intermediarios,
            )
            identificador = "|".join(chave)
            if self.selecao == ("aresta", *chave):
                cor = "#F59E0B"
            elif geometria.calibrada_manualmente:
                cor = "#5B7896"
            else:
                cor = "#FB923C"
            segmentos.extend(self._segmentos(pontos, identificador, cor))
        return segmentos

    def segmentos_previa_qml(self) -> list[dict[str, object]]:
        operacao = self.operacao_rua
        if operacao.origem is None:
            return []
        pontos = [self.projeto.posicoes[operacao.origem]]
        pontos.extend(operacao.pontos_intermediarios)
        if operacao.destino is not None:
            pontos.append(self.projeto.posicoes[operacao.destino])
        return self._segmentos(pontos, "previa", "#F59E0B")


__all__ = ["EditorCidade3D", "ModoEditor", "OperacaoRua"]
