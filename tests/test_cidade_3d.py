"""Testes da conversão espacial e do veículo do protótipo Cidade 3D."""

from __future__ import annotations

import math
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from models.grafo import Grafo, criar_cenario_exemplo
    from ui.cidade_3d import Cidade3DWidget, construir_mapa_espacial
    from ui.janela_principal import JanelaPrincipal

    PYSIDE6_DISPONIVEL = True
except ModuleNotFoundError:
    PYSIDE6_DISPONIVEL = False


@unittest.skipUnless(PYSIDE6_DISPONIVEL, "PySide6 não está instalado")
class TestMapeamentoEspacial3D(unittest.TestCase):
    def test_vertices_e_arestas_preservam_o_grafo(self) -> None:
        grafo = criar_cenario_exemplo()
        mapa = construir_mapa_espacial(grafo)

        self.assertEqual(set(mapa.posicoes), {v.identificador for v in grafo.listar_vertices()})
        self.assertEqual(len(mapa.arestas), len(grafo.listar_arestas()))
        pesos = {frozenset((a.origem, a.destino)): a.peso for a in mapa.arestas}
        for aresta in grafo.listar_arestas():
            self.assertEqual(
                pesos[frozenset((aresta.origem.identificador, aresta.destino.identificador))],
                aresta.peso,
            )

    def test_coordenadas_explicitas_sao_deterministicas(self) -> None:
        grafo = criar_cenario_exemplo()
        primeiro = construir_mapa_espacial(grafo)
        segundo = construir_mapa_espacial(grafo)
        self.assertEqual(primeiro, segundo)
        self.assertEqual((primeiro.posicoes["A"].x, primeiro.posicoes["A"].y), (3.0, 0.0))


