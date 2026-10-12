#!/usr/bin/env python3
"""Valida e captura a vaga inicial usando os GLBs e um backend 3D real."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from PySide6.QtCore import QElapsedTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from models.rota import AlgoritmoRota  # noqa: E402
from ui.janela_principal import JanelaPrincipal  # noqa: E402


CENARIO = RAIZ / "delivery-route-cidade-completa-corrigida.json"
DESTINO = RAIZ / "evidencias/estacionamento"


def aguardar(app: QApplication, milissegundos: int) -> None:
    relogio = QElapsedTimer()
    relogio.start()
    while relogio.elapsed() < milissegundos:
        app.processEvents()
        QTest.qWait(20)


def salvar(janela: JanelaPrincipal, nome: str, app: QApplication) -> None:
    aguardar(app, 350)
    if not janela.grab().save(str(DESTINO / nome)):
        raise RuntimeError(f"Não foi possível salvar {nome}.")


def capturar() -> dict[str, object]:
    DESTINO.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    janela = JanelaPrincipal(auto_inicializar_3d=True)
    janela.resize(1600, 1000)
    janela.show()
    if not janela.abrir_projeto(CENARIO):
        raise RuntimeError("O cenário corrigido foi rejeitado.")

    relogio = QElapsedTimer()
    relogio.start()
    while relogio.elapsed() < 30_000:
        app.processEvents()
        if janela.visualizacao.modelos_visiveis_na_cena:
            break
        QTest.qWait(50)
    visualizacao = janela.visualizacao
    if not visualizacao.modelos_visiveis_na_cena:
        raise RuntimeError("Os GLBs não ficaram visíveis em 30 segundos.")
    if not visualizacao.renderizacao_real_disponivel:
        raise RuntimeError("O ambiente não disponibilizou um backend 3D real.")
    estacionamento = janela.projeto.estacionamento_inicial
    if estacionamento is None or not estacionamento.validado:
        raise RuntimeError("A vaga inicial não foi validada.")

    visualizacao.definir_rede_ruas_visivel(False)
    visualizacao.atualizar_marcadores(
        [item for item in janela.editor.marcadores_qml() if item["id"] == "D"]
    )
    centro = estacionamento.posicao

    visualizacao.camera.focar(centro, (0.30, 0.08, 0.30))
    visualizacao.camera.visao_aerea()
    visualizacao._aplicar_camera()
    salvar(janela, "01-visao-aerea.png", app)

    visualizacao.camera.focar(
        (centro[0], centro[1] + 0.025, centro[2]), (0.24, 0.08, 0.14)
    )
    visualizacao.camera.yaw = math.pi / 2
    visualizacao.camera.pitch = 0.18
    visualizacao._aplicar_camera()
    salvar(janela, "02-visao-lateral.png", app)

    visualizacao.camera_atras_do_carro()
    salvar(janela, "03-camera-atras.png", app)

    indice_tsp = janela.seletor_algoritmo.findData(AlgoritmoRota.TSP.value)
    janela.seletor_algoritmo.setCurrentIndex(indice_tsp)
    janela.selecionar_todos_clientes.setChecked(True)
    janela.botao_calcular.click()
    janela.botao_iniciar.click()
    janela.animacao_missao.timer.stop()
    quadro_inicial = janela.controlador_missao.quadro()
    quadro_movido = janela.controlador_missao.avancar(0.20)
    janela._atualizar_quadro_missao(quadro_movido, 0.20)
    deslocamento = math.dist(quadro_inicial.posicao, quadro_movido.posicao)
    quadro_reiniciado = janela.controlador_missao.reiniciar(iniciar=False)
    janela._atualizar_quadro_missao(quadro_reiniciado, 0.0)
    visualizacao.camera_atras_do_carro()
    salvar(janela, "04-apos-reinicio.png", app)

    manifesto = {
        "cenario": CENARIO.name,
        "backend": visualizacao.diagnostico_backend(),
        "renderizacao_real": visualizacao.renderizacao_real_disponivel,
        "estacionamento": {
            "deposito": estacionamento.deposito,
            "posicao": list(estacionamento.posicao),
            "orientacao_graus": estacionamento.orientacao_graus,
            "superficie": estacionamento.superficie,
            "validado": estacionamento.validado,
        },
        "inicio_missao": {
            "posicao_inicial": list(quadro_inicial.posicao),
            "posicao_apos_0_2s": list(quadro_movido.posicao),
            "deslocamento_continuo": deslocamento,
        },
        "reinicio": {
            "posicao": list(quadro_reiniciado.posicao),
            "orientacao_graus": quadro_reiniciado.orientacao_graus,
            "retornou_a_vaga": quadro_reiniciado.posicao == estacionamento.posicao,
        },
        "evidencias": [
            "01-visao-aerea.png",
            "02-visao-lateral.png",
            "03-camera-atras.png",
            "04-apos-reinicio.png",
        ],
    }
    (DESTINO / "manifesto.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    janela.close()
    app.processEvents()
    return manifesto


if __name__ == "__main__":
    print(json.dumps(capturar(), ensure_ascii=False, indent=2))
