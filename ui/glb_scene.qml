import QtQuick 2.15
import QtQuick3D 6.5

Item {
    id: raiz
    objectName: "raizCenaGLB"
    // Resultado do raycast tridimensional usado pelo editor de ruas. A
    // posição é emitida em coordenadas de cena, já considerando câmera,
    // escala, rotação e deslocamento dos Loader3D.
    signal pontoSelecionado(real x, real y, real z, string objeto, bool encontrado)
    property real pickX: -1
    property real pickY: -1
    onPickYChanged: {
        if (raiz.pickX >= 0 && raiz.pickY >= 0)
            selecionarPonto(raiz.pickX, raiz.pickY)
    }
    property string modoRenderizacao: "offscreen"
    property url cidadeFonte
    property url carroFonte
    // Os GLBs originais são preservados apenas para diagnóstico. Modelos
    // renderizáveis são cenas QML/mesh produzidas pelo Balsam.
    property url cidadeFonteOriginal
    property url carroFonteOriginal
    property url cidadeDiagnosticoMesh
    property url carroDiagnosticoMesh
    property bool mostrarCidade: true
    property bool mostrarCarro: true
    property real escalaCidade: 1.0
    property vector3d posicaoCidade: Qt.vector3d(0, 0, 0)
    // A escala de configuração padrão (0,018) mantém o carro de ~6,28
    // unidades proporcional à cidade importada (~224 unidades).
    property real escalaCarro: 0.018
    property vector3d posicaoCarro: Qt.vector3d(0, 0, 0)
    property vector3d centroModeloCarro: Qt.vector3d(0, 0, 0)
    property vector3d minimoModeloCarro: Qt.vector3d(0, 0, 0)
    property real orientacaoCarro: 0
    property real correcaoEixoCarro: 0
    property bool cameraAerea: false
    property real distanciaCamera: 4.0
    property real alturaCamera: 2.0
    property real campoVisao: 42.0
    property vector3d centroCena: Qt.vector3d(0, 0, 0)
    property real raioCena: 2.0
    // A câmera livre é controlada pelo QWidget RenderizadorQtQuick3D. Os
    // ângulos estão em radianos para que o estado orbital Python possa ser
    // aplicado sem conversões acumuladas.
    property bool cameraLivre: false
    property real cameraYaw: 3.14159265359
    property real cameraPitch: 0.58
    property vector3d centroCameraLivre: Qt.vector3d(0, 0, 0)
    // Marcadores leves sobre o cenário. Slots fixos evitam criar componentes
    // dinamicamente durante uma missão e continuam funcionando em Qt 6.5.
    property vector3d marcador0Posicao: Qt.vector3d(0, 0, 0)
    property vector3d marcador1Posicao: Qt.vector3d(0, 0, 0)
    property vector3d marcador2Posicao: Qt.vector3d(0, 0, 0)
    property vector3d marcador3Posicao: Qt.vector3d(0, 0, 0)
    property vector3d marcador4Posicao: Qt.vector3d(0, 0, 0)
    property vector3d marcador5Posicao: Qt.vector3d(0, 0, 0)
    property vector3d marcador6Posicao: Qt.vector3d(0, 0, 0)
    property vector3d marcador7Posicao: Qt.vector3d(0, 0, 0)
    property vector3d marcador8Posicao: Qt.vector3d(0, 0, 0)
    property vector3d marcador9Posicao: Qt.vector3d(0, 0, 0)
    property vector3d marcador10Posicao: Qt.vector3d(0, 0, 0)
    property vector3d marcador11Posicao: Qt.vector3d(0, 0, 0)
    property vector3d marcador12Posicao: Qt.vector3d(0, 0, 0)
    property vector3d marcador13Posicao: Qt.vector3d(0, 0, 0)
    property vector3d marcador14Posicao: Qt.vector3d(0, 0, 0)
    property vector3d marcador15Posicao: Qt.vector3d(0, 0, 0)
    property var marcadoresVisiveis: []
    property var marcadoresCores: []
    property var segmentosRotaVisiveis: []
    property vector3d segmentoRota0Posicao: Qt.vector3d(0, 0, 0)
    property vector3d segmentoRota1Posicao: Qt.vector3d(0, 0, 0)
    property vector3d segmentoRota2Posicao: Qt.vector3d(0, 0, 0)
    property vector3d segmentoRota3Posicao: Qt.vector3d(0, 0, 0)
    property vector3d segmentoRota4Posicao: Qt.vector3d(0, 0, 0)
    property vector3d segmentoRota5Posicao: Qt.vector3d(0, 0, 0)
    property vector3d segmentoRota6Posicao: Qt.vector3d(0, 0, 0)
    property vector3d segmentoRota7Posicao: Qt.vector3d(0, 0, 0)
    property vector3d segmentoRota0Escala: Qt.vector3d(0.01, 0.01, 0.01)
    property vector3d segmentoRota1Escala: Qt.vector3d(0.01, 0.01, 0.01)
    property vector3d segmentoRota2Escala: Qt.vector3d(0.01, 0.01, 0.01)
    property vector3d segmentoRota3Escala: Qt.vector3d(0.01, 0.01, 0.01)
    property vector3d segmentoRota4Escala: Qt.vector3d(0.01, 0.01, 0.01)
    property vector3d segmentoRota5Escala: Qt.vector3d(0.01, 0.01, 0.01)
    property vector3d segmentoRota6Escala: Qt.vector3d(0.01, 0.01, 0.01)
    property vector3d segmentoRota7Escala: Qt.vector3d(0.01, 0.01, 0.01)
    property vector3d segmentoRota0Rotacao: Qt.vector3d(0, 0, 0)
    property vector3d segmentoRota1Rotacao: Qt.vector3d(0, 0, 0)
    property vector3d segmentoRota2Rotacao: Qt.vector3d(0, 0, 0)
    property vector3d segmentoRota3Rotacao: Qt.vector3d(0, 0, 0)
    property vector3d segmentoRota4Rotacao: Qt.vector3d(0, 0, 0)
    property vector3d segmentoRota5Rotacao: Qt.vector3d(0, 0, 0)
    property vector3d segmentoRota6Rotacao: Qt.vector3d(0, 0, 0)
    property vector3d segmentoRota7Rotacao: Qt.vector3d(0, 0, 0)

    // Chamado pelo Python após cada gesto. A atribuição imperativa é
    // necessária em algumas versões do PySide6 nas quais bindings de
    // QQuick3DNode não são reavaliados quando uma propriedade vector3d é
    // alterada através de QObject.setProperty().
    function atualizarCamera() {
        comportamentoPosicaoCamera.enabled = false
        comportamentoAlvoCamera.enabled = false
        comportamentoAlvoCameraLivre.enabled = false
        if (raiz.cameraLivre) {
            alvoCameraLivre.position = raiz.centroCameraLivre
            alvoCamera.position = raiz.posicaoCarro
            cameraNode.position = Qt.vector3d(
                raiz.centroCameraLivre.x
                    + Math.cos(raiz.cameraYaw) * Math.cos(raiz.cameraPitch) * raiz.distanciaCamera,
                raiz.centroCameraLivre.y
                    + Math.sin(raiz.cameraPitch) * raiz.distanciaCamera,
                raiz.centroCameraLivre.z
                    + Math.sin(raiz.cameraYaw) * Math.cos(raiz.cameraPitch) * raiz.distanciaCamera
            )
            cameraNode.lookAtNode = alvoCameraLivre
        } else if (raiz.cameraAerea) {
            alvoCamera.position = raiz.centroCena
            cameraNode.position = Qt.vector3d(
                raiz.centroCena.x - raiz.distanciaCamera,
                raiz.centroCena.y + raiz.distanciaCamera * 0.58,
                raiz.centroCena.z
            )
            cameraNode.lookAtNode = alvoCamera
        } else {
            alvoCamera.position = raiz.posicaoCarro
            cameraNode.position = Qt.vector3d(
                raiz.posicaoCarro.x
                    - Math.cos(raiz.orientacaoCarro * Math.PI / 180.0) * raiz.distanciaCamera,
                raiz.posicaoCarro.y + raiz.alturaCamera,
                raiz.posicaoCarro.z
                    - Math.sin(raiz.orientacaoCarro * Math.PI / 180.0) * raiz.distanciaCamera
            )
            cameraNode.lookAtNode = alvoCamera
        }
        comportamentoPosicaoCamera.enabled = raiz.cameraLivre || !raiz.cameraAerea
        comportamentoAlvoCamera.enabled = !raiz.cameraAerea && !raiz.cameraLivre
        comportamentoAlvoCameraLivre.enabled = raiz.cameraLivre
    }

    function selecionarPonto(x, y) {
        var resultado = visao.pick(x, y)
        if (resultado.objectHit) {
            const ponto = resultado.scenePosition
            const nome = resultado.objectHit.objectName || "malha-cidade"
            raiz.pontoSelecionado(ponto.x, ponto.y, ponto.z, nome, true)
        } else {
            raiz.pontoSelecionado(0, 0, 0, "", false)
        }
    }

    function tornarPickable(no) {
        if (!no)
            return
        // As cenas geradas pelo Balsam são uma árvore de Nodes/Models. Tornar
        // cada Model pickable é necessário para que View3D.pick atravesse o
        // Loader3D e devolva a malha real atingida.
        if (no.pickable !== undefined)
            no.pickable = true
        if (no.children) {
            for (let indice = 0; indice < no.children.length; ++indice)
                tornarPickable(no.children[indice])
        }
    }

    View3D {
        id: visao
        objectName: "view3dGLB"
        anchors.fill: parent
        renderMode: raiz.modoRenderizacao === "underlay" ? View3D.Underlay
                   : raiz.modoRenderizacao === "overlay" ? View3D.Overlay
                   : raiz.modoRenderizacao === "inline" ? View3D.Inline
                   : View3D.Offscreen
        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Color
            clearColor: "#101827"
            antialiasingMode: SceneEnvironment.MSAA
        }
        Node {
            id: alvoCamera
            objectName: "alvoCamera"
            position: (!raiz.cameraLivre && raiz.cameraAerea) ? raiz.centroCena : raiz.posicaoCarro
            Behavior on position {
                id: comportamentoAlvoCamera
                enabled: !raiz.cameraAerea && !raiz.cameraLivre
                SmoothedAnimation { velocity: 5.0 }
            }
        }
        Node {
            id: alvoCameraLivre
            objectName: "alvoCameraLivre"
            position: raiz.centroCameraLivre
            Behavior on position {
                id: comportamentoAlvoCameraLivre
                enabled: raiz.cameraLivre
                SmoothedAnimation { velocity: 8.0 }
            }
        }
        PerspectiveCamera {
            id: cameraNode
            objectName: "cameraGLB"
            position: raiz.cameraLivre
                ? Qt.vector3d(
                    raiz.centroCameraLivre.x
                        + Math.cos(raiz.cameraYaw) * Math.cos(raiz.cameraPitch) * raiz.distanciaCamera,
                    raiz.centroCameraLivre.y
                        + Math.sin(raiz.cameraPitch) * raiz.distanciaCamera,
                    raiz.centroCameraLivre.z
                        + Math.sin(raiz.cameraYaw) * Math.cos(raiz.cameraPitch) * raiz.distanciaCamera
                )
                : raiz.cameraAerea
                // A câmera de inspeção permanece acima e à esquerda do
                // centro, mantendo a mesma orientação frontal das malhas que
                // a câmera de missão usa. Uma posição diretamente em +Z
                // observa o verso escuro de alguns assets importados.
                ? Qt.vector3d(
                    raiz.centroCena.x - raiz.distanciaCamera,
                    raiz.centroCena.y + raiz.distanciaCamera * 0.58,
                    raiz.centroCena.z
                )
                : Qt.vector3d(
                    raiz.posicaoCarro.x - Math.cos(raiz.orientacaoCarro * Math.PI / 180.0) * raiz.distanciaCamera,
                    raiz.posicaoCarro.y + raiz.alturaCamera,
                    raiz.posicaoCarro.z - Math.sin(raiz.orientacaoCarro * Math.PI / 180.0) * raiz.distanciaCamera
                )
            Behavior on position {
                id: comportamentoPosicaoCamera
                enabled: raiz.cameraLivre || !raiz.cameraAerea
                SmoothedAnimation { velocity: 5.0 }
            }
            lookAtNode: raiz.cameraLivre ? alvoCameraLivre : alvoCamera
            fieldOfView: raiz.campoVisao
            clipNear: 0.01
            clipFar: 100000.0
        }
        camera: cameraNode
        DirectionalLight {
            eulerRotation: Qt.vector3d(-45, -30, 0)
            brightness: 1.2
        }
        Loader3D {
            id: cidadeLoader
            objectName: "cidadeLoader"
            source: raiz.cidadeFonte
            visible: raiz.mostrarCidade
            position: raiz.posicaoCidade
            scale: Qt.vector3d(raiz.escalaCidade, raiz.escalaCidade, raiz.escalaCidade)
        }
        Connections {
            target: cidadeLoader
            function onStatusChanged() {
                if (cidadeLoader.item)
                    raiz.tornarPickable(cidadeLoader.item)
            }
        }
        Loader3D {
            id: carroLoader
            objectName: "carroLoader"
            source: raiz.carroFonte
            visible: raiz.mostrarCarro
            // O pivô exportado não coincide com o centro nem com o solo.
            // Compensar os limites reais mantém o carro sobre a rua e sob a
            // câmera, mesmo quando o arquivo é substituído por outro GLB.
            position: Qt.vector3d(
                raiz.posicaoCarro.x - raiz.centroModeloCarro.x * raiz.escalaCarro,
                raiz.posicaoCarro.y - raiz.minimoModeloCarro.y * raiz.escalaCarro,
                raiz.posicaoCarro.z - raiz.centroModeloCarro.z * raiz.escalaCarro
            )
            scale: Qt.vector3d(raiz.escalaCarro, raiz.escalaCarro, raiz.escalaCarro)
            eulerRotation: Qt.vector3d(0, raiz.orientacaoCarro + raiz.correcaoEixoCarro, 0)
        }
        // Malhas reais (não GLB) mantidas invisíveis para que o diagnóstico
        // também consiga inspecionar o recurso final em versões do Qt que
        // não expõem os filhos do Loader3D ao objeto Python.
        Model {
            source: raiz.cidadeDiagnosticoMesh
            visible: false
        }
        Model {
            source: raiz.carroDiagnosticoMesh
            visible: false
        }
        Model { source: "#Sphere"; visible: raiz.marcadoresVisiveis.length > 0 && raiz.marcadoresVisiveis[0]; position: raiz.marcador0Posicao; scale: Qt.vector3d(0.035, 0.035, 0.035); materials: [DefaultMaterial { diffuseColor: raiz.marcadoresCores.length > 0 ? raiz.marcadoresCores[0] : "#F8FAFC" }] }
        Model { source: "#Sphere"; visible: raiz.marcadoresVisiveis.length > 1 && raiz.marcadoresVisiveis[1]; position: raiz.marcador1Posicao; scale: Qt.vector3d(0.035, 0.035, 0.035); materials: [DefaultMaterial { diffuseColor: raiz.marcadoresCores.length > 1 ? raiz.marcadoresCores[1] : "#F8FAFC" }] }
        Model { source: "#Sphere"; visible: raiz.marcadoresVisiveis.length > 2 && raiz.marcadoresVisiveis[2]; position: raiz.marcador2Posicao; scale: Qt.vector3d(0.035, 0.035, 0.035); materials: [DefaultMaterial { diffuseColor: raiz.marcadoresCores.length > 2 ? raiz.marcadoresCores[2] : "#F8FAFC" }] }
        Model { source: "#Sphere"; visible: raiz.marcadoresVisiveis.length > 3 && raiz.marcadoresVisiveis[3]; position: raiz.marcador3Posicao; scale: Qt.vector3d(0.035, 0.035, 0.035); materials: [DefaultMaterial { diffuseColor: raiz.marcadoresCores.length > 3 ? raiz.marcadoresCores[3] : "#F8FAFC" }] }
        Model { source: "#Sphere"; visible: raiz.marcadoresVisiveis.length > 4 && raiz.marcadoresVisiveis[4]; position: raiz.marcador4Posicao; scale: Qt.vector3d(0.035, 0.035, 0.035); materials: [DefaultMaterial { diffuseColor: raiz.marcadoresCores.length > 4 ? raiz.marcadoresCores[4] : "#F8FAFC" }] }
        Model { source: "#Sphere"; visible: raiz.marcadoresVisiveis.length > 5 && raiz.marcadoresVisiveis[5]; position: raiz.marcador5Posicao; scale: Qt.vector3d(0.035, 0.035, 0.035); materials: [DefaultMaterial { diffuseColor: raiz.marcadoresCores.length > 5 ? raiz.marcadoresCores[5] : "#F8FAFC" }] }
        Model { source: "#Sphere"; visible: raiz.marcadoresVisiveis.length > 6 && raiz.marcadoresVisiveis[6]; position: raiz.marcador6Posicao; scale: Qt.vector3d(0.035, 0.035, 0.035); materials: [DefaultMaterial { diffuseColor: raiz.marcadoresCores.length > 6 ? raiz.marcadoresCores[6] : "#F8FAFC" }] }
        Model { source: "#Sphere"; visible: raiz.marcadoresVisiveis.length > 7 && raiz.marcadoresVisiveis[7]; position: raiz.marcador7Posicao; scale: Qt.vector3d(0.035, 0.035, 0.035); materials: [DefaultMaterial { diffuseColor: raiz.marcadoresCores.length > 7 ? raiz.marcadoresCores[7] : "#F8FAFC" }] }
        Model { source: "#Sphere"; visible: raiz.marcadoresVisiveis.length > 8 && raiz.marcadoresVisiveis[8]; position: raiz.marcador8Posicao; scale: Qt.vector3d(0.035, 0.035, 0.035); materials: [DefaultMaterial { diffuseColor: raiz.marcadoresCores.length > 8 ? raiz.marcadoresCores[8] : "#F8FAFC" }] }
        Model { source: "#Sphere"; visible: raiz.marcadoresVisiveis.length > 9 && raiz.marcadoresVisiveis[9]; position: raiz.marcador9Posicao; scale: Qt.vector3d(0.035, 0.035, 0.035); materials: [DefaultMaterial { diffuseColor: raiz.marcadoresCores.length > 9 ? raiz.marcadoresCores[9] : "#F8FAFC" }] }
        Model { source: "#Sphere"; visible: raiz.marcadoresVisiveis.length > 10 && raiz.marcadoresVisiveis[10]; position: raiz.marcador10Posicao; scale: Qt.vector3d(0.035, 0.035, 0.035); materials: [DefaultMaterial { diffuseColor: raiz.marcadoresCores.length > 10 ? raiz.marcadoresCores[10] : "#F8FAFC" }] }
        Model { source: "#Sphere"; visible: raiz.marcadoresVisiveis.length > 11 && raiz.marcadoresVisiveis[11]; position: raiz.marcador11Posicao; scale: Qt.vector3d(0.035, 0.035, 0.035); materials: [DefaultMaterial { diffuseColor: raiz.marcadoresCores.length > 11 ? raiz.marcadoresCores[11] : "#F8FAFC" }] }
        Model { source: "#Sphere"; visible: raiz.marcadoresVisiveis.length > 12 && raiz.marcadoresVisiveis[12]; position: raiz.marcador12Posicao; scale: Qt.vector3d(0.035, 0.035, 0.035); materials: [DefaultMaterial { diffuseColor: raiz.marcadoresCores.length > 12 ? raiz.marcadoresCores[12] : "#F8FAFC" }] }
        Model { source: "#Sphere"; visible: raiz.marcadoresVisiveis.length > 13 && raiz.marcadoresVisiveis[13]; position: raiz.marcador13Posicao; scale: Qt.vector3d(0.035, 0.035, 0.035); materials: [DefaultMaterial { diffuseColor: raiz.marcadoresCores.length > 13 ? raiz.marcadoresCores[13] : "#F8FAFC" }] }
        Model { source: "#Sphere"; visible: raiz.marcadoresVisiveis.length > 14 && raiz.marcadoresVisiveis[14]; position: raiz.marcador14Posicao; scale: Qt.vector3d(0.035, 0.035, 0.035); materials: [DefaultMaterial { diffuseColor: raiz.marcadoresCores.length > 14 ? raiz.marcadoresCores[14] : "#F8FAFC" }] }
        Model { source: "#Sphere"; visible: raiz.marcadoresVisiveis.length > 15 && raiz.marcadoresVisiveis[15]; position: raiz.marcador15Posicao; scale: Qt.vector3d(0.035, 0.035, 0.035); materials: [DefaultMaterial { diffuseColor: raiz.marcadoresCores.length > 15 ? raiz.marcadoresCores[15] : "#F8FAFC" }] }
        Model { source: "#Cube"; visible: raiz.segmentosRotaVisiveis.length > 0 && raiz.segmentosRotaVisiveis[0]; position: raiz.segmentoRota0Posicao; scale: raiz.segmentoRota0Escala; eulerRotation: raiz.segmentoRota0Rotacao; materials: [DefaultMaterial { diffuseColor: "#F59E0B" }] }
        Model { source: "#Cube"; visible: raiz.segmentosRotaVisiveis.length > 1 && raiz.segmentosRotaVisiveis[1]; position: raiz.segmentoRota1Posicao; scale: raiz.segmentoRota1Escala; eulerRotation: raiz.segmentoRota1Rotacao; materials: [DefaultMaterial { diffuseColor: "#F59E0B" }] }
        Model { source: "#Cube"; visible: raiz.segmentosRotaVisiveis.length > 2 && raiz.segmentosRotaVisiveis[2]; position: raiz.segmentoRota2Posicao; scale: raiz.segmentoRota2Escala; eulerRotation: raiz.segmentoRota2Rotacao; materials: [DefaultMaterial { diffuseColor: "#F59E0B" }] }
        Model { source: "#Cube"; visible: raiz.segmentosRotaVisiveis.length > 3 && raiz.segmentosRotaVisiveis[3]; position: raiz.segmentoRota3Posicao; scale: raiz.segmentoRota3Escala; eulerRotation: raiz.segmentoRota3Rotacao; materials: [DefaultMaterial { diffuseColor: "#F59E0B" }] }
        Model { source: "#Cube"; visible: raiz.segmentosRotaVisiveis.length > 4 && raiz.segmentosRotaVisiveis[4]; position: raiz.segmentoRota4Posicao; scale: raiz.segmentoRota4Escala; eulerRotation: raiz.segmentoRota4Rotacao; materials: [DefaultMaterial { diffuseColor: "#F59E0B" }] }
        Model { source: "#Cube"; visible: raiz.segmentosRotaVisiveis.length > 5 && raiz.segmentosRotaVisiveis[5]; position: raiz.segmentoRota5Posicao; scale: raiz.segmentoRota5Escala; eulerRotation: raiz.segmentoRota5Rotacao; materials: [DefaultMaterial { diffuseColor: "#F59E0B" }] }
        Model { source: "#Cube"; visible: raiz.segmentosRotaVisiveis.length > 6 && raiz.segmentosRotaVisiveis[6]; position: raiz.segmentoRota6Posicao; scale: raiz.segmentoRota6Escala; eulerRotation: raiz.segmentoRota6Rotacao; materials: [DefaultMaterial { diffuseColor: "#F59E0B" }] }
        Model { source: "#Cube"; visible: raiz.segmentosRotaVisiveis.length > 7 && raiz.segmentosRotaVisiveis[7]; position: raiz.segmentoRota7Posicao; scale: raiz.segmentoRota7Escala; eulerRotation: raiz.segmentoRota7Rotacao; materials: [DefaultMaterial { diffuseColor: "#F59E0B" }] }
    }
}
