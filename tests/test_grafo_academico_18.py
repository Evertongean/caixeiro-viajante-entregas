"""Regressão integral do grafo acadêmico de 18 vértices de Póvoa."""

from __future__ import annotations

from collections import Counter
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from algorithms.caixeiro_viajante import LIMITE_PADRAO_CLIENTES
from models.cenario_academico import (
    CAMINHO_CENARIO_ACADEMICO_18,
    carregar_cenario_academico_18,
)
from models.grafo import TipoVertice
from models.missao import ControladorMissao, EstadoMissao
from models.projeto_cidade import (
    carregar_projeto_cidade,
    projeto_para_dados,
    salvar_projeto_cidade,
)
from models.rota import EstadoEspacial, calcular_dijkstra, calcular_tsp
from scripts.gerar_grafo_academico_18 import (
    ARESTAS_ACADEMICAS_18,
    criar_projeto_academico_18,
    distribuir_vertices_automaticamente,
)
from ui.assets_3d import (
    ESCALA_CARRO_PADRAO,
    ESCALA_CIDADE_PADRAO,
    inspecionar_modelo,
)
from ui.editor_cidade import EditorCidade3D
from ui.reconhecimento_superficies import reconhecer_superficies


RAIZ = Path(__file__).resolve().parents[1]
ARESTAS_ESPERADAS = {
    frozenset((origem, destino)): peso
    for origem, destino, peso in ARESTAS_ACADEMICAS_18
}
VINCULOS_ESPACIAIS_ESPERADOS = (
    "D",
    "X4",
    "X1",
    "X20",
    "X17",
    "F",
    "X11",
    "C",
    "X23",
    "X5",
    "X19",
    "X18",
    "X15",
    "X10",
    "X16",
    "X7",
    "X3",
    "X6",
)


