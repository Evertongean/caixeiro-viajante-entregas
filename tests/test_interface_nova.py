"""Testes headless da composição e inicialização da nova interface."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtQuickWidgets import QQuickWidget
    from PySide6.QtWidgets import QApplication

    from ui.assets_3d import ConversorBalsam
    from ui.camera_orbital import ModoCamera
    from ui.janela_principal import JanelaPrincipal

    PYSIDE6_DISPONIVEL = True
except ModuleNotFoundError:
    PYSIDE6_DISPONIVEL = False


@unittest.skipUnless(PYSIDE6_DISPONIVEL, "PySide6 não está instalado")
class TestNovaInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.aplicacao = QApplication.instance() or QApplication([])

    def criar_janela(self) -> JanelaPrincipal:
        janela = JanelaPrincipal(auto_inicializar_3d=False)
        janela.show()
        self.aplicacao.processEvents()
        self.addCleanup(self._fechar, janela)
        return janela

    def _fechar(self, janela: JanelaPrincipal) -> None:
        janela.close()
        janela.deleteLater()
        self.aplicacao.processEvents()

    def test_inicializa_janela_unica_com_tres_regioes(self) -> None:
        janela = self.criar_janela()
        self.assertEqual(janela.windowTitle(), "Delivery Route — Simulador de Rotas")
        self.assertEqual(janela.divisor.count(), 2)
        self.assertIsNotNone(janela.cartao_status)
        self.assertIsInstance(janela.visualizacao, QQuickWidget)

    def test_referencias_dos_modelos_sao_as_fornecidas(self) -> None:
        janela = self.criar_janela()
        cidade, carro = janela.visualizacao.referencias_modelos
        self.assertEqual(cidade.name, "cidade.glb")
        self.assertEqual(carro.name, "carro.glb")
        self.assertTrue(cidade.is_file())
        self.assertTrue(carro.is_file())

    def test_qml_usa_picking_3d_e_posicao_real_da_cena(self) -> None:
        qml = (Path(__file__).parents[1] / "ui" / "cena_3d.qml").read_text(
            encoding="utf-8"
        )
        self.assertIn("visualizacao.pick(x, y)", qml)
        self.assertIn("resultado.scenePosition", qml)
        self.assertIn("resultado.objectHit", qml)

    def test_divisao_inicial_aproxima_setenta_e_cinco_por_cento(self) -> None:
        janela = self.criar_janela()
        tamanhos = janela.divisor.sizes()
        proporcao = tamanhos[0] / sum(tamanhos)
        self.assertGreater(proporcao, 0.70)
        self.assertLess(proporcao, 0.80)
        self.assertGreater(janela.visualizacao.width(), 500)
        self.assertGreater(janela.visualizacao.height(), 350)

    def test_controles_futuros_estao_explicitamente_desabilitados(self) -> None:
        janela = self.criar_janela()
        self.assertTrue(all(not botao.isEnabled() for botao in janela.botoes_edicao))
        self.assertFalse(janela.botao_calcular.isEnabled())
        self.assertFalse(janela.botao_iniciar.isEnabled())
        self.assertFalse(janela.botao_pausar.isEnabled())
        self.assertIn("Em breve", janela.botao_iniciar.text())

    def test_seletor_prepara_campos_correspondentes_ao_algoritmo(self) -> None:
        janela = self.criar_janela()
        self.assertEqual(janela.campos_algoritmo.currentIndex(), 0)
        janela.seletor_algoritmo.setCurrentIndex(1)
        self.assertEqual(janela.campos_algoritmo.currentIndex(), 1)
        self.assertEqual(janela.lista_clientes.count(), 3)

    def test_cartoes_comecam_em_estado_neutro(self) -> None:
        janela = self.criar_janela()
        self.assertEqual(janela.cartao_distancia.valor.text(), "—")
        self.assertEqual(
            janela.cartao_percurso.valor.text(), "Nenhuma rota calculada"
        )
        self.assertEqual(janela.cartao_clientes.valor.text(), "0")

    def test_redimensionamento_preserva_painel_e_area_3d(self) -> None:
        janela = self.criar_janela()
        janela.resize(1100, 720)
        self.aplicacao.processEvents()
        tamanhos = janela.divisor.sizes()
        self.assertGreaterEqual(tamanhos[1], 300)
        self.assertGreaterEqual(janela.visualizacao.width(), 560)
        self.assertGreaterEqual(janela.visualizacao.height(), 380)

    def test_projeto_invalido_nao_substitui_o_grafo_atual(self) -> None:
        janela = self.criar_janela()
        grafo_atual = janela.grafo
        with tempfile.TemporaryDirectory() as pasta:
            invalido = Path(pasta) / "invalido.json"
            invalido.write_text("{não é json", encoding="utf-8")
            with patch("ui.janela_principal.QMessageBox.warning"):
                self.assertFalse(janela.abrir_projeto(invalido))
        self.assertIs(janela.grafo, grafo_atual)
        self.assertIs(janela.projeto.grafo, grafo_atual)

    def test_inicializa_qml_modelos_camera_e_cache_reais(self) -> None:
        with tempfile.TemporaryDirectory() as cache:
            janela = JanelaPrincipal(
                conversor=ConversorBalsam(cache),
                auto_inicializar_3d=False,
            )
            janela.show()
            self.addCleanup(self._fechar, janela)
            self.aplicacao.processEvents()
            visualizacao = janela.visualizacao
            visualizacao.inicializar()
            for _ in range(12):
                self.aplicacao.processEvents()

            self.assertTrue(visualizacao.inicializado)
            self.assertTrue(visualizacao.modelos_preparados)
            self.assertEqual(visualizacao.status(), QQuickWidget.Status.Ready)
            self.assertTrue(visualizacao.area_valida)
            self.assertIsNotNone(visualizacao.info_cidade)
            self.assertIsNotNone(visualizacao.info_carro)
            self.assertTrue(visualizacao.modelos_visiveis_na_cena)
            self.assertTrue(all(botao.isEnabled() for botao in janela.botoes_edicao))
            recebidos = []
            visualizacao.ponto_selecionado.connect(lambda *dados: recebidos.append(dados))
            visualizacao.rootObject().pontoSelecionado.emit(
                1.25, 0.5, -2.0, "Object_42", "gray", True
            )
            self.aplicacao.processEvents()
            self.assertEqual(
                recebidos[-1],
                (1.25, 0.5, -2.0, "Object_42", "gray", True),
            )

            distancia = visualizacao.camera.distancia
            visualizacao.orbitar(25, -10)
            visualizacao.zoom(1)
            self.assertLess(visualizacao.camera.distancia, distancia)
            visualizacao.focar_carro()
            self.assertEqual(visualizacao.camera.modo, ModoCamera.LIVRE)
            self.assertAlmostEqual(
                visualizacao.camera.centro[0], visualizacao.posicao_carro[0]
            )
            visualizacao.camera_atras_do_carro()
            self.assertEqual(
                visualizacao.camera.modo, ModoCamera.ATRAS_DO_CARRO
            )
            self.assertEqual(
                visualizacao.rootObject().property("cameraModo"),
                "atras_do_carro",
            )
            visualizacao.camera_livre()
            self.assertEqual(visualizacao.camera.modo, ModoCamera.LIVRE)

            backend = visualizacao.diagnostico_backend()
            if backend.casefold() == "software":
                self.assertFalse(visualizacao.renderizacao_real_disponivel)
            else:
                self.assertTrue(visualizacao.renderizacao_real_disponivel)


if __name__ == "__main__":
    unittest.main()
