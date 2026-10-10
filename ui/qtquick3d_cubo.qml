import QtQuick 2.15
import QtQuick3D 6.5

Item {
    id: raiz
    objectName: "raizCenaMinima"
    property string modoRenderizacao: "offscreen"
    View3D {
        objectName: "view3dMinima"
        anchors.fill: parent
        // QQuickWidget precisa de uma textura fora da composição 2D. Deixar
        // o modo explícito evita que uma alteração do backend escolha
        // Underlay/Inline sem que exista uma janela nativa para compor.
        renderMode: raiz.modoRenderizacao === "underlay" ? View3D.Underlay
                   : raiz.modoRenderizacao === "overlay" ? View3D.Overlay
                   : raiz.modoRenderizacao === "inline" ? View3D.Inline
                   : View3D.Offscreen
        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Color
            clearColor: "#29415f"
        }
        PerspectiveCamera {
            id: camera
            // Os primitivos nativos (#Cube) têm 100 unidades de lado. A
            // câmera em z=5 ficaria dentro da caixa e as faces seriam
            // descartadas; z=350 é o enquadramento usado pelos exemplos do
            // Qt e deixa o cubo inteiro dentro do frustum.
            position: Qt.vector3d(0, 0, 350)
            // O eixo -Z é o eixo de visão padrão da câmera. A orientação
            // explícita torna o teste independente de lookAtNode e de ordem
            // de avaliação dos nós durante a primeira moldura.
            eulerRotation: Qt.vector3d(0, 0, 0)
            clipNear: 0.01
            clipFar: 1000.0
            fieldOfView: 45
        }
        camera: camera
        DirectionalLight {
            eulerRotation: Qt.vector3d(-35, -35, 0)
            brightness: 2.0
        }
        Model {
            id: cubo
            objectName: "cuboDiagnostico"
            source: "#Cube"
            position: Qt.vector3d(0, 0, 0)
            scale: Qt.vector3d(1, 1, 1)
            visible: true
            materials: DefaultMaterial {
                // A primeira prova deve separar geometria/câmera de luz e
                // shaders PBR. A luz continua na cena para o segundo teste.
                lighting: DefaultMaterial.NoLighting
                diffuseColor: "#ef3340"
                opacity: 1.0
            }
        }
    }
}
