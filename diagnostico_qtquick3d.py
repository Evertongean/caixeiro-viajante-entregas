"""Teste visual independente do Qt Quick 3D.

Uso em um desktop Linux:

    .venv/bin/python diagnostico_qtquick3d.py
    .venv/bin/python diagnostico_qtquick3d.py --integration quickview
    .venv/bin/python diagnostico_qtquick3d.py --integration qquickwidget

O mesmo programa pode validar a integração headless com ``--offscreen`` ou
forçar o backend de software com ``--software``. Sem ``--offscreen`` ele mantém
a janela aberta para que o cubo vermelho seja confirmado visualmente. Use
``--model carro``, ``--model cidade`` ou ``--model ambos`` para testar os
assets importados isoladamente ou em conjunto.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offscreen", action="store_true", help="validar sem abrir uma janela visível")
    parser.add_argument("--software", action="store_true", help="usar QT_QUICK_BACKEND=software")
    parser.add_argument(
        "--integration",
        choices=("qquickwidget", "quickview"),
        default="qquickwidget",
        help="integração do teste do cubo: widget dentro de QWidget ou janela Qt Quick independente",
    )
    parser.add_argument(
        "--render-mode",
        choices=("offscreen", "underlay", "overlay", "inline"),
        default="offscreen",
        help="modo View3D usado no diagnóstico (offscreen é o modo recomendado)",
    )
    parser.add_argument(
        "--frame-output",
        type=Path,
        help="salvar a imagem capturada para inspeção (PNG, quando o backend permitir)",
    )
    parser.add_argument(
        "--model",
        choices=("cubo", "carro", "cidade", "ambos"),
        default="cubo",
        help="cena a testar (padrão: cubo)",
    )
    args = parser.parse_args()
    if args.offscreen:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    if args.software:
        os.environ.setdefault("QT_QUICK_BACKEND", "software")

    from PySide6.QtCore import QObject, QUrl, QTimer
    from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget
    from PySide6.QtQuick import QQuickView
    from PySide6.QtQuickWidgets import QQuickWidget
    from ui.modelos_glb import inspecionar_glb
    from ui.renderizador_qtquick3d import RenderizadorQtQuick3D

    app = QApplication.instance() or QApplication(sys.argv)
    if args.model != "cubo" and args.integration == "quickview":
        parser.error("--integration quickview é reservado ao teste do cubo; use qquickwidget para os GLB")
    janela = QMainWindow()
    janela.setWindowTitle("Diagnóstico Qt Quick 3D")
    janela.resize(800, 600)
    janela_quickview = None
    if args.model == "cubo" and args.integration == "quickview":
        # A é uma janela Qt Quick nativa. Ela remove QWidget/QQuickWidget da
        # equação e permite distinguir falha do Qt Quick 3D de composição.
        janela_quickview = QQuickView()
        janela_quickview.setTitle("Diagnóstico Qt Quick 3D — QQuickView")
        janela_quickview.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        janela_quickview.setSource(QUrl.fromLocalFile(str(Path(__file__).parent / "ui/qtquick3d_cubo.qml")))
        if janela_quickview.rootObject() is not None:
            janela_quickview.rootObject().setProperty("modoRenderizacao", args.render_mode)
        janela_quickview.resize(800, 600)
        quick = janela_quickview
        rotulo = None
    elif args.model == "cubo":
        # B é o caso em que a cena é uma textura 3D dentro de QWidget.
        conteudo = QWidget()
        layout = QVBoxLayout(conteudo)
        rotulo = QLabel("Cubo vermelho · aguardando View3D")
        quick = QQuickWidget()
        quick.setObjectName("quickWidgetDiagnostico")
        quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        quick.setClearColor("#172033")
        quick.setSource(QUrl.fromLocalFile(str(Path(__file__).parent / "ui/qtquick3d_cubo.qml")))
        if quick.rootObject() is not None:
            quick.rootObject().setProperty("modoRenderizacao", args.render_mode)
        layout.addWidget(rotulo)
        layout.addWidget(quick, 1)
        janela.setCentralWidget(conteudo)
    else:
        rotulo = QLabel("Modelos GLB · aguardando Loader3D")
        quick = RenderizadorQtQuick3D()
        conteudo = QWidget()
        layout = QVBoxLayout(conteudo)
        layout.addWidget(rotulo)
        layout.addWidget(quick, 1)
        janela.setCentralWidget(conteudo)
        if quick.rootObject() is not None:
            quick.rootObject().setProperty("modoRenderizacao", args.render_mode)
    if janela_quickview is not None:
        janela_quickview.show()
    else:
        janela.show()

    if args.model != "cubo":
        app.processEvents()
        raiz_assets = Path(__file__).parent / "assets/models"
        cidade = inspecionar_glb(raiz_assets / "cidade.glb")
        carro = inspecionar_glb(raiz_assets / "carro.glb")
        quick.carregar_modelos(cidade.caminho, carro.caminho)
        quick.configurar_cidade((0.0, 0.0, 0.0), 0.01)
        quick.configurar_limites_carro(carro.caixa.centro, carro.caixa.minimo)
        quick.posicionar_carro((0.0, 0.0, 0.0), 0.0, 0.018)
        if args.model == "carro":
            quick.definir_modelos_visiveis(False, True)
            # O Loader3D recebe o pivô compensado e fica na origem; enquadrar
            # pelo centro bruto do GLB deslocaria a câmera para fora do asset.
            quick.focar_carro((0.0, 0.0, 0.0), carro.caixa.dimensoes, 0.018)
        elif args.model == "cidade":
            quick.definir_modelos_visiveis(True, False)
            quick.enquadrar_cidade(cidade.caixa.centro, cidade.caixa.dimensoes, 0.01)
        else:
            quick.definir_modelos_visiveis(True, True)
            quick.enquadrar_cidade(cidade.caixa.centro, cidade.caixa.dimensoes, 0.01)
            centro_cidade = tuple(float(cidade.caixa.centro[i]) * 0.01 for i in range(3))
            margem = max(float(valor) for valor in cidade.caixa.dimensoes) * 0.01 * 0.55
            quick.posicionar_carro(
                (centro_cidade[0] + margem, 0.0, centro_cidade[2] + margem),
                0.0,
                0.018,
            )
            raio_cidade = max(max(float(valor) for valor in cidade.caixa.dimensoes) * 0.01 * 0.62, 0.15)
            quick.configurar_camera(True, max(raio_cidade * 2.2, 0.4))
        quick.show()

    sinais_renderizacao = {"before": 0, "after": 0}
    try:
        janela_render = janela_quickview if janela_quickview is not None else quick.quickWindow()
        janela_render.beforeRendering.connect(lambda: sinais_renderizacao.__setitem__("before", sinais_renderizacao["before"] + 1))
        janela_render.afterRendering.connect(lambda: sinais_renderizacao.__setitem__("after", sinais_renderizacao["after"] + 1))
    except (AttributeError, RuntimeError):
        janela_render = None

    def informar() -> None:
        raiz = quick.rootObject()
        view = None
        if raiz is not None:
            view = next(
                (
                    obj
                    for obj in raiz.findChildren(QObject)
                    if obj.objectName() in {"view3dMinima", "view3dGLB"}
                ),
                None,
            )
        view_largura = float(view.width()) if view is not None else 0.0
        view_altura = float(view.height()) if view is not None else 0.0
        try:
            status_pronto = quick.status().name == "Ready"
        except (AttributeError, RuntimeError):
            status_pronto = False
        status = "pronto" if status_pronto else "falhou"
        try:
            janela_api = janela_quickview if janela_quickview is not None else quick.quickWindow()
            api = janela_api.rendererInterface().graphicsApi()
            backend = getattr(api, "name", str(api))
        except (AttributeError, RuntimeError):
            backend = "desconhecido"
        mensagem = (
            f"QQuickWidget={quick.width()}x{quick.height()} · "
            f"raiz={float(raiz.width()) if raiz else 0:.0f}x{float(raiz.height()) if raiz else 0:.0f} · "
            f"View3D={view_largura:.0f}x{view_altura:.0f} · QML={status} · backend={backend}"
        )
        if args.model != "cubo":
            loaders = [obj for obj in raiz.findChildren(QObject) if obj.metaObject().className() == "QQuick3DLoader"]
            carregados = sum(obj.property("item") is not None for obj in loaders)
            mensagem += f" · Loader3D={carregados}/{len(loaders)}"
            for diagnostico in quick.diagnosticos:
                print(f"diagnóstico: {diagnostico}")
        if rotulo is not None:
            rotulo.setText(mensagem)
        print(mensagem)
        for erro in quick.errors():
            print(f"QML: {erro.toString()}", file=sys.stderr)
        imagem = None
        try:
            if janela_quickview is not None:
                imagem = janela_quickview.grabWindow()
            elif hasattr(quick, "grabFramebuffer"):
                imagem = quick.grabFramebuffer()
            else:
                imagem = quick.grab().toImage()
        except (AttributeError, RuntimeError) as erro:
            print(f"frame: falha ao capturar ({erro})", file=sys.stderr)
        if imagem is not None and not imagem.isNull():
            vermelhos = 0
            fora_fundo = 0
            fundo = imagem.pixelColor(0, 0)
            largura = imagem.width()
            altura = imagem.height()
            for y in range(altura):
                for x in range(largura):
                    cor = imagem.pixelColor(x, y)
                    if (
                        abs(cor.red() - fundo.red()) > 5
                        or abs(cor.green() - fundo.green()) > 5
                        or abs(cor.blue() - fundo.blue()) > 5
                    ):
                        fora_fundo += 1
                    if cor.red() >= 180 and cor.green() <= 110 and cor.blue() <= 110 and cor.alpha() > 0:
                        vermelhos += 1
            print(
                f"frame={largura}x{altura} · pixels_fora_fundo={fora_fundo} · "
                f"pixels_vermelhos={vermelhos}"
            )
            if args.frame_output is not None:
                args.frame_output.parent.mkdir(parents=True, exist_ok=True)
                if imagem.save(str(args.frame_output)):
                    print(f"frame salvo em {args.frame_output}")
                else:
                    print(f"frame: não foi possível salvar {args.frame_output}", file=sys.stderr)
        else:
            print("frame: indisponível (a janela ainda não produziu uma imagem)")
        try:
            window = quick if janela_quickview is not None else quick.quickWindow()
            print(
                "renderizador: "
                f"exposed={window.isExposed()} · visibilidade={window.visibility().name} · "
                f"renderingSignals={sinais_renderizacao['before']}/{sinais_renderizacao['after']}"
            )
        except (AttributeError, RuntimeError) as erro:
            print(f"renderizador: estado indisponível ({erro})", file=sys.stderr)
        if args.offscreen:
            QTimer.singleShot(100, app.quit)
        elif args.frame_output is not None:
            # Uma captura solicitada pela CI/diagnóstico é uma execução finita;
            # sem esse modo o programa permanece aberto para inspeção manual.
            QTimer.singleShot(50, app.quit)

    QTimer.singleShot(150, informar)
    codigo = app.exec()
    if janela_quickview is not None:
        janela_quickview.close()
    janela.close()
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
