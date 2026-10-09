"""Testes do formato JSON e da reconstrução segura dos grafos."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from models.grafo import TipoVertice, criar_cenario_exemplo
from models.persistencia import (
    ErroPersistencia,
    FORMATO_NOME,
    FORMATO_VERSAO,
    carregar_grafo,
    grafo_de_dados,
    grafo_para_dados,
    salvar_grafo,
)


class TestPersistencia(unittest.TestCase):
    def setUp(self) -> None:
        self.grafo = criar_cenario_exemplo()

    def test_salva_e_carrega_preservando_o_grafo(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "entregas.json"
            salvar_grafo(self.grafo, caminho)
            carregado = carregar_grafo(caminho)

        self.assertEqual(carregado.listar_vertices(), self.grafo.listar_vertices())
        self.assertEqual(carregado.listar_arestas(), self.grafo.listar_arestas())
        self.assertEqual(carregado.obter_deposito().identificador, "D")

    def test_formato_tem_versao_e_aresta_unica(self) -> None:
        dados = grafo_para_dados(self.grafo)
        self.assertEqual(dados["formato"], FORMATO_NOME)
        self.assertEqual(dados["versao"], FORMATO_VERSAO)
        self.assertEqual(dados["deposito"], "D")
        self.assertEqual(len(dados["arestas"]), 7)
        self.assertFalse(
            any(
                aresta["origem"] == outra["destino"]
                and aresta["destino"] == outra["origem"]
                for indice, aresta in enumerate(dados["arestas"])
                for outra in dados["arestas"][indice + 1 :]
            )
        )

    def test_rejeita_json_vazio_e_malformado(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            vazio = Path(pasta) / "vazio.json"
            vazio.write_text("", encoding="utf-8")
            with self.assertRaises(ErroPersistencia):
                carregar_grafo(vazio)

            invalido = Path(pasta) / "invalido.json"
            invalido.write_text("{ nao e json", encoding="utf-8")
            with self.assertRaises(ErroPersistencia):
                carregar_grafo(invalido)

    def test_rejeita_versao_e_raiz_incompativeis(self) -> None:
        dados = grafo_para_dados(self.grafo)
        for alteracao in (
            {"versao": 99},
            {"formato": "outro"},
            {"vertices": {}},
        ):
            invalido = copy.deepcopy(dados)
            invalido.update(alteracao)
            with self.subTest(alteracao=alteracao):
                with self.assertRaises(ErroPersistencia):
                    grafo_de_dados(invalido)

    def test_rejeita_vertices_e_arestas_invalidos(self) -> None:
        base = grafo_para_dados(self.grafo)
        casos = []

        duplicado = copy.deepcopy(base)
        duplicado["vertices"].append(copy.deepcopy(duplicado["vertices"][0]))
        casos.append(duplicado)

        tipo_desconhecido = copy.deepcopy(base)
        tipo_desconhecido["vertices"][0]["tipo"] = "fantasma"
        casos.append(tipo_desconhecido)

        referencia = copy.deepcopy(base)
        referencia["arestas"][0]["destino"] = "inexistente"
        casos.append(referencia)

        laco = copy.deepcopy(base)
        laco["arestas"][0]["destino"] = laco["arestas"][0]["origem"]
        casos.append(laco)

        peso = copy.deepcopy(base)
        peso["arestas"][0]["peso"] = -2
        casos.append(peso)

        aresta_duplicada = copy.deepcopy(base)
        aresta_duplicada["arestas"].append(
            {
                "origem": "X",
                "destino": "D",
                "peso": 2,
            }
        )
        casos.append(aresta_duplicada)

        for invalido in casos:
            with self.assertRaises(ErroPersistencia):
                grafo_de_dados(invalido)

    def test_arquivo_sem_deposito_e_valido(self) -> None:
        dados = {
            "formato": FORMATO_NOME,
            "versao": FORMATO_VERSAO,
            "deposito": None,
            "vertices": [
                {
                    "identificador": "A",
                    "nome": "Cliente",
                    "tipo": TipoVertice.CLIENTE.value,
                    "x": 0,
                    "y": 0,
                }
            ],
            "arestas": [],
        }
        self.assertIsNone(grafo_de_dados(dados).obter_deposito())

    def test_falha_de_escrita_nao_cria_diretorio_implicitamente(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "nao-existe" / "projeto.json"
            with self.assertRaises(OSError):
                salvar_grafo(self.grafo, caminho)


if __name__ == "__main__":
    unittest.main()
