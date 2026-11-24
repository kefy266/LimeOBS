import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import LimeBackend

// Yeni sürüm bulununca sağ altta çıkan güncelleme kartı.
Rectangle {
    id: root
    readonly property bool hasUpdate: App.updateInfo && App.updateInfo.version !== undefined
    readonly property bool busy: App.updateState.length > 0

    visible: hasUpdate
    width: 340
    implicitHeight: content.implicitHeight + 32
    radius: Theme.radiusLg
    color: Theme.elevated
    border.width: 1
    border.color: Theme.border

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: 16
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Icon { name: "download"; size: 18; color: Theme.accent }
            Text {
                Layout.fillWidth: true
                text: root.hasUpdate ? qsTr("LimeOBS %1 hazır").arg(App.updateInfo.version) : ""
                font.family: Theme.font
                font.pixelSize: Theme.fontBody
                font.weight: Font.DemiBold
                color: Theme.text
            }
            IconButton {
                visible: !root.busy
                iconName: "x"
                tip: qsTr("Sonra")
                onClicked: App.dismissUpdate()
            }
        }
        Text {
            Layout.fillWidth: true
            text: root.busy ? qsTr("İndiriliyor… %%1").arg(Math.round(App.updateProgress * 100))
                            : qsTr("Şu an %1 kullanıyorsun. Güncelleyince LimeOBS kendini yeniden başlatır.").arg(App.appVersion)
            wrapMode: Text.WordWrap
            font.family: Theme.font
            font.pixelSize: Theme.fontSmall
            color: Theme.textMuted
        }
        Rectangle {
            visible: root.busy
            Layout.fillWidth: true
            implicitHeight: 6
            radius: 3
            color: Theme.border
            Rectangle {
                width: parent.width * App.updateProgress
                height: parent.height
                radius: 3
                color: Theme.accent
            }
        }
        OButton {
            visible: !root.busy
            Layout.fillWidth: true
            text: qsTr("Şimdi güncelle")
            variant: "primary"
            iconName: "refresh"
            onClicked: App.installUpdate()
        }
    }
}
