"""Testes da enumeração exaustiva observável e interrompível."""

from __future__ import annotations

from multiprocessing import get_context
from queue import Empty
from time import monotonic
import unittest

from algorithms.caixeiro_viajante import held_karp
from algorithms.forca_bruta_tempo_real import (
    ProgressoForcaBruta,
    forca_bruta_tempo_real,
)
from algorithms.processo_forca_bruta import executar_forca_bruta_processo
from models.cenario_academico import carregar_cenario_academico_18
from models.grafo import criar_cenario_exemplo
from ui.formatacao import formatar_percentual_progresso


class TestForcaBrutaTempoReal(unittest.TestCase):
    def test_enumera_cada_permutacao_e_conta_fatorial_exato(self) -> None:
        fotografias: list[ProgressoForcaBruta] = []
        resultado = forca_bruta_tempo_real(
            criar_cenario_exemplo(),
            progresso=fotografias.append,
            intervalo_progresso_segundos=0,
        )

        self.assertTrue(resultado.concluida)
        self.assertEqual(resultado.total_permutacoes, 6)
        self.assertEqual(resultado.permutacoes_avaliadas, 6)
        self.assertEqual(resultado.melhor_resultado.sequencias_avaliadas, 6)
        self.assertEqual(resultado.melhor_resultado.distancia_total, 15.0)
        self.assertEqual(fotografias[-1].permutacoes_avaliadas, 6)

    def test_resultado_concluido_iguala_held_karp(self) -> None:
        grafo = criar_cenario_exemplo()
        exaustiva = forca_bruta_tempo_real(grafo)
        dinamica = held_karp(grafo)
        self.assertEqual(
            exaustiva.melhor_resultado.distancia_total,
            dinamica.distancia_total,
        )

    def test_interrupcao_preserva_contagem_e_melhor_solucao_real(self) -> None:
        interromper = False

        def progresso(fotografia: ProgressoForcaBruta) -> None:
            nonlocal interromper
            if fotografia.permutacoes_avaliadas >= 3:
                interromper = True

        resultado = forca_bruta_tempo_real(
            criar_cenario_exemplo(),
            interromper=lambda: interromper,
            progresso=progresso,
            intervalo_progresso_segundos=0,
        )

        self.assertFalse(resultado.concluida)
        self.assertEqual(resultado.motivo_interrupcao, "usuario")
        self.assertEqual(resultado.permutacoes_avaliadas, 3)
        self.assertEqual(resultado.melhor_resultado.sequencias_avaliadas, 3)
        self.assertTrue(resultado.melhor_resultado.encontrada)
        self.assertLessEqual(resultado.melhor_resultado.distancia_total, 18.0)

    def test_limite_de_tempo_interrompe_sem_mudar_a_enumeracao(self) -> None:
        projeto = carregar_cenario_academico_18()
        clientes = tuple(str(indice) for indice in range(2, 12))
        resultado = forca_bruta_tempo_real(
            projeto.grafo,
            clientes,
            duracao_maxima_segundos=0.01,
            intervalo_progresso_segundos=0,
        )
        self.assertFalse(resultado.concluida)
        self.assertEqual(resultado.motivo_interrupcao, "tempo_limite")
        self.assertGreater(resultado.permutacoes_avaliadas, 0)
        self.assertLess(
            resultado.permutacoes_avaliadas, resultado.total_permutacoes
        )

    def test_percentual_nao_exagera_avanco_sobre_dezessete_fatorial(self) -> None:
        total = 355_687_428_096_000
        self.assertEqual(
            formatar_percentual_progresso(1, total),
            "menos de 0,000001%",
        )
        self.assertEqual(
            formatar_percentual_progresso(total, total), "100,000000%"
        )

    def test_processo_inicia_17_clientes_e_aceita_interrupcao(self) -> None:
        projeto = carregar_cenario_academico_18()
        clientes = tuple(
            cliente.identificador for cliente in projeto.grafo.listar_clientes()
        )
        contexto = get_context("spawn")
        evento = contexto.Event()
        fila = contexto.Queue(maxsize=16)
        processo = contexto.Process(
            target=executar_forca_bruta_processo,
            args=(projeto.grafo, clientes, None, evento, fila),
        )
        processo.start()
        self.addCleanup(self._limpar_processo, processo, evento, fila)

        resultado = None
        prazo = monotonic() + 15.0
        iteracoes_no_processo_principal = 0
        solicitada = False
        while monotonic() < prazo and resultado is None:
            iteracoes_no_processo_principal += 1
            try:
                tipo, carga = fila.get(timeout=0.2)
            except Empty:
                continue
            if tipo == "progresso" and carga.permutacoes_avaliadas > 0:
                evento.set()
                solicitada = True
            elif tipo == "resultado":
                resultado = carga
            elif tipo == "erro":
                self.fail(carga)

        processo.join(timeout=2.0)
        self.assertTrue(solicitada)
        self.assertIsNotNone(resultado)
        self.assertFalse(resultado.concluida)
        self.assertGreater(resultado.permutacoes_avaliadas, 0)
        self.assertLess(
            resultado.permutacoes_avaliadas, resultado.total_permutacoes
        )
        self.assertIsNotNone(resultado.melhor_resultado)
        self.assertGreater(iteracoes_no_processo_principal, 0)

    @staticmethod
    def _limpar_processo(processo, evento, fila) -> None:
        evento.set()
        processo.join(timeout=1.0)
        if processo.is_alive():
            processo.terminate()
            processo.join(timeout=1.0)
        fila.cancel_join_thread()
        fila.close()


if __name__ == "__main__":
    unittest.main()
