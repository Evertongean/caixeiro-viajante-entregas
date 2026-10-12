"""Controlador determinístico da missão, independente de Qt e da renderização."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import atan2, degrees, isfinite, sqrt

from models.rota import AlgoritmoRota, RotaCalculada


Ponto3D = tuple[float, float, float]


class ErroMissao(ValueError):
    """A missão não pode ser criada ou receber a transição solicitada."""


class EstadoMissao(str, Enum):
    PRONTA = "pronta"
    EM_MOVIMENTO = "em_movimento"
    PAUSADA = "pausada"
    EM_ENTREGA = "em_entrega"
    CONCLUIDA = "concluida"
    ENCERRADA = "encerrada"


class TipoEventoMissao(str, Enum):
    ENTREGA = "entrega"
    CONCLUSAO = "conclusao"


@dataclass(frozen=True, slots=True)
class EventoMissao:
    tipo: TipoEventoMissao
    vertice: str


@dataclass(frozen=True, slots=True)
class QuadroMissao:
    estado: EstadoMissao
    posicao: Ponto3D
    orientacao_graus: float
    indice_aresta: int
    origem_aresta: str
    destino_aresta: str
    progresso_aresta: float
    distancia_percorrida: float
    distancia_restante: float
    clientes_atendidos: tuple[str, ...]
    total_clientes: int
    proximo_cliente: str | None
    tempo_decorrido: float
    eventos: tuple[EventoMissao, ...] = ()


@dataclass(frozen=True, slots=True)
class ResumoMissao:
    algoritmo: AlgoritmoRota
    origem: str
    destino: str | None
    clientes_selecionados: tuple[str, ...]
    ordem_atendimento: tuple[str, ...]
    distancia_total: float
    distancia_percorrida: float
    tempo_decorrido: float
    clientes_atendidos: int
    total_clientes: int
    concluida: bool


@dataclass(frozen=True, slots=True)
class _TrechoMovimento:
    indice_aresta: int
    inicio: Ponto3D
    fim: Ponto3D
    comprimento: float
    transicao_estacionamento: bool = False


def _distancia(a: Ponto3D, b: Ponto3D) -> float:
    return sqrt(sum((b[eixo] - a[eixo]) ** 2 for eixo in range(3)))


def _interpolar(a: Ponto3D, b: Ponto3D, proporcao: float) -> Ponto3D:
    return tuple(
        a[eixo] + (b[eixo] - a[eixo]) * proporcao for eixo in range(3)
    )  # type: ignore[return-value]


def _angulo_movimento(inicio: Ponto3D, fim: Ponto3D) -> float:
    """Yaw em graus, com zero apontando para +Z na cena Qt Quick 3D."""
    return degrees(atan2(fim[0] - inicio[0], fim[2] - inicio[2]))


def _aproximar_angulo(atual: float, alvo: float, limite: float) -> float:
    diferenca = (alvo - atual + 180.0) % 360.0 - 180.0
    if abs(diferenca) <= limite:
        return alvo
    return atual + (limite if diferenca > 0 else -limite)


class ControladorMissao:
    """Percorre exatamente as polilinhas espaciais da rota calculada."""

    def __init__(
        self,
        rota: RotaCalculada,
        *,
        velocidade_base: float = 0.18,
        tempo_parada_entrega: float = 1.0,
        velocidade_rotacao: float = 240.0,
        posicao_inicial: Ponto3D | None = None,
        orientacao_inicial_graus: float | None = None,
    ) -> None:
        if not isinstance(rota, RotaCalculada):
            raise TypeError("É necessário fornecer uma RotaCalculada.")
        if not rota.segmentos_espaciais:
            raise ErroMissao("A rota não possui um trajeto espacial para percorrer.")
        if not rota.calibracao_completa:
            raise ErroMissao(
                "A missão exige todos os trechos espaciais confirmados manualmente."
            )
        if any(
            not segmento.disponivel or not segmento.confirmado_manualmente
            for segmento in rota.segmentos_espaciais
        ):
            raise ErroMissao(
                "A missão exige todos os trechos espaciais confirmados manualmente."
            )
        for nome, valor, permite_zero in (
            ("velocidade_base", velocidade_base, False),
            ("tempo_parada_entrega", tempo_parada_entrega, True),
            ("velocidade_rotacao", velocidade_rotacao, False),
        ):
            if not isfinite(valor) or valor < 0 or (not permite_zero and valor == 0):
                raise ValueError(f"{nome} deve ser positivo e finito.")

        self.rota = rota
        self.velocidade_base = float(velocidade_base)
        self.tempo_parada_entrega = float(tempo_parada_entrega)
        self.velocidade_rotacao = float(velocidade_rotacao)
        self._multiplicador = 1.0
        self._comprimentos_arestas: list[float] = []
        self._trechos: list[_TrechoMovimento] = []
        for segmento in rota.segmentos_espaciais:
            comprimento_aresta = 0.0
            for inicio, fim in zip(segmento.pontos, segmento.pontos[1:]):
                comprimento = _distancia(inicio, fim)
                if comprimento <= 1e-12:
                    continue
                self._trechos.append(
                    _TrechoMovimento(segmento.indice, inicio, fim, comprimento)
                )
                comprimento_aresta += comprimento
            if comprimento_aresta <= 1e-12:
                raise ErroMissao(
                    f"O trecho {segmento.origem} → {segmento.destino} "
                    "não possui comprimento espacial."
                )
            self._comprimentos_arestas.append(comprimento_aresta)

        inicio_rota = self._trechos[0].inicio
        self._posicao_inicial = (
            tuple(float(valor) for valor in posicao_inicial)
            if posicao_inicial is not None
            else inicio_rota
        )
        if len(self._posicao_inicial) != 3 or not all(
            isfinite(valor) for valor in self._posicao_inicial
        ):
            raise ValueError("A posição inicial deve possuir três coordenadas finitas.")
        orientacao_rota = _angulo_movimento(inicio_rota, self._trechos[0].fim)
        self._orientacao_inicial = (
            float(orientacao_inicial_graus)
            if orientacao_inicial_graus is not None
            else orientacao_rota
        )
        if not isfinite(self._orientacao_inicial):
            raise ValueError("A orientação inicial deve ser finita.")
        distancia_transicao = _distancia(self._posicao_inicial, inicio_rota)
        if distancia_transicao > 1e-12:
            self._trechos.insert(
                0,
                _TrechoMovimento(
                    0,
                    self._posicao_inicial,
                    inicio_rota,
                    distancia_transicao,
                    True,
                ),
            )

        self._clientes_programados = tuple(
            identificador
            for identificador in rota.ordem_atendimento
            if identificador in rota.clientes_selecionados
        )
        self._reiniciar_estado()

    @property
    def multiplicador_velocidade(self) -> float:
        return self._multiplicador

    @multiplicador_velocidade.setter
    def multiplicador_velocidade(self, valor: float) -> None:
        if valor not in (0.5, 1.0, 2.0, 4.0):
            raise ValueError("A velocidade deve ser 0,5x, 1x, 2x ou 4x.")
        self._multiplicador = float(valor)

    @property
    def ativo(self) -> bool:
        return self.estado not in (EstadoMissao.CONCLUIDA, EstadoMissao.ENCERRADA)

    def _reiniciar_estado(self) -> None:
        self.estado = EstadoMissao.PRONTA
        self._estado_antes_pausa = EstadoMissao.EM_MOVIMENTO
        self._indice_trecho = 0
        self._distancia_no_trecho = 0.0
        self._geometria_na_aresta = 0.0
        self._distancia_oficial_anterior = 0.0
        self._indice_entrega = 0
        self._clientes_atendidos: list[str] = []
        self._espera_restante = 0.0
        self.tempo_decorrido = 0.0
        self.posicao = self._posicao_inicial
        self.orientacao_graus = self._orientacao_inicial

    def iniciar(self) -> QuadroMissao:
        if self.estado is not EstadoMissao.PRONTA:
            raise ErroMissao(
                "A missão só pode ser iniciada a partir do estado pronto."
            )
        self.estado = EstadoMissao.EM_MOVIMENTO
        return self.quadro()

    def pausar(self) -> QuadroMissao:
        if self.estado not in (EstadoMissao.EM_MOVIMENTO, EstadoMissao.EM_ENTREGA):
            raise ErroMissao("A missão não está em execução.")
        self._estado_antes_pausa = self.estado
        self.estado = EstadoMissao.PAUSADA
        return self.quadro()

    def continuar(self) -> QuadroMissao:
        if self.estado is not EstadoMissao.PAUSADA:
            raise ErroMissao("A missão não está pausada.")
        self.estado = self._estado_antes_pausa
        return self.quadro()

    def reiniciar(self, *, iniciar: bool = True) -> QuadroMissao:
        if self.estado is EstadoMissao.ENCERRADA:
            raise ErroMissao("Uma missão encerrada não pode ser reiniciada.")
        self._reiniciar_estado()
        if iniciar:
            self.estado = EstadoMissao.EM_MOVIMENTO
        return self.quadro()

    def encerrar(self) -> QuadroMissao:
        self.estado = EstadoMissao.ENCERRADA
        self.posicao = self._posicao_inicial
        self.orientacao_graus = self._orientacao_inicial
        return self.quadro()

    def _indice_aresta_atual(self) -> int:
        if self._indice_trecho >= len(self._trechos):
            return len(self.rota.segmentos_espaciais) - 1
        return self._trechos[self._indice_trecho].indice_aresta

    def _distancia_oficial(self) -> float:
        if self.estado is EstadoMissao.CONCLUIDA:
            return self.rota.distancia_total
        indice = self._indice_aresta_atual()
        comprimento = self._comprimentos_arestas[indice]
        proporcao = min(max(self._geometria_na_aresta / comprimento, 0.0), 1.0)
        peso = self.rota.segmentos_espaciais[indice].peso
        return min(
            self.rota.distancia_total,
            self._distancia_oficial_anterior + peso * proporcao,
        )

    def quadro(
        self, eventos: tuple[EventoMissao, ...] = ()
    ) -> QuadroMissao:
        indice = self._indice_aresta_atual()
        segmento = self.rota.segmentos_espaciais[indice]
        percorrida = self._distancia_oficial()
        comprimento = self._comprimentos_arestas[indice]
        progresso = min(max(self._geometria_na_aresta / comprimento, 0.0), 1.0)
        if self.estado is EstadoMissao.CONCLUIDA:
            progresso = 1.0
        proximo = (
            self._clientes_programados[self._indice_entrega]
            if self._indice_entrega < len(self._clientes_programados)
            else None
        )
        return QuadroMissao(
            estado=self.estado,
            posicao=self.posicao,
            orientacao_graus=self.orientacao_graus,
            indice_aresta=indice,
            origem_aresta=segmento.origem,
            destino_aresta=segmento.destino,
            progresso_aresta=progresso,
            distancia_percorrida=percorrida,
            distancia_restante=max(0.0, self.rota.distancia_total - percorrida),
            clientes_atendidos=tuple(self._clientes_atendidos),
            total_clientes=len(self._clientes_programados),
            proximo_cliente=proximo,
            tempo_decorrido=self.tempo_decorrido,
            eventos=eventos,
        )

    def avancar(self, delta_segundos: float) -> QuadroMissao:
        if not isfinite(delta_segundos) or delta_segundos < 0:
            raise ValueError("O delta de tempo deve ser não negativo e finito.")
        if self.estado not in (EstadoMissao.EM_MOVIMENTO, EstadoMissao.EM_ENTREGA):
            return self.quadro()

        restante_tempo = float(delta_segundos)
        eventos: list[EventoMissao] = []
        while restante_tempo > 1e-12 and self.estado in (
            EstadoMissao.EM_MOVIMENTO,
            EstadoMissao.EM_ENTREGA,
        ):
            if self.estado is EstadoMissao.EM_ENTREGA:
                consumido = min(restante_tempo, self._espera_restante)
                self._espera_restante -= consumido
                self.tempo_decorrido += consumido
                restante_tempo -= consumido
                if self._espera_restante <= 1e-12:
                    self._espera_restante = 0.0
                    self.estado = EstadoMissao.EM_MOVIMENTO
                else:
                    break
                continue

            trecho = self._trechos[self._indice_trecho]
            falta = trecho.comprimento - self._distancia_no_trecho
            velocidade = self.velocidade_base * self._multiplicador
            tempo_necessario = falta / velocidade
            consumido = min(restante_tempo, tempo_necessario)
            deslocamento = velocidade * consumido
            self._distancia_no_trecho = min(
                trecho.comprimento, self._distancia_no_trecho + deslocamento
            )
            if not trecho.transicao_estacionamento:
                self._geometria_na_aresta += deslocamento
            proporcao = self._distancia_no_trecho / trecho.comprimento
            self.posicao = _interpolar(trecho.inicio, trecho.fim, proporcao)
            alvo = _angulo_movimento(trecho.inicio, trecho.fim)
            self.orientacao_graus = _aproximar_angulo(
                self.orientacao_graus,
                alvo,
                self.velocidade_rotacao * consumido,
            )
            self.tempo_decorrido += consumido
            restante_tempo -= consumido
            if self._distancia_no_trecho < trecho.comprimento - 1e-12:
                break

            self.posicao = trecho.fim
            indice_aresta_concluida = trecho.indice_aresta
            proximo_indice = self._indice_trecho + 1
            terminou_aresta = (
                proximo_indice >= len(self._trechos)
                or self._trechos[proximo_indice].indice_aresta
                != indice_aresta_concluida
            )
            self._indice_trecho = proximo_indice
            self._distancia_no_trecho = 0.0
            if trecho.transicao_estacionamento:
                continue
            if terminou_aresta:
                segmento = self.rota.segmentos_espaciais[indice_aresta_concluida]
                self._distancia_oficial_anterior += segmento.peso
                self._geometria_na_aresta = 0.0
                if (
                    self._indice_entrega < len(self._clientes_programados)
                    and segmento.destino
                    == self._clientes_programados[self._indice_entrega]
                ):
                    cliente = segmento.destino
                    self._clientes_atendidos.append(cliente)
                    self._indice_entrega += 1
                    eventos.append(EventoMissao(TipoEventoMissao.ENTREGA, cliente))
                    if self.tempo_parada_entrega > 0:
                        self._espera_restante = self.tempo_parada_entrega
                        self.estado = EstadoMissao.EM_ENTREGA

            if self._indice_trecho >= len(self._trechos):
                self.estado = EstadoMissao.CONCLUIDA
                self._distancia_oficial_anterior = self.rota.distancia_total
                self._geometria_na_aresta = self._comprimentos_arestas[-1]
                eventos.append(
                    EventoMissao(
                        TipoEventoMissao.CONCLUSAO,
                        self.rota.percurso_completo[-1],
                    )
                )
                break

        return self.quadro(tuple(eventos))

    def resumo(self) -> ResumoMissao:
        return ResumoMissao(
            algoritmo=self.rota.algoritmo,
            origem=self.rota.origem,
            destino=self.rota.destino,
            clientes_selecionados=self.rota.clientes_selecionados,
            ordem_atendimento=self.rota.ordem_atendimento,
            distancia_total=self.rota.distancia_total,
            distancia_percorrida=self._distancia_oficial(),
            tempo_decorrido=self.tempo_decorrido,
            clientes_atendidos=len(self._clientes_atendidos),
            total_clientes=len(self._clientes_programados),
            concluida=self.estado is EstadoMissao.CONCLUIDA,
        )


__all__ = [
    "ControladorMissao",
    "ErroMissao",
    "EstadoMissao",
    "EventoMissao",
    "QuadroMissao",
    "ResumoMissao",
    "TipoEventoMissao",
]
