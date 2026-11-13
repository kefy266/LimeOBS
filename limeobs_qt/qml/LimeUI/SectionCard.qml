import QtQuick
import QtQuick.Layouts

// Başlıklı kart. İçerik ColumnLayout'a eklenir.
Rectangle {
    id: root
    property string title
    property string iconName
    property string badge
    default property alias content: body.data

    Layout.fillWidth: true
    implicitHeight: layout.implicitHeight + 32
    radius: Theme.radius
    color: Theme.surface
    border.width: 1
    border.color: Theme.border

    ColumnLayout {
        id: layout
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 16
        spacing: 12

        RowLayout {
            visible: root.title.length > 0
            Layout.fillWidth: true
            spacing: 8
            Icon {
                visible: root.iconName.length > 0
                name: root.iconName
                size: 17
                color: Theme.accent
            }
            Text {
                Layout.fillWidth: true
                text: root.title
                font.family: Theme.font
                font.pixelSize: Theme.fontUi
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Text {
                visible: root.badge.length > 0
                text: root.badge
                font.family: Theme.font
                font.pixelSize: Theme.fontCaption
                color: Theme.textFaint
            }
        }

        ColumnLayout {
            id: body
            Layout.fillWidth: true
            spacing: 0
        }
    }
}
