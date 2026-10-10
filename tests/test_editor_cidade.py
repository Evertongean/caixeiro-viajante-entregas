"""Testes do controlador que liga a edição visual ao grafo oficial."""

from __future__ import annotations

import math
import unittest

from algorithms.caixeiro_viajante import caixeiro_viajante
from algorithms.dijkstra import dijkstra
from models.grafo import Grafo, TipoVertice
from models.projeto_cidade import (
    ClassificacaoSuperficie,
    GeometriaRua,
    ProjetoCidade,
)
from ui.editor_cidade import EditorCidade3D, ModoEditor


class TestEditorCidade3D(unittest.TestCase):
    def setUp(self) -> None:
        self.projeto = ProjetoCidade(grafo=Grafo())
        self.editor = EditorCidade3D(self.projeto)

    def _criar_rede_minima(self) -> None:
        self.editor.criar_vertice(
            "D", "Depósito", TipoVertice.DEPOSITO, (1.0, 0.2, 2.0)
        )
        self.editor.criar_vertice(
            "C1", "Cliente 1", TipoVertice.CLIENTE, (4.0, 0.2, 6.0)
        )

    def test_converte_posicao_da_cena_para_plano_xz_do_grafo(self) -> None:
        vertice = self.editor.criar_vertice(
            "X1", "Esquina", TipoVertice.CRUZAMENTO, (1.25, 8.0, -3.5)
        )
        self.assertEqual((vertice.x, vertice.y), (1.25, -3.5))
        self.assertEqual(self.projeto.posicoes["X1"], (1.25, 8.0, -3.5))
        with self.assertRaises(ValueError):
            self.editor.criar_vertice(
                "X2", "Inválido", TipoVertice.CRUZAMENTO, (math.inf, 0, 0)
            )

    def test_classificacao_manual_aceita_rua_e_rejeita_bloqueios(self) -> None:
        referencia = self.editor.referencia_superficie("Object_42", "gray")
        self.assertFalse(self.editor.superficie_trafegavel(referencia))
        with self.assertRaisesRegex(ValueError, "não classificada"):
            self.editor.validar_superficie_trafegavel(referencia)

        self.editor.classificar_superficie(
            referencia, ClassificacaoSuperficie.BLOQUEADA
        )
        with self.assertRaisesRegex(ValueError, "bloqueada"):
            self.editor.validar_superficie_trafegavel(referencia)

        self.editor.classificar_superficie(referencia, ClassificacaoSuperficie.RUA)
        self.editor.validar_superficie_trafegavel(referencia)
        self.assertTrue(self.editor.superficie_trafegavel(referencia))

    def test_cria_vertices_e_garante_deposito_unico(self) -> None:
        self._criar_rede_minima()
        self.assertEqual(self.projeto.grafo.obter_deposito().identificador, "D")
        with self.assertRaisesRegex(ValueError, "no máximo um depósito"):
            self.editor.criar_vertice(
                "D2", "Outro depósito", TipoVertice.DEPOSITO, (0, 0, 0)
            )
        self.assertNotIn("D2", self.projeto.posicoes)

    def test_detecta_vertice_proximo_para_evitar_duplicidade(self) -> None:
        self.editor.criar_vertice(
            "X", "Cruzamento", TipoVertice.CRUZAMENTO, (1, 2, 3)
        )
        self.assertEqual(self.editor.vertice_proximo((1.02, 2, 3.01)), "X")
        self.assertIsNone(self.editor.vertice_proximo((2, 2, 3)))

    def test_cria_aresta_com_pontos_intermediarios_e_peso_oficial(self) -> None:
        self._criar_rede_minima()
        self.editor.iniciar_rua()
        self.assertEqual(self.editor.selecionar_extremo_rua("D"), "origem")
        self.assertEqual(self.editor.selecionar_extremo_rua("C1"), "destino")
        self.editor.adicionar_ponto_intermediario((1.0, 0.2, 6.0))
        self.assertAlmostEqual(self.editor.comprimento_operacao_rua(), 7.0)
        self.editor.confirmar_rua(3.75, 0.5)

        self.assertEqual(self.projeto.grafo.obter_distancia("D", "C1"), 3.75)
        geometria = self.projeto.geometria_rua("D", "C1")
        self.assertEqual(geometria.pontos_intermediarios, [(1.0, 0.2, 6.0)])
        self.assertEqual(len(self.editor.segmentos_ruas_qml()), 2)
        self.assertEqual(self.editor.modo, ModoEditor.NAVEGAR)

    def test_desfaz_extremos_e_curvas_sem_alterar_o_grafo(self) -> None:
        self._criar_rede_minima()
        self.editor.iniciar_rua("D", "C1")
        self.editor.adicionar_ponto_intermediario((2, 0.2, 4))
        self.assertEqual(self.editor.desfazer_ponto_rua(), "ponto_intermediario")
        self.assertEqual(self.editor.desfazer_ponto_rua(), "destino")
        self.assertEqual(self.editor.desfazer_ponto_rua(), "origem")
        self.assertEqual(self.editor.desfazer_ponto_rua(), None)
        self.assertFalse(self.projeto.grafo.existe_aresta("D", "C1"))

    def test_edita_peso_e_geometria_da_rua(self) -> None:
        self._criar_rede_minima()
        self.editor.iniciar_rua("D", "C1")
        self.editor.confirmar_rua(5, 1)
        self.editor.iniciar_rua("D", "C1", editar=True)
        self.editor.adicionar_ponto_intermediario((3, 0.2, 4))
        self.editor.confirmar_rua(2.25, 0.25)
        self.assertEqual(self.projeto.grafo.obter_distancia("D", "C1"), 2.25)
        self.assertEqual(
            self.projeto.geometria_rua("D", "C1").pontos_intermediarios,
            [(3.0, 0.2, 4.0)],
        )

    def test_criar_rua_calibra_aresta_preexistente_sem_duplicar(self) -> None:
        self._criar_rede_minima()
        self.projeto.grafo.adicionar_aresta("D", "C1", 9)
        self.editor.iniciar_rua()
        self.editor.selecionar_extremo_rua("D")
        self.editor.selecionar_extremo_rua("C1")
        self.assertEqual(self.editor.operacao_rua.editando_aresta, ("C1", "D"))
        self.editor.adicionar_ponto_intermediario((2, 0.2, 5))
        self.editor.confirmar_rua(6, 0.5)
        self.assertEqual(self.projeto.grafo.obter_distancia("D", "C1"), 6)
        self.assertEqual(len(self.projeto.grafo.listar_arestas()), 1)

    def test_rua_pendente_e_laranja_e_calibrada_e_azul(self) -> None:
        self._criar_rede_minima()
        self.projeto.grafo.adicionar_aresta("D", "C1", 4)
        chave = self.projeto.chave_aresta("D", "C1")
        self.projeto.ruas[chave] = GeometriaRua("D", "C1", [], False)
        self.assertEqual(self.editor.segmentos_ruas_qml()[0]["cor"], "#FB923C")
        self.projeto.ruas[chave].calibrada_manualmente = True
        self.assertEqual(self.editor.segmentos_ruas_qml()[0]["cor"], "#5B7896")

    def test_reposiciona_e_edita_vertice_preservando_conexoes(self) -> None:
        self._criar_rede_minima()
        self.editor.iniciar_rua("D", "C1")
        self.editor.confirmar_rua(5, 1)
        self.editor.reposicionar_vertice("C1", (8, 0.5, 9))
        self.editor.editar_vertice("C1", nome="Mercado", tipo=TipoVertice.CLIENTE)
        cliente = self.projeto.grafo.obter_vertice("C1")
        self.assertEqual((cliente.nome, cliente.x, cliente.y), ("Mercado", 8, 9))
        self.assertEqual(self.projeto.grafo.obter_distancia("D", "C1"), 5)

    def test_exclusao_de_rua_e_vertice_mantem_geometria_consistente(self) -> None:
        self._criar_rede_minima()
        self.editor.iniciar_rua("D", "C1")
        self.editor.confirmar_rua(5, 1)
        self.editor.remover_aresta("D", "C1")
        self.assertEqual(self.projeto.ruas, {})
        self.assertFalse(self.projeto.grafo.existe_aresta("D", "C1"))

        self.editor.iniciar_rua("D", "C1")
        self.editor.confirmar_rua(5, 1)
        self.editor.remover_vertice("C1")
        self.assertEqual(self.projeto.ruas, {})
        self.assertNotIn("C1", self.projeto.posicoes)
        with self.assertRaises(KeyError):
            self.projeto.grafo.obter_vertice("C1")

    def test_dijkstra_e_tsp_operam_no_mesmo_grafo_editado(self) -> None:
        self._criar_rede_minima()
        self.editor.iniciar_rua("D", "C1")
        self.editor.confirmar_rua(4.5, 1)

        menor = dijkstra(self.projeto.grafo, "D", "C1")
        rota = caixeiro_viajante(self.projeto.grafo)
        self.assertEqual(menor.caminho, ["D", "C1"])
        self.assertEqual(menor.distancia_total, 4.5)
        self.assertTrue(rota.encontrada)
        self.assertEqual(rota.ordem_entregas, ["D", "C1", "D"])
        self.assertEqual(rota.distancia_total, 9.0)


if __name__ == "__main__":
    unittest.main()
