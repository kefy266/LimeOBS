import QtQuick
import QtQuick.Layouts

// Ders satırı: ad, ayrıntı, başarı oranı çubuğu ve sağda değer.
Item {
    id: root
    property string name
    property string detail
    property string value
    property real ratio: 0
    property bool showDivider: true

    Layout.fillWidth: true
    implicitHeight: col.implicitHeight + 18

    Rectangle {
        visible: root.showDivider
        width: parent.width
        height: 1
        color: Theme.border
    }

    ColumnLayout {
        id: col
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: 6
        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: root.name
                font.family: Theme.font
                font.pixelSize: Theme.fontUi
                color: Theme.text
            }
            Text {
                text: root.detail
                font.family: Theme.font
                font.pixelSize: Theme.fontCaption
                color: Theme.textFaint
            }
            Text {
                Layout.preferredWidth: 64
                horizontalAlignment: Text.AlignRight
                text: root.value
                font.family: Theme.font
                font.pixelSize: Theme.fontUi
                font.weight: Font.DemiBold
                font.features: { "tnum": 1 }
                color: Theme.text
            }
        }
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 6
            radius: 3
            color: Theme.surfaceAlt
            Rectangle {
                width: parent.width * Math.max(0, Math.min(1, root.ratio))
                height: parent.height
                radius: 3
                color: root.ratio >= 0.75 ? Theme.accent : root.ratio >= 0.5 ? Theme.warning : Theme.danger
            }
        }
    }
}
