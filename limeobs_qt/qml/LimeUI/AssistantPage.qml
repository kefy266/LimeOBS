import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import LimeBackend

// Orbital'in sohbet ekranı: boşken ortada karşılama + büyük yazı kartı, sohbette mesajlar ve altta kart.
Item {
    id: page
    property bool busy: false
    readonly property bool empty: messages.count === 0
    readonly property var suggestions: [
        { icon: "list", text: qsTr("Haftamı analiz et"),
          prompt: qsTr("Bu haftaki ödev ve ders yükümü analiz et, nelere öncelik vermeliyim?") },
        { icon: "chart", text: qsTr("Sınav gidişatım"),
          prompt: qsTr("Deneme sınavlarındaki gidişatımı yorumla: nerede iyiyim, nereye çalışmalıyım?") },
        { icon: "calendar", text: qsTr("Yarına hazırlık"),
          prompt: qsTr("Yarın için neye hazırlanmalıyım? Dersler ve teslim edeceğim ödevlere göre kısa bir plan yap.") },
    ]

    function ask(text) {
        if (busy)
            return
        messages.append({ role: "user", text: text, failed: false })
        messages.append({ role: "assistant", text: "", failed: false })
        busy = true
        App.ask(text)
    }
    function reset() {
        messages.clear()
        App.resetChat()
    }

    ListModel { id: messages }

    Connections {
        target: App
        function onAssistantDelta(piece) {
            const i = messages.count - 1
            messages.setProperty(i, "text", messages.get(i).text + piece)
        }
        function onAssistantDone() { page.busy = false }
        function onAssistantFailed(message) {
            const i = messages.count - 1
            messages.setProperty(i, "text", message)
            messages.setProperty(i, "failed", true)
            page.busy = false
        }
    }

    // --- Karşılama
    ColumnLayout {
        visible: page.empty
        width: Math.min(parent.width - 48, Theme.contentWidth - 50)
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -40
        spacing: 16

        Image {
            Layout.alignment: Qt.AlignHCenter
            source: "logo.png"
            sourceSize: Qt.size(56, 56)
            Layout.preferredWidth: 56
            Layout.preferredHeight: 56
            Accessible.ignored: true
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("Nasıl yardımcı olabilirim?")
            font.family: Theme.font
            font.pixelSize: Theme.fontDisplay
            font.weight: Font.DemiBold
            color: Theme.text
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("Dersler, ödevler, sınav sonuçları ve yemek listesi hakkında soru sorabilirsin.")
            font.family: Theme.font
            font.pixelSize: Theme.fontBody
            color: Theme.textMuted
        }
        Composer {
            Layout.fillWidth: true
            Layout.topMargin: 12
            large: true
            busy: page.busy
            onSubmitted: text => page.ask(text)
        }
        Flow {
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: page.suggestions
                delegate: AbstractButton {
                    id: chip
                    required property var modelData
                    implicitHeight: 36
                    implicitWidth: chipRow.implicitWidth + 30
                    hoverEnabled: true
                    Accessible.name: modelData.text
                    onClicked: page.ask(modelData.prompt)
                    background: Rectangle {
                        radius: height / 2
                        color: chip.hovered ? Theme.hover : "transparent"
                        border.width: 1
                        border.color: Theme.border
                    }
                    contentItem: Item {
                        Row {
                            id: chipRow
                            anchors.centerIn: parent
                            spacing: 8
                            Icon { name: chip.modelData.icon; size: 15; color: Theme.textMuted; anchors.verticalCenter: parent.verticalCenter }
                            Text {
                                text: chip.modelData.text
                                font.family: Theme.font
                                font.pixelSize: Theme.fontUi
                                color: Theme.text
                                anchors.verticalCenter: parent.verticalCenter
                            }
                        }
                    }
                }
            }
        }
    }

    // --- Sohbet
    ColumnLayout {
        visible: !page.empty
        anchors.fill: parent
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 12
            Item { Layout.fillWidth: true }
            OButton {
                text: qsTr("Yeni sohbet")
                iconName: "plus"
                variant: "ghost"
                enabled: !page.busy
                onClicked: page.reset()
            }
        }

        ListView {
            id: chat
            Layout.fillWidth: true
            Layout.fillHeight: true
            model: messages
            spacing: 18
            clip: true
            bottomMargin: 16
            onCountChanged: positionViewAtEnd()
            delegate: ChatMessage {
                width: Math.min(chat.width - 48, Theme.contentWidth - 50)
                x: (chat.width - width) / 2
                onTextChanged: chat.positionViewAtEnd()
            }
        }

        Composer {
            Layout.fillWidth: true
            Layout.maximumWidth: Theme.contentWidth - 50
            Layout.alignment: Qt.AlignHCenter
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            busy: page.busy
            onSubmitted: text => page.ask(text)
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 8
            Layout.bottomMargin: 12
            text: qsTr("Asistan hata yapabilir. Önemli bilgileri OBS'den kontrol et.")
            font.family: Theme.font
            font.pixelSize: Theme.fontCaption
            color: Theme.textFaint
        }
    }
}
