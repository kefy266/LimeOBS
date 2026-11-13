import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import LimeBackend

// Hesap satırındaki ayarlar açılır kutusu: tema ve çıkış.
Popup {
    id: root
    width: 240
    padding: 12
    background: Rectangle {
        radius: Theme.radius
        color: Theme.elevated
        border.width: 1
        border.color: Theme.border
    }
    contentItem: ColumnLayout {
        spacing: 10
        Text {
            text: qsTr("Görünüm")
            font.family: Theme.font
            font.pixelSize: Theme.fontCaption
            color: Theme.textFaint
        }
        Segmented {
            Layout.fillWidth: true
            model: [{ value: "system", label: qsTr("Sistem") }, { value: "light", label: qsTr("Açık") },
                    { value: "dark", label: qsTr("Koyu") }]
            value: App.themeMode
            onPicked: v => App.themeMode = v
        }
        OButton {
            Layout.fillWidth: true
            text: qsTr("Çıkış yap")
            iconName: "logout"
            variant: "danger"
            onClicked: { root.close(); App.logout() }
        }
    }
}
