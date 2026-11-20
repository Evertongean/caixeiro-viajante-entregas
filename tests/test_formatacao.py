"""Testes da apresentação simplificada de distâncias."""

from __future__ import annotations

import unittest

from ui.formatacao import (
    arredondar_para_exibicao,
    formatar_distancia_km,
    formatar_numero_br,
)


class TestFormatacaoDistancias(unittest.TestCase):
    def test_formata_uma_casa_e_virgula_em_portugues(self) -> None:
        casos = (
            (7.468894270, "7,5"),
            (0.329347, "0,3"),
            (15.546, "15,5"),
            (5.8, "5,8"),
            (10.0, "10,0"),
        )
        for valor, esperado in casos:
            with self.subTest(valor=valor):
                self.assertEqual(formatar_numero_br(valor), esperado)

    def test_unidades_sao_apenas_apresentacao(self) -> None:
        self.assertEqual(formatar_distancia_km(7.468894270), "7,5 km")

    def test_arredondamento_explicito_nao_inventa_minimo(self) -> None:
        self.assertEqual(arredondar_para_exibicao(0.04), 0.0)
        self.assertEqual(arredondar_para_exibicao(0.05), 0.1)


if __name__ == "__main__":
    unittest.main()
