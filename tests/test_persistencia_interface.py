"""Integração dos arquivos JSON com a janela principal."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from models.grafo import TipoVertice
    from ui.janela_principal import JanelaPrincipal

    PYSIDE6_DISPONIVEL = True
except ModuleNotFoundError:
    PYSIDE6_DISPONIVEL = False


@unittest.skipUnless(PYSIDE6_DISPONIVEL, "PySide6 não está instalado")
class TestPersistenciaInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.aplicacao = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.janela = JanelaPrincipal()
        self.janela.definir_modo_interface("edicao")
        self.janela.show()
        self.aplicacao.processEvents()

    def tearDown(self) -> None:
        self.janela._grafo_modificado = False
        self.janela.close()
        self.janela.deleteLater()
        self.aplicacao.processEvents()

    def test_salva_associa_caminho_e_abre_atualizando_interface(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "modificado.json"
            self.janela.adicionar_vertice("Z", "Cliente Z", TipoVertice.CLIENTE, 9, 9)
            self.janela.adicionar_aresta("D", "Z", 1)
            self.assertTrue(self.janela.salvar_projeto(caminho))
            self.assertFalse(self.janela.alteracoes_pendentes)
            self.assertEqual(self.janela.caminho_projeto, caminho)

            self.janela.combo_origem.setCurrentIndex(self.janela.combo_origem.findData("D"))
            self.janela.combo_destino.setCurrentIndex(self.janela.combo_destino.findData("Z"))
            self.janela.definir_modo_interface("visualizacao")
            self.janela.calcular_rota()
            self.assertIsNotNone(self.janela.resultado_atual)

            self.assertTrue(self.janela.abrir_projeto(caminho, confirmar=False))
            self.assertFalse(self.janela.alteracoes_pendentes)
            self.assertEqual(self.janela.caminho_projeto, caminho)
            self.assertIsNone(self.janela.resultado_atual)
            self.assertFalse(self.janela.mapa_cidade.arestas_destacadas)
            self.assertEqual(self.janela.lista_clientes_rota.count(), 4)
            self.assertGreaterEqual(self.janela.combo_destino.findData("Z"), 0)
            self.assertIs(self.janela.mapa_cidade.grafo, self.janela.grafo)
            self.assertIs(self.janela.visualizador_grafo.grafo, self.janela.grafo)

    def test_carregado_permite_dijkstra_e_tsp(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "cenario.json"
            self.assertTrue(self.janela.salvar_projeto(caminho))
            self.assertTrue(self.janela.abrir_projeto(caminho, confirmar=False))

            self.janela.definir_modo_interface("visualizacao")
            self.janela.combo_origem.setCurrentIndex(self.janela.combo_origem.findData("D"))
            self.janela.combo_destino.setCurrentIndex(self.janela.combo_destino.findData("B"))
            self.janela.calcular_rota()
            self.assertEqual(self.janela.resultado_atual.caminho, ["D", "X", "A", "B"])

            self.janela.combo_algoritmo.setCurrentIndex(
                self.janela.combo_algoritmo.findData("tsp")
            )
            self.janela.calcular_rota()
            self.assertTrue(self.janela.resultado_atual.encontrada)

    def test_arquivo_invalido_preserva_grafo_e_estado_pendente(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "invalido.json"
            caminho.write_text("{ quebrado", encoding="utf-8")
            self.janela.adicionar_vertice("Z", "Cliente Z", TipoVertice.CLIENTE, 9, 9)
            vertices_antes = self.janela.grafo.listar_vertices()
            self.assertTrue(self.janela.alteracoes_pendentes)

            self.assertFalse(self.janela.abrir_projeto(caminho, confirmar=False))
            self.assertEqual(self.janela.grafo.listar_vertices(), vertices_antes)
            self.assertTrue(self.janela.alteracoes_pendentes)
            self.assertIn("Não foi possível carregar", self.janela.rotulo_aviso.text())

    def test_falha_de_salvamento_nao_marca_projeto_como_salvo(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "diretorio-inexistente" / "x.json"
            self.janela.adicionar_vertice("Z", "Cliente Z", TipoVertice.CLIENTE, 9, 9)
            self.assertFalse(self.janela.salvar_projeto(caminho))
            self.assertTrue(self.janela.alteracoes_pendentes)
            self.assertIsNone(self.janela.caminho_projeto)

    def test_operacao_pendente_pode_ser_cancelada_ou_descartada(self) -> None:
        self.janela.adicionar_vertice("Z", "Cliente Z", TipoVertice.CLIENTE, 9, 9)
        with patch.object(
            QMessageBox, "exec", return_value=QMessageBox.StandardButton.Cancel
        ):
            self.assertFalse(self.janela.restaurar_cenario_exemplo())
        self.assertTrue(self.janela.alteracoes_pendentes)
        self.assertIsNotNone(self.janela.grafo.obter_vertice("Z"))

        with patch.object(
            QMessageBox, "exec", return_value=QMessageBox.StandardButton.Discard
        ):
            self.assertTrue(self.janela.restaurar_cenario_exemplo())
        self.assertFalse(self.janela.alteracoes_pendentes)
        self.assertEqual(len(self.janela.grafo.listar_vertices()), 5)


if __name__ == "__main__":
    unittest.main()