@unittest.skipUnless(PYSIDE6_DISPONIVEL, "PySide6 não está instalado")
class TestVeiculoCidade3D(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.aplicacao = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.widget = Cidade3DWidget(criar_cenario_exemplo())
        self.widget.resize(900, 600)
        self.widget.show()
        self.aplicacao.processEvents()

    def tearDown(self) -> None:
        self.widget.close()
        self.widget.deleteLater()
        self.aplicacao.processEvents()

    def test_rota_usa_somente_conexoes_reais(self) -> None:
        self.widget.definir_rota(["D", "X", "A", "B"])
        self.assertEqual(self.widget.rota_destacada, ("D", "X", "A", "B"))
        with self.assertRaises(ValueError):
            self.widget.definir_rota(["D", "B"])
        self.assertEqual(self.widget.rota_destacada, ())

    def test_interpolacao_e_orientacao_do_veiculo(self) -> None:
        self.widget.definir_rota(["D", "X", "A", "B"])
        self.widget.definir_velocidade(1.0)
        self.assertTrue(self.widget.iniciar_percurso())
        self.widget.avancar_simulacao(1.0)

        self.assertAlmostEqual(self.widget.progresso, 1 / 6)
        self.assertAlmostEqual(self.widget.posicao_veiculo.x, 1.0)
        self.assertAlmostEqual(self.widget.posicao_veiculo.y, 0.5)
        self.assertAlmostEqual(self.widget.orientacao_veiculo, math.atan2(1, 2))

    def test_pausa_continua_e_reinicia_sem_bloquear(self) -> None:
        self.widget.definir_rota(["D", "X", "A"])
        self.widget.iniciar_percurso()
        self.widget.avancar_simulacao(0.5)
        progresso = self.widget.progresso
        self.widget.pausar_percurso()
        self.widget.avancar_simulacao(2.0)
        self.assertAlmostEqual(self.widget.progresso, progresso)
        self.assertTrue(self.widget.continuar_percurso())
        self.widget.avancar_simulacao(0.5)
        self.assertGreater(self.widget.progresso, progresso)
        self.assertTrue(self.widget.reiniciar_percurso())
        self.assertEqual(self.widget.progresso, 0.0)

    def test_rota_vazia_e_grafo_novo_limpa_estado(self) -> None:
        self.widget.definir_rota(["D", "X"])
        self.widget.definir_rota([])
        self.assertEqual(self.widget.rota_destacada, ())
        self.widget.carregar_grafo(Grafo())
        self.assertEqual(self.widget.mapa_espacial.posicoes, {})
        self.assertIsNone(self.widget.posicao_veiculo)

    def test_missao_rejeita_rota_vazia_e_usa_camera_em_terceira_pessoa(self) -> None:
        self.assertFalse(self.widget.entrar_missao([]))
        self.assertFalse(self.widget.em_missao)
        self.assertTrue(self.widget.entrar_missao(["D", "X", "A", "B"]))
        self.assertTrue(self.widget.em_missao)
        self.assertTrue(self.widget.camera_em_terceira_pessoa)
        self.assertEqual(self.widget.destino_atual, "X")
        self.assertEqual(self.widget.clientes_atendidos, ())

    def test_missao_registra_entregas_e_conclui(self) -> None:
        self.widget.entrar_missao(["D", "X", "A", "B", "C", "D"])
        self.widget.definir_velocidade(10.0)
        self.assertTrue(self.widget.iniciar_percurso())
        self.widget.avancar_simulacao(2.0)

        self.assertEqual(self.widget.progresso, 1.0)
        self.assertEqual(self.widget.clientes_atendidos, ("A", "B", "C"))
        self.assertIn("Missão concluída", self.widget.resumo_missao)
        self.assertAlmostEqual(self.widget.distancia_restante, 0.0)

    def test_missao_pode_alternar_camera_reiniciar_e_sair(self) -> None:
        self.widget.entrar_missao(["D", "X", "A"])
        self.assertEqual(self.widget.alternar_camera(), "aerea")
        self.assertEqual(self.widget.alternar_camera(), "terceira_pessoa")
        self.widget.iniciar_percurso()
        self.widget.avancar_simulacao(0.5)
        self.assertTrue(self.widget.reiniciar_missao())
        self.assertEqual(self.widget.progresso, 0.0)
        self.widget.sair_missao()
        self.assertFalse(self.widget.em_missao)
        self.assertEqual(self.widget.modo_camera, "aerea")

    def test_camera_livre_recebe_gestos_e_volta_apos_missao(self) -> None:
        distancia = self.widget.camera_orbital.distancia
        yaw = self.widget.camera_orbital.yaw
        centro = self.widget.camera_orbital.centro
        self.widget._zoom_camera_glb(1.0)
        self.widget._orbitar_camera_glb(20.0, 10.0)
        self.widget._deslocar_camera_glb(10.0, -5.0)
        self.assertLess(self.widget.camera_orbital.distancia, distancia)
        self.assertNotEqual(self.widget.camera_orbital.yaw, yaw)
        self.assertNotEqual(self.widget.camera_orbital.centro, centro)
        self.assertTrue(self.widget.camera_livre_ativa)

        self.assertTrue(self.widget.entrar_missao(["D", "X", "A"]))
        self.assertFalse(self.widget.camera_livre_ativa)
        self.widget.sair_missao()
        self.assertTrue(self.widget.camera_livre_ativa)

    def test_missao_pausa_e_continua_o_percurso(self) -> None:
        self.widget.entrar_missao(["D", "X", "A", "B"])
        self.widget.iniciar_percurso()
        self.widget.avancar_simulacao(0.4)
        progresso = self.widget.progresso
        self.widget.pausar_percurso()
        self.widget.avancar_simulacao(2.0)
        self.assertAlmostEqual(self.widget.progresso, progresso)
        self.assertTrue(self.widget.continuar_percurso())
        self.widget.avancar_simulacao(0.4)
        self.assertGreater(self.widget.progresso, progresso)

    def test_encerramento_para_o_timer_da_missao(self) -> None:
        self.widget.entrar_missao(["D", "X", "A"])
        self.widget.iniciar_percurso()
        self.assertTrue(self.widget.timer_ativo)
        self.widget.close()
        self.assertFalse(self.widget.timer_ativo)


@unittest.skipUnless(PYSIDE6_DISPONIVEL, "PySide6 não está instalado")
class TestIntegracaoJanelaCidade3D(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.aplicacao = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.janela = JanelaPrincipal()
        self.janela.show()
        self.aplicacao.processEvents()

    def tearDown(self) -> None:
        self.janela.close()
        self.janela.deleteLater()
        self.aplicacao.processEvents()

    def test_modo_3d_preserva_resultado_e_rota_das_outras_views(self) -> None:
        self.janela.combo_origem.setCurrentIndex(self.janela.combo_origem.findData("D"))
        self.janela.combo_destino.setCurrentIndex(self.janela.combo_destino.findData("B"))
        self.janela.calcular_rota()
        resultado = self.janela.resultado_atual
        self.assertEqual(self.janela.cidade_3d.rota_destacada, ("D", "X", "A", "B"))

        self.janela.definir_modo("cidade3d")
        self.assertIs(self.janela.pilha_visualizacoes.currentWidget(), self.janela.cidade_3d)
        self.assertIs(self.janela.resultado_atual, resultado)
        self.janela.definir_modo("grafo")
        self.assertEqual(self.janela.visualizador_grafo.rota_destacada, ("D", "X", "A", "B"))

        self.janela.limpar_rota()
        self.assertEqual(self.janela.cidade_3d.rota_destacada, ())

    def test_botao_inicia_e_fecha_missao_sem_recalcular(self) -> None:
        self.janela.combo_origem.setCurrentIndex(self.janela.combo_origem.findData("D"))
        self.janela.combo_destino.setCurrentIndex(self.janela.combo_destino.findData("B"))
        self.assertFalse(self.janela.botao_iniciar_missao_3d.isEnabled())
        self.janela.calcular_rota()
        resultado = self.janela.resultado_atual
        self.assertTrue(self.janela.botao_iniciar_missao_3d.isEnabled())
        self.janela._iniciar_missao_3d()
        self.assertTrue(self.janela.cidade_3d.em_missao)
        self.assertIs(self.janela.resultado_atual, resultado)
        self.janela._voltar_da_missao_3d()
        self.assertFalse(self.janela.cidade_3d.em_missao)
        self.assertIs(self.janela.resultado_atual, resultado)


if __name__ == "__main__":
    unittest.main()
