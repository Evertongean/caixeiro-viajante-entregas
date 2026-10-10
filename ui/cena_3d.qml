pragma ComponentBehavior: Bound

import QtQuick 2.15
import QtQuick3D 6.5

Item {
    id: raiz
    objectName: "raizCena3D"

    signal pontoSelecionado(real x, real y, real z, string objeto,
                            string material, bool encontrado)
    property real pickX: -1
    property real pickY: -1
    property string modoInteracao: "navegar"
    onPickYChanged: {
        if (pickX >= 0 && pickY >= 0)
            executarPick(pickX, pickY)
    }

    property url cidadeFonte
    property url carroFonte
    property real escalaCidade: 0.01
    property real escalaCarro: 0.018
    property vector3d centroCamera: Qt.vector3d(0, 0, 0)
    property real cameraYaw: 3.14159265359
    property real cameraPitch: 0.58
    property real cameraDistancia: 4.0
    property string cameraModo: "livre"
    property vector3d cameraSeguimentoPosicao: Qt.vector3d(0, 0.24, 0.42)
    property vector3d cameraSeguimentoAlvo: Qt.vector3d(0, 0, 0)
    property vector3d posicaoCarro: Qt.vector3d(0, 0, 0)
    property vector3d centroModeloCarro: Qt.vector3d(0, 0, 0)
    property vector3d minimoModeloCarro: Qt.vector3d(0, 0, 0)
    property real rotacaoCarro: 0.0
    property real alturaCarro: 0.01
    property bool cidadePronta: cidadeLoader.item !== null
    property bool carroPronto: carroLoader.item !== null
    property int modelosProntos: (cidadePronta ? 1 : 0) + (carroPronto ? 1 : 0)
    property var marcadores: []
    property var segmentosRuas: []
    property var segmentosPrevia: []
    property var segmentosRota: []
    property var marcadoresRota: []
    property bool mostrarRedeRuas: true
    property real larguraRedeMundo: 0.0035
    property real espessuraRedeMundo: 0.0008
    // O cubo primitivo mede 100 unidades. Estes valores sao dimensoes reais
    // na cena, e nao escalas magicas dependentes da camera.
    property real larguraRotaMundo: 0.006
    property real espessuraRotaMundo: 0.0012
    property real distanciaRotulosCruzamentos: 2.4
    property string origemUltimoPick: "nenhuma"
    property bool marcadorTemporarioVisivel: false
    property vector3d marcadorTemporarioPosicao: Qt.vector3d(0, 0, 0)

    function tornarSelecionavel(no) {
        if (!no)
            return
        if (no.pickable !== undefined)
            no.pickable = true
        if (no.children) {
            for (let indice = 0; indice < no.children.length; ++indice)
                tornarSelecionavel(no.children[indice])
        }
    }

    function descendeDe(no, ancestral) {
        let atual = no
        while (atual) {
            if (atual === ancestral)
                return true
            atual = atual.parent
        }
        return false
    }

    function origemDoPick(no, nome) {
        if (descendeDe(no, cidadeLoader.item))
            return "cidade"
        if (descendeDe(no, carroLoader.item))
            return "carro"
        if (nome.startsWith("vertice:") || nome.startsWith("aresta:")
                || nome.startsWith("marcador-rota:")
                || nome === "destaque-rota" || nome === "previa-rua"
                || nome === "marcador-temporario")
            return "editor"
        return "outro"
    }

    function executarPick(x, y) {
        const resultado = visualizacao.pick(x, y)
        if (!resultado.objectHit) {
            origemUltimoPick = "nenhuma"
            pontoSelecionado(0, 0, 0, "", "", false)
            return
        }
        const objeto = resultado.objectHit.objectName || "malha-sem-nome"
        origemUltimoPick = origemDoPick(resultado.objectHit, objeto)
        let material = ""
        try {
            if (resultado.objectHit.materials
                    && resultado.objectHit.materials.length > 0)
                material = resultado.objectHit.materials[0].objectName || ""
        } catch (erro) {
            material = ""
        }
        const ponto = resultado.scenePosition
        pontoSelecionado(ponto.x, ponto.y, ponto.z, objeto, material, true)
    }

    function centroSegmento(item) {
        return Qt.vector3d((item.ax + item.bx) / 2,
                           (item.ay + item.by) / 2,
                           (item.az + item.bz) / 2)
    }

    function comprimentoSegmento(item) {
        const dx = item.bx - item.ax
        const dy = item.by - item.ay
        const dz = item.bz - item.az
        return Math.sqrt(dx * dx + dy * dy + dz * dz)
    }

    function rotacaoSegmento(item) {
        const dx = item.bx - item.ax
        const dy = item.by - item.ay
        const dz = item.bz - item.az
        const horizontal = Math.sqrt(dx * dx + dz * dz)
        const yaw = Math.atan2(dx, dz) * 180 / Math.PI
        const pitch = -Math.atan2(dy, horizontal) * 180 / Math.PI
        return Qt.vector3d(pitch, yaw, 0)
    }

    function marcadorEstaNaRota(identificador) {
        for (let indice = 0; indice < marcadoresRota.length; ++indice) {
            if (marcadoresRota[indice].id === identificador)
                return true
        }
        return false
    }

    // mapFrom3DScene depende internamente da matriz da camera, mas essa
    // dependencia nao e descoberta automaticamente pelo mecanismo de
    // bindings do QML. Os argumentos explicitos invalidam a projecao para
    // toda alteracao que muda a matriz ou o viewport.
    function projetarPonto(ponto, yaw, pitch, distancia, centro,
                           posicaoSeguimento, alvoSeguimento,
                           larguraViewport, alturaViewport, modo) {
        // Os parametros existem para estabelecer dependencias reativas
        // individuais, inclusive quando dois movimentos numericos se anulam.
        return visualizacao.mapFrom3DScene(ponto)
    }

    function projecaoVisivel(ponto, largura, altura) {
        return ponto.z > 0
            && ponto.x >= largura / 2
            && ponto.x <= visualizacao.width - largura / 2
            && ponto.y >= altura
            && ponto.y <= visualizacao.height
    }

    function rotuloMarcadorVisivel(item) {
        return item.tipo !== "cruzamento"
            || cameraDistancia <= distanciaRotulosCruzamentos
    }

    function rotuloRotaVisivel(item) {
        return cameraModo !== "atras_do_carro"
            || item.texto.startsWith("PRÓXIMA")
            || item.texto.includes("FIM")
    }

    Rectangle {
        anchors.fill: parent
        color: "#07111f"
    }

    View3D {
        id: visualizacao
        objectName: "view3dPrincipal"
        anchors.fill: parent
        renderMode: View3D.Offscreen
        camera: cameraPrincipal

        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Color
            clearColor: "#07111f"
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }

        Node {
            id: alvoCamera
            objectName: "alvoCamera"
            position: raiz.cameraModo === "atras_do_carro"
                ? raiz.cameraSeguimentoAlvo
                : raiz.centroCamera
        }

        PerspectiveCamera {
            id: cameraPrincipal
            objectName: "cameraPrincipal"
            position: raiz.cameraModo === "atras_do_carro"
                ? raiz.cameraSeguimentoPosicao
                : Qt.vector3d(
                    raiz.centroCamera.x
                        + Math.cos(raiz.cameraYaw) * Math.cos(raiz.cameraPitch)
                        * raiz.cameraDistancia,
                    raiz.centroCamera.y
                        + Math.sin(raiz.cameraPitch) * raiz.cameraDistancia,
                    raiz.centroCamera.z
                        + Math.sin(raiz.cameraYaw) * Math.cos(raiz.cameraPitch)
                        * raiz.cameraDistancia
                )
            lookAtNode: alvoCamera
            fieldOfView: 43
            clipNear: 0.005
            clipFar: 1000
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(-48, -32, 0)
            color: "#fff7e8"
            brightness: 1.35
            castsShadow: true
            shadowFactor: 55
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(-25, 145, 0)
            color: "#8ebcff"
            brightness: 0.72
        }

        Loader3D {
            id: cidadeLoader
            objectName: "cidadeLoader"
            source: raiz.cidadeFonte
            scale: Qt.vector3d(
                raiz.escalaCidade, raiz.escalaCidade, raiz.escalaCidade
            )
            onStatusChanged: {
                if (item)
                    raiz.tornarSelecionavel(item)
            }
        }

        Node {
            id: transformacaoCarro
            objectName: "transformacaoCarro"
            position: Qt.vector3d(
                raiz.posicaoCarro.x,
                raiz.posicaoCarro.y + raiz.alturaCarro,
                raiz.posicaoCarro.z
            )
            eulerRotation: Qt.vector3d(0, raiz.rotacaoCarro, 0)

            Loader3D {
                id: carroLoader
                objectName: "carroLoader"
                source: raiz.carroFonte
                position: Qt.vector3d(
                    -raiz.centroModeloCarro.x * raiz.escalaCarro,
                    -raiz.minimoModeloCarro.y * raiz.escalaCarro,
                    -raiz.centroModeloCarro.z * raiz.escalaCarro
                )
                scale: Qt.vector3d(
                    raiz.escalaCarro, raiz.escalaCarro, raiz.escalaCarro
                )
            }
        }

        Repeater3D {
            model: raiz.segmentosRuas
            delegate: Model {
                id: segmentoRua
                required property var modelData
                objectName: "aresta:" + modelData.aresta
                source: "#Cube"
                visible: raiz.mostrarRedeRuas
                pickable: visible && raiz.modoInteracao === "navegar"
                position: raiz.centroSegmento(modelData)
                eulerRotation: raiz.rotacaoSegmento(modelData)
                scale: Qt.vector3d(
                    raiz.larguraRedeMundo / 100,
                    raiz.espessuraRedeMundo / 100,
                    raiz.comprimentoSegmento(modelData) / 100
                )
                materials: PrincipledMaterial {
                    baseColor: segmentoRua.modelData.cor
                    emissiveFactor: Qt.vector3d(0.03, 0.06, 0.09)
                    roughness: 0.48
                }
            }
        }

        Repeater3D {
            model: raiz.segmentosPrevia
            delegate: Model {
                id: segmentoPrevia
                required property var modelData
                objectName: "previa-rua"
                source: "#Cube"
                pickable: false
                position: raiz.centroSegmento(modelData)
                eulerRotation: raiz.rotacaoSegmento(modelData)
                scale: Qt.vector3d(
                    0.00005,
                    0.00001,
                    raiz.comprimentoSegmento(modelData) / 100
                )
                materials: PrincipledMaterial {
                    baseColor: "#F59E0B"
                    emissiveFactor: Qt.vector3d(0.45, 0.20, 0.02)
                    roughness: 0.28
                }
            }
        }

        Repeater3D {
            model: raiz.segmentosRota
            delegate: Model {
                id: segmentoRota
                required property var modelData
                objectName: "destaque-rota"
                source: "#Cube"
                pickable: false
                position: raiz.centroSegmento(modelData)
                eulerRotation: raiz.rotacaoSegmento(modelData)
                scale: Qt.vector3d(
                    raiz.larguraRotaMundo / 100,
                    raiz.espessuraRotaMundo / 100,
                    raiz.comprimentoSegmento(modelData) / 100
                )
                materials: PrincipledMaterial {
                    baseColor: segmentoRota.modelData.cor
                    emissiveFactor: segmentoRota.modelData.estado === "atual"
                        ? Qt.vector3d(0.42, 0.22, 0.03)
                        : segmentoRota.modelData.estado === "percorrido"
                            ? Qt.vector3d(0.06, 0.10, 0.14)
                            : segmentoRota.modelData.confirmado
                                ? Qt.vector3d(0.08, 0.34, 0.46)
                                : Qt.vector3d(0.38, 0.15, 0.02)
                    roughness: 0.30
                }
            }
        }

        Repeater3D {
            model: raiz.marcadores
            delegate: Model {
                id: marcador3D
                required property var modelData
                objectName: "vertice:" + modelData.id
                source: "#Sphere"
                pickable: true
                position: Qt.vector3d(
                    modelData.x, modelData.y + 0.045, modelData.z
                )
                scale: raiz.cameraModo === "atras_do_carro"
                    ? Qt.vector3d(0.00007, 0.00007, 0.00007)
                    : Qt.vector3d(0.00032, 0.00032, 0.00032)
                materials: PrincipledMaterial {
                    baseColor: marcador3D.modelData.cor
                    emissiveFactor: Qt.vector3d(0.16, 0.16, 0.16)
                    roughness: 0.24
                }
            }
        }

        Repeater3D {
            model: raiz.marcadoresRota
            delegate: Model {
                id: marcadorRota3D
                required property var modelData
                objectName: "marcador-rota:" + modelData.id
                source: "#Sphere"
                pickable: false
                position: Qt.vector3d(
                    modelData.x, modelData.y + 0.048, modelData.z
                )
                scale: raiz.cameraModo === "atras_do_carro"
                    ? Qt.vector3d(0.00008, 0.00008, 0.00008)
                    : Qt.vector3d(0.00036, 0.00036, 0.00036)
                materials: PrincipledMaterial {
                    baseColor: marcadorRota3D.modelData.cor
                    emissiveFactor: Qt.vector3d(0.35, 0.55, 0.60)
                    roughness: 0.16
                }
            }
        }

        Model {
            objectName: "marcador-temporario"
            source: "#Sphere"
            visible: raiz.marcadorTemporarioVisivel
            pickable: false
            position: Qt.vector3d(
                raiz.marcadorTemporarioPosicao.x,
                raiz.marcadorTemporarioPosicao.y + 0.045,
                raiz.marcadorTemporarioPosicao.z
            )
            scale: Qt.vector3d(0.00050, 0.00050, 0.00050)
            materials: PrincipledMaterial {
                baseColor: "#F59E0B"
                emissiveFactor: Qt.vector3d(0.55, 0.24, 0.02)
                roughness: 0.20
            }
        }
    }

    Repeater {
        model: raiz.marcadores
        delegate: Rectangle {
            id: etiquetaMarcador
            required property var modelData
            objectName: "etiqueta-marcador:" + modelData.id
            property vector3d projetado: raiz.projetarPonto(
                Qt.vector3d(modelData.x, modelData.y + 0.078, modelData.z),
                raiz.cameraYaw, raiz.cameraPitch, raiz.cameraDistancia,
                raiz.centroCamera, raiz.cameraSeguimentoPosicao,
                raiz.cameraSeguimentoAlvo, visualizacao.width,
                visualizacao.height, raiz.cameraModo
            )
            x: projetado.x - width / 2
            y: projetado.y - height
            z: 20
            visible: raiz.projecaoVisivel(projetado, width, height)
                     && raiz.cameraModo !== "atras_do_carro"
                     && !raiz.marcadorEstaNaRota(modelData.id)
                     && raiz.rotuloMarcadorVisivel(modelData)
            width: textoMarcador.implicitWidth + 16
            height: 22
            radius: 6
            color: "#DC0B1728"
            border.color: modelData.cor
            border.width: 1

            Text {
                id: textoMarcador
                anchors.centerIn: parent
                color: "#F4F8FF"
                font.pixelSize: 9
                font.weight: Font.DemiBold
                text: etiquetaMarcador.modelData.tipo === "cruzamento"
                    ? etiquetaMarcador.modelData.id
                    : etiquetaMarcador.modelData.id + " · "
                        + etiquetaMarcador.modelData.nome
            }
        }
    }

    Repeater {
        model: raiz.marcadoresRota
        delegate: Rectangle {
            id: etiquetaRota
            required property var modelData
            objectName: "etiqueta-rota:" + modelData.id
            property real alturaAncora: raiz.cameraModo === "atras_do_carro"
                ? 0.072 : 0.088
            property vector3d projetado: raiz.projetarPonto(
                Qt.vector3d(
                    modelData.x, modelData.y + alturaAncora, modelData.z
                ),
                raiz.cameraYaw, raiz.cameraPitch, raiz.cameraDistancia,
                raiz.centroCamera, raiz.cameraSeguimentoPosicao,
                raiz.cameraSeguimentoAlvo, visualizacao.width,
                visualizacao.height, raiz.cameraModo
            )
            x: projetado.x - width / 2
            y: projetado.y - height
            z: 24
            visible: raiz.projecaoVisivel(projetado, width, height)
                     && raiz.rotuloRotaVisivel(modelData)
            width: textoRota.implicitWidth + 16
            height: 21
            radius: 7
            color: "#E607111F"
            border.color: modelData.cor
            border.width: 1

            Text {
                id: textoRota
                anchors.centerIn: parent
                color: "#F4F8FF"
                font.pixelSize: 9
                font.weight: Font.Bold
                text: etiquetaRota.modelData.texto
            }
        }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 18
        width: estadoTexto.implicitWidth + 28
        height: 34
        radius: 17
        color: raiz.modelosProntos === 2 ? "#cc0d2539" : "#dd111c2d"
        border.color: raiz.modelosProntos === 2 ? "#2dd4bf" : "#35608d"
        border.width: 1

        Text {
            id: estadoTexto
            anchors.centerIn: parent
            color: raiz.modelosProntos === 2 ? "#99f6e4" : "#b8c7dc"
            font.pixelSize: 12
            font.weight: Font.DemiBold
            text: raiz.modelosProntos === 2
                ? "●  CENA 3D PRONTA"
                : "PREPARANDO MODELOS 3D…"
        }
    }
}
