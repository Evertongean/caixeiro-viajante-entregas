"""Testes da calibração espacial das ruas do modelo GLB."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from models.grafo import criar_cenario_exemplo
from ui.modelos_glb import (
    carregar_mapeamento_3d,
    inspecionar_glb,
    mapear_grafo_cidade_glb,
    salvar_mapeamento_3d,
)


class TestCalibracaoCidadeGLB(unittest.TestCase):
    def setUp(self) -> None:
        raiz = Path(__file__).resolve().parents[1]
        self.grafo = criar_cenario_exemplo()
        cidade = inspecionar_glb(raiz / "assets/models/cidade.glb")
        self.mapeamento = mapear_grafo_cidade_glb(self.grafo, cidade)

    def test_curva_expande_rota_sem_alterar_grafo(self) -> None:
        arestas_antes = len(self.grafo.listar_arestas())
        calibrado = self.mapeamento.com_ponto_intermediario("D", "X", (0.0, 0.0, 0.0))
        pontos = calibrado.expandir_percurso(("D", "X"))
        self.assertEqual(len(pontos), 3)
        self.assertTrue(calibrado.viario_calibrado)
        self.assertEqual(len(self.grafo.listar_arestas()), arestas_antes)

    def test_persistencia_json_preserva_vertices_e_curvas(self) -> None:
        calibrado = self.mapeamento.com_posicao("D", (1.0, 2.0, 3.0)).com_ponto_intermediario(
            "D", "X", (1.5, 2.0, 3.0)
        )
        with tempfile.TemporaryDirectory() as diretorio:
            caminho = salvar_mapeamento_3d(calibrado, Path(diretorio) / "ruas.json")
            carregado = carregar_mapeamento_3d(caminho)
        self.assertEqual(carregado.posicoes, calibrado.posicoes)
        self.assertEqual(carregado.pontos_intermediarios, calibrado.pontos_intermediarios)
        self.assertTrue(carregado.viario_calibrado)


if __name__ == "__main__":
    unittest.main()
