import QtQuick
import QtQuick.Controls.Basic

CheckBox {
    id: control
    hoverEnabled: true
    font.family: Theme.font
    font.pixelSize: Theme.fontUi
    spacing: 10

    indicator: Rectangle {
        x: control.leftPadding
        y: (control.height - height) / 2
        implicitWidth: 20
        implicitHeight: 20
        radius: 6
        color: control.checked ? Theme.accent : (control.hovered ? Theme.hover : Theme.surfaceAlt)
        border.width: control.checked ? 0 : 1
        border.color: control.hovered ? Theme.borderStrong : Theme.border
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Icon {
            anchors.centerIn: parent
            visible: control.checked
            name: "check"
            size: 14
            color: Theme.textOnAccent
        }
    }
    contentItem: Text {
        leftPadding: control.indicator.width + (control.text.length ? control.spacing : 0)
        text: control.text
        font: control.font
        color: Theme.text
        verticalAlignment: Text.AlignVCenter
    }
}
