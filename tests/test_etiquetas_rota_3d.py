"""Regressoes da projecao das etiquetas e da fita de rota no QML."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6 import QtQuick3D  # noqa: F401 - registra os tipos QML
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QVector3D
    from PySide6.QtQuickWidgets import QQuickWidget
    from PySide6.QtWidgets import QApplication

    PYSIDE6_DISPONIVEL = True
except ModuleNotFoundError:
    PYSIDE6_DISPONIVEL = False


@unittest.skipUnless(PYSIDE6_DISPONIVEL, "PySide6 não está instalado")
class TestEtiquetasERota3D(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.aplicacao = QApplication.instance() or QApplication([])
        cls.qml = Path(__file__).parents[1] / "ui" / "cena_3d.qml"

    def setUp(self) -> None:
        self.cena = QQuickWidget()
        self.cena.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self.cena.resize(800, 600)
        self.cena.setSource(QUrl.fromLocalFile(str(self.qml)))
        self.cena.show()
        self._processar()
        self.raiz = self.cena.rootObject()
        self.assertEqual(self.cena.status(), QQuickWidget.Status.Ready)
        self.assertIsNotNone(self.raiz)

    def tearDown(self) -> None:
        self.cena.close()
        self.cena.deleteLater()
        self._processar()

    def _processar(self, ciclos: int = 5) -> None:
        for _ in range(ciclos):
            self.aplicacao.processEvents()

    @staticmethod
    def _itens(item):
        for filho in item.childItems():
            yield filho
            yield from TestEtiquetasERota3D._itens(filho)

    def _item(self, nome: str):
        for item in self._itens(self.raiz):
            if item.objectName() == nome:
                return item
        self.fail(f"Item QML não encontrado: {nome}")

    def _etiquetas(self, prefixo: str = "etiqueta-") -> list:
        return [
            item
            for item in self._itens(self.raiz)
            if item.objectName().startswith(prefixo)
        ]

    @staticmethod
    def _marcador(identificador: str, x: float = 0.4) -> dict[str, object]:
        return {
            "id": identificador,
            "nome": "Cliente",
            "tipo": "cliente",
            "cor": "#2DD4BF",
            "x": x,
            "y": 0.0,
            "z": 0.0,
        }

    @staticmethod
    def _posicao(item) -> tuple[float, float]:
        return float(item.x()), float(item.y())

    def test_etiqueta_usa_exatamente_a_projecao_do_marcador(self) -> None:
        self.raiz.setProperty("marcadores", [self._marcador("A")])
        self._processar()
        etiqueta = self._item("etiqueta-marcador:A")
        projetado = etiqueta.property("projetado")

        self.assertAlmostEqual(
            etiqueta.x() + etiqueta.width() / 2, projetado.x(), places=3
        )
        self.assertAlmostEqual(etiqueta.y() + etiqueta.height(), projetado.y(), places=3)
        self.assertTrue(etiqueta.isVisible())

    def test_zoom_rotacao_e_deslocamento_reprojetam_etiqueta(self) -> None:
        self.raiz.setProperty("marcadores", [self._marcador("A")])
        self._processar()
        etiqueta = self._item("etiqueta-marcador:A")
        anterior = self._posicao(etiqueta)

        for propriedade, valor in (
            ("cameraDistancia", 2.0),
            ("cameraYaw", 2.5),
            ("centroCamera", QVector3D(0.2, 0.1, -0.1)),
        ):
            with self.subTest(propriedade=propriedade):
                self.raiz.setProperty(propriedade, valor)
                self._processar()
                atual = self._posicao(etiqueta)
                self.assertNotEqual(atual, anterior)
                anterior = atual

    def test_camera_seguidora_e_troca_de_camera_reprojetam_rota(self) -> None:
        self.raiz.setProperty(
            "marcadoresRota",
            [{**self._marcador("A"), "texto": "PRÓXIMA · ENTREGA 1"}],
        )
        self._processar()
        etiqueta = self._item("etiqueta-rota:A")
        livre = self._posicao(etiqueta)

        self.raiz.setProperty("cameraModo", "atras_do_carro")
        self.raiz.setProperty(
            "cameraSeguimentoPosicao", QVector3D(0.0, 0.24, 0.42)
        )
        self.raiz.setProperty("cameraSeguimentoAlvo", QVector3D(0.0, 0.0, 0.0))
        self._processar()
        perseguicao = self._posicao(etiqueta)
        self.assertNotEqual(perseguicao, livre)

        self.raiz.setProperty(
            "cameraSeguimentoPosicao", QVector3D(0.12, 0.24, 0.42)
        )
        self.raiz.setProperty("cameraSeguimentoAlvo", QVector3D(0.12, 0.0, 0.0))
        self._processar()
        self.assertNotEqual(self._posicao(etiqueta), perseguicao)

    def test_camera_seguidora_prioriza_somente_a_proxima_entrega(self) -> None:
        self.raiz.setProperty(
            "marcadoresRota",
            [
                {**self._marcador("A", 0.0), "texto": "PRÓXIMA · ENTREGA 1"},
                {**self._marcador("B", 0.1), "texto": "ENTREGA 2"},
                {**self._marcador("C", -0.1), "texto": "FIM"},
            ],
        )
        self.raiz.setProperty("cameraModo", "atras_do_carro")
        self._processar()

        self.assertTrue(self._item("etiqueta-rota:A").isVisible())
        self.assertFalse(self._item("etiqueta-rota:B").isVisible())
        self.assertTrue(self._item("etiqueta-rota:C").isVisible())

    def test_redimensionamento_reprojeta_no_novo_viewport(self) -> None:
        self.raiz.setProperty("marcadores", [self._marcador("A")])
        self._processar()
        etiqueta = self._item("etiqueta-marcador:A")
        anterior = self._posicao(etiqueta)

        self.cena.resize(1000, 500)
        self._processar()
        self.assertNotEqual(self._posicao(etiqueta), anterior)
        self.assertLessEqual(etiqueta.x() + etiqueta.width(), self.raiz.width())

    def test_ponto_atras_da_camera_e_fora_do_viewport_ficam_ocultos(self) -> None:
        for identificador, x in (("ATRAS", -10.0), ("FORA", 100.0)):
            with self.subTest(identificador=identificador):
                self.raiz.setProperty("marcadores", [self._marcador(identificador, x)])
                self._processar()
                self.assertFalse(
                    self._item(f"etiqueta-marcador:{identificador}").isVisible()
                )

    def test_reposicionamento_e_remocao_atualizam_delegates(self) -> None:
        self.raiz.setProperty("marcadores", [self._marcador("A", 0.0)])
        self._processar()
        anterior = self._posicao(self._item("etiqueta-marcador:A"))

        self.raiz.setProperty("marcadores", [self._marcador("A", 0.8)])
        self._processar()
        self.assertNotEqual(
            self._posicao(self._item("etiqueta-marcador:A")), anterior
        )
        self.raiz.setProperty("marcadores", [])
        self._processar()
        self.assertEqual(self._etiquetas("etiqueta-marcador:"), [])

    def test_cruzamentos_distantes_sao_simplificados_sem_ocultar_clientes(self) -> None:
        cruzamento = {**self._marcador("X"), "tipo": "cruzamento"}
        self.raiz.setProperty("marcadores", [cruzamento, self._marcador("A", 0.0)])
        self.raiz.setProperty("cameraDistancia", 3.0)
        self._processar()
        self.assertFalse(self._item("etiqueta-marcador:X").isVisible())
        self.assertTrue(self._item("etiqueta-marcador:A").isVisible())

        self.raiz.setProperty("cameraDistancia", 2.0)
        self._processar()
        self.assertTrue(self._item("etiqueta-marcador:X").isVisible())

    def test_fita_tem_largura_mundial_fina_e_orientacao_correta(self) -> None:
        self.assertAlmostEqual(self.raiz.property("larguraRotaMundo"), 0.006)
        self.assertAlmostEqual(self.raiz.property("espessuraRotaMundo"), 0.0012)
        self.assertLess(
            self.raiz.property("espessuraRotaMundo"),
            self.raiz.property("larguraRotaMundo"),
        )
        horizontal = self.raiz.rotacaoSegmento(
            {"ax": 0, "ay": 0, "az": 0, "bx": 1, "by": 0, "bz": 0}
        )
        inclinada = self.raiz.rotacaoSegmento(
            {"ax": 0, "ay": 0, "az": 0, "bx": 0, "by": 1, "bz": 1}
        )
        self.assertAlmostEqual(horizontal.y(), 90.0)
        self.assertAlmostEqual(inclinada.x(), -45.0)

    def test_rede_do_editor_nao_duplica_visual_da_rota_calculada(self) -> None:
        fonte = self.qml.read_text(encoding="utf-8")
        self.assertIn("visible: raiz.segmentosRota.length === 0", fonte)


if __name__ == "__main__":
    unittest.main()
