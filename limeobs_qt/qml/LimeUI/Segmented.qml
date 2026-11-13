import QtQuick

// Sekme seçici. model: [{value, label}]
Rectangle {
    id: root
    property var model: []
    property string value: ""
    signal picked(string value)

    implicitHeight: 34
    implicitWidth: row.implicitWidth + 6
    radius: Theme.radiusSm + 2
    color: Theme.surfaceAlt
    border.width: 1
    border.color: Theme.border

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 2
        Repeater {
            model: root.model
            delegate: Rectangle {
                id: seg
                required property var modelData
                readonly property bool on: root.value === modelData.value
                width: label.implicitWidth + 22
                height: root.height - 6
                radius: Theme.radiusSm
                color: on ? Theme.elevated : (area.containsMouse ? Theme.hover : "transparent")
                border.width: on ? 1 : 0
                border.color: Theme.border
                Accessible.role: Accessible.PageTab
                Accessible.name: modelData.label
                Behavior on color { ColorAnimation { duration: Theme.fast } }
                Text {
                    id: label
                    anchors.centerIn: parent
                    text: seg.modelData.label
                    font.family: Theme.font
                    font.pixelSize: Theme.fontSmall
                    font.weight: seg.on ? Font.DemiBold : Font.Normal
                    color: seg.on ? Theme.text : Theme.textMuted
                }
                MouseArea {
                    id: area
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (!seg.on) root.picked(seg.modelData.value)
                }
            }
        }
    }
}
