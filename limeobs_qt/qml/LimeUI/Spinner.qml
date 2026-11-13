import QtQuick
import QtQuick.Shapes

Item {
    id: spinner
    implicitWidth: 18
    implicitHeight: 18
    Accessible.role: Accessible.Indicator
    Accessible.name: qsTr("Yükleniyor")

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        RotationAnimation on rotation { from: 0; to: 360; duration: 900; loops: Animation.Infinite; running: spinner.visible }
        ShapePath {
            strokeColor: Theme.accent
            strokeWidth: 2
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathAngleArc {
                centerX: spinner.width / 2
                centerY: spinner.height / 2
                radiusX: spinner.width / 2 - 2
                radiusY: spinner.height / 2 - 2
                startAngle: 0
                sweepAngle: 270
            }
        }
    }
}
