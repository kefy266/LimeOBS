import QtQuick

// Pencerenin altında birkaç saniye görünen kısa bildirim.
Rectangle {
    id: root
    property string message
    function show(text) {
        message = text
        state = "shown"
        hideTimer.restart()
    }

    anchors.horizontalCenter: parent.horizontalCenter
    y: parent.height
    z: 100
    width: Math.min(label.implicitWidth + 36, parent.width - 48)
    height: label.implicitHeight + 22
    radius: height / 2
    color: Theme.text
    Accessible.role: Accessible.AlertMessage
    Accessible.name: message

    Text {
        id: label
        anchors.centerIn: parent
        width: Math.min(implicitWidth, root.parent.width - 84)
        text: root.message
        wrapMode: Text.WordWrap
        horizontalAlignment: Text.AlignHCenter
        font.family: Theme.font
        font.pixelSize: Theme.fontUi
        color: Theme.bg
    }

    Timer { id: hideTimer; interval: 3500; onTriggered: root.state = "" }

    states: State {
        name: "shown"
        PropertyChanges { root.y: root.parent.height - root.height - 24 }
    }
    transitions: Transition {
        YAnimator { duration: Theme.normal; easing.type: Easing.OutCubic }
    }
}
