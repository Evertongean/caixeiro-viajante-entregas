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
    EDITAR_TRACADO = "editar_tracado"


@dataclass(frozen=True, slots=True)
class ResultadoSnap:
    posicao: tuple[float, float, float]
    encaixado: bool = False
    origem: str | None = None
    distancia: float | None = None


@dataclass(slots=True)
class OperacaoRua:
    origem: str | None = None
    destino: str | None = None
    pontos_intermediarios: list[tuple[float, float, float]] = field(
        default_factory=list
    )
    editando_aresta: tuple[str, str] | None = None
    pontos_originais: tuple[tuple[float, float, float], ...] = ()
    historico: list[list[tuple[float, float, float]]] = field(default_factory=list)
    futuro: list[list[tuple[float, float, float]]] = field(default_factory=list)
    ponto_selecionado: int | None = None
    arrastando: int | None = None
    posicao_antes_arraste: tuple[float, float, float] | None = None
    previa_valida: bool = True
    snap_ativo: bool = True
    snap_origem: str | None = None

    @property
    def modificada(self) -> bool:
        return tuple(self.pontos_intermediarios) != self.pontos_originais


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
        atualizado = self.projeto.grafo.atualizar_vertice(
            identificador,
            nome=nome,
            tipo=tipo,
            x=atual.x,
            y=atual.y,
        )
        if atual.tipo is not atualizado.tipo and (
            atual.tipo is TipoVertice.DEPOSITO
            or atualizado.tipo is TipoVertice.DEPOSITO
        ):
            self.projeto.estacionamento_inicial = None
        return atualizado

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
        if atualizado.tipo is TipoVertice.DEPOSITO:
            self.projeto.estacionamento_inicial = None
        return atualizado

    def remover_vertice(self, identificador: str) -> Vertice:
        removido = self.projeto.grafo.remover_vertice(identificador)
        if removido.tipo is TipoVertice.DEPOSITO:
            self.projeto.estacionamento_inicial = None
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
        self.operacao_rua = OperacaoRua(
            origem,
            destino,
            intermediarios,
            chave,
            tuple(intermediarios),
        )
        if editar:
            self.modo = ModoEditor.EDITAR_TRACADO

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
        self._guardar_estado()
        self.operacao_rua.pontos_intermediarios.append(self._posicao(posicao))
        self.operacao_rua.ponto_selecionado = (
            len(self.operacao_rua.pontos_intermediarios) - 1
        )

    def inserir_ponto_intermediario(
        self, indice_segmento: int, posicao: Sequence[float]
    ) -> int:
        """Insere no segmento visual mantendo a ordem da polilinha."""
        operacao = self.operacao_rua
        if operacao.origem is None or operacao.destino is None:
            raise ValueError("Selecione os extremos antes de inserir uma curva.")
        if not 0 <= indice_segmento <= len(operacao.pontos_intermediarios):
            raise IndexError("O segmento selecionado não pertence à rua.")
        self._guardar_estado()
        operacao.pontos_intermediarios.insert(
            indice_segmento, self._posicao(posicao)
        )
        operacao.ponto_selecionado = indice_segmento
        return indice_segmento

    def selecionar_ponto_intermediario(self, indice: int | None) -> None:
        if indice is not None and not (
            0 <= indice < len(self.operacao_rua.pontos_intermediarios)
        ):
            raise IndexError("O ponto de controle não pertence à rua.")
        self.operacao_rua.ponto_selecionado = indice

    def remover_ponto_intermediario(self, indice: int | None = None) -> tuple[float, float, float]:
        operacao = self.operacao_rua
        escolhido = operacao.ponto_selecionado if indice is None else indice
        if escolhido is None or not 0 <= escolhido < len(operacao.pontos_intermediarios):
            raise ValueError("Selecione um ponto intermediário para removê-lo.")
        self._guardar_estado()
        removido = operacao.pontos_intermediarios.pop(escolhido)
        operacao.ponto_selecionado = (
            min(escolhido, len(operacao.pontos_intermediarios) - 1)
            if operacao.pontos_intermediarios
            else None
        )
        return removido

    def _guardar_estado(self) -> None:
        operacao = self.operacao_rua
        operacao.historico.append(list(operacao.pontos_intermediarios))
        operacao.futuro.clear()

    def desfazer_edicao_rua(self) -> bool:
        operacao = self.operacao_rua
        if not operacao.historico:
            return False
        operacao.futuro.append(list(operacao.pontos_intermediarios))
        operacao.pontos_intermediarios = operacao.historico.pop()
        operacao.ponto_selecionado = None
        operacao.previa_valida = True
        operacao.snap_origem = None
        return True

    def refazer_edicao_rua(self) -> bool:
        operacao = self.operacao_rua
        if not operacao.futuro:
            return False
        operacao.historico.append(list(operacao.pontos_intermediarios))
        operacao.pontos_intermediarios = operacao.futuro.pop()
        operacao.ponto_selecionado = None
        operacao.previa_valida = True
        operacao.snap_origem = None
        return True

    def iniciar_arraste_ponto(self, indice: int) -> None:
        self.selecionar_ponto_intermediario(indice)
        operacao = self.operacao_rua
        operacao.arrastando = indice
        operacao.posicao_antes_arraste = operacao.pontos_intermediarios[indice]
        operacao.previa_valida = True

    def atualizar_arraste_ponto(
        self,
        posicao: Sequence[float],
        *,
        valida: bool = True,
        snap_origem: str | None = None,
    ) -> None:
        operacao = self.operacao_rua
        if operacao.arrastando is None:
            raise ValueError("Nenhum ponto de controle está sendo arrastado.")
        operacao.pontos_intermediarios[operacao.arrastando] = self._posicao(posicao)
        operacao.previa_valida = bool(valida)
        operacao.snap_origem = snap_origem

    def finalizar_arraste_ponto(self, *, valida: bool) -> bool:
        operacao = self.operacao_rua
        if operacao.arrastando is None or operacao.posicao_antes_arraste is None:
            return False
        indice = operacao.arrastando
        anterior = operacao.posicao_antes_arraste
        atual = operacao.pontos_intermediarios[indice]
        alterou = valida and atual != anterior
        if alterou:
            estado_anterior = list(operacao.pontos_intermediarios)
            estado_anterior[indice] = anterior
            operacao.historico.append(estado_anterior)
            operacao.futuro.clear()
        elif not valida:
            operacao.pontos_intermediarios[indice] = anterior
        operacao.arrastando = None
        operacao.posicao_antes_arraste = None
        operacao.previa_valida = True
        operacao.snap_origem = None
        return alterou

    @staticmethod
    def _projetar_no_segmento(
        ponto: tuple[float, float, float],
        inicio: tuple[float, float, float],
        fim: tuple[float, float, float],
    ) -> tuple[tuple[float, float, float], float]:
        vetor = tuple(b - a for a, b in zip(inicio, fim))
        denominador = sum(valor * valor for valor in vetor)
        if denominador <= 1e-18:
            return inicio, dist(ponto, inicio)
        t = sum((p - a) * v for p, a, v in zip(ponto, inicio, vetor)) / denominador
        t = max(0.0, min(1.0, t))
        projecao = tuple(a + t * v for a, v in zip(inicio, vetor))
        return projecao, dist(ponto, projecao)  # type: ignore[arg-type]

    def aplicar_snap(
        self,
        posicao: Sequence[float],
        *,
        tolerancia: float = 0.045,
    ) -> ResultadoSnap:
        ponto = self._posicao(posicao)
        if not self.operacao_rua.snap_ativo:
            return ResultadoSnap(ponto)
        candidatos: list[tuple[float, str, tuple[float, float, float]]] = []
        for identificador, vertice in self.projeto.posicoes.items():
            candidatos.append((dist(ponto, vertice), f"vértice {identificador}", vertice))
        for chave, geometria in self.projeto.ruas.items():
            if chave == self.operacao_rua.editando_aresta:
                continue
            polilinha = self.projeto.polilinha_rua(*chave)
            for indice, (inicio, fim) in enumerate(zip(polilinha, polilinha[1:])):
                projecao, distancia = self._projetar_no_segmento(ponto, inicio, fim)
                candidatos.append(
                    (distancia, f"rua {chave[0]} ↔ {chave[1]} (segmento {indice + 1})", projecao)
                )
        if not candidatos:
            return ResultadoSnap(ponto)
        distancia, origem, encaixado = min(candidatos, key=lambda item: item[0])
        if distancia > tolerancia:
            return ResultadoSnap(ponto)
        return ResultadoSnap(encaixado, True, origem, distancia)

    def segmento_operacao_mais_proximo(
        self, posicao: Sequence[float]
    ) -> tuple[int, tuple[float, float, float], float]:
        operacao = self.operacao_rua
        if operacao.origem is None or operacao.destino is None:
            raise ValueError("A rua ainda não possui os dois extremos.")
        ponto = self._posicao(posicao)
        polilinha = self.pontos_rua(
            operacao.origem, operacao.destino, operacao.pontos_intermediarios
        )
        candidatos = []
        for indice, (inicio, fim) in enumerate(zip(polilinha, polilinha[1:])):
            projecao, distancia = self._projetar_no_segmento(ponto, inicio, fim)
            candidatos.append((distancia, indice, projecao))
        if not candidatos:
            raise ValueError("A rua não possui segmento onde inserir o ponto.")
        distancia, indice, projecao = min(candidatos, key=lambda item: item[0])
        return indice, projecao, distancia

    def definir_snap_ativo(self, ativo: bool) -> None:
        self.operacao_rua.snap_ativo = bool(ativo)
        if not ativo:
            self.operacao_rua.snap_origem = None

    def desfazer_ponto_rua(self) -> str | None:
        operacao = self.operacao_rua
        if operacao.pontos_intermediarios:
            self._guardar_estado()
            operacao.pontos_intermediarios.pop()
            operacao.ponto_selecionado = None
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

    def confirmar_rua(
        self,
        peso: float,
        fator_km_por_unidade: float,
        *,
        validada_automaticamente: bool = True,
    ) -> None:
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
            bool(validada_automaticamente),
        )
        self.projeto.fator_km_por_unidade = float(fator_km_por_unidade)
        self.cancelar_operacao()
        self.modo = ModoEditor.NAVEGAR

    def validar_operacao_rua(self) -> list[str]:
        """Valida o que é conclusivo sem prometer colisão perfeita com edifícios."""
        operacao = self.operacao_rua
        if operacao.origem is None or operacao.destino is None:
            return ["Selecione os dois extremos da rua."]
        pontos = self.pontos_rua(
            operacao.origem, operacao.destino, operacao.pontos_intermediarios
        )
        problemas: list[str] = []
        comprimentos = [dist(a, b) for a, b in zip(pontos, pontos[1:])]
        if not comprimentos or sum(comprimentos) <= 1e-9:
            problemas.append("A polilinha deve possuir comprimento positivo.")
        if any(comprimento <= 1e-7 for comprimento in comprimentos):
            problemas.append("Existem pontos consecutivos duplicados.")
        positivos = sorted(valor for valor in comprimentos if valor > 1e-7)
        if len(positivos) >= 2:
            mediana = positivos[len(positivos) // 2]
            if mediana > 0 and max(positivos) > mediana * 8:
                problemas.append(
                    "Há um salto muito grande entre pontos; confira se o "
                    "segmento permanece na via."
                )
        if not operacao.previa_valida:
            problemas.append("O ponto em edição não está sobre uma superfície válida.")
        return problemas

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

    def segmentos_ruas_qml(
        self,
        validacoes_automaticas: dict[
            tuple[str, str], tuple[bool, bool, str]
        ] | None = None,
    ) -> list[dict[str, object]]:
        segmentos: list[dict[str, object]] = []
        for chave, geometria in self.projeto.ruas.items():
            pontos = self.pontos_rua(
                geometria.origem,
                geometria.destino,
                geometria.pontos_intermediarios,
            )
            identificador = "|".join(chave)
            validacao = (
                validacoes_automaticas.get(chave)
                if validacoes_automaticas is not None
                else None
            )
            if self.selecao == ("aresta", *chave):
                cor = "#F59E0B"
            elif validacao is not None and validacao[0]:
                cor = "#5B7896"
            elif validacao is not None and validacao[1]:
                cor = "#EF4444"
            elif validacao is not None:
                cor = "#FB923C"
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
        cor = "#EF4444" if not operacao.previa_valida else "#FACC15"
        return self._segmentos(pontos, "previa", cor)

    def controles_rua_qml(self) -> list[dict[str, object]]:
        operacao = self.operacao_rua
        if operacao.origem is None or operacao.destino is None:
            return []
        pontos = self.pontos_rua(
            operacao.origem, operacao.destino, operacao.pontos_intermediarios
        )
        controles: list[dict[str, object]] = []
        ultimo = len(pontos) - 1
        for indice, ponto in enumerate(pontos):
            intermediario = 0 < indice < ultimo
            indice_intermediario = indice - 1 if intermediario else -1
            cor = "#22C55E" if indice == 0 else "#F97316" if indice == ultimo else "#E6F4FF"
            if intermediario and indice_intermediario == operacao.ponto_selecionado:
                cor = "#22D3EE" if operacao.previa_valida else "#EF4444"
            controles.append(
                {
                    "id": indice,
                    "indiceIntermediario": indice_intermediario,
                    "movel": intermediario,
                    "cor": cor,
                    "x": ponto[0],
                    "y": ponto[1],
                    "z": ponto[2],
                    "encaixado": intermediario
                    and indice_intermediario == operacao.ponto_selecionado
                    and operacao.snap_origem is not None,
                }
            )
        return controles


__all__ = ["EditorCidade3D", "ModoEditor", "OperacaoRua", "ResultadoSnap"]
