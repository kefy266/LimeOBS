import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    property string label
    property string value
    property string note
    property bool good: false

    Layout.fillWidth: true
    Layout.preferredWidth: 1
    implicitHeight: col.implicitHeight + 28
    radius: Theme.radius
    color: Theme.surface
    border.width: 1
    border.color: Theme.border

    ColumnLayout {
        id: col
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.margins: 16
        spacing: 2
        Text {
            text: root.label
            font.family: Theme.font
            font.pixelSize: Theme.fontSmall
            color: Theme.textMuted
        }
        Text {
            Layout.fillWidth: true
            text: root.value
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: Theme.fontUi
            elide: Text.ElideRight
            font.family: Theme.font
            font.pixelSize: Theme.fontDisplay - 4
            font.weight: Font.DemiBold
            font.features: { "tnum": 1 }
            color: Theme.text
        }
        Text {
            visible: root.note.length > 0
            text: root.note
            font.family: Theme.font
            font.pixelSize: Theme.fontSmall
            color: root.good ? Theme.accent : Theme.textMuted
        }
    }
}
