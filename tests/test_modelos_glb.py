"""Testes do diagnóstico e do alinhamento dos assets GLB."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from models.grafo import criar_cenario_exemplo
from ui.modelos_glb import (
    ConfiguracaoModelos3D,
    inspecionar_glb,
    mapear_grafo_cidade_glb,
)

try:
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QApplication
    from ui.renderizador_qtquick3d import (
        RenderizadorQtQuick3D,
        qtquick3d_disponivel,
        testar_cena_minima,
    )
except ModuleNotFoundError:
    QObject = None
    QApplication = None
    RenderizadorQtQuick3D = None
    qtquick3d_disponivel = lambda: False


class TestModelosGLB(unittest.TestCase):
    def setUp(self) -> None:
        raiz = Path(__file__).resolve().parents[1]
        self.cidade = inspecionar_glb(raiz / "assets/models/cidade.glb")
        self.carro = inspecionar_glb(raiz / "assets/models/carro.glb")

    def test_assets_do_projeto_sao_validos_e_tem_diagnostico(self) -> None:
        self.assertTrue(self.cidade.valido)
        self.assertTrue(self.carro.valido)
        self.assertGreater(self.cidade.malhas, 0)
        self.assertGreater(self.carro.materiais, 0)
        self.assertGreater(self.carro.imagens, 0)
        self.assertEqual(self.cidade.eixo_vertical, "Y")
        self.assertIsNotNone(self.cidade.dimensoes)

    def test_arquivo_invalido_nao_e_aceito(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".glb") as arquivo:
            arquivo.write(b"nao e glb")
            arquivo.flush()
            info = inspecionar_glb(arquivo.name)
        self.assertFalse(info.valido)
        self.assertTrue(info.mensagens)

    def test_mapeamento_preserva_vertices_e_rejeita_rota_inexistente(self) -> None:
        mapa = mapear_grafo_cidade_glb(criar_cenario_exemplo(), self.cidade)
        self.assertTrue(mapa.valido)
        self.assertEqual(set(mapa.posicoes), {"D", "X", "A", "B", "C"})
        self.assertEqual(mapa.validar_rota(criar_cenario_exemplo(), ["D", "X", "A"])[0], True)
        self.assertEqual(mapa.validar_rota(criar_cenario_exemplo(), ["D", "B"])[0], False)

    def test_configuracao_rejeita_escala_invalida(self) -> None:
        with self.assertRaises(ValueError):
            ConfiguracaoModelos3D(escala_carro=0).validar()

    @unittest.skipUnless(qtquick3d_disponivel(), "Qt Quick 3D não está instalado")
    def test_cena_qtquick3d_carrega_os_dois_arquivos(self) -> None:
        app = QApplication.instance() or QApplication([])
        cena = RenderizadorQtQuick3D()
        cena.carregar_modelos(self.cidade.caminho, self.carro.caminho)
        self.assertIsNotNone(cena.rootObject())
        fontes = {
            str(obj.property("source"))
            for obj in cena.rootObject().findChildren(QObject)
            if obj.metaObject().className() == "QQuick3DModel"
        }
        self.assertTrue(any("cidade.glb" in fonte for fonte in fontes))
        self.assertTrue(any("carro.glb" in fonte for fonte in fontes))
        cena.close()
        app.processEvents()

    @unittest.skipUnless(qtquick3d_disponivel(), "Qt Quick 3D não está instalado")
    def test_cena_qtquick3d_sincroniza_dimensoes_apos_ficar_visivel(self) -> None:
        app = QApplication.instance() or QApplication([])
        cena = RenderizadorQtQuick3D()
        cena.resize(640, 480)
        cena.show()
        app.processEvents()
        dimensoes = cena.dimensoes_renderizacao
        self.assertGreater(dimensoes["widget_python"][0], 0)
        self.assertGreater(dimensoes["widget_python"][1], 0)
        self.assertGreater(dimensoes["raiz_qml"][0], 0)
        self.assertGreater(dimensoes["view3d"][0], 0)
        cena.close()
        app.processEvents()

    @unittest.skipUnless(qtquick3d_disponivel(), "Qt Quick 3D não está instalado")
    def test_cena_minima_tem_cubo_configurado(self) -> None:
        app = QApplication.instance() or QApplication([])
        diagnostico = testar_cena_minima()
        self.assertTrue(diagnostico.ok)
        self.assertIn("cubo", diagnostico.mensagem)
        app.processEvents()


if __name__ == "__main__":
    unittest.main()

