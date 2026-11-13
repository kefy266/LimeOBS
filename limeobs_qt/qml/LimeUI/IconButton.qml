import QtQuick
import QtQuick.Controls.Basic

AbstractButton {
    id: control
    property string iconName
    property string tip
    property int iconSize: 18

    implicitWidth: 34
    implicitHeight: 34
    hoverEnabled: true
    Accessible.name: tip
    ToolTip.visible: hovered && tip.length > 0
    ToolTip.text: tip
    ToolTip.delay: 500

    background: Rectangle {
        radius: Theme.radiusSm
        color: control.hovered ? Theme.hover : "transparent"
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
    contentItem: Item {
        Icon {
            anchors.centerIn: parent
            name: control.iconName
            size: control.iconSize
            color: control.enabled ? Theme.textMuted : Theme.textFaint
        }
    }
}
