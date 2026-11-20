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
    // Oynatıcı yalnızca gerektiğinde yüklenir (QtMultimedia yoksa backend dosyayı harici açar)
    Loader { id: media; active: false; source: "MediaViewer.qml" }
    Connections {
        target: App
        function onToast(message) { toast.show(message) }
        function onMediaReady(url, name, audioOnly) {
            media.active = true
            if (media.item) media.item.play(url, name, audioOnly)
            else toast.show(qsTr("Oynatıcı açılamadı."))
        }
    }

    Component { id: login; LoginPage {} }
    Component { id: shell; Shell {} }
}
