"""Regressão da rede viária reconstruída diretamente sobre o cidade.glb."""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from models.missao import ControladorMissao, EstadoMissao
from models.projeto_cidade import carregar_projeto_cidade, projeto_para_dados
from models.rota import AlgoritmoRota, calcular_dijkstra, calcular_tsp
from scripts.gerar_cidade_completa import ANOTACOES_PADRAO, gerar_projeto
from scripts.validar_cidade_completa import CLIENTES, validar
from ui.janela_principal import JanelaPrincipal


RAIZ = Path(__file__).parents[1]
CENARIO = RAIZ / "delivery-route-cidade-completa.json"


class TestCidadeCompleta(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.projeto = carregar_projeto_cidade(CENARIO)
        cls.relatorio = validar(CENARIO, ANOTACOES_PADRAO)
        cls.aplicacao = QApplication.instance() or QApplication([])

    def test_gerador_reproduz_exatamente_o_json(self) -> None:
        reproduzido, cobertura = gerar_projeto(ANOTACOES_PADRAO)
        self.assertEqual(projeto_para_dados(reproduzido), projeto_para_dados(self.projeto))
        self.assertEqual(cobertura["trechos_reais_identificados"], 33)
        self.assertEqual(cobertura["trechos_reais_mapeados"], 33)
        self.assertEqual(cobertura["regioes_sem_cobertura"], [])

    def test_quantidades_e_calibracao_com_evidencia_geometrica(self) -> None:
        self.assertEqual(self.relatorio["depositos"], 1)
        self.assertEqual(self.relatorio["clientes"], 5)
        self.assertEqual(self.relatorio["cruzamentos"], 24)
        self.assertEqual(self.relatorio["arestas_apos_subdivisoes"], 39)
        self.assertEqual(self.relatorio["ruas_calibradas"], 39)
        self.assertEqual(self.relatorio["ruas_pendentes"], 0)
        self.assertEqual(self.relatorio["triangulos_asfalto"], 264)
        self.assertGreater(self.relatorio["amostras_laterais_no_asfalto"], 10_000)

    def test_clientes_representam_cinco_imoveis_e_regioes_distintas(self) -> None:
        anotacoes = json.loads(ANOTACOES_PADRAO.read_text(encoding="utf-8"))
        clientes = [item for item in anotacoes["pontos_servico"] if item["tipo"] == "cliente"]
        self.assertEqual(len(clientes), 5)
        self.assertEqual(len({item["imovel_referencia"] for item in clientes}), 5)
        self.assertEqual(
            {item["regiao"] for item in clientes},
            {"norte", "sul", "oeste", "leste", "central"},
        )

    def test_grafo_inteiro_e_conectado_sem_arestas_duplicadas(self) -> None:
        grafo = self.projeto.grafo
        inicio = grafo.obter_deposito().identificador
        visitados: set[str] = set()
        fila = [inicio]
        while fila:
            atual = fila.pop()
            if atual in visitados:
                continue
            visitados.add(atual)
            fila.extend(set(grafo.obter_vizinhos(atual)) - visitados)
        self.assertEqual(visitados, {v.identificador for v in grafo.listar_vertices()})
        chaves = [
            frozenset((a.origem.identificador, a.destino.identificador))
            for a in grafo.listar_arestas()
        ]
        self.assertEqual(len(chaves), len(set(chaves)))

    def test_dijkstra_alcanca_cada_cliente_por_ruas_confirmadas(self) -> None:
        esperados = {
            "A": ("D", "X13", "X8", "X22", "X21", "X2", "A"),
            "B": ("D", "X14", "X19", "B"),
            "C": ("D", "X13", "X12", "C"),
            "E": ("D", "X14", "X15", "X10", "X11", "E"),
            "F": ("D", "X13", "X8", "F"),
        }
        for cliente, percurso in esperados.items():
            with self.subTest(cliente=cliente):
                rota = calcular_dijkstra(self.projeto, "D", cliente)
                self.assertEqual(rota.percurso_completo, percurso)
                self.assertTrue(rota.calibracao_completa)
                self.assertEqual(rota.arestas_pendentes, ())

    def test_tsp_exato_usa_cruzamentos_e_retorna_ao_deposito(self) -> None:
        rota = calcular_tsp(self.projeto, CLIENTES)
        self.assertEqual(
            rota.ordem_atendimento,
            ("D", "B", "E", "F", "A", "C", "D"),
        )
        self.assertAlmostEqual(rota.distancia_total, 9.236)
        self.assertEqual(len(rota.segmentos_espaciais), 24)
        self.assertTrue(rota.calibracao_completa)

    def test_ruas_nao_direcionadas_invertem_a_mesma_geometria(self) -> None:
        for aresta in self.projeto.grafo.listar_arestas():
            origem = aresta.origem.identificador
            destino = aresta.destino.identificador
            with self.subTest(rua=f"{origem}-{destino}"):
                direta = self.projeto.polilinha_rua(origem, destino)
                inversa = self.projeto.polilinha_rua(destino, origem)
                self.assertEqual(direta, tuple(reversed(inversa)))

    def test_missao_completa_entrega_cinco_e_retorna(self) -> None:
        rota = calcular_tsp(self.projeto, CLIENTES)
        controlador = ControladorMissao(
            rota,
            velocidade_base=10.0,
            tempo_parada_entrega=0.0,
            velocidade_rotacao=720.0,
        )
        quadro = controlador.iniciar()
        for _ in range(10_000):
            if quadro.estado is EstadoMissao.CONCLUIDA:
                break
            quadro = controlador.avancar(0.02)
        self.assertEqual(quadro.estado, EstadoMissao.CONCLUIDA)
        self.assertEqual(set(quadro.clientes_atendidos), set(CLIENTES))
        self.assertEqual(quadro.posicao, self.projeto.posicoes["D"])

    def test_interface_carrega_e_calcula_tsp_sem_reconstruir_a_tela(self) -> None:
        janela = JanelaPrincipal(auto_inicializar_3d=False)
        self.addCleanup(janela.close)
        janela.show()
        self.aplicacao.processEvents()
        self.assertTrue(janela.abrir_projeto(CENARIO))
        self.assertEqual(janela.lista_clientes.count(), 5)
        indice = janela.seletor_algoritmo.findData(AlgoritmoRota.TSP.value)
        janela.seletor_algoritmo.setCurrentIndex(indice)
        janela.selecionar_todos_clientes.setChecked(True)
        janela.botao_calcular.click()
        self.assertEqual(janela.rota_calculada.ordem_atendimento[0], "D")
        self.assertEqual(janela.rota_calculada.ordem_atendimento[-1], "D")
        self.assertEqual(janela.cartao_clientes.valor.text(), "0 / 5")


if __name__ == "__main__":
    unittest.main()
