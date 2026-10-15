"""Regressões do cenário mínimo usado exclusivamente pela GUI."""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from models.cenario_inicial import (
    CAMINHO_CONFIGURACAO_INICIAL,
    carregar_configuracao_inicial,
    criar_projeto_inicial,
)
from models.estacionamento import DimensoesVeiculo, validar_estacionamento
from models.grafo import TipoVertice
from models.persistencia import ErroPersistencia
from ui.assets_3d import (
    ESCALA_CARRO_PADRAO,
    ESCALA_CIDADE_PADRAO,
    caminho_modelo,
    inspecionar_modelo,
)
from ui.reconhecimento_superficies import reconhecer_superficies


class TestCenarioInicial(unittest.TestCase):
    def test_configuracao_versionada_cria_apenas_deposito(self) -> None:
        config = carregar_configuracao_inicial()
        projeto = criar_projeto_inicial(config)
        vertices = projeto.grafo.listar_vertices()
        self.assertTrue(config.modelo_corresponde())
        self.assertEqual(len(vertices), 1)
        self.assertEqual(vertices[0].identificador, "D")
        self.assertEqual(vertices[0].nome, "Depósito Central")
        self.assertIs(vertices[0].tipo, TipoVertice.DEPOSITO)
        self.assertEqual(projeto.grafo.listar_clientes(), [])
        self.assertEqual(projeto.grafo.listar_arestas(), [])
        self.assertEqual(projeto.ruas, {})
        self.assertEqual(projeto.superficies, {})
        self.assertEqual(projeto.posicoes, {"D": config.posicao_deposito})
        self.assertIsNotNone(projeto.estacionamento_inicial)
        self.assertNotEqual(
            projeto.estacionamento_inicial.posicao,
            projeto.posicoes["D"],
        )
        self.assertAlmostEqual(
            math.dist(
                projeto.estacionamento_inicial.posicao,
                projeto.posicoes["D"],
            ),
            0.08,
        )
        self.assertEqual(projeto.estacionamento_inicial.orientacao_graus, -90.0)
        self.assertEqual(
            projeto.estacionamento_inicial.superficie,
            "wh_plane_0|plane",
        )

    def test_configuracao_rejeita_formato_desconhecido(self) -> None:
        dados = json.loads(CAMINHO_CONFIGURACAO_INICIAL.read_text(encoding="utf-8"))
        dados["formato"] = "formato-invalido"
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "invalido.json"
            caminho.write_text(json.dumps(dados), encoding="utf-8")
            with self.assertRaisesRegex(ErroPersistencia, "Formato"):
                carregar_configuracao_inicial(caminho)

    def test_deposito_e_carro_estao_sobre_rua_real_do_glb(self) -> None:
        config = carregar_configuracao_inicial()
        projeto = criar_projeto_inicial(config)
        with tempfile.TemporaryDirectory() as cache:
            mapa = reconhecer_superficies(
                caminho_modelo("cidade.glb"),
                escala=ESCALA_CIDADE_PADRAO,
                diretorio_cache=cache,
            ).mapa
        deposito = mapa.validar_posicao(config.posicao_deposito)
        self.assertTrue(deposito.valido, deposito.motivo)

        info_carro = inspecionar_modelo(caminho_modelo("carro.glb"))
        dimensoes = DimensoesVeiculo(
            largura=info_carro.limites.dimensoes[0] * ESCALA_CARRO_PADRAO,
            altura=info_carro.limites.dimensoes[1] * ESCALA_CARRO_PADRAO,
            comprimento=info_carro.limites.dimensoes[2] * ESCALA_CARRO_PADRAO,
        )
        validacao = validar_estacionamento(
            projeto.estacionamento_inicial,
            mapa,
            dimensoes,
        )
        self.assertTrue(validacao.valido, validacao.motivo)
        self.assertEqual(validacao.superficie, config.superficie_estacionamento)


if __name__ == "__main__":
    unittest.main()
