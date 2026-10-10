import QtQuick 2.15
import QtQuick3D 6.5

Item {
    id: raiz
    objectName: "raizCena3D"

    property url cidadeFonte
    property url carroFonte
    property real escalaCidade: 0.01
    property real escalaCarro: 0.018
    property vector3d centroCamera: Qt.vector3d(0, 0, 0)
    property real cameraYaw: 3.14159265359
    property real cameraPitch: 0.58
    property real cameraDistancia: 4.0
    property string cameraModo: "livre"
    property vector3d posicaoCarro: Qt.vector3d(0, 0, 0)
    property vector3d centroModeloCarro: Qt.vector3d(0, 0, 0)
    property vector3d minimoModeloCarro: Qt.vector3d(0, 0, 0)
    property real rotacaoCarro: 0.0
    property real alturaCarro: 0.01
    property bool cidadePronta: cidadeLoader.item !== null
    property bool carroPronto: carroLoader.item !== null
    property int modelosProntos: (cidadePronta ? 1 : 0) + (carroPronto ? 1 : 0)

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
                ? raiz.posicaoCarro
                : raiz.centroCamera
        }

        PerspectiveCamera {
            id: cameraPrincipal
            objectName: "cameraPrincipal"
            position: raiz.cameraModo === "atras_do_carro"
                ? Qt.vector3d(
                    raiz.posicaoCarro.x,
                    raiz.posicaoCarro.y + 0.24,
                    raiz.posicaoCarro.z + 0.42
                )
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
        }

        Loader3D {
            id: carroLoader
            objectName: "carroLoader"
            source: raiz.carroFonte
            position: Qt.vector3d(
                raiz.posicaoCarro.x
                    - raiz.centroModeloCarro.x * raiz.escalaCarro,
                raiz.posicaoCarro.y + raiz.alturaCarro
                    - raiz.minimoModeloCarro.y * raiz.escalaCarro,
                raiz.posicaoCarro.z
                    - raiz.centroModeloCarro.z * raiz.escalaCarro
            )
            scale: Qt.vector3d(
                raiz.escalaCarro, raiz.escalaCarro, raiz.escalaCarro
            )
            eulerRotation: Qt.vector3d(0, raiz.rotacaoCarro, 0)
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
