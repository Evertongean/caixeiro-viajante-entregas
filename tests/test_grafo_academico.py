"""Regressão integral do grafo acadêmico opcional de cinco vértices."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from algorithms.caixeiro_viajante import caixeiro_viajante
from models.cenario_academico import (
    CAMINHO_CENARIO_ACADEMICO,
    carregar_cenario_academico,
)
from models.grafo import TipoVertice
from models.missao import ControladorMissao, EstadoMissao
from models.projeto_cidade import (
    carregar_projeto_cidade,
    projeto_para_dados,
    salvar_projeto_cidade,
)
from models.rota import calcular_dijkstra, calcular_tsp
from scripts.gerar_grafo_academico import (
    ARESTAS_ACADEMICAS,
    criar_projeto_academico,
)
from ui.assets_3d import (
    ESCALA_CARRO_PADRAO,
    ESCALA_CIDADE_PADRAO,
    inspecionar_modelo,
)
from ui.reconhecimento_superficies import reconhecer_superficies


RAIZ = Path(__file__).resolve().parents[1]
ARESTAS_ESPERADAS = {
    frozenset((origem, destino)): peso
    for origem, destino, peso in ARESTAS_ACADEMICAS
}


class TestGrafoAcademico(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.projeto = carregar_cenario_academico()
        info_carro = inspecionar_modelo(RAIZ / cls.projeto.modelo_carro)
        cls.meia_largura_seguranca = (
            info_carro.limites.dimensoes[0] * ESCALA_CARRO_PADRAO * 0.5 + 0.006
        )
        cls._cache = tempfile.TemporaryDirectory()
        cls.mapa = reconhecer_superficies(
            RAIZ / cls.projeto.modelo_cidade,
            escala=ESCALA_CIDADE_PADRAO,
            diretorio_cache=cls._cache.name,
        ).mapa

    @classmethod
    def tearDownClass(cls) -> None:
        cls._cache.cleanup()

    def test_arquivo_e_reproduzivel_a_partir_da_malha_aferida(self) -> None:
        reproduzido = criar_projeto_academico()
        self.assertEqual(
            projeto_para_dados(reproduzido), projeto_para_dados(self.projeto)
        )

    def test_integridade_exata_do_grafo(self) -> None:
        vertices = self.projeto.grafo.listar_vertices()
        depositos = [item for item in vertices if item.tipo is TipoVertice.DEPOSITO]
        clientes = [item for item in vertices if item.tipo is TipoVertice.CLIENTE]
        self.assertEqual([item.identificador for item in vertices], list("12345"))
        self.assertEqual([item.identificador for item in depositos], ["1"])
        self.assertEqual([item.identificador for item in clientes], list("2345"))

        arestas = self.projeto.grafo.listar_arestas()
        obtidas = {
            frozenset(
                (aresta.origem.identificador, aresta.destino.identificador)
            ): aresta.peso
            for aresta in arestas
        }
        self.assertEqual(len(arestas), 8)
        self.assertEqual(obtidas, ARESTAS_ESPERADAS)
        self.assertEqual(len(self.projeto.ruas), 8)

    def test_dijkstra_de_1_a_3_custa_6_km(self) -> None:
        rota = calcular_dijkstra(self.projeto, "1", "3")
        self.assertEqual(rota.percurso_completo, ("1", "2", "3"))
        self.assertEqual(rota.distancia_total, 6.0)
        self.assertTrue(rota.calibracao_completa)

    def test_tsp_real_encontra_rota_otima_de_15_km(self) -> None:
        resultado = caixeiro_viajante(self.projeto.grafo, ("2", "3", "4", "5"))
        rota = calcular_tsp(self.projeto, ("2", "3", "4", "5"))
        self.assertTrue(resultado.encontrada)
        self.assertEqual(resultado.sequencias_avaliadas, 24)
        self.assertEqual(resultado.distancia_total, 15.0)
        self.assertEqual(rota.distancia_total, 15.0)
        self.assertEqual(rota.ordem_atendimento, ("1", "2", "3", "5", "4", "1"))
        self.assertEqual(rota.ordem_atendimento[0], "1")
        self.assertEqual(rota.ordem_atendimento[-1], "1")
        self.assertEqual(set(rota.ordem_atendimento[1:-1]), set("2345"))
        self.assertTrue(rota.calibracao_completa)

    def test_vertices_e_polilinhas_passam_no_mapa_automatico_com_margem(self) -> None:
        for identificador, posicao in self.projeto.posicoes.items():
            with self.subTest(vertice=identificador):
                resultado = self.mapa.validar_posicao(
                    posicao, self.meia_largura_seguranca
                )
                self.assertTrue(resultado.valido, resultado.motivo)
                self.assertTrue(resultado.conclusivo)

        for aresta in self.projeto.grafo.listar_arestas():
            origem = aresta.origem.identificador
            destino = aresta.destino.identificador
            with self.subTest(aresta=f"{origem}-{destino}"):
                direta = self.projeto.polilinha_rua(origem, destino)
                inversa = self.projeto.polilinha_rua(destino, origem)
                self.assertGreaterEqual(len(direta), 2)
                self.assertEqual(direta, tuple(reversed(inversa)))
                resultado = self.mapa.validar_polilinha(
                    direta, self.meia_largura_seguranca
                )
                self.assertTrue(resultado.valido, resultado.motivo)
                self.assertTrue(resultado.conclusivo)

    def test_persistencia_preserva_pesos_polilinhas_e_estacionamento(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "academico.json"
            salvar_projeto_cidade(self.projeto, caminho)
            recarregado = carregar_projeto_cidade(caminho)
        self.assertEqual(
            projeto_para_dados(recarregado), projeto_para_dados(self.projeto)
        )
        self.assertEqual(recarregado.estacionamento_inicial.deposito, "1")
        self.assertTrue(recarregado.estacionamento_inicial.validado)
        self.assertEqual(recarregado.grafo.obter_distancia("1", "5"), 6.0)
        self.assertEqual(
            recarregado.polilinha_rua("4", "5"),
            self.projeto.polilinha_rua("4", "5"),
        )

    def test_missao_percorre_geometrias_contabiliza_15_km_e_retorna(self) -> None:
        rota = calcular_tsp(self.projeto, ("2", "3", "4", "5"))
        estacionamento = self.projeto.estacionamento_inicial
        controlador = ControladorMissao(
            rota,
            velocidade_base=10.0,
            tempo_parada_entrega=0.0,
            velocidade_rotacao=720.0,
            posicao_inicial=estacionamento.posicao,
            orientacao_inicial_graus=estacionamento.orientacao_graus,
        )
        quadro = controlador.iniciar()
        for _ in range(10_000):
            if quadro.estado is EstadoMissao.CONCLUIDA:
                break
            quadro = controlador.avancar(0.02)
        self.assertEqual(quadro.estado, EstadoMissao.CONCLUIDA)
        self.assertEqual(set(quadro.clientes_atendidos), set("2345"))
        self.assertEqual(quadro.distancia_percorrida, 15.0)
        self.assertEqual(quadro.distancia_restante, 0.0)
        self.assertEqual(quadro.posicao, estacionamento.posicao)


try:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from ui.janela_principal import JanelaPrincipal

    PYSIDE6_DISPONIVEL = True
except ModuleNotFoundError:
    PYSIDE6_DISPONIVEL = False


@unittest.skipUnless(PYSIDE6_DISPONIVEL, "PySide6 não está instalado")
class TestInterfaceGrafoAcademico(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.aplicacao = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.janela = JanelaPrincipal(auto_inicializar_3d=False)
        self.addCleanup(self._fechar)

    def _fechar(self) -> None:
        self.janela.close()
        self.janela.deleteLater()
        self.aplicacao.processEvents()

    def test_opcao_carrega_exemplo_sem_alterar_o_padrao_nem_o_asset(self) -> None:
        self.assertEqual(
            [vertice.identificador for vertice in self.janela.grafo.listar_vertices()],
            ["D"],
        )
        self.assertEqual(
            self.janela.botao_carregar_grafo_academico.text(),
            "Carregar grafo acadêmico",
        )
        conteudo_antes = CAMINHO_CENARIO_ACADEMICO.read_bytes()
        self.assertTrue(self.janela.carregar_grafo_academico(confirmar=False))
        self.assertEqual(
            [vertice.identificador for vertice in self.janela.grafo.listar_vertices()],
            list("12345"),
        )
        self.assertEqual(len(self.janela.grafo.listar_arestas()), 8)
        self.assertIsNone(self.janela.caminho_projeto)
        self.assertFalse(self.janela.projeto_modificado)
        self.assertEqual(CAMINHO_CENARIO_ACADEMICO.read_bytes(), conteudo_antes)

    def test_cancelamento_preserva_projeto_com_alteracoes_nao_salvas(self) -> None:
        grafo_anterior = self.janela.grafo
        self.janela._definir_projeto_modificado(True)
        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.StandardButton.No,
        ):
            self.assertFalse(self.janela.carregar_grafo_academico())
        self.assertIs(self.janela.grafo, grafo_anterior)
        self.assertTrue(self.janela.projeto_modificado)


if __name__ == "__main__":
    unittest.main()
