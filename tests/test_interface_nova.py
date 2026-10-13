"""Testes headless da composição e inicialização da nova interface."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QPoint, QTimer, Qt
    from PySide6.QtQuickWidgets import QQuickWidget
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

    from models.grafo import TipoVertice
    from ui.assets_3d import ConversorBalsam
    from ui.camera_orbital import ModoCamera
    from ui.janela_principal import JanelaPrincipal
    from models.projeto_cidade import ClassificacaoSuperficie, GeometriaRua
    from ui.dialogos_editor import DialogoSuperficie, DialogoVertice
    from ui.editor_cidade import ModoEditor

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
        self.assertIn("visualizacao.pickAll(x, y)", qml)
        self.assertIn('diagnosticoUltimoPick = "fora_viewport"', qml)
        self.assertIn('diagnosticoUltimoPick = "sem_geometria"', qml)

    def test_qml_seleciona_ruas_com_tolerancia_e_desambigua(self) -> None:
        qml = (Path(__file__).parents[1] / "ui" / "cena_3d.qml").read_text(
            encoding="utf-8"
        )
        self.assertIn("candidatosRua(x, y, segmentosRuas, 10)", qml)
        self.assertIn("indiceCandidato = (indiceCandidato + 1)", qml)
        self.assertIn('"ruas_ambiguas:"', qml)

    def test_qml_controles_arrastaveis_nao_movem_extremos(self) -> None:
        qml = (Path(__file__).parents[1] / "ui" / "cena_3d.qml").read_text(
            encoding="utf-8"
        )
        self.assertIn('objectName: "controle-rua:"', qml)
        self.assertIn("pickable: modelData.movel", qml)
        self.assertIn("executarPickArraste", qml)
        self.assertIn('raiz.modoInteracao === "editar_tracado"', qml)

    def test_divisao_inicial_aproxima_setenta_e_cinco_por_cento(self) -> None:
        janela = self.criar_janela()
        tamanhos = janela.divisor.sizes()
        proporcao = tamanhos[0] / sum(tamanhos)
        self.assertGreater(proporcao, 0.70)
        self.assertLess(proporcao, 0.80)
        self.assertGreater(janela.visualizacao.width(), 500)
        self.assertGreater(janela.visualizacao.height(), 350)

    def test_editor_aguarda_3d_e_missao_aguarda_rota_calibrada(self) -> None:
        janela = self.criar_janela()
        self.assertTrue(all(not botao.isEnabled() for botao in janela.botoes_edicao))
        self.assertTrue(janela.botao_calcular.isEnabled())
        self.assertFalse(janela.botao_iniciar.isEnabled())
        self.assertFalse(janela.botao_pausar.isEnabled())
        self.assertEqual(janela.botao_iniciar.text(), "Iniciar missão")
        self.assertIn("Calcule uma rota", janela.botao_iniciar.toolTip())
        with patch("ui.janela_principal.QMessageBox.warning") as aviso:
            janela._iniciar_missao()
        self.assertIsNone(janela.controlador_missao)
        aviso.assert_called_once()

    def test_missao_lista_ruas_nao_calibradas_e_permanece_bloqueada(self) -> None:
        janela = self.criar_janela()
        janela.visualizacao.modelos_preparados = True
        janela.origem.setCurrentIndex(janela.origem.findData("D"))
        janela.destino.setCurrentIndex(janela.destino.findData("B"))
        janela.botao_calcular.click()
        self.assertFalse(janela.botao_iniciar.isEnabled())
        self.assertIn("D ↔ X", janela.botao_iniciar.toolTip())
        self.assertIn("A ↔ X", janela.botao_iniciar.toolTip())
        self.assertIn("A ↔ B", janela.botao_iniciar.toolTip())
        self.assertIn("Use Criar rua", janela.botao_iniciar.toolTip())

    def test_missao_inicia_bloqueia_edicao_pausa_e_encerra(self) -> None:
        janela = self.criar_janela()
        janela.visualizacao.modelos_preparados = True
        janela.visualizacao.info_cidade = SimpleNamespace(
            limites=SimpleNamespace(minimo=(0, 0, 0), maximo=(1, 1, 1))
        )
        for botao in (
            janela.botao_camera_aerea_missao,
            janela.botao_camera_livre,
            janela.botao_camera_atras,
        ):
            botao.setEnabled(True)
        janela.projeto.posicoes = {
            "D": (0.0, 0.0, 0.0),
            "X": (1.0, 0.0, 0.0),
            "A": (2.0, 0.0, 0.0),
            "B": (3.0, 0.0, 0.0),
            "C": (1.0, 0.0, 2.0),
        }
        for origem, destino in (("D", "X"), ("X", "A"), ("A", "B")):
            janela.projeto.ruas[janela.projeto.chave_aresta(origem, destino)] = (
                GeometriaRua(origem, destino, [], True)
            )
        janela.origem.setCurrentIndex(janela.origem.findData("D"))
        janela.destino.setCurrentIndex(janela.destino.findData("B"))
        janela.botao_calcular.click()
        self.assertTrue(janela.botao_iniciar.isEnabled())
        janela.botao_iniciar.click()
        self.assertTrue(janela._sessao_missao_ativa)
        self.assertFalse(janela.botao_abrir_projeto.isEnabled())
        self.assertTrue(all(not botao.isEnabled() for botao in janela.botoes_edicao))
        janela.botao_pausar.click()
        self.assertTrue(janela.botao_continuar.isEnabled())
        posicao = janela.controlador_missao.quadro().posicao
        janela.botao_camera_aerea_missao.click()
        self.assertEqual(janela.visualizacao.camera.modo, ModoCamera.AEREA)
        janela.botao_camera_livre.click()
        self.assertEqual(janela.visualizacao.camera.modo, ModoCamera.LIVRE)
        janela.botao_camera_atras.click()
        self.assertEqual(janela.visualizacao.camera.modo, ModoCamera.ATRAS_DO_CARRO)
        self.assertEqual(janela.controlador_missao.quadro().posicao, posicao)
        with patch("ui.janela_principal.QMessageBox.warning"):
            self.assertFalse(janela.abrir_projeto("outro.json"))
        janela.botao_continuar.click()
        janela.seletor_velocidade.setCurrentIndex(3)
        self.assertEqual(janela.controlador_missao.multiplicador_velocidade, 4.0)
        janela.botao_encerrar.click()
        self.assertFalse(janela._sessao_missao_ativa)
        self.assertTrue(janela.botao_abrir_projeto.isEnabled())
        self.assertIsNone(janela.animacao_missao)
        self.assertIsNone(janela.controlador_missao)

    def test_qml_camera_de_perseguicao_nao_usa_deslocamento_fixo(self) -> None:
        qml = (Path(__file__).parents[1] / "ui" / "cena_3d.qml").read_text(
            encoding="utf-8"
        )
        self.assertIn("cameraSeguimentoPosicao", qml)
        self.assertIn("cameraSeguimentoAlvo", qml)
        self.assertNotIn("raiz.posicaoCarro.z + 0.42", qml)

    def test_seletor_prepara_campos_correspondentes_ao_algoritmo(self) -> None:
        janela = self.criar_janela()
        self.assertEqual(janela.campos_algoritmo.currentIndex(), 0)
        janela.seletor_algoritmo.setCurrentIndex(1)
        self.assertEqual(janela.campos_algoritmo.currentIndex(), 1)
        self.assertEqual(janela.lista_clientes.count(), 3)
        self.assertEqual(janela.botao_calcular.text(), "Calcular melhor rota")
        self.assertIn("D — Depósito Central", janela.deposito_tsp.text())

    def test_cartoes_comecam_em_estado_neutro(self) -> None:
        janela = self.criar_janela()
        self.assertEqual(janela.cartao_distancia.valor.text(), "—")
        self.assertEqual(
            janela.cartao_percurso.valor.text(), "Nenhuma rota calculada"
        )
        self.assertEqual(janela.cartao_clientes.valor.text(), "0")

    def test_selecao_individual_e_selecionar_todos_clientes(self) -> None:
        janela = self.criar_janela()
        janela.seletor_algoritmo.setCurrentIndex(1)
        janela.lista_clientes.item(0).setCheckState(Qt.CheckState.Unchecked)
        self.assertEqual(len(janela._clientes_selecionados()), 2)
        self.assertIn("2 de 3", janela.quantidade_clientes.text())
        janela.selecionar_todos_clientes.setChecked(False)
        self.assertEqual(janela._clientes_selecionados(), [])
        janela.selecionar_todos_clientes.setChecked(True)
        self.assertEqual(len(janela._clientes_selecionados()), 3)

    def test_calcula_dijkstra_e_atualiza_cartoes(self) -> None:
        janela = self.criar_janela()
        janela.origem.setCurrentIndex(janela.origem.findData("D"))
        janela.destino.setCurrentIndex(janela.destino.findData("B"))
        janela.botao_calcular.click()
        self.assertEqual(
            janela.rota_calculada.percurso_completo,
            ("D", "X", "A", "B"),
        )
        self.assertEqual(janela.cartao_distancia.valor.text(), "6 km")
        self.assertEqual(janela.cartao_percurso.valor.text(), "D → X → A → B")
        self.assertEqual(
            janela.cartao_clientes.valor.text(), "0 / 2"
        )
        self.assertEqual(
            janela.resultado_clientes.text(), "Clientes no percurso: A, B"
        )
        self.assertIn("pendentes", janela.cartao_status.valor.text())

    def test_calcula_tsp_mostrando_ordem_e_percurso_separados(self) -> None:
        janela = self.criar_janela()
        janela.seletor_algoritmo.setCurrentIndex(1)
        janela.botao_calcular.click()
        self.assertEqual(janela.cartao_distancia.valor.text(), "15 km")
        self.assertIn("D → A → B → C → D", janela.resultado_ordem.text())
        self.assertIn(
            "D → X → A → B → C → D", janela.resultado_percurso.text()
        )
        self.assertEqual(
            janela.cartao_clientes.valor.text(), "0 / 3"
        )
        self.assertEqual(
            janela.resultado_clientes.text(), "Clientes selecionados: A, B, C"
        )

    def test_calculo_preserva_rede_e_controle_de_visibilidade(self) -> None:
        janela = self.criar_janela()
        janela._sincronizar_cena()
        self.assertIn("conexões: 7", janela.resumo_editor.text())
        self.assertIn("traçadas: 0", janela.resumo_editor.text())
        self.assertIn("pendentes: 7", janela.resumo_editor.text())
        janela.projeto.posicoes = {
            vertice.identificador: (vertice.x, 0.0, vertice.y)
            for vertice in janela.grafo.listar_vertices()
        }
        for aresta in janela.grafo.listar_arestas():
            origem = aresta.origem.identificador
            destino = aresta.destino.identificador
            chave = janela.projeto.chave_aresta(origem, destino)
            janela.projeto.ruas[chave] = GeometriaRua(origem, destino, [], True)
        janela._sincronizar_cena()
        self.assertIn("confirmadas: 7", janela.resumo_editor.text())
        self.assertIn("pendentes: 0", janela.resumo_editor.text())
        ruas_antes = dict(janela.projeto.ruas)

        janela.seletor_algoritmo.setCurrentIndex(1)
        janela.botao_calcular.click()
        self.assertEqual(janela.projeto.ruas, ruas_antes)
        self.assertTrue(janela.mostrar_rede_ruas.isChecked())
        self.assertTrue(janela.visualizacao._rede_ruas_visivel)

        janela.mostrar_rede_ruas.setChecked(False)
        self.assertFalse(janela.visualizacao._rede_ruas_visivel)

    def test_tsp_confirmado_habilita_missao_e_pendencia_real_bloqueia(self) -> None:
        janela = self.criar_janela()
        janela.visualizacao.modelos_preparados = True
        janela.projeto.posicoes = {
            vertice.identificador: (vertice.x, 0.0, vertice.y)
            for vertice in janela.grafo.listar_vertices()
        }
        for aresta in janela.grafo.listar_arestas():
            origem = aresta.origem.identificador
            destino = aresta.destino.identificador
            chave = janela.projeto.chave_aresta(origem, destino)
            janela.projeto.ruas[chave] = GeometriaRua(origem, destino, [], True)
        janela.seletor_algoritmo.setCurrentIndex(1)
        janela.botao_calcular.click()
        self.assertTrue(janela.rota_calculada.calibracao_completa)
        self.assertTrue(janela.botao_iniciar.isEnabled())

        del janela.projeto.ruas[janela.projeto.chave_aresta("A", "B")]
        janela.botao_calcular.click()
        self.assertFalse(janela.rota_calculada.calibracao_completa)
        self.assertFalse(janela.botao_iniciar.isEnabled())
        self.assertEqual(janela.rota_calculada.arestas_pendentes, (("A", "B"),))
        self.assertEqual(janela.resultado_calibracao.text().count("A ↔ B"), 1)

    def test_tsp_sem_clientes_mostra_erro_claro_sem_criar_rota(self) -> None:
        janela = self.criar_janela()
        janela.seletor_algoritmo.setCurrentIndex(1)
        janela.selecionar_todos_clientes.setChecked(False)
        janela.botao_calcular.click()
        self.assertIsNone(janela.rota_calculada)
        self.assertIn("pelo menos um cliente", janela.cartao_status.valor.text())
        self.assertIn("pelo menos um cliente", janela.resultado_calibracao.text())

    def test_limpa_e_invalida_rota_apos_excluir_rua(self) -> None:
        janela = self.criar_janela()
        janela.botao_calcular.click()
        self.assertIsNotNone(janela.rota_calculada)
        janela.editor.selecao = ("aresta", "A", "B")
        with patch(
            "ui.janela_principal.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            janela._excluir_selecao()
        self.assertIsNone(janela.rota_calculada)
        self.assertIn("recalcular", janela.cartao_status.valor.text())
        self.assertFalse(janela.botao_limpar_rota.isEnabled())

    def test_editar_vertice_invalida_rota_anterior(self) -> None:
        janela = self.criar_janela()
        janela.botao_calcular.click()
        janela.editor.selecao = ("vertice", "A")
        with patch("ui.janela_principal.DialogoVertice") as dialogo:
            dialogo.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialogo.return_value.dados.return_value = (
                "A",
                "Cliente atualizado",
                TipoVertice.CLIENTE,
            )
            janela._editar_selecao()
        self.assertIsNone(janela.rota_calculada)
        self.assertIn("recalcular", janela.cartao_status.valor.text())

    def test_editar_arrastar_cancelar_confirmar_e_reabrir_rua(self) -> None:
        janela = self.criar_janela()
        janela.projeto.posicoes = {
            vertice.identificador: (vertice.x, 0.0, vertice.y)
            for vertice in janela.grafo.listar_vertices()
        }
        inicio = janela.projeto.posicoes["D"]
        fim = janela.projeto.posicoes["X"]
        meio = tuple((a + b) / 2 for a, b in zip(inicio, fim))
        chave = janela.projeto.chave_aresta("D", "X")
        janela.projeto.ruas[chave] = GeometriaRua("D", "X", [meio], True)
        original = list(janela.projeto.ruas[chave].pontos_intermediarios)
        janela.botao_calcular.click()
        self.assertIsNotNone(janela.rota_calculada)

        janela.editor.selecao = ("aresta", *chave)
        janela._editar_selecao()
        self.assertIs(janela.editor.modo, ModoEditor.EDITAR_TRACADO)
        janela.editor.iniciar_arraste_ponto(0)
        alterado = (meio[0] + 0.1, meio[1], meio[2] + 0.1)
        janela.editor.atualizar_arraste_ponto(alterado)
        janela.editor.finalizar_arraste_ponto(valida=True)
        janela._sincronizar_cena()
        self.assertIn("não salvas", janela.detalhes_rua.text())
        janela._cancelar_operacao()
        self.assertEqual(janela.projeto.ruas[chave].pontos_intermediarios, original)

        janela._editar_selecao()
        janela.editor.iniciar_arraste_ponto(0)
        janela.editor.atualizar_arraste_ponto(alterado)
        janela.editor.finalizar_arraste_ponto(valida=True)
        self.assertIsNotNone(janela.rota_calculada)
        with patch("ui.janela_principal.DialogoRua") as dialogo:
            dialogo.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialogo.return_value.dados.return_value = (
                janela.grafo.obter_distancia("D", "X"),
                janela.projeto.fator_km_por_unidade,
            )
            janela._confirmar_operacao()
        self.assertEqual(janela.projeto.ruas[chave].pontos_intermediarios, [alterado])
        self.assertIsNone(janela.rota_calculada)

        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "rua-editada.json"
            self.assertTrue(janela.salvar_projeto(caminho))
            self.assertTrue(janela.abrir_projeto(caminho))
        self.assertEqual(
            janela.projeto.geometria_rua("X", "D").pontos_intermediarios,
            [alterado],
        )

    def test_limpar_rota_remove_resultados_e_destaques(self) -> None:
        janela = self.criar_janela()
        janela.botao_calcular.click()
        janela.botao_limpar_rota.click()
        self.assertIsNone(janela.rota_calculada)
        self.assertEqual(janela.cartao_distancia.valor.text(), "—")
        self.assertEqual(
            janela.cartao_percurso.valor.text(), "Nenhuma rota calculada"
        )
        self.assertEqual(janela.cartao_status.valor.text(), "Aguardando cálculo.")

    def test_interface_informa_destino_inacessivel(self) -> None:
        janela = self.criar_janela()
        for origem, destino in (("B", "C"), ("C", "D"), ("A", "C")):
            janela.grafo.remover_aresta(origem, destino)
        janela.destino.setCurrentIndex(janela.destino.findData("C"))
        janela.botao_calcular.click()
        self.assertIsNone(janela.rota_calculada)
        self.assertEqual(
            janela.cartao_status.valor.text(), "Destino inacessível."
        )

    def test_redimensionamento_preserva_painel_e_area_3d(self) -> None:
        janela = self.criar_janela()
        janela.resize(1100, 720)
        self.aplicacao.processEvents()
        tamanhos = janela.divisor.sizes()
        self.assertGreaterEqual(tamanhos[1], 280)
        self.assertGreaterEqual(janela.visualizacao.width(), 450)
        self.assertGreaterEqual(janela.visualizacao.height(), 230)

    def test_layout_responde_a_todos_os_tamanhos_alvo(self) -> None:
        janela = self.criar_janela()
        tamanhos = ((1920, 1080), (1366, 768), (1280, 720), (960, 640))
        for largura, altura in tamanhos:
            with self.subTest(tamanho=(largura, altura)):
                janela.resize(largura, altura)
                self.aplicacao.processEvents()
                if QApplication.platformName() == "offscreen":
                    esperado = (largura, altura)
                else:
                    area = janela.screen().availableGeometry()
                    esperado = (min(largura, area.width()), min(altura, area.height()))
                self.assertEqual((janela.width(), janela.height()), esperado)
                self.assertGreaterEqual(janela.visualizacao.width(), 450)
                self.assertGreaterEqual(janela.visualizacao.height(), 230)
                self.assertGreaterEqual(janela.divisor.sizes()[1], 280)
                self.assertGreater(
                    janela.rolagem_controles.verticalScrollBar().maximum(), 0
                )
                esperadas = 2 if largura < 1180 else 4
                self.assertEqual(janela._colunas_cartoes, esperadas)

    def test_ferramenta_ativa_fica_visivel_e_exclusiva(self) -> None:
        janela = self.criar_janela()
        janela._modo_navegar()
        self.assertTrue(janela.botao_navegar.isChecked())
        janela._ativar_classificacao()
        self.assertTrue(janela.botao_classificar.isChecked())
        self.assertFalse(janela.botao_navegar.isChecked())
        self.assertIn("Classificar superfície", janela.estado_ferramenta.text())
        self.assertIn("manualmente", janela.instrucao_editor.text())

    def test_fluxo_real_classifica_persiste_e_permite_criar_ponto(self) -> None:
        janela = self.criar_janela()
        referencia = "wh_plane_0|gray"
        janela._ativar_classificacao()
        janela.visualizacao._origem_ultimo_pick = "cidade"

        def escolher(classificacao: ClassificacaoSuperficie) -> list[QDialog]:
            capturados = []

            def responder() -> None:
                dialogo = QApplication.activeModalWidget()
                if isinstance(dialogo, DialogoSuperficie):
                    capturados.append(dialogo)
                    indice = dialogo.classificacao.findData(classificacao.value)
                    dialogo.classificacao.setCurrentIndex(indice)
                    dialogo.accept()

            QTimer.singleShot(0, responder)
            janela._processar_pick(1.0, 0.0, 2.0, "wh_plane_0", "gray", True)
            return capturados

        for classificacao in (
            ClassificacaoSuperficie.RUA,
            ClassificacaoSuperficie.CALCADA,
            ClassificacaoSuperficie.BLOQUEADA,
            ClassificacaoSuperficie.RUA,
        ):
            with self.subTest(classificacao=classificacao):
                capturados = escolher(classificacao)
                self.assertEqual(len(capturados), 1)
                self.assertIs(
                    janela.projeto.superficies[referencia], classificacao
                )
                self.assertEqual(len(janela.projeto.superficies), 1)

        self.assertIn("Superfícies rua: 1", janela.resumo_editor.text())
        self.assertTrue(janela.projeto_modificado)
        self.assertEqual(janela.botao_salvar_projeto.text(), "Salvar •")

        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "classificacao.json"
            self.assertTrue(janela.salvar_projeto(caminho))
            self.assertFalse(janela.projeto_modificado)
            self.assertTrue(janela.abrir_projeto(caminho))
        self.assertIs(
            janela.projeto.superficies[referencia], ClassificacaoSuperficie.RUA
        )
        self.assertIn("Superfícies rua: 1", janela.resumo_editor.text())

        janela._ativar_adicao(None)
        janela.visualizacao._origem_ultimo_pick = "cidade"
        vertices_antes = len(janela.grafo.listar_vertices())

        def cadastrar_ponto() -> None:
            dialogo = QApplication.activeModalWidget()
            if isinstance(dialogo, DialogoVertice):
                dialogo.identificador.setText("P26")
                dialogo.nome.setText("Ponto do asfalto")
                indice = dialogo.tipo.findData(TipoVertice.CRUZAMENTO.value)
                dialogo.tipo.setCurrentIndex(indice)
                dialogo.accept()

        QTimer.singleShot(0, cadastrar_ponto)
        janela._processar_pick(1.0, 0.0, 2.0, "wh_plane_0", "gray", True)
        self.assertEqual(len(janela.grafo.listar_vertices()), vertices_antes + 1)
        self.assertIs(
            janela.grafo.obter_vertice("P26").tipo, TipoVertice.CRUZAMENTO
        )

    def test_cancelar_classificacao_nao_altera_projeto(self) -> None:
        janela = self.criar_janela()
        janela._ativar_classificacao()
        janela.visualizacao._origem_ultimo_pick = "cidade"

        def cancelar() -> None:
            dialogo = QApplication.activeModalWidget()
            if isinstance(dialogo, DialogoSuperficie):
                dialogo.reject()

        QTimer.singleShot(0, cancelar)
        janela._processar_pick(1.0, 0.0, 2.0, "wh_plane_0", "gray", True)
        self.assertEqual(janela.projeto.superficies, {})
        self.assertFalse(janela.projeto_modificado)

    def test_pick_vazio_e_objetos_fora_da_cidade_sao_rejeitados(self) -> None:
        janela = self.criar_janela()
        janela._ativar_classificacao()
        janela._processar_pick(0, 0, 0, "", "", False)
        self.assertIn("Nenhuma geometria", janela.instrucao_editor.text())

        for origem, mensagem in (
            ("carro", "carro não pode"),
            ("editor", "Marcadores e linhas"),
            ("outro", "não pertence"),
        ):
            with self.subTest(origem=origem):
                janela.visualizacao._origem_ultimo_pick = origem
                with patch("ui.janela_principal.DialogoSuperficie") as dialogo:
                    janela._processar_pick(0, 0, 0, "objeto", "material", True)
                dialogo.assert_not_called()
                self.assertIn(mensagem, janela.instrucao_editor.text())

    def test_classificacao_invalida_na_integracao_e_tratada_sem_alteracao(self) -> None:
        janela = self.criar_janela()
        janela._ativar_classificacao()
        with (
            patch("ui.janela_principal.DialogoSuperficie") as dialogo,
            patch("ui.janela_principal.QMessageBox.warning") as aviso,
        ):
            dialogo.return_value.exec.return_value = QDialog.DialogCode.Accepted
            dialogo.return_value.valor.side_effect = ValueError(
                "A classificação selecionada é inválida."
            )
            janela._clicar_superficie((1.0, 0.0, 2.0), "wh_plane_0|gray")
        self.assertEqual(janela.projeto.superficies, {})
        aviso.assert_called_once()
        self.assertIn("Escolha uma opção válida", janela.instrucao_editor.text())

    def test_pick_real_da_malha_da_cidade_quando_backend_disponivel(self) -> None:
        janela = self.criar_janela()
        janela.resize(1366, 768)
        self.aplicacao.processEvents()
        janela.visualizacao.inicializar()
        for _ in range(30):
            self.aplicacao.processEvents()
        if not janela.visualizacao.renderizacao_real_disponivel:
            self.skipTest("O backend headless não oferece picking Qt Quick 3D real.")

        recebidos = []
        janela.visualizacao.ponto_selecionado.connect(
            lambda *dados: recebidos.append(dados)
        )
        janela.visualizacao.solicitar_pick(526, 400)
        for _ in range(10):
            self.aplicacao.processEvents()
        self.assertTrue(recebidos)
        self.assertTrue(recebidos[-1][-1])
        self.assertEqual(janela.visualizacao.origem_ultimo_pick, "cidade")
        self.assertEqual(recebidos[-1][3:5], ("wh_plane_0", "plane"))

    def test_grafico_real_seleciona_e_arrasta_controle_sem_salvar(self) -> None:
        janela = self.criar_janela()
        janela.resize(1366, 768)
        self.aplicacao.processEvents()
        janela.visualizacao.inicializar()
        for _ in range(40):
            self.aplicacao.processEvents()
        if not janela.visualizacao.renderizacao_real_disponivel:
            self.skipTest("O backend atual não oferece Qt Quick 3D/OpenGL real.")
        caminho = Path(__file__).parents[1] / "delivery-route-cidade-completa.json"
        self.assertTrue(janela.abrir_projeto(caminho))
        for _ in range(12):
            self.aplicacao.processEvents()

        escolhido = None
        for chave, geometria in janela.projeto.ruas.items():
            pontos = janela.projeto.polilinha_rua(*chave)
            if len(pontos) < 2:
                continue
            meio = tuple((a + b) / 2 for a, b in zip(pontos[0], pontos[1]))
            px, py, profundidade = janela.visualizacao.projetar_ponto(meio)
            extremo_tela = janela.visualizacao.projetar_ponto(pontos[1])
            if (
                profundidade > 0
                and 20 < px < janela.visualizacao.width() - 20
                and 20 < py < janela.visualizacao.height() - 20
            ):
                escolhido = (
                    chave,
                    meio,
                    QPoint(round(px), round(py)),
                    QPoint(round(extremo_tela[0]), round(extremo_tela[1])),
                )
                break
        self.assertIsNotNone(escolhido)
        chave, meio, tela, extremo_tela = escolhido
        dx = extremo_tela.x() - tela.x()
        dy = extremo_tela.y() - tela.y()
        norma = max((dx * dx + dy * dy) ** 0.5, 1.0)
        clique_tolerante = QPoint(
            round(tela.x() - 6 * dy / norma),
            round(tela.y() + 6 * dx / norma),
        )
        janela.visualizacao.solicitar_pick(
            clique_tolerante.x(), clique_tolerante.y()
        )
        for _ in range(5):
            self.aplicacao.processEvents()
        self.assertEqual(janela.editor.selecao, ("aresta", *chave))

        janela._editar_selecao()
        janela.editor.inserir_ponto_intermediario(0, meio)
        janela._sincronizar_cena()
        for _ in range(5):
            self.aplicacao.processEvents()
        controle = janela.visualizacao.projetar_ponto(
            (meio[0], meio[1] + 0.026, meio[2])
        )
        origem = QPoint(round(controle[0]), round(controle[1]))
        destino = QPoint(
            round(origem.x() + 6 * dx / norma),
            round(origem.y() + 6 * dy / norma),
        )
        QTest.mousePress(janela.visualizacao, Qt.MouseButton.LeftButton, pos=origem)
        self.aplicacao.processEvents()
        self.assertEqual(
            janela.editor.operacao_rua.arrastando,
            0,
            msg=f"Controle não capturado em {origem}; {janela.instrucao_editor.text()}",
        )
        QTest.mouseMove(janela.visualizacao, destino, delay=25)
        self.aplicacao.processEvents()
        previa_movida = janela.editor.operacao_rua.pontos_intermediarios[0]
        self.assertNotEqual(
            previa_movida,
            meio,
            msg=f"Prévia não acompanhou o mouse; {janela.instrucao_editor.text()}",
        )
        QTest.mouseRelease(
            janela.visualizacao, Qt.MouseButton.LeftButton, pos=destino
        )
        for _ in range(8):
            self.aplicacao.processEvents()
        self.assertNotEqual(
            janela.editor.operacao_rua.pontos_intermediarios[0],
            meio,
            msg=f"Arraste foi revertido; {janela.instrucao_editor.text()}",
        )
        self.assertEqual(
            janela.projeto.geometria_rua(*chave).pontos_intermediarios, []
        )
        janela._cancelar_operacao()
        self.assertEqual(
            janela.projeto.geometria_rua(*chave).pontos_intermediarios, []
        )

    def test_sincronizacao_nao_recria_campos_quando_grafo_nao_mudou(self) -> None:
        janela = self.criar_janela()
        janela._sincronizar_cena()
        primeiro_item = janela.lista_clientes.item(0)
        janela._sincronizar_cena()
        self.assertIs(janela.lista_clientes.item(0), primeiro_item)

    def test_qml_evitaria_etiquetas_duplicadas_na_rota(self) -> None:
        qml = (Path(__file__).parents[1] / "ui" / "cena_3d.qml").read_text(
            encoding="utf-8"
        )
        self.assertIn("function marcadorEstaNaRota", qml)
        self.assertIn("!raiz.marcadorEstaNaRota(modelData.id)", qml)

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

    def test_carregar_projeto_valido_invalida_rota_anterior(self) -> None:
        janela = self.criar_janela()
        janela.botao_calcular.click()
        self.assertIsNotNone(janela.rota_calculada)
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "projeto.json"
            self.assertTrue(janela.salvar_projeto(caminho))
            self.assertTrue(janela.abrir_projeto(caminho))
        self.assertIsNone(janela.rota_calculada)
        self.assertIn("Calcule uma nova rota", janela.cartao_status.valor.text())

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

            for origem, destino in (("D", "X"), ("X", "A"), ("A", "B")):
                inicio = janela.projeto.posicoes[origem]
                fim = janela.projeto.posicoes[destino]
                meio = tuple((a + b) / 2 for a, b in zip(inicio, fim))
                chave = janela.projeto.chave_aresta(origem, destino)
                janela.projeto.ruas[chave] = GeometriaRua(
                    origem, destino, [meio], True
                )
            janela._sincronizar_cena()
            janela.origem.setCurrentIndex(janela.origem.findData("D"))
            janela.destino.setCurrentIndex(janela.destino.findData("B"))
            janela.botao_calcular.click()
            self.assertEqual(
                len(visualizacao.rootObject().property("segmentosRota")), 6
            )
            self.assertGreaterEqual(
                len(visualizacao.rootObject().property("marcadoresRota")), 2
            )
            janela._enquadrar_rota()
            yaw = visualizacao.camera.yaw
            visualizacao.orbitar(10, 0)
            self.assertNotEqual(visualizacao.camera.yaw, yaw)

            backend = visualizacao.diagnostico_backend()
            if backend.casefold() == "software":
                self.assertFalse(visualizacao.renderizacao_real_disponivel)
            else:
                self.assertTrue(visualizacao.renderizacao_real_disponivel)


if __name__ == "__main__":
    unittest.main()
