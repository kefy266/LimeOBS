import QtQuick
import QtQuick.Layouts

// Kart içi satır: solda (isteğe bağlı) kısa etiket, ortada başlık + alt satır, sağda rozet.
Item {
    id: root
    property string lead
    property string title
    property string subtitle
    property string trailing
    property bool highlight: false
    property bool showDivider: true

    Layout.fillWidth: true
    implicitHeight: row.implicitHeight + 18

    Rectangle {
        visible: root.showDivider
        anchors.top: parent.top
        width: parent.width
        height: 1
        color: Theme.border
    }

    RowLayout {
        id: row
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: 14

        Text {
            visible: root.lead.length > 0
            Layout.preferredWidth: 92
            text: root.lead
            font.family: Theme.font
            font.pixelSize: Theme.fontSmall
            font.features: { "tnum": 1 }
            color: Theme.textFaint
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1
            Text {
                Layout.fillWidth: true
                text: root.title
                wrapMode: Text.WordWrap
                font.family: Theme.font
                font.pixelSize: Theme.fontUi
                font.weight: root.highlight ? Font.DemiBold : Font.Normal
                color: Theme.text
            }
            Text {
                visible: root.subtitle.length > 0
                Layout.fillWidth: true
                text: root.subtitle
                elide: Text.ElideRight
                font.family: Theme.font
                font.pixelSize: Theme.fontSmall
                color: Theme.textMuted
            }
        }
        Rectangle {
            visible: root.trailing.length > 0
            Layout.preferredWidth: badgeText.implicitWidth + 16
            Layout.preferredHeight: 22
            radius: 11
            color: root.highlight ? Theme.accentSoft : Theme.surfaceAlt
            Text {
                id: badgeText
                anchors.centerIn: parent
                text: root.trailing
                font.family: Theme.font
                font.pixelSize: Theme.fontCaption
                font.weight: Font.Medium
                color: root.highlight ? Theme.accent : Theme.textMuted
            }
        }
    }
}
