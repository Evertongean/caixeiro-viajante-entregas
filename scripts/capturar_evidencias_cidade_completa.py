#!/usr/bin/env python3
"""Captura as cinco evidências visuais da cidade completa com OpenGL real."""

from __future__ import annotations

import json
import sys
from pathlib import Path


RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from PySide6.QtCore import QElapsedTimer  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from models.missao import EstadoMissao  # noqa: E402
from models.rota import AlgoritmoRota  # noqa: E402
from ui.janela_principal import JanelaPrincipal  # noqa: E402


CENARIO = RAIZ_PROJETO / "delivery-route-cidade-completa.json"
DESTINO = RAIZ_PROJETO / "evidencias/cidade-completa"


def _aguardar(aplicacao: QApplication, milissegundos: int) -> None:
    cronometro = QElapsedTimer()
    cronometro.start()
    while cronometro.elapsed() < milissegundos:
        aplicacao.processEvents()
        QTest.qWait(20)


def _salvar(widget, caminho: Path, aplicacao: QApplication) -> None:
    _aguardar(aplicacao, 250)
    if not widget.grab().save(str(caminho)):
        raise RuntimeError(f"Não foi possível salvar {caminho}.")


def capturar() -> dict[str, object]:
    DESTINO.mkdir(parents=True, exist_ok=True)
    aplicacao = QApplication.instance() or QApplication([])
    janela = JanelaPrincipal(auto_inicializar_3d=True)
    janela.resize(1600, 1000)
    janela.show()
    aplicacao.processEvents()
    if not janela.abrir_projeto(CENARIO):
        raise RuntimeError("A interface rejeitou o cenário da cidade completa.")

    cronometro = QElapsedTimer()
    cronometro.start()
    while cronometro.elapsed() < 30_000:
        aplicacao.processEvents()
        if janela.visualizacao.modelos_visiveis_na_cena:
            break
        QTest.qWait(50)
    if not janela.visualizacao.modelos_visiveis_na_cena:
        raise RuntimeError("Os modelos 3D não ficaram visíveis dentro de 30 segundos.")
    if not janela.visualizacao.renderizacao_real_disponivel:
        raise RuntimeError("O backend atual não oferece renderização 3D real.")

    evidencias: list[dict[str, str]] = []
    todos_marcadores = janela.editor.marcadores_qml()

    janela.visualizacao.camera_livre()
    janela.visualizacao.enquadrar_cidade()
    janela.visualizacao.definir_rede_ruas_visivel(True)
    janela.visualizacao.atualizar_marcadores(todos_marcadores)
    caminho = DESTINO / "01-cidade-completa.png"
    _salvar(janela, caminho, aplicacao)
    evidencias.append({"imagem": caminho.name, "descricao": "Cidade, cruzamentos e malha completa."})

    servicos = [item for item in todos_marcadores if item["tipo"] != "cruzamento"]
    janela.visualizacao.atualizar_marcadores(servicos)
    janela.visualizacao.definir_rede_ruas_visivel(False)
    caminho = DESTINO / "02-clientes-e-deposito.png"
    _salvar(janela, caminho, aplicacao)
    evidencias.append({"imagem": caminho.name, "descricao": "Cinco clientes e depósito, sem rótulos de cruzamentos."})

    janela.visualizacao.atualizar_marcadores(todos_marcadores)
    janela.visualizacao.definir_rede_ruas_visivel(True)
    janela.visualizacao.visao_aerea()
    caminho = DESTINO / "03-rede-de-ruas.png"
    _salvar(janela, caminho, aplicacao)
    evidencias.append({"imagem": caminho.name, "descricao": "Vista aérea ortogonal da cobertura viária."})

    indice_tsp = janela.seletor_algoritmo.findData(AlgoritmoRota.TSP.value)
    janela.seletor_algoritmo.setCurrentIndex(indice_tsp)
    janela.selecionar_todos_clientes.setChecked(True)
    janela.botao_calcular.click()
    aplicacao.processEvents()
    if janela.rota_calculada is None or not janela.rota_calculada.calibracao_completa:
        raise RuntimeError("A interface não produziu a rota TSP calibrada.")
    janela.visualizacao.visao_aerea()
    caminho = DESTINO / "04-rota-tsp.png"
    _salvar(janela, caminho, aplicacao)
    evidencias.append({"imagem": caminho.name, "descricao": "Rota TSP exata destacada e cinco entregas."})

    if not janela.botao_iniciar.isEnabled():
        raise RuntimeError("A missão permaneceu bloqueada apesar da validação espacial.")
    janela.botao_iniciar.click()
    aplicacao.processEvents()
    if janela.controlador_missao is None:
        raise RuntimeError("O controlador da missão não foi iniciado.")
    janela.controlador_missao.velocidade_base = 0.8
    janela.controlador_missao.tempo_parada_entrega = 0.0
    cronometro.restart()
    while cronometro.elapsed() < 5_000:
        aplicacao.processEvents()
        quadro = janela.controlador_missao.quadro()
        if quadro.distancia_percorrida >= 0.35:
            break
        if quadro.estado is EstadoMissao.CONCLUIDA:
            raise RuntimeError("A missão terminou antes da captura em movimento.")
        QTest.qWait(20)
    caminho = DESTINO / "05-missao-camera-carro.png"
    _salvar(janela, caminho, aplicacao)
    quadro = janela.controlador_missao.quadro()
    quadro_captura = quadro
    evidencias.append({"imagem": caminho.name, "descricao": "Carro em movimento com câmera de perseguição."})

    janela.controlador_missao.velocidade_base = 10.0
    janela.controlador_missao.velocidade_rotacao = 720.0
    cronometro.restart()
    while cronometro.elapsed() < 10_000:
        aplicacao.processEvents()
        quadro = janela.controlador_missao.quadro()
        if quadro.estado is EstadoMissao.CONCLUIDA:
            break
        QTest.qWait(10)
    if quadro.estado is not EstadoMissao.CONCLUIDA:
        raise RuntimeError("A missão da interface não foi concluída em 10 segundos.")
    if len(quadro.clientes_atendidos) != 5:
        raise RuntimeError("O painel da missão não registrou cinco entregas.")
    if quadro.posicao != janela.projeto.posicoes["D"]:
        raise RuntimeError("O carro não retornou exatamente ao depósito.")

    manifesto = {
        "cenario": CENARIO.name,
        "backend": janela.visualizacao.diagnostico_backend(),
        "renderizacao_real": janela.visualizacao.renderizacao_real_disponivel,
        "modelos_visiveis": janela.visualizacao.modelos_visiveis_na_cena,
        "marcadores": len(todos_marcadores),
        "segmentos_ruas": len(janela.editor.segmentos_ruas_qml()),
        "segmentos_tsp": len(janela.rota_calculada.segmentos_espaciais),
        "ordem_tsp": list(janela.rota_calculada.ordem_atendimento),
        "distancia_tsp": janela.rota_calculada.distancia_total,
        "captura_missao": {
            "estado_na_imagem": quadro_captura.estado.value,
            "distancia_percorrida_na_imagem": quadro_captura.distancia_percorrida,
            "camera": janela.visualizacao.camera.modo.value,
        },
        "missao_completa": {
            "estado": quadro.estado.value,
            "entregas": f"{len(quadro.clientes_atendidos)}/5",
            "painel": janela.cartao_clientes.valor.text(),
            "retornou_ao_deposito": quadro.posicao == janela.projeto.posicoes["D"],
        },
        "evidencias": evidencias,
    }
    (DESTINO / "manifesto.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    janela.close()
    aplicacao.processEvents()
    return manifesto


def main() -> int:
    print(json.dumps(capturar(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
