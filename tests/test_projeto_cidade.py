"""Testes do formato espacial compatível com os projetos de grafo antigos."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from models.grafo import Grafo, TipoVertice
from models.persistencia import salvar_grafo
from models.projeto_cidade import (
    ClassificacaoSuperficie,
    FORMATO_PROJETO_CIDADE,
    ProjetoCidade,
    carregar_projeto_cidade,
    projeto_de_dados,
    projeto_para_dados,
    salvar_projeto_cidade,
)
from ui.editor_cidade import EditorCidade3D


class TestProjetoCidade(unittest.TestCase):
    def criar_projeto(self) -> ProjetoCidade:
        projeto = ProjetoCidade(grafo=Grafo(), fator_km_por_unidade=0.125)
        editor = EditorCidade3D(projeto)
        editor.criar_vertice("D", "Base", TipoVertice.DEPOSITO, (1, 0.1, 2))
        editor.criar_vertice("C", "Loja", TipoVertice.CLIENTE, (5, 0.1, 8))
        editor.iniciar_rua("D", "C")
        editor.adicionar_ponto_intermediario((3, 0.1, 4))
        editor.confirmar_rua(2.75, 0.125)
        projeto.superficies["Object_9|plane"] = ClassificacaoSuperficie.RUA
        return projeto

    def test_round_trip_preserva_grafo_e_metadados_espaciais(self) -> None:
        projeto = self.criar_projeto()
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "cidade.json"
            salvar_projeto_cidade(projeto, caminho)
            carregado = carregar_projeto_cidade(caminho)

        self.assertEqual(carregado.grafo.obter_distancia("D", "C"), 2.75)
        self.assertEqual(carregado.posicoes, projeto.posicoes)
        self.assertEqual(
            carregado.geometria_rua("D", "C").pontos_intermediarios,
            [(3.0, 0.1, 4.0)],
        )
        self.assertEqual(
            carregado.superficies["Object_9|plane"], ClassificacaoSuperficie.RUA
        )
        self.assertEqual(carregado.fator_km_por_unidade, 0.125)

    def test_json_referencia_modelos_sem_incorporar_binarios(self) -> None:
        dados = projeto_para_dados(self.criar_projeto())
        self.assertEqual(dados["formato"], FORMATO_PROJETO_CIDADE)
        self.assertEqual(dados["modelos"]["cidade"], "assets/models/cidade.glb")
        serializado = json.dumps(dados)
        self.assertNotIn("data:application", serializado)
        self.assertNotIn("buffers", dados)

    def test_carrega_projeto_antigo_sem_dados_espaciais(self) -> None:
        projeto = self.criar_projeto()
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "legado.json"
            salvar_grafo(projeto.grafo, caminho)
            carregado = carregar_projeto_cidade(caminho)
        self.assertEqual(carregado.grafo.obter_distancia("D", "C"), 2.75)
        self.assertEqual(carregado.posicoes, {})
        self.assertEqual(carregado.ruas, {})
        self.assertEqual(carregado.superficies, {})

    def test_rejeita_rua_visual_sem_aresta_oficial(self) -> None:
        dados = projeto_para_dados(self.criar_projeto())
        dados["grafo"]["arestas"] = []
        with self.assertRaisesRegex(ValueError, "não corresponde"):
            projeto_de_dados(dados)

    def test_rejeita_metadados_espaciais_invalidos(self) -> None:
        dados = projeto_para_dados(self.criar_projeto())
        dados["editor_3d"]["posicoes"]["D"] = [1, 2]
        with self.assertRaisesRegex(ValueError, "três coordenadas"):
            projeto_de_dados(dados)


if __name__ == "__main__":
    unittest.main()
