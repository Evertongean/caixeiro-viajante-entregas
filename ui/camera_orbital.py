"""Estado matemático e testável da câmera da cena 3D."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, pi, sin, sqrt
from typing import Sequence


class ModoCamera(str, Enum):
    """Modos disponíveis na visualização e na missão."""

    LIVRE = "livre"
    AEREA = "aerea"
    ATRAS_DO_CARRO = "atras_do_carro"


def _vetor3(valor: Sequence[float]) -> tuple[float, float, float]:
    if len(valor) != 3:
        raise ValueError("Uma coordenada 3D deve ter três componentes.")
    return tuple(float(componente) for componente in valor)  # type: ignore[return-value]


@dataclass(slots=True)
class CameraOrbital:
    """Câmera orbital com zoom, rotação, deslocamento e enquadramento."""

    centro: tuple[float, float, float] = (0.0, 0.0, 0.0)
    yaw: float = pi
    pitch: float = 0.58
    distancia: float = 4.0
    distancia_minima: float = 0.08
    distancia_maxima: float = 100.0
    modo: ModoCamera = ModoCamera.LIVRE
    passo_zoom: float = 1.12
    _raio: float = 1.0

    def __post_init__(self) -> None:
        self.centro = _vetor3(self.centro)
        self._limitar()

    def _limitar(self) -> None:
        self.distancia_minima = max(0.001, float(self.distancia_minima))
        self.distancia_maxima = max(
            self.distancia_minima, float(self.distancia_maxima)
        )
        self.yaw = float(self.yaw) % (2 * pi)
        self.pitch = max(0.08, min(1.49, float(self.pitch)))
        self.distancia = max(
            self.distancia_minima,
            min(self.distancia_maxima, float(self.distancia)),
        )

    def orbitar(self, delta_x: float, delta_y: float) -> None:
        """Rotaciona a câmera sem alterar a geometria da cena."""
        self.modo = ModoCamera.LIVRE
        self.yaw = (self.yaw - float(delta_x) * 0.008) % (2 * pi)
        self.pitch += float(delta_y) * 0.008
        self._limitar()

    def deslocar(self, delta_x: float, delta_y: float) -> None:
        """Desloca o alvo no plano horizontal/vertical da câmera."""
        self.modo = ModoCamera.LIVRE
        fator = max(self.distancia * 0.0018, 0.0002)
        direita = (-sin(self.yaw), 0.0, cos(self.yaw))
        self.centro = (
            self.centro[0] - float(delta_x) * fator * direita[0],
            self.centro[1] + float(delta_y) * fator,
            self.centro[2] - float(delta_x) * fator * direita[2],
        )

    def zoom(self, passos: float) -> None:
        """Aproxima para passos positivos e afasta para passos negativos."""
        if not passos:
            return
        expoente = max(-100.0, min(100.0, float(passos)))
        self.distancia *= self.passo_zoom ** (-expoente)
        self._limitar()

    def enquadrar(
        self,
        minimo: Sequence[float],
        maximo: Sequence[float],
        *,
        escala: float = 1.0,
        modo: ModoCamera = ModoCamera.LIVRE,
    ) -> None:
        """Centraliza e dimensiona a câmera a partir da caixa do modelo."""
        minimo3, maximo3 = _vetor3(minimo), _vetor3(maximo)
        escala = abs(float(escala))
        dimensoes = tuple((maximo3[i] - minimo3[i]) * escala for i in range(3))
        if any(dimensao <= 0 for dimensao in dimensoes):
            raise ValueError("Os limites do modelo devem formar uma caixa válida.")
        self.centro = tuple(
            (minimo3[i] + maximo3[i]) * 0.5 * escala for i in range(3)
        )  # type: ignore[assignment]
        diagonal_xz = sqrt(dimensoes[0] ** 2 + dimensoes[2] ** 2)
        self._raio = max(diagonal_xz * 0.55, dimensoes[1] * 0.75, 0.05)
        self.distancia_minima = max(self._raio * 0.10, 0.01)
        self.distancia_maxima = max(self._raio * 8.0, 1.0)
        self.distancia = self._raio * 1.9
        self.yaw = pi * 1.18
        self.pitch = 0.58
        self.modo = modo
        self._limitar()

    def visao_aerea(self) -> None:
        """Adota um ângulo alto sem mover ou escalar a cidade."""
        self.modo = ModoCamera.AEREA
        self.pitch = 1.32
        self.yaw = pi
        self.distancia = max(self._raio * 2.15, self.distancia_minima)
        self._limitar()

    def focar(
        self,
        centro: Sequence[float],
        dimensoes: Sequence[float],
    ) -> None:
        """Enquadra um objeto já posicionado no espaço da cena."""
        self.centro = _vetor3(centro)
        dx, dy, dz = _vetor3(dimensoes)
        self._raio = max(sqrt(dx * dx + dz * dz) * 0.55, dy * 0.75, 0.04)
        self.distancia_minima = max(self._raio * 0.12, 0.008)
        self.distancia_maxima = max(self._raio * 12.0, 1.0)
        self.distancia = self._raio * 2.2
        self.yaw = pi * 1.25
        self.pitch = 0.34
        self.modo = ModoCamera.LIVRE
        self._limitar()

    def preparar_camera_atras_do_carro(self, posicao: Sequence[float]) -> None:
        """Ativa o modo cujo posicionamento dinâmico vem da câmera seguidora."""
        self.centro = _vetor3(posicao)
        self.modo = ModoCamera.ATRAS_DO_CARRO

    @property
    def posicao(self) -> tuple[float, float, float]:
        horizontal = cos(self.pitch) * self.distancia
        return (
            self.centro[0] + cos(self.yaw) * horizontal,
            self.centro[1] + sin(self.pitch) * self.distancia,
            self.centro[2] + sin(self.yaw) * horizontal,
        )

    @property
    def raio(self) -> float:
        return self._raio
