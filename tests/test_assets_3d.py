"""Testes de inspeção e cache dos modelos 3D existentes."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ui.assets_3d import (
    ConversorBalsam,
    ErroModelo3D,
    caminho_modelo,
    inspecionar_modelo,
)


class TestAssets3D(unittest.TestCase):
    def test_referencias_apontam_para_os_glbs_fornecidos(self) -> None:
        cidade = caminho_modelo("cidade.glb")
        carro = caminho_modelo("carro.glb")
        self.assertTrue(cidade.is_file())
        self.assertTrue(carro.is_file())
        self.assertEqual(cidade.name, "cidade.glb")
        self.assertEqual(carro.name, "carro.glb")

    def test_inspeciona_cidade_com_limites_reais(self) -> None:
        info = inspecionar_modelo(caminho_modelo("cidade.glb"))
        self.assertGreater(info.malhas, 700)
        self.assertGreater(info.materiais, 20)
        self.assertTrue(all(valor > 0 for valor in info.limites.dimensoes))
        self.assertGreater(info.limites.dimensoes[2], 200)

    def test_inspeciona_carro_e_texturas(self) -> None:
        info = inspecionar_modelo(caminho_modelo("carro.glb"))
        self.assertEqual(info.malhas, 17)
        self.assertGreaterEqual(info.texturas, 2)
        self.assertTrue(all(valor > 0 for valor in info.limites.dimensoes))

    def test_rejeita_arquivo_que_nao_seja_glb(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            invalido = Path(pasta) / "invalido.glb"
            invalido.write_bytes(b"nao e glb")
            with self.assertRaises(ErroModelo3D):
                inspecionar_modelo(invalido)

    def test_conversor_reutiliza_cache(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            conversor_falso = raiz / "pyside6-balsam"
            conversor_falso.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                "saida = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])\n"
                "(saida / 'Modelo.qml').write_text('import QtQuick3D\\nNode {}', encoding='utf-8')\n",
                encoding="utf-8",
            )
            conversor_falso.chmod(0o755)
            conversor = ConversorBalsam(
                raiz / "cache", executavel=conversor_falso
            )
            primeira = conversor.converter(caminho_modelo("carro.glb"))
            segunda = conversor.converter(caminho_modelo("carro.glb"))

            self.assertTrue(primeira.qml.is_file())
            self.assertFalse(primeira.veio_do_cache)
            self.assertTrue(segunda.veio_do_cache)
            self.assertEqual(primeira.qml, segunda.qml)


if __name__ == "__main__":
    unittest.main()
