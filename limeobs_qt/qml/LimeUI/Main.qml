import QtQuick
import QtQuick.Controls.Basic
import LimeBackend

ApplicationWindow {
    width: 1180
    height: 780
    minimumWidth: 760
    minimumHeight: 520
    visible: true
    title: "LimeOBS"
    color: Theme.bg

    Component.onCompleted: App.tryAutoLogin()

    Loader {
        anchors.fill: parent
        sourceComponent: App.loggedIn ? shell : login
    }

    Toast { id: toast }
    Connections {
        target: App
        function onToast(message) { toast.show(message) }
    }

    Component { id: login; LoginPage {} }
    Component { id: shell; Shell {} }
}
