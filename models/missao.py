"""Controlador cinemático da missão, independente de Qt e da renderização."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import acos, atan2, degrees, isfinite, sqrt

from models.rota import AlgoritmoRota, RotaCalculada


Ponto3D = tuple[float, float, float]
EPSILON = 1e-10


class ErroMissao(ValueError):
    """A missão não pode ser criada ou receber a transição solicitada."""


class EstadoMissao(str, Enum):
    PRONTA = "pronta"
    EM_MOVIMENTO = "em_movimento"
    PAUSADA = "pausada"
    EM_ENTREGA = "em_entrega"
    CONCLUIDA = "concluida"
    ENCERRADA = "encerrada"


class FaseMovimento(str, Enum):
    """Fase cinemática exibível sem misturar a regra com a interface."""

    PARADO = "parado"
    ACELERANDO = "acelerando"
    CRUZEIRO = "velocidade de cruzeiro"
    FREANDO_CURVA = "freando para curva"
    EM_CURVA = "realizando curva"
    FREANDO_ENTREGA = "freando para entrega"
    ENTREGANDO = "entrega em andamento"
    RETOMANDO = "retomando deslocamento"
    FREANDO_DESTINO = "freando para destino"
    PAUSADO = "pausado"
    CONCLUIDO = "missão concluída"


class TipoCurva(str, Enum):
    RETA = "reta"
    SUAVE = "suave"
    MODERADA = "moderada"
    FECHADA = "fechada"
    RETORNO = "retorno em U"


class TipoEventoMissao(str, Enum):
    ENTREGA = "entrega"
    CONCLUSAO = "conclusao"


@dataclass(frozen=True, slots=True)
class EventoMissao:
    tipo: TipoEventoMissao
    vertice: str


@dataclass(frozen=True, slots=True)
class CurvaRota:
    """Mudança relevante de direção em uma posição da geometria percorrida."""

    indice_trecho: int
    distancia_percurso: float
    angulo_graus: float
    tipo: TipoCurva
    fator_velocidade: float


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
    velocidade_atual: float
    velocidade_desejada: float
    velocidade_maxima: float
    fase_movimento: FaseMovimento
    distancia_proxima_curva: float | None
    tipo_proxima_curva: TipoCurva | None
    distancia_proxima_parada: float
    distancia_proxima_entrega: float | None
    distancia_destino_final: float
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


@dataclass(frozen=True, slots=True)
class _ParadaRota:
    distancia_percurso: float
    vertice: str
    entrega: bool
    posicao: Ponto3D


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


def _angulo_entre_trechos(
    anterior: _TrechoMovimento, seguinte: _TrechoMovimento
) -> float:
    ax = anterior.fim[0] - anterior.inicio[0]
    az = anterior.fim[2] - anterior.inicio[2]
    bx = seguinte.fim[0] - seguinte.inicio[0]
    bz = seguinte.fim[2] - seguinte.inicio[2]
    norma_a = sqrt(ax * ax + az * az)
    norma_b = sqrt(bx * bx + bz * bz)
    if norma_a <= EPSILON or norma_b <= EPSILON:
        return 0.0
    cosseno = max(-1.0, min(1.0, (ax * bx + az * bz) / (norma_a * norma_b)))
    return degrees(acos(cosseno))


def _classificar_curva(angulo: float) -> tuple[TipoCurva, float]:
    """Classifica a curva e devolve a fração segura da velocidade máxima.

    Mudanças abaixo de 12° são tratadas como ruído/colinearidade. As demais
    usam 85% (suave), 62% (moderada), 40% (fechada) e 22% (retorno em U).
    """
    if angulo < 12.0:
        return TipoCurva.RETA, 1.0
    if angulo < 40.0:
        return TipoCurva.SUAVE, 0.85
    if angulo < 75.0:
        return TipoCurva.MODERADA, 0.62
    if angulo < 135.0:
        return TipoCurva.FECHADA, 0.40
    return TipoCurva.RETORNO, 0.22


class ControladorMissao:
    """Percorre a polilinha com aceleração e look-ahead determinísticos.

    ``velocidade_base`` continua sendo aceito por compatibilidade e representa
    a velocidade máxima em unidades espaciais por segundo de simulação.
    """

    def __init__(
        self,
        rota: RotaCalculada,
        *,
        velocidade_base: float = 0.18,
        tempo_parada_entrega: float = 1.0,
        velocidade_rotacao: float = 240.0,
        posicao_inicial: Ponto3D | None = None,
        orientacao_inicial_graus: float | None = None,
        aceleracao: float | None = None,
        desaceleracao_conforto: float | None = None,
        frenagem_maxima: float | None = None,
        passo_maximo: float = 1.0 / 120.0,
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
            ("passo_maximo", passo_maximo, False),
        ):
            if not isfinite(valor) or valor < 0 or (not permite_zero and valor == 0):
                raise ValueError(f"{nome} deve ser positivo e finito.")

        self.rota = rota
        self.tempo_parada_entrega = float(tempo_parada_entrega)
        self.velocidade_rotacao = float(velocidade_rotacao)
        self.passo_maximo = float(passo_maximo)
        self._multiplicador = 1.0
        self._aceleracao_automatica = aceleracao is None
        self._desaceleracao_automatica = desaceleracao_conforto is None
        self._frenagem_automatica = frenagem_maxima is None
        self._velocidade_maxima = 0.0
        self._aceleracao = 0.0
        self._desaceleracao_conforto = 0.0
        self._frenagem_maxima = 0.0
        self.velocidade_base = float(velocidade_base)
        for nome, valor in (
            ("aceleracao", aceleracao),
            ("desaceleracao_conforto", desaceleracao_conforto),
            ("frenagem_maxima", frenagem_maxima),
        ):
            if valor is not None and (not isfinite(valor) or valor <= 0):
                raise ValueError(f"{nome} deve ser positivo e finito.")
        if aceleracao is not None:
            self._aceleracao = float(aceleracao)
        if desaceleracao_conforto is not None:
            self._desaceleracao_conforto = float(desaceleracao_conforto)
        if frenagem_maxima is not None:
            self._frenagem_maxima = float(frenagem_maxima)
        if self._frenagem_maxima < self._desaceleracao_conforto:
            raise ValueError(
                "A frenagem máxima não pode ser menor que a de conforto."
            )

        self._comprimentos_arestas: list[float] = []
        self._trechos: list[_TrechoMovimento] = []
        for segmento in rota.segmentos_espaciais:
            comprimento_aresta = 0.0
            for inicio, fim in zip(segmento.pontos, segmento.pontos[1:]):
                comprimento = _distancia(inicio, fim)
                if comprimento <= EPSILON:
                    continue
                self._trechos.append(
                    _TrechoMovimento(segmento.indice, inicio, fim, comprimento)
                )
                comprimento_aresta += comprimento
            if comprimento_aresta <= EPSILON:
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
            raise ValueError(
                "A posição inicial deve possuir três coordenadas finitas."
            )
        orientacao_rota = _angulo_movimento(inicio_rota, self._trechos[0].fim)
        self._orientacao_inicial = (
            float(orientacao_inicial_graus)
            if orientacao_inicial_graus is not None
            else orientacao_rota
        )
        if not isfinite(self._orientacao_inicial):
            raise ValueError("A orientação inicial deve ser finita.")

        distancia_transicao = _distancia(self._posicao_inicial, inicio_rota)
        if distancia_transicao > EPSILON:
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
        fim_rota = self._trechos[-1].fim
        retorna_ao_estacionamento = (
            rota.algoritmo is AlgoritmoRota.TSP
            and rota.percurso_completo[-1] == rota.origem
            and _distancia(fim_rota, self._posicao_inicial) > EPSILON
        )
        if retorna_ao_estacionamento:
            self._trechos.append(
                _TrechoMovimento(
                    len(rota.segmentos_espaciais) - 1,
                    fim_rota,
                    self._posicao_inicial,
                    _distancia(fim_rota, self._posicao_inicial),
                    True,
                )
            )

        self._clientes_programados = tuple(
            identificador
            for identificador in rota.ordem_atendimento
            if identificador in rota.clientes_selecionados
        )
        self._distancias_acumuladas = self._calcular_distancias_acumuladas()
        self._curvas = self._detectar_curvas()
        self._paradas = self._identificar_paradas()
        self._reiniciar_estado()

    @property
    def velocidade_base(self) -> float:
        return self._velocidade_maxima

    @velocidade_base.setter
    def velocidade_base(self, valor: float) -> None:
        if not isfinite(valor) or valor <= 0:
            raise ValueError("velocidade_base deve ser positiva e finita.")
        self._velocidade_maxima = float(valor)
        if self._aceleracao_automatica:
            self._aceleracao = self._velocidade_maxima * 1.6
        if self._desaceleracao_automatica:
            self._desaceleracao_conforto = self._velocidade_maxima * 2.2
        if self._frenagem_automatica:
            self._frenagem_maxima = self._velocidade_maxima * 4.0

    @property
    def velocidade_maxima(self) -> float:
        return self._velocidade_maxima

    @property
    def aceleracao(self) -> float:
        return self._aceleracao

    @property
    def desaceleracao_conforto(self) -> float:
        return self._desaceleracao_conforto

    @property
    def frenagem_maxima(self) -> float:
        return self._frenagem_maxima

    @property
    def curvas_detectadas(self) -> tuple[CurvaRota, ...]:
        return self._curvas

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

    def distancia_frenagem(
        self, velocidade_alvo: float = 0.0, *, frenagem: float | None = None
    ) -> float:
        desaceleracao = self._desaceleracao_conforto if frenagem is None else frenagem
        if not isfinite(velocidade_alvo) or velocidade_alvo < 0:
            raise ValueError("A velocidade alvo deve ser não negativa e finita.")
        if not isfinite(desaceleracao) or desaceleracao <= 0:
            raise ValueError("A desaceleração deve ser positiva e finita.")
        diferenca = self.velocidade_atual**2 - velocidade_alvo**2
        return max(0.0, diferenca / (2.0 * desaceleracao))

    def _calcular_distancias_acumuladas(self) -> tuple[float, ...]:
        acumuladas = [0.0]
        for trecho in self._trechos:
            acumuladas.append(acumuladas[-1] + trecho.comprimento)
        return tuple(acumuladas)

    def _detectar_curvas(self) -> tuple[CurvaRota, ...]:
        curvas: list[CurvaRota] = []
        for indice, (anterior, seguinte) in enumerate(
            zip(self._trechos, self._trechos[1:])
        ):
            if _distancia(anterior.fim, seguinte.inicio) > 1e-7:
                continue
            angulo = _angulo_entre_trechos(anterior, seguinte)
            tipo, fator = _classificar_curva(angulo)
            if tipo is TipoCurva.RETA:
                continue
            curvas.append(
                CurvaRota(
                    indice_trecho=indice,
                    distancia_percurso=self._distancias_acumuladas[indice + 1],
                    angulo_graus=angulo,
                    tipo=tipo,
                    fator_velocidade=fator,
                )
            )
        return tuple(curvas)

    def _fim_espacial_do_segmento(self, indice_aresta: int) -> float:
        finais = [
            self._distancias_acumuladas[indice + 1]
            for indice, trecho in enumerate(self._trechos)
            if trecho.indice_aresta == indice_aresta
            and not trecho.transicao_estacionamento
        ]
        return max(finais)

    def _identificar_paradas(self) -> tuple[_ParadaRota, ...]:
        paradas: list[_ParadaRota] = []
        indice_cliente = 0
        for segmento in self.rota.segmentos_espaciais:
            if (
                indice_cliente < len(self._clientes_programados)
                and segmento.destino == self._clientes_programados[indice_cliente]
            ):
                paradas.append(
                    _ParadaRota(
                        self._fim_espacial_do_segmento(segmento.indice),
                        segmento.destino,
                        True,
                        segmento.pontos[-1],
                    )
                )
                indice_cliente += 1
        paradas.append(
            _ParadaRota(
                self._distancias_acumuladas[-1],
                self.rota.percurso_completo[-1],
                False,
                self._trechos[-1].fim,
            )
        )
        return tuple(paradas)

    def _reiniciar_estado(self) -> None:
        self.estado = EstadoMissao.PRONTA
        self._estado_antes_pausa = EstadoMissao.EM_MOVIMENTO
        self._fase_antes_pausa = FaseMovimento.PARADO
        self.fase_movimento = FaseMovimento.PARADO
        self._indice_trecho = 0
        self._distancia_no_trecho = 0.0
        self._geometria_na_aresta = 0.0
        self._distancia_oficial_anterior = 0.0
        self._indice_entrega = 0
        self._indice_parada = 0
        self._clientes_atendidos: list[str] = []
        self._espera_restante = 0.0
        self._retomando_apos_entrega = False
        self.tempo_decorrido = 0.0
        self.posicao = self._posicao_inicial
        self.orientacao_graus = self._orientacao_inicial
        self.velocidade_atual = 0.0
        self.velocidade_desejada = 0.0

    def iniciar(self) -> QuadroMissao:
        if self.estado is not EstadoMissao.PRONTA:
            raise ErroMissao(
                "A missão só pode ser iniciada a partir do estado pronto."
            )
        self.estado = EstadoMissao.EM_MOVIMENTO
        self.fase_movimento = FaseMovimento.ACELERANDO
        return self.quadro()

    def pausar(self) -> QuadroMissao:
        if self.estado not in (EstadoMissao.EM_MOVIMENTO, EstadoMissao.EM_ENTREGA):
            raise ErroMissao("A missão não está em execução.")
        self._estado_antes_pausa = self.estado
        self._fase_antes_pausa = self.fase_movimento
        self.estado = EstadoMissao.PAUSADA
        self.fase_movimento = FaseMovimento.PAUSADO
        return self.quadro()

    def continuar(self) -> QuadroMissao:
        if self.estado is not EstadoMissao.PAUSADA:
            raise ErroMissao("A missão não está pausada.")
        self.estado = self._estado_antes_pausa
        self.fase_movimento = self._fase_antes_pausa
        return self.quadro()

    def reiniciar(self, *, iniciar: bool = True) -> QuadroMissao:
        if self.estado is EstadoMissao.ENCERRADA:
            raise ErroMissao("Uma missão encerrada não pode ser reiniciada.")
        self._reiniciar_estado()
        if iniciar:
            self.estado = EstadoMissao.EM_MOVIMENTO
            self.fase_movimento = FaseMovimento.ACELERANDO
        return self.quadro()

    def encerrar(self) -> QuadroMissao:
        self.estado = EstadoMissao.ENCERRADA
        self.fase_movimento = FaseMovimento.PARADO
        self.posicao = self._posicao_inicial
        self.orientacao_graus = self._orientacao_inicial
        self.velocidade_atual = 0.0
        self.velocidade_desejada = 0.0
        return self.quadro()

    def _indice_aresta_atual(self) -> int:
        if self._indice_trecho >= len(self._trechos):
            return len(self.rota.segmentos_espaciais) - 1
        return self._trechos[self._indice_trecho].indice_aresta

    def _distancia_global(self) -> float:
        if self._indice_trecho >= len(self._trechos):
            return self._distancias_acumuladas[-1]
        return (
            self._distancias_acumuladas[self._indice_trecho]
            + self._distancia_no_trecho
        )

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

    def _proxima_parada(self) -> tuple[_ParadaRota, float]:
        parada = self._paradas[min(self._indice_parada, len(self._paradas) - 1)]
        return parada, max(0.0, parada.distancia_percurso - self._distancia_global())

    def _proxima_curva(self) -> tuple[CurvaRota | None, float | None]:
        atual = self._distancia_global()
        for curva in self._curvas:
            distancia = curva.distancia_percurso - atual
            zona_saida = min(
                0.04,
                self._trechos[curva.indice_trecho + 1].comprimento * 0.35,
            )
            if distancia >= -zona_saida:
                return curva, max(0.0, distancia)
        return None, None

    def _velocidade_segura(self) -> tuple[float, FaseMovimento]:
        desejada = self._velocidade_maxima
        fase = FaseMovimento.CRUZEIRO
        distancia_atual = self._distancia_global()

        for curva in self._curvas:
            distancia = curva.distancia_percurso - distancia_atual
            zona_saida = min(
                0.04,
                self._trechos[curva.indice_trecho + 1].comprimento * 0.35,
            )
            if distancia < -zona_saida:
                continue
            segura = self._velocidade_maxima * curva.fator_velocidade
            if distancia <= 0.0:
                permitida = segura
                fase_curva = FaseMovimento.EM_CURVA
            else:
                permitida = sqrt(
                    segura * segura
                    + 2.0 * self._desaceleracao_conforto * distancia
                )
                fase_curva = FaseMovimento.FREANDO_CURVA
            if permitida < desejada:
                desejada = permitida
                fase = fase_curva

        parada, distancia_parada = self._proxima_parada()
        permitida_parada = sqrt(
            max(0.0, 2.0 * self._desaceleracao_conforto * distancia_parada)
        )
        if permitida_parada < desejada:
            desejada = permitida_parada
            fase = (
                FaseMovimento.FREANDO_ENTREGA
                if parada.entrega
                else FaseMovimento.FREANDO_DESTINO
            )
        return min(self._velocidade_maxima, desejada), fase

    def quadro(
        self, eventos: tuple[EventoMissao, ...] = ()
    ) -> QuadroMissao:
        indice = self._indice_aresta_atual()
        segmento = self.rota.segmentos_espaciais[indice]
        percorrida = self._distancia_oficial()
        comprimento = self._comprimentos_arestas[indice]
        progresso = min(max(self._geometria_na_aresta / comprimento, 0.0), 1.0)
        if (
            self.estado is EstadoMissao.CONCLUIDA
            or self._distancia_oficial_anterior >= self.rota.distancia_total - EPSILON
        ):
            progresso = 1.0
        proximo = (
            self._clientes_programados[self._indice_entrega]
            if self._indice_entrega < len(self._clientes_programados)
            else None
        )
        curva, distancia_curva = self._proxima_curva()
        proxima_parada, distancia_parada = self._proxima_parada()
        distancia_final = max(
            0.0, self._distancias_acumuladas[-1] - self._distancia_global()
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
            velocidade_atual=self.velocidade_atual,
            velocidade_desejada=self.velocidade_desejada,
            velocidade_maxima=self._velocidade_maxima,
            fase_movimento=self.fase_movimento,
            distancia_proxima_curva=distancia_curva,
            tipo_proxima_curva=curva.tipo if curva is not None else None,
            distancia_proxima_parada=distancia_parada,
            distancia_proxima_entrega=(
                distancia_parada if proxima_parada.entrega else None
            ),
            distancia_destino_final=distancia_final,
            eventos=eventos,
        )

    def _concluir_aresta(self, trecho: _TrechoMovimento) -> None:
        if trecho.transicao_estacionamento:
            return
        proximo_indice = self._indice_trecho + 1
        terminou_aresta = (
            proximo_indice >= len(self._trechos)
            or self._trechos[proximo_indice].transicao_estacionamento
            or self._trechos[proximo_indice].indice_aresta != trecho.indice_aresta
        )
        if terminou_aresta:
            segmento = self.rota.segmentos_espaciais[trecho.indice_aresta]
            self._distancia_oficial_anterior = min(
                self.rota.distancia_total,
                self._distancia_oficial_anterior + segmento.peso,
            )
            self._geometria_na_aresta = 0.0

    def _avancar_distancia(self, distancia: float) -> None:
        restante = max(0.0, distancia)
        while restante > EPSILON and self._indice_trecho < len(self._trechos):
            trecho = self._trechos[self._indice_trecho]
            falta = trecho.comprimento - self._distancia_no_trecho
            deslocamento = min(restante, falta)
            self._distancia_no_trecho += deslocamento
            if not trecho.transicao_estacionamento:
                self._geometria_na_aresta += deslocamento
            proporcao = self._distancia_no_trecho / trecho.comprimento
            self.posicao = _interpolar(trecho.inicio, trecho.fim, proporcao)
            restante -= deslocamento
            if self._distancia_no_trecho < trecho.comprimento - EPSILON:
                break
            self.posicao = trecho.fim
            self._concluir_aresta(trecho)
            self._indice_trecho += 1
            self._distancia_no_trecho = 0.0

    def _atingir_parada(self, eventos: list[EventoMissao]) -> None:
        parada = self._paradas[self._indice_parada]
        self.posicao = parada.posicao
        self.velocidade_atual = 0.0
        self.velocidade_desejada = 0.0
        self._indice_parada += 1
        if parada.entrega:
            if parada.vertice not in self._clientes_atendidos:
                self._clientes_atendidos.append(parada.vertice)
                self._indice_entrega += 1
                eventos.append(
                    EventoMissao(TipoEventoMissao.ENTREGA, parada.vertice)
                )
            if self.tempo_parada_entrega > 0:
                self._espera_restante = self.tempo_parada_entrega
                self.estado = EstadoMissao.EM_ENTREGA
                self.fase_movimento = FaseMovimento.ENTREGANDO
            else:
                self._retomando_apos_entrega = True
                self.fase_movimento = FaseMovimento.RETOMANDO
            return

        self.estado = EstadoMissao.CONCLUIDA
        self.fase_movimento = FaseMovimento.CONCLUIDO
        self._distancia_oficial_anterior = self.rota.distancia_total
        self._geometria_na_aresta = self._comprimentos_arestas[-1]
        eventos.append(EventoMissao(TipoEventoMissao.CONCLUSAO, parada.vertice))

    def _atualizar_orientacao(self, delta: float) -> None:
        if self._indice_trecho >= len(self._trechos):
            return
        trecho = self._trechos[self._indice_trecho]
        alvo = _angulo_movimento(trecho.inicio, trecho.fim)
        limite = max(
            self.velocidade_rotacao * delta,
            90.0
            * delta
            * (1.0 + (1.0 - self.velocidade_atual / self._velocidade_maxima)),
        )
        self.orientacao_graus = _aproximar_angulo(
            self.orientacao_graus, alvo, limite
        )

    def _integrar_movimento(
        self, delta: float, eventos: list[EventoMissao]
    ) -> None:
        parada, distancia_parada = self._proxima_parada()
        if distancia_parada <= EPSILON:
            self._atingir_parada(eventos)
            return

        desejada, fase_limitante = self._velocidade_segura()
        self.velocidade_desejada = desejada
        anterior = self.velocidade_atual
        if desejada > anterior + EPSILON:
            self.velocidade_atual = min(
                desejada, anterior + self._aceleracao * delta
            )
            self.fase_movimento = (
                FaseMovimento.RETOMANDO
                if self._retomando_apos_entrega
                else FaseMovimento.ACELERANDO
            )
        elif desejada < anterior - EPSILON:
            desaceleracao = self._desaceleracao_conforto
            velocidade_parada = 0.0 if fase_limitante in (
                FaseMovimento.FREANDO_ENTREGA,
                FaseMovimento.FREANDO_DESTINO,
            ) else desejada
            distancia_alvo = distancia_parada
            if fase_limitante is FaseMovimento.FREANDO_CURVA:
                _, distancia_curva = self._proxima_curva()
                distancia_alvo = distancia_curva or 0.0
            necessaria = (
                max(0.0, anterior**2 - velocidade_parada**2)
                / max(2.0 * distancia_alvo, EPSILON)
            )
            if necessaria > self._desaceleracao_conforto * 1.05:
                desaceleracao = min(self._frenagem_maxima, necessaria)
            self.velocidade_atual = max(
                desejada, anterior - desaceleracao * delta
            )
            self.fase_movimento = fase_limitante
        else:
            self.velocidade_atual = desejada
            self.fase_movimento = fase_limitante

        if (
            self._retomando_apos_entrega
            and self.velocidade_atual >= min(
                self.velocidade_desejada, self._velocidade_maxima * 0.8
            ) - EPSILON
        ):
            self._retomando_apos_entrega = False

        deslocamento = (anterior + self.velocidade_atual) * 0.5 * delta
        deslocamento = min(deslocamento, distancia_parada)
        self._avancar_distancia(deslocamento)
        self._atualizar_orientacao(delta)
        if distancia_parada - deslocamento <= EPSILON:
            self._atingir_parada(eventos)

    def avancar(self, delta_segundos: float) -> QuadroMissao:
        if not isfinite(delta_segundos) or delta_segundos < 0:
            raise ValueError("O delta de tempo deve ser não negativo e finito.")
        if self.estado not in (EstadoMissao.EM_MOVIMENTO, EstadoMissao.EM_ENTREGA):
            return self.quadro()

        restante_tempo = float(delta_segundos) * self._multiplicador
        eventos: list[EventoMissao] = []
        while restante_tempo > EPSILON and self.estado in (
            EstadoMissao.EM_MOVIMENTO,
            EstadoMissao.EM_ENTREGA,
        ):
            passo = min(restante_tempo, self.passo_maximo)
            if self.estado is EstadoMissao.EM_ENTREGA:
                consumido = min(passo, self._espera_restante)
                self._espera_restante -= consumido
                self.tempo_decorrido += consumido
                restante_tempo -= consumido
                if self._espera_restante <= EPSILON:
                    self._espera_restante = 0.0
                    self.estado = EstadoMissao.EM_MOVIMENTO
                    self.fase_movimento = FaseMovimento.RETOMANDO
                    self._retomando_apos_entrega = True
                continue

            self._integrar_movimento(passo, eventos)
            self.tempo_decorrido += passo
            restante_tempo -= passo

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
    "CurvaRota",
    "ErroMissao",
    "EstadoMissao",
    "EventoMissao",
    "FaseMovimento",
    "QuadroMissao",
    "ResumoMissao",
    "TipoCurva",
    "TipoEventoMissao",
]
