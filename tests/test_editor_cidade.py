"""Testes do controlador que liga a edição visual ao grafo oficial."""

from __future__ import annotations

import math
import unittest

from algorithms.caixeiro_viajante import caixeiro_viajante
from algorithms.dijkstra import dijkstra
from models.grafo import Grafo, TipoVertice
from models.missao import ControladorMissao
from models.projeto_cidade import (
    ClassificacaoSuperficie,
    EstacionamentoVeiculo,
    GeometriaRua,
    ProjetoCidade,
)
from ui.editor_cidade import EditorCidade3D, ModoEditor
from models.rota import calcular_dijkstra


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

    def test_mudar_deposito_invalida_estacionamento_antigo(self) -> None:
        self._criar_rede_minima()
        self.projeto.estacionamento_inicial = EstacionamentoVeiculo(
            deposito="D",
            posicao=(1.0, 0.2, 2.0),
            orientacao_graus=90.0,
            superficie="rua|asfalto",
            validado=True,
        )
        self.editor.reposicionar_vertice("D", (4.0, 0.2, 5.0))
        self.assertIsNone(self.projeto.estacionamento_inicial)

        self.projeto.estacionamento_inicial = EstacionamentoVeiculo(
            deposito="D",
            posicao=(4.0, 0.2, 5.0),
            orientacao_graus=90.0,
            validado=True,
        )
        self.editor.editar_vertice(
            "D", nome="Antigo depósito", tipo=TipoVertice.CRUZAMENTO
        )
        self.assertIsNone(self.projeto.estacionamento_inicial)

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

    def _criar_rua_editavel(self) -> None:
        self._criar_rede_minima()
        self.editor.iniciar_rua("D", "C1")
        self.editor.adicionar_ponto_intermediario((2.0, 0.2, 3.0))
        self.editor.adicionar_ponto_intermediario((3.0, 0.2, 5.0))
        self.editor.confirmar_rua(5.0, 1.0)
        self.editor.iniciar_rua("D", "C1", editar=True)

    def test_edicao_e_transacional_ate_confirmar(self) -> None:
        self._criar_rua_editavel()
        original = list(self.projeto.geometria_rua("D", "C1").pontos_intermediarios)
        self.editor.iniciar_arraste_ponto(0)
        self.editor.atualizar_arraste_ponto((2.5, 0.2, 3.5))
        self.assertEqual(
            self.projeto.geometria_rua("D", "C1").pontos_intermediarios,
            original,
        )
        self.assertTrue(self.editor.finalizar_arraste_ponto(valida=True))
        self.editor.cancelar_operacao()
        self.assertEqual(
            self.projeto.geometria_rua("D", "C1").pontos_intermediarios,
            original,
        )

    def test_arraste_invalido_restaura_posicao_anterior(self) -> None:
        self._criar_rua_editavel()
        anterior = self.editor.operacao_rua.pontos_intermediarios[0]
        self.editor.iniciar_arraste_ponto(0)
        self.editor.atualizar_arraste_ponto((99, 99, 99), valida=False)
        self.assertFalse(self.editor.finalizar_arraste_ponto(valida=False))
        self.assertEqual(self.editor.operacao_rua.pontos_intermediarios[0], anterior)
        self.assertFalse(self.editor.operacao_rua.modificada)

    def test_inserir_remover_desfazer_e_refazer_preservam_ordem(self) -> None:
        self._criar_rua_editavel()
        self.editor.inserir_ponto_intermediario(1, (2.5, 0.2, 4.0))
        self.assertEqual(
            self.editor.operacao_rua.pontos_intermediarios,
            [(2.0, 0.2, 3.0), (2.5, 0.2, 4.0), (3.0, 0.2, 5.0)],
        )
        self.editor.remover_ponto_intermediario(1)
        self.assertTrue(self.editor.desfazer_edicao_rua())
        self.assertEqual(len(self.editor.operacao_rua.pontos_intermediarios), 3)
        self.assertTrue(self.editor.refazer_edicao_rua())
        self.assertEqual(len(self.editor.operacao_rua.pontos_intermediarios), 2)

    def test_snap_em_vertice_segmento_e_desativado(self) -> None:
        self._criar_rua_editavel()
        perto_vertice = self.editor.aplicar_snap((1.01, 0.2, 2.01), tolerancia=0.05)
        self.assertTrue(perto_vertice.encaixado)
        self.assertEqual(perto_vertice.posicao, self.projeto.posicoes["D"])

        self.editor.definir_snap_ativo(False)
        livre = self.editor.aplicar_snap((1.01, 0.2, 2.01), tolerancia=0.05)
        self.assertFalse(livre.encaixado)
        self.assertEqual(livre.posicao, (1.01, 0.2, 2.01))

        self.editor.definir_snap_ativo(True)
        self.editor.criar_vertice("X", "Esquina X", TipoVertice.CRUZAMENTO, (0, 0.2, 0))
        self.editor.criar_vertice("Y", "Esquina Y", TipoVertice.CRUZAMENTO, (0, 0.2, 2))
        self.projeto.grafo.adicionar_aresta("X", "Y", 2)
        chave = self.projeto.chave_aresta("X", "Y")
        self.projeto.ruas[chave] = GeometriaRua("X", "Y", [], True)
        segmento = self.editor.aplicar_snap((0.02, 0.2, 1.0), tolerancia=0.05)
        self.assertTrue(segmento.encaixado)
        self.assertAlmostEqual(segmento.posicao[0], 0.0)
        self.assertIn("rua", segmento.origem)

    def test_controles_diferenciam_extremos_e_intermediarios(self) -> None:
        self._criar_rua_editavel()
        controles = self.editor.controles_rua_qml()
        self.assertEqual(controles[0]["cor"], "#22C55E")
        self.assertFalse(controles[0]["movel"])
        self.assertEqual(controles[-1]["cor"], "#F97316")
        self.assertFalse(controles[-1]["movel"])
        self.assertTrue(all(item["movel"] for item in controles[1:-1]))

    def test_confirmacao_atualiza_comprimento_e_geometria_na_orientacao_inversa(self) -> None:
        self._criar_rua_editavel()
        self.editor.iniciar_arraste_ponto(0)
        self.editor.atualizar_arraste_ponto((2.0, 0.2, 4.0))
        self.editor.finalizar_arraste_ponto(valida=True)
        comprimento = self.editor.comprimento_operacao_rua()
        self.editor.confirmar_rua(5.0, 1.0)
        direta = self.projeto.polilinha_rua("D", "C1")
        inversa = self.projeto.polilinha_rua("C1", "D")
        self.assertEqual(inversa, tuple(reversed(direta)))
        self.assertAlmostEqual(
            comprimento, self.editor.comprimento_geometrico(direta)
        )

    def test_validacao_rejeita_pontos_duplicados(self) -> None:
        self._criar_rua_editavel()
        self.editor.inserir_ponto_intermediario(
            1, self.editor.operacao_rua.pontos_intermediarios[0]
        )
        self.assertTrue(
            any("duplicados" in item for item in self.editor.validar_operacao_rua())
        )

    def test_missao_nova_usa_polilinha_confirmada_sem_cache_antigo(self) -> None:
        self._criar_rua_editavel()
        novo_ponto = (2.4, 0.2, 4.2)
        self.editor.iniciar_arraste_ponto(0)
        self.editor.atualizar_arraste_ponto(novo_ponto)
        self.editor.finalizar_arraste_ponto(valida=True)
        self.editor.confirmar_rua(5.0, 1.0)

        rota = calcular_dijkstra(self.projeto, "D", "C1")
        self.assertIn(novo_ponto, rota.segmentos_espaciais[0].pontos)
        missao = ControladorMissao(rota, velocidade_base=10.0)
        missao.iniciar()
        visitados = [missao.quadro().posicao]
        for _ in range(20):
            visitados.append(missao.avancar(0.05).posicao)
            if not missao.ativo:
                break
        self.assertTrue(
            any(math.dist(ponto, novo_ponto) < 0.15 for ponto in visitados)
        )


if __name__ == "__main__":
    unittest.main()
