from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from models.trafegabilidade import (
    AmostraTrafegabilidade,
    MapaTrafegabilidade,
    TipoRegiao,
)
from models.estacionamento import DimensoesVeiculo, resolver_estacionamento
from models.projeto_cidade import carregar_projeto_cidade
from ui.assets_3d import ESCALA_CARRO_PADRAO, inspecionar_modelo
from ui.reconhecimento_superficies import (
    chave_cache_reconhecimento,
    reconhecer_superficies,
)


RAIZ = Path(__file__).resolve().parents[1]


class TestMapaTrafegabilidade(unittest.TestCase):
    def criar_mapa(self) -> MapaTrafegabilidade:
        rua = AmostraTrafegabilidade(TipoRegiao.RUA, 0.0, "asfalto", 1.0)
        bloqueio = AmostraTrafegabilidade(TipoRegiao.EDIFICIO, 0.2, "casa", 1.0)
        celulas = [rua for _ in range(7 * 5)]
        celulas[2 * 7 + 3] = bloqueio
        return MapaTrafegabilidade(0.0, 0.0, 1.0, 7, 5, celulas)

    def test_consulta_e_segmento_rejeitam_obstaculo(self) -> None:
        mapa = self.criar_mapa()
        self.assertEqual(mapa.amostrar(0.5, 0.5).tipo, TipoRegiao.RUA)
        self.assertEqual(mapa.amostrar(3.5, 2.5).tipo, TipoRegiao.EDIFICIO)
        resultado = mapa.validar_segmento((0.5, 0.0, 2.5), (6.5, 0.0, 2.5))
        self.assertFalse(resultado.valido)
        self.assertTrue(resultado.conclusivo)

    def test_largura_do_veiculo_considera_celulas_vizinhas(self) -> None:
        mapa = self.criar_mapa()
        centro = (3.5, 0.0, 1.5)
        self.assertTrue(mapa.validar_posicao(centro).valido)
        self.assertFalse(mapa.validar_posicao(centro, meia_largura=1.0).valido)

    def test_busca_contorna_obstaculo_e_simplifica(self) -> None:
        mapa = self.criar_mapa()
        caminho = mapa.sugerir_caminho((0.5, 0.0, 2.5), (6.5, 0.0, 2.5))
        self.assertIsNotNone(caminho)
        assert caminho is not None
        self.assertGreater(len(caminho), 2)
        self.assertTrue(mapa.validar_polilinha(caminho).valido)

    def test_serializacao_compacta_preserva_consultas(self) -> None:
        mapa = self.criar_mapa()
        restaurado = MapaTrafegabilidade.de_dados(mapa.para_dados())
        for x, z in ((0.5, 0.5), (3.5, 2.5), (6.5, 4.5)):
            self.assertEqual(restaurado.amostrar(x, z), mapa.amostrar(x, z))


class TestReconhecimentoCidadeReal(unittest.TestCase):
    def test_reconhece_regioes_reais_e_reutiliza_cache_por_conteudo(self) -> None:
        mensagens: list[str] = []
        with tempfile.TemporaryDirectory() as pasta:
            cidade = RAIZ / "assets" / "models" / "cidade.glb"
            primeiro = reconhecer_superficies(
                cidade,
                diretorio_cache=pasta,
                progresso=mensagens.append,
            )
            segundo = reconhecer_superficies(
                cidade,
                diretorio_cache=pasta,
            )
            copia_alterada = Path(pasta) / "cidade-alterada.glb"
            shutil.copyfile(cidade, copia_alterada)
            with copia_alterada.open("ab") as arquivo:
                arquivo.write(b"alteracao")
            self.assertNotEqual(
                chave_cache_reconhecimento(cidade, 0.01, 0.01),
                chave_cache_reconhecimento(copia_alterada, 0.01, 0.01),
            )
            self.assertNotEqual(
                chave_cache_reconhecimento(cidade, 0.01, 0.01),
                chave_cache_reconhecimento(cidade, 0.01, 0.02),
            )
        self.assertFalse(primeiro.veio_do_cache)
        self.assertTrue(segundo.veio_do_cache)
        self.assertEqual(primeiro.chave_cache, segundo.chave_cache)
        self.assertGreater(primeiro.estatisticas[TipoRegiao.RUA], 10_000)
        self.assertGreater(primeiro.estatisticas[TipoRegiao.CALCADA], 1_000)
        self.assertGreater(primeiro.estatisticas[TipoRegiao.EDIFICIO], 1_000)
        self.assertGreater(primeiro.estatisticas[TipoRegiao.VERDE], 1_000)
        self.assertGreater(primeiro.estatisticas[TipoRegiao.DESCONHECIDA], 0)
        self.assertTrue(any("Analisando" in mensagem for mensagem in mensagens))
        referencias_rua = {
            celula.referencia
            for _, _, celula in primeiro.mapa.iterar_celulas()
            if celula is not None and celula.tipo == TipoRegiao.RUA
        }
        self.assertIn("wh_plane_0|plane", referencias_rua)

        amostras_por_tipo = {}
        for coluna, linha, celula in primeiro.mapa.iterar_celulas():
            if celula is not None and celula.tipo not in amostras_por_tipo:
                x, z = primeiro.mapa.centro_celula(coluna, linha)
                amostras_por_tipo[celula.tipo] = (x, celula.altura, z)
        self.assertTrue(
            primeiro.mapa.validar_posicao(amostras_por_tipo[TipoRegiao.RUA]).valido
        )
        for tipo in (
            TipoRegiao.CALCADA,
            TipoRegiao.EDIFICIO,
            TipoRegiao.VERDE,
            TipoRegiao.DESCONHECIDA,
        ):
            self.assertFalse(
                primeiro.mapa.validar_posicao(amostras_por_tipo[tipo]).valido
            )

        projeto = carregar_projeto_cidade(
            RAIZ / "delivery-route-cidade-completa.json"
        )
        projeto.superficies.clear()
        self.assertEqual(projeto.superficies, {})
        dimensoes_modelo = inspecionar_modelo(
            RAIZ / "assets" / "models" / "carro.glb"
        ).limites.dimensoes
        dimensoes = DimensoesVeiculo(
            *(valor * ESCALA_CARRO_PADRAO for valor in dimensoes_modelo)
        )
        margem_lateral = dimensoes.largura * 0.5 + 0.006
        for chave in projeto.ruas:
            with self.subTest(rua=chave):
                self.assertTrue(
                    primeiro.mapa.validar_polilinha(
                        projeto.polilinha_rua(*chave), margem_lateral
                    ).valido
                )
        estacionamento = resolver_estacionamento(projeto, primeiro.mapa, dimensoes)
        self.assertTrue(estacionamento.validado)
        self.assertEqual(estacionamento.superficie, "wh_plane_0|plane")


if __name__ == "__main__":
    unittest.main()
