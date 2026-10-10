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

    function executarPick(x, y) {
        const resultado = visualizacao.pick(x, y)
        if (!resultado.objectHit) {
            pontoSelecionado(0, 0, 0, "", "", false)
            return
        }
        const objeto = resultado.objectHit.objectName || "malha-sem-nome"
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
                pickable: raiz.modoInteracao === "navegar"
                position: raiz.centroSegmento(modelData)
                eulerRotation: raiz.rotacaoSegmento(modelData)
                scale: Qt.vector3d(
                    0.00010,
                    0.00010,
                    raiz.comprimentoSegmento(modelData) / 100
                )
                materials: PrincipledMaterial {
                    baseColor: segmentoRua.modelData.cor
                    emissiveFactor: Qt.vector3d(0.12, 0.25, 0.40)
                    roughness: 0.35
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
                    0.00014,
                    0.00014,
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
                    0.00018,
                    0.00018,
                    raiz.comprimentoSegmento(modelData) / 100
                )
                materials: PrincipledMaterial {
                    baseColor: segmentoRota.modelData.cor
                    emissiveFactor: segmentoRota.modelData.estado === "atual"
                        ? Qt.vector3d(0.95, 0.48, 0.04)
                        : segmentoRota.modelData.estado === "percorrido"
                            ? Qt.vector3d(0.14, 0.25, 0.32)
                            : segmentoRota.modelData.confirmado
                                ? Qt.vector3d(0.18, 0.72, 0.95)
                                : Qt.vector3d(0.78, 0.30, 0.03)
                    roughness: 0.18
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
                    ? Qt.vector3d(0.00012, 0.00012, 0.00012)
                    : Qt.vector3d(0.00042, 0.00042, 0.00042)
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
                    ? Qt.vector3d(0.00018, 0.00018, 0.00018)
                    : Qt.vector3d(0.00062, 0.00062, 0.00062)
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
            property vector3d projetado: visualizacao.mapFrom3DScene(
                Qt.vector3d(modelData.x, modelData.y + 0.095, modelData.z)
            )
            x: projetado.x - width / 2 + raiz.cameraYaw * 0
            y: projetado.y - height + raiz.cameraPitch * 0
            z: 20
            visible: projetado.z > 0
                     && raiz.cameraModo !== "atras_do_carro"
                     && !raiz.marcadorEstaNaRota(modelData.id)
            width: textoMarcador.implicitWidth + 16
            height: 24
            radius: 7
            color: "#E6111C2D"
            border.color: modelData.cor
            border.width: 1

            Text {
                id: textoMarcador
                anchors.centerIn: parent
                color: "#F4F8FF"
                font.pixelSize: 10
                font.weight: Font.DemiBold
                text: etiquetaMarcador.modelData.id + " · "
                      + etiquetaMarcador.modelData.nome
            }
        }
    }

    Repeater {
        model: raiz.marcadoresRota
        delegate: Rectangle {
            id: etiquetaRota
            required property var modelData
            property vector3d projetado: visualizacao.mapFrom3DScene(
                Qt.vector3d(modelData.x, modelData.y + 0.145, modelData.z)
            )
            x: projetado.x - width / 2 + raiz.cameraYaw * 0
            y: projetado.y - height + raiz.cameraPitch * 0
            z: 24
            visible: projetado.z > 0
            width: textoRota.implicitWidth + 18
            height: 23
            radius: 8
            color: "#EE07111F"
            border.color: modelData.cor
            border.width: 2

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
