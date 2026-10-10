"""Testes do editor 3D e do projeto versionado."""

from __future__ import annotations

import tempfile
import unittest
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from models.grafo import criar_cenario_exemplo
from models.projeto_3d import carregar_projeto_3d, projeto_3d_para_dados, salvar_projeto_3d
from ui.editor_ruas_3d import EditorRuas3D, ModoEdicaoRua

try:
    from PySide6.QtWidgets import QApplication
    from ui.janela_principal_3d import JanelaPrincipal3D
except ModuleNotFoundError:  # pragma: no cover
    QApplication = None
    JanelaPrincipal3D = None


class TestEditorRuas3D(unittest.TestCase):
    def test_picking_exige_superficie_ou_nome_semantico(self) -> None:
        editor = EditorRuas3D()
        editor.iniciar_rua((0, 0, 0))
        editor.selecionar_fim((2, 0, 0))
        self.assertFalse(editor.validar_rua()[0])
        editor.marcar_superficie(((0, 0, 0), (2, 0, 0)), raio_tolerancia=1.0)
        self.assertTrue(editor.validar_rua()[0])

    def test_curva_peso_e_undo(self) -> None:
        editor = EditorRuas3D(fator_distancia=2)
        editor.marcar_superficie(((0, 0, 0), (1, 0, 0), (2, 0, 0)), raio_tolerancia=1)
        editor.iniciar_rua((0, 0, 0))
        editor.adicionar_curva((1, 0, 0))
        editor.selecionar_fim((2, 0, 0))
        self.assertAlmostEqual(editor.peso_sugerido(), 4)
        editor.desfazer_ultimo_ponto()
        self.assertEqual(len(editor.pontos_pendentes), 2)

    def test_rotas_configuradas_sao_validadas(self) -> None:
        editor = EditorRuas3D()
        editor.registrar_rua("A", "B")
        self.assertEqual(editor.rota_configurada(("A", "B", "C")), ("B–C",))

    def test_projeto_3d_preserva_grafo_e_editor(self) -> None:
        editor = EditorRuas3D()
        editor.marcar_superficie(((0, 0, 0),), raio_tolerancia=2)
        editor.registrar_rua("D", "X")
        dados = projeto_3d_para_dados(
            criar_cenario_exemplo(),
            caminho_cidade="assets/models/cidade.glb",
            caminho_carro="assets/models/carro.glb",
            editor=editor,
        )
        with tempfile.TemporaryDirectory() as pasta:
            caminho = salvar_projeto_3d(dados, Path(pasta) / "cidade.json")
            projeto = carregar_projeto_3d(caminho)
        self.assertEqual(len(projeto["grafo"].listar_vertices()), 5)
        self.assertIn(("D", "X"), projeto["editor"].ruas_configuradas)
        self.assertEqual(projeto["editor"].modo, ModoEdicaoRua.NAVEGACAO)


@unittest.skipUnless(QApplication is not None, "PySide6 não está instalado")
class TestJanelaPrincipal3D(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_interface_exclusivamente_3d_e_calcula_algoritmos(self) -> None:
        janela = JanelaPrincipal3D()
        janela.show()
        self.app.processEvents()
        self.assertEqual(janela.modo_atual, "cidade3d")
        self.assertFalse(hasattr(janela, "botao_cidade"))
        janela.combo_origem.setCurrentIndex(janela.combo_origem.findData("D"))
        janela.combo_destino.setCurrentIndex(janela.combo_destino.findData("B"))
        janela.calcular_rota()
        self.assertEqual(janela._rota_pendente, ("D", "X", "A", "B"))
        resultado = janela.resultado_atual
        janela.limpar_rota()
        self.assertIsNone(janela.resultado_atual)
        self.assertEqual(janela.cidade_3d.rota_destacada, ())
        janela.close()
        janela.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
