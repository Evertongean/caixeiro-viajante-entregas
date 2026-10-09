"""Cenários do editor interativo usando a mesma API dos diálogos Qt."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from models.grafo import TipoVertice
    from ui.janela_principal import JanelaPrincipal

    PYSIDE6_DISPONIVEL = True
except ModuleNotFoundError:
    PYSIDE6_DISPONIVEL = False


@unittest.skipUnless(PYSIDE6_DISPONIVEL, "PySide6 não está instalado")
class TestEditorInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.aplicacao = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.janela = JanelaPrincipal()
        self.janela.definir_modo_interface("edicao")
        self.janela.show()
        self.aplicacao.processEvents()

    def tearDown(self) -> None:
        # O fechamento dos testes não representa uma ação destrutiva do
        # usuário; a janela real continua solicitando salvar/descartar.
        self.janela._grafo_modificado = False
        self.janela.close()
        self.janela.deleteLater()
        self.aplicacao.processEvents()

    def test_adiciona_vertice_e_atualiza_as_duas_views_e_seletores(self) -> None:
        self.janela.adicionar_vertice("Z", "Cliente Z", TipoVertice.CLIENTE, 9, 3)
        self.assertIs(self.janela.mapa_cidade.grafo, self.janela.grafo)
        self.assertIs(self.janela.visualizador_grafo.grafo, self.janela.grafo)
        self.assertIsNotNone(self.janela.grafo.obter_vertice("Z"))
        self.assertGreater(self.janela.lista_locais.count(), 5)
        self.assertGreaterEqual(self.janela.lista_clientes_rota.count(), 4)
        self.assertGreaterEqual(self.janela.combo_origem.findData("Z"), 0)
        self.assertGreaterEqual(self.janela.combo_destino.findData("Z"), 0)

    def test_edita_vertice_preserva_conexoes(self) -> None:
        self.janela.selecionar_vertice("X")
        self.janela.editar_vertice(
            "X", nome="Cruzamento Norte", tipo=TipoVertice.CRUZAMENTO, x=8, y=8
        )
        self.assertEqual(self.janela.grafo.obter_vizinhos("X")["D"], 2)
        self.assertEqual(self.janela.vertice_selecionado, "X")
        self.assertIn("Cruzamento Norte", self.janela.rotulo_detalhes.text())

    def test_remove_vertice_remove_ruas_e_selecao(self) -> None:
        self.janela.selecionar_vertice("X")
        self.janela.remover_vertice("X")
        self.assertIsNone(self.janela.vertice_selecionado)
        self.assertNotIn("X", {v.identificador for v in self.janela.grafo.listar_vertices()})
        self.assertFalse(any("X" in {a.origem.identificador, a.destino.identificador}
                             for a in self.janela.grafo.listar_arestas()))

    def test_operacoes_de_aresta_validam_e_atualizam_peso(self) -> None:
        self.janela.adicionar_aresta("D", "B", 9)
        self.assertEqual(self.janela.grafo.obter_distancia("D", "B"), 9)
        with self.assertRaisesRegex(ValueError, "já existe"):
            self.janela.adicionar_aresta("B", "D", 2)
        self.janela.editar_aresta("D", "B", 4.5)
        self.assertEqual(self.janela.grafo.obter_distancia("B", "D"), 4.5)
        self.janela.remover_aresta("D", "B")
        with self.assertRaises(ValueError):
            self.janela.grafo.obter_distancia("D", "B")

    def test_edicao_invalida_resultado_e_destaques(self) -> None:
        self.janela.definir_modo_interface("visualizacao")
        self.janela.combo_origem.setCurrentIndex(self.janela.combo_origem.findData("D"))
        self.janela.combo_destino.setCurrentIndex(self.janela.combo_destino.findData("B"))
        self.janela.calcular_rota()
        self.assertTrue(self.janela.mapa_cidade.arestas_destacadas)
        self.janela.definir_modo_interface("edicao")
        self.janela.editar_aresta("D", "X", 2.5)
        self.assertIsNone(self.janela.resultado_atual)
        self.assertFalse(self.janela.mapa_cidade.arestas_destacadas)
        self.assertFalse(self.janela.visualizador_grafo.arestas_destacadas)
        self.assertIn("Grafo alterado", self.janela.painel_resultados.estado_vazio.text())

    def test_dijkstra_usa_grafo_modificado(self) -> None:
        self.janela.adicionar_aresta("D", "B", 1)
        self.janela.combo_origem.setCurrentIndex(self.janela.combo_origem.findData("D"))
        self.janela.combo_destino.setCurrentIndex(self.janela.combo_destino.findData("B"))
        self.janela.calcular_rota()
        self.assertEqual(self.janela.resultado_atual.caminho, ["D", "B"])
        self.assertEqual(self.janela.resultado_atual.distancia_total, 1)

    def test_tsp_usa_cliente_e_ruas_adicionados(self) -> None:
        self.janela.adicionar_vertice("Z", "Cliente Z", TipoVertice.CLIENTE, 9, 9)
        self.janela.adicionar_aresta("D", "Z", 1)
        self.janela.adicionar_aresta("Z", "A", 1)
        self.janela.combo_algoritmo.setCurrentIndex(self.janela.combo_algoritmo.findData("tsp"))
        self.janela.calcular_rota()
        resultado = self.janela.resultado_atual
        self.assertTrue(resultado.encontrada)
        self.assertIn("Z", resultado.ordem_entregas)

    def test_remover_deposito_deixa_tsp_validar_ausencia(self) -> None:
        self.janela.remover_vertice("D")
        self.janela.combo_algoritmo.setCurrentIndex(self.janela.combo_algoritmo.findData("tsp"))
        self.janela.calcular_rota()
        self.assertIsNone(self.janela.grafo.obter_deposito())
        self.assertIn("depósito", self.janela.painel_resultados.rotulo_rota.text())

    def test_restauracao_reconstroi_o_cenario_e_descarta_edicoes(self) -> None:
        self.janela.adicionar_vertice("Z", "Cliente Z", TipoVertice.CLIENTE, 9, 9)
        self.assertTrue(self.janela.grafo_modificado)
        self.assertTrue(self.janela.restaurar_cenario_exemplo(confirmar=False))
        self.assertFalse(self.janela.grafo_modificado)
        self.assertEqual(len(self.janela.grafo.listar_vertices()), 5)
        self.assertEqual(len(self.janela.grafo.listar_arestas()), 7)
        self.assertEqual(self.janela.modo_interface, "visualizacao")


if __name__ == "__main__":
    unittest.main()
