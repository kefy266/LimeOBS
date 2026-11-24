import QtQuick
import QtQuick.Controls.Basic
import LimeBackend

ApplicationWindow {
    id: window
    signal hiddenToTray()
    width: 1180
    height: 780
    minimumWidth: 760
    minimumHeight: 520
    visible: true
    title: "LimeOBS"
    color: Theme.bg

    Component.onCompleted: App.tryAutoLogin()

    // Tepsi açıksa kapatma düğmesi pencereyi gizler (uygulama arka planda bildirim göndermeye devam eder)
    onClosing: close => {
        if (App.trayAvailable && App.trayEnabled && App.loggedIn) {
            close.accepted = false
            window.hide()
            window.hiddenToTray()
        } else {
            Qt.quit()
        }
    }

    Loader {
        anchors.fill: parent
        sourceComponent: App.loggedIn ? shell : login
    }

    UpdateBanner {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 20
        z: 50
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
