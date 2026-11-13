import QtQuick
import QtQuick.Controls.Basic

// Metin butonu. variant: "primary" | "secondary" | "ghost" | "danger"
Button {
    id: control
    property string variant: "secondary"
    property string iconName: ""

    hoverEnabled: true
    implicitHeight: 36
    leftPadding: 14
    rightPadding: 14
    font.family: Theme.font
    font.pixelSize: Theme.fontUi
    font.weight: Font.Medium

    readonly property color fg: variant === "primary" ? Theme.textOnAccent
                              : variant === "danger" ? Theme.danger : Theme.text

    contentItem: Row {
        spacing: 8
        Icon {
            visible: control.iconName.length > 0
            name: control.iconName
            size: 16
            color: control.fg
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            text: control.text
            font: control.font
            color: control.fg
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    background: Rectangle {
        radius: Theme.radiusSm + 2
        color: {
            if (!control.enabled)
                return control.variant === "primary" ? Theme.selected : "transparent"
            switch (control.variant) {
            case "primary": return control.hovered ? Theme.accentHover : Theme.accent
            case "danger": return control.hovered ? Theme.dangerSoft : "transparent"
            case "ghost": return control.hovered ? Theme.hover : "transparent"
            default: return control.hovered ? Theme.hover : Theme.surface
            }
        }
        border.width: control.variant === "secondary" || control.variant === "danger" ? 1 : 0
        border.color: control.variant === "danger" ? Theme.danger : Theme.border
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
}
