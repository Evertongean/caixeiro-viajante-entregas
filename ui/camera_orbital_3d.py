"""Estado matemático da câmera orbital da visualização Qt Quick 3D.

O controlador não conhece Qt nem os modelos GLB. Isso deixa os limites e as
transformações testáveis em ambientes sem uma superfície gráfica e evita que
o estado da navegação livre seja misturado ao acompanhamento do carro.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sin, sqrt
from typing import Sequence


def _tripla(valor: Sequence[float]) -> tuple[float, float, float]:
    if len(valor) < 3:
        raise ValueError("uma coordenada 3D precisa de três componentes")
    return (float(valor[0]), float(valor[1]), float(valor[2]))


@dataclass
class CameraOrbital3D:
    """Câmera esférica com alvo deslocável e limites dimensionais.

    ``yaw`` e ``pitch`` são radianos. O eixo Y é vertical, como no Qt Quick
    3D; ``pitch`` fica sempre entre o horizonte e quase o zênite para impedir
    que a câmera vire de cabeça para baixo.
    """

    centro: tuple[float, float, float] = (0.0, 0.0, 0.0)
    yaw: float = pi
    pitch: float = 0.58
    distancia: float = 1.0
    distancia_minima: float = 0.04
    distancia_maxima: float = 100.0
    passo_zoom: float = 1.12
    limite_pitch_minimo: float = 0.10
    limite_pitch_maximo: float = 1.48
    _raio_enquadramento: float = 1.0

    def __post_init__(self) -> None:
        self.centro = _tripla(self.centro)
        self._normalizar()

    def _normalizar(self) -> None:
        self.distancia_minima = max(1e-4, float(self.distancia_minima))
        self.distancia_maxima = max(self.distancia_minima, float(self.distancia_maxima))
        self.yaw = float(self.yaw) % (2.0 * pi)
        self.pitch = max(
            float(self.limite_pitch_minimo),
            min(float(self.limite_pitch_maximo), float(self.pitch)),
        )
        self.distancia = max(
            self.distancia_minima,
            min(self.distancia_maxima, float(self.distancia)),
        )

    def orbitar(self, delta_x: float, delta_y: float, *, sensibilidade: float = 0.009) -> None:
        """Gira em resposta ao arrasto do botão esquerdo."""

        self.yaw = (self.yaw - float(delta_x) * float(sensibilidade)) % (2.0 * pi)
        self.pitch = max(
            self.limite_pitch_minimo,
            min(self.limite_pitch_maximo, self.pitch + float(delta_y) * float(sensibilidade)),
        )

    def zoom(self, passos: float) -> None:
        """Altera a distância, preservando limites e sem escalar a geometria."""

        passos = float(passos)
        if passos == 0.0:
            return
        if passos >= 100.0:
            self.distancia = self.distancia_minima
            return
        if passos <= -100.0:
            self.distancia = self.distancia_maxima
            return
        fator = float(self.passo_zoom) ** (-passos)
        self.distancia = max(
            self.distancia_minima,
            min(self.distancia_maxima, self.distancia * fator),
        )

    def deslocar(self, delta_x: float, delta_y: float, *, escala: float | None = None) -> None:
        """Desloca o alvo no plano da câmera (botão direito + arrasto)."""

        fator = float(escala) if escala is not None else max(self.distancia * 0.002, 1e-4)
        # Vetor horizontal à direita da câmera. O deslocamento vertical usa o
        # eixo Y do mundo para manter ruas e prédios estáveis no enquadramento.
        direita = (-sin(self.yaw), 0.0, cos(self.yaw))
        self.centro = (
            self.centro[0] - float(delta_x) * fator * direita[0],
            self.centro[1] + float(delta_y) * fator,
            self.centro[2] - float(delta_x) * fator * direita[2],
        )

    # Alias explícito usado por clientes que chamam a operação de pan.
    pan = deslocar

    def enquadrar(
        self,
        centro: Sequence[float],
        dimensoes: Sequence[float],
        escala: float = 1.0,
        posicao: Sequence[float] = (0.0, 0.0, 0.0),
    ) -> None:
        """Calcula alvo, distância e limites a partir da caixa real do modelo."""

        centro_modelo = _tripla(centro)
        dimensoes_modelo = _tripla(dimensoes)
        deslocamento = _tripla(posicao)
        escala = abs(float(escala))
        self.centro = tuple(
            centro_modelo[indice] * escala + deslocamento[indice]
            for indice in range(3)
        )
        diagonal_xz = sqrt(dimensoes_modelo[0] ** 2 + dimensoes_modelo[2] ** 2)
        raio = max(diagonal_xz * escala * 0.66, dimensoes_modelo[1] * escala * 0.58, 0.04)
        self._raio_enquadramento = raio
        self.distancia_minima = max(raio * 0.08, 0.008)
        self.distancia_maxima = max(raio * 8.0, self.distancia_minima * 4.0, 0.12)
        self.distancia = max(raio * 1.9, self.distancia_minima)
        # Vista inicial oblíqua semelhante à anterior, mas agora orbitável.
        self.yaw = pi
        self.pitch = 0.58
        self._normalizar()

    def focar(
        self,
        centro: Sequence[float],
        dimensoes: Sequence[float],
        escala: float = 1.0,
    ) -> None:
        """Enquadra um único objeto e mantém o mesmo contrato de limites."""

        centro_objeto = _tripla(centro)
        dimensoes_objeto = _tripla(dimensoes)
        escala = abs(float(escala))
        diagonal_xz = sqrt(dimensoes_objeto[0] ** 2 + dimensoes_objeto[2] ** 2)
        raio = max(diagonal_xz * escala * 0.48, dimensoes_objeto[1] * escala * 0.55, 0.04)
        self.centro = centro_objeto
        self._raio_enquadramento = raio
        self.distancia_minima = max(raio * 0.08, 0.008)
        self.distancia_maxima = max(raio * 8.0, self.distancia_minima * 4.0, 0.12)
        self.distancia = max(raio * 1.55, self.distancia_minima)
        # Um foco de objeto começa de frente, evitando que o carro fique
        # reduzido a uma silhueta no mesmo ângulo da cidade.
        self.yaw = pi * 0.82
        self.pitch = 0.34
        self._normalizar()

    def posicao_camera(self) -> tuple[float, float, float]:
        horizontal = cos(self.pitch) * self.distancia
        return (
            self.centro[0] + cos(self.yaw) * horizontal,
            self.centro[1] + sin(self.pitch) * self.distancia,
            self.centro[2] + sin(self.yaw) * horizontal,
        )

    @property
    def alvo(self) -> tuple[float, float, float]:
        return self.centro

    @property
    def raio(self) -> float:
        return self._raio_enquadramento


__all__ = ["CameraOrbital3D"]
