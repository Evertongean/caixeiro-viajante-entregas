import math
import unittest

from ui.camera_orbital_3d import CameraOrbital3D


class TestCameraOrbital3D(unittest.TestCase):
    def setUp(self) -> None:
        self.camera = CameraOrbital3D()
        self.camera.enquadrar((10.0, 2.0, -4.0), (202.27, 59.56, 224.41), 0.01)

    def test_enquadramento_define_distancia_e_limites_reais(self) -> None:
        self.assertEqual(self.camera.centro, (0.1, 0.02, -0.04))
        self.assertGreater(self.camera.distancia, self.camera.distancia_minima)
        self.assertGreater(self.camera.distancia_maxima, self.camera.distancia)

    def test_zoom_altera_distancia_e_respeita_limites(self) -> None:
        inicial = self.camera.distancia
        self.camera.zoom(1)
        self.assertLess(self.camera.distancia, inicial)
        self.camera.zoom(10_000)
        self.assertEqual(self.camera.distancia, self.camera.distancia_minima)
        self.camera.zoom(-10_000)
        self.assertEqual(self.camera.distancia, self.camera.distancia_maxima)

    def test_orbita_tem_yaw_circular_e_pitch_limitado(self) -> None:
        yaw = self.camera.yaw
        self.camera.orbitar(100, 100_000)
        self.assertNotEqual(self.camera.yaw, yaw)
        self.assertGreaterEqual(self.camera.pitch, self.camera.limite_pitch_minimo)
        self.assertLessEqual(self.camera.pitch, self.camera.limite_pitch_maximo)
        self.camera.orbitar(-100_000, -100_000)
        self.assertGreaterEqual(self.camera.yaw, 0.0)
        self.assertLess(self.camera.yaw, 2 * math.pi)

    def test_pan_desloca_somente_o_alvo(self) -> None:
        centro = self.camera.centro
        self.camera.deslocar(30, -10)
        self.assertNotEqual(self.camera.centro, centro)
        self.assertEqual(len(self.camera.posicao_camera()), 3)

    def test_foco_carro_reduz_o_enquadramento(self) -> None:
        self.camera.focar((1, 0, 2), (2.52, 1.89, 6.28), 0.018)
        self.assertLess(self.camera.distancia, 1.0)
        self.assertEqual(self.camera.centro, (1.0, 0.0, 2.0))


if __name__ == "__main__":
    unittest.main()
