"""Testes do estado matemático da nova câmera 3D."""

import math
import unittest

from ui.camera_orbital import CameraOrbital, ModoCamera


class TestCameraOrbital(unittest.TestCase):
    def test_enquadramento_usa_centro_e_dimensoes_reais(self) -> None:
        camera = CameraOrbital()
        camera.enquadrar((-10, -2, -5), (10, 6, 15), escala=0.1)

        self.assertEqual(camera.centro, (0.0, 0.2, 0.5))
        self.assertGreater(camera.distancia, camera.distancia_minima)
        self.assertLess(camera.distancia, camera.distancia_maxima)

    def test_orbita_e_limita_pitch(self) -> None:
        camera = CameraOrbital()
        yaw_inicial = camera.yaw
        camera.orbitar(40, 10000)

        self.assertNotEqual(camera.yaw, yaw_inicial)
        self.assertLessEqual(camera.pitch, 1.49)
        self.assertEqual(camera.modo, ModoCamera.LIVRE)

    def test_zoom_respeita_limites(self) -> None:
        camera = CameraOrbital(distancia=5, distancia_minima=1, distancia_maxima=10)
        camera.zoom(1000)
        self.assertEqual(camera.distancia, 1)
        camera.zoom(-1000)
        self.assertEqual(camera.distancia, 10)

    def test_deslocamento_move_alvo_sem_alterar_geometria(self) -> None:
        camera = CameraOrbital(centro=(0, 0, 0), yaw=math.pi, distancia=5)
        camera.deslocar(20, -10)
        self.assertNotEqual(camera.centro, (0.0, 0.0, 0.0))

    def test_visao_aerea_e_camera_atras_do_carro(self) -> None:
        camera = CameraOrbital()
        camera.enquadrar((-1, -1, -1), (1, 1, 1))
        camera.visao_aerea()
        self.assertEqual(camera.modo, ModoCamera.AEREA)
        self.assertGreater(camera.pitch, 1.2)

        camera.preparar_camera_atras_do_carro((2, 0, 3))
        self.assertEqual(camera.modo, ModoCamera.ATRAS_DO_CARRO)
        self.assertEqual(camera.centro, (2.0, 0.0, 3.0))

    def test_rejeita_caixa_sem_volume(self) -> None:
        with self.assertRaisesRegex(ValueError, "caixa válida"):
            CameraOrbital().enquadrar((0, 0, 0), (0, 1, 1))


if __name__ == "__main__":
    unittest.main()