class TestGrafoAcademico18(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.projeto = carregar_cenario_academico_18()
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

    def test_arquivo_e_reproduzivel_por_distribuicao_automatica(self) -> None:
        reproduzido = criar_projeto_academico_18()
        self.assertEqual(
            projeto_para_dados(reproduzido), projeto_para_dados(self.projeto)
        )
        base = carregar_projeto_cidade(
            RAIZ / "delivery-route-cidade-completa-corrigida.json"
        )
        self.assertEqual(
            distribuir_vertices_automaticamente(base),
            VINCULOS_ESPACIAIS_ESPERADOS,
        )

    def test_integridade_exata_dos_18_vertices_e_45_arestas(self) -> None:
        vertices = self.projeto.grafo.listar_vertices()
        self.assertEqual(
            [vertice.identificador for vertice in vertices],
            [str(indice) for indice in range(1, 19)],
        )
        self.assertEqual(
            [
                vertice.identificador
                for vertice in vertices
                if vertice.tipo is TipoVertice.DEPOSITO
            ],
            ["1"],
        )
        self.assertEqual(
            len(
                [
                    vertice
                    for vertice in vertices
                    if vertice.tipo is TipoVertice.CLIENTE
                ]
            ),
            17,
        )
        arestas = self.projeto.grafo.listar_arestas()
        obtidas = {
            frozenset(
                (aresta.origem.identificador, aresta.destino.identificador)
            ): aresta.peso
            for aresta in arestas
        }
        self.assertEqual(len(arestas), 45)
        self.assertEqual(obtidas, ARESTAS_ESPERADAS)
        self.assertEqual(len(self.projeto.ruas), 45)

    def test_posicoes_distintas_distribuidas_e_sobre_asfalto(self) -> None:
        posicoes = list(self.projeto.posicoes.values())
        self.assertEqual(len(posicoes), 18)
        self.assertEqual(len(set(posicoes)), 18)
        menor_distancia = min(
            ((a[0] - b[0]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5
            for indice, a in enumerate(posicoes)
            for b in posicoes[indice + 1 :]
        )
        self.assertGreaterEqual(menor_distancia, 0.39)
        for identificador, posicao in self.projeto.posicoes.items():
            with self.subTest(vertice=identificador):
                resultado = self.mapa.validar_posicao(
                    posicao, self.meia_largura_seguranca
                )
                self.assertTrue(resultado.valido, resultado.motivo)
                self.assertTrue(resultado.conclusivo)

    def test_todas_as_polilinhas_sao_bidirecionais_e_trafegaveis(self) -> None:
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

    def test_trechos_fisicos_compartilhados_nao_criam_arestas(self) -> None:
        usos: Counter[frozenset[tuple[float, float, float]]] = Counter()
        for geometria in self.projeto.ruas.values():
            pontos = self.projeto.polilinha_rua(
                geometria.origem, geometria.destino
            )
            usos.update(frozenset((a, b)) for a, b in zip(pontos, pontos[1:]))
        self.assertGreater(max(usos.values()), 1)
        self.assertEqual(len(self.projeto.grafo.listar_arestas()), 45)

    def test_selecao_de_vertice_destaca_somente_arestas_associadas(self) -> None:
        editor = EditorCidade3D(self.projeto)
        editor.selecao = ("vertice", "1")
        segmentos = editor.segmentos_ruas_qml()
        associados = [
            item
            for item in segmentos
            if any("1" in aresta.split("|") for aresta in item["arestas"])
        ]
        demais = [
            item
            for item in segmentos
            if all("1" not in aresta.split("|") for aresta in item["arestas"])
        ]
        self.assertTrue(associados)
        self.assertTrue(demais)
        self.assertTrue(all(item["cor"] == "#22D3EE" for item in associados))
        self.assertTrue(all(item["cor"] == "#334155" for item in demais))

    def test_renderizacao_agrega_trechos_compartilhados_sem_perder_arestas(self) -> None:
        segmentos = EditorCidade3D(self.projeto).segmentos_ruas_qml()
        self.assertTrue(any(len(item["arestas"]) > 1 for item in segmentos))
        arestas_renderizadas = {
            aresta for item in segmentos for aresta in item["arestas"]
        }
        self.assertEqual(len(arestas_renderizadas), 45)

    def test_dijkstra_usa_pesos_oficiais_com_geometria_completa(self) -> None:
        rota = calcular_dijkstra(self.projeto, "1", "18")
        self.assertEqual(rota.percurso_completo, ("1", "13", "14", "17", "18"))
        self.assertEqual(rota.distancia_total, 93.0)
        self.assertIs(rota.estado_espacial, EstadoEspacial.COMPLETO)
        self.assertEqual(rota.arestas_pendentes, ())

    def test_tsp_de_subconjunto_preserva_ordem_e_percurso_completo(self) -> None:
        selecionados = ("2", "5", "8", "11", "14", "16")
        rota = calcular_tsp(self.projeto, selecionados)
        self.assertEqual(
            rota.ordem_atendimento,
            ("1", "2", "5", "11", "14", "16", "8", "1"),
        )
        self.assertEqual(
            rota.percurso_completo,
            ("1", "2", "3", "4", "5", "6", "11", "15", "14", "16", "13", "8", "1"),
        )
        self.assertEqual(rota.distancia_total, 286.0)
        self.assertEqual(set(rota.clientes_selecionados), set(selecionados))
        self.assertIs(rota.estado_espacial, EstadoEspacial.COMPLETO)
        self.assertEqual(LIMITE_PADRAO_CLIENTES, 8)

    def test_persistencia_preserva_todo_o_cenario(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "academico-18.json"
            salvar_projeto_cidade(self.projeto, caminho)
            recarregado = carregar_projeto_cidade(caminho)
        self.assertEqual(
            projeto_para_dados(recarregado), projeto_para_dados(self.projeto)
        )
        self.assertEqual(recarregado.estacionamento_inicial.deposito, "1")
        self.assertTrue(recarregado.estacionamento_inicial.validado)

    def test_missao_tsp_percorre_ruas_entrega_e_retorna_ao_deposito(self) -> None:
        selecionados = ("2", "5", "8", "11", "14", "16")
        rota = calcular_tsp(self.projeto, selecionados)
        estacionamento = self.projeto.estacionamento_inicial
        controlador = ControladorMissao(
            rota,
            velocidade_base=20.0,
            tempo_parada_entrega=0.0,
            velocidade_rotacao=720.0,
            posicao_inicial=estacionamento.posicao,
            orientacao_inicial_graus=estacionamento.orientacao_graus,
        )
        quadro = controlador.iniciar()
        for _ in range(20_000):
            if quadro.estado is EstadoMissao.CONCLUIDA:
                break
            quadro = controlador.avancar(0.02)
        self.assertEqual(quadro.estado, EstadoMissao.CONCLUIDA)
        self.assertEqual(set(quadro.clientes_atendidos), set(selecionados))
        self.assertEqual(quadro.distancia_percorrida, 286.0)
        self.assertEqual(quadro.distancia_restante, 0.0)
        self.assertEqual(quadro.posicao, estacionamento.posicao)


try:
    from PySide6.QtWidgets import QApplication

    from ui.janela_principal import JanelaPrincipal

    PYSIDE6_DISPONIVEL = True
except ModuleNotFoundError:
    PYSIDE6_DISPONIVEL = False


@unittest.skipUnless(PYSIDE6_DISPONIVEL, "PySide6 não está instalado")
class TestInterfaceGrafoAcademico18(unittest.TestCase):
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

    def test_opcao_carrega_18_vertices_e_seleciona_todos_com_held_karp(self) -> None:
        conteudo_antes = CAMINHO_CENARIO_ACADEMICO_18.read_bytes()
        self.assertEqual(
            self.janela.botao_carregar_grafo_academico_18.text(),
            "Carregar grafo de 18 vértices",
        )
        self.assertTrue(self.janela.carregar_grafo_academico_18(confirmar=False))
        self.assertEqual(len(self.janela.grafo.listar_vertices()), 18)
        self.assertEqual(len(self.janela.grafo.listar_arestas()), 45)
        self.assertEqual(len(self.janela._clientes_selecionados()), 17)
        self.assertEqual(self.janela.lista_clientes.count(), 17)
        self.assertEqual(self.janela.seletor_metodo_tsp.currentData(), "held_karp")
        self.assertEqual(
            self.janela.complexidade_permutacoes.text(),
            "355.687.428.096.000",
        )
        self.assertIsNone(self.janela.caminho_projeto)
        self.assertFalse(self.janela.projeto_modificado)
        self.assertEqual(CAMINHO_CENARIO_ACADEMICO_18.read_bytes(), conteudo_antes)


if __name__ == "__main__":
    unittest.main()
