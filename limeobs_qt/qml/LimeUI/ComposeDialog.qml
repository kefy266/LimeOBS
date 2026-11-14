import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import LimeBackend

// Öğretmene / yöneticiye mesaj yazma ve yanıtlama penceresi.
Popup {
    id: root
    property var receiver: null        // {name, userType, userId}
    property string replyId: ""
    property var results: []
    property string status: ""
    property bool sending: false
    property bool sent: false

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(560, parent ? parent.width - 48 : 560)
    modal: true
    padding: 22
    background: Rectangle {
        radius: Theme.radiusLg
        color: Theme.elevated
        border.width: 1
        border.color: Theme.border
    }

    // name: aranacak alıcı adı; receiverData verilirse (yanıt) arama yapılmaz
    function openFor(name, reply, receiverData, subject) {
        replyId = reply || ""
        receiver = receiverData || null
        status = ""
        sent = false
        results = []
        search.text = receiverData ? "" : name
        title.text = subject || ""
        body.text = ""
        if (!receiverData && name)
            App.searchReceivers(name)
        open()
        (receiverData ? body : title).forceActiveFocus()
    }

    Connections {
        target: App
        function onDataChanged(name) {
            if (name === "receivers") {
                const r = App.page("receivers")
                if (r.query !== search.text)
                    return
                root.results = r.results
                if (!root.receiver && r.results.length === 1)
                    root.receiver = r.results[0]
            } else if (name === "mailSent" && root.opened) {
                const r = App.page("mailSent")
                root.sending = false
                root.sent = r.ok
                root.status = r.message
                if (r.ok)
                    closeTimer.start()
            }
        }
    }
    Timer { id: closeTimer; interval: 1200; onTriggered: root.close() }

    component Field: TextField {
        id: field
        Layout.fillWidth: true
        implicitHeight: 40
        leftPadding: 12
        color: Theme.text
        placeholderTextColor: Theme.textFaint
        font.family: Theme.font
        font.pixelSize: Theme.fontUi
        background: Rectangle {
            radius: Theme.radiusSm + 2
            color: Theme.surfaceAlt
            border.width: 1
            border.color: field.activeFocus ? Theme.accent : Theme.border
        }
    }

    contentItem: ColumnLayout {
        spacing: 10
        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: root.replyId ? qsTr("Yanıtla") : qsTr("Yeni mesaj")
                font.family: Theme.font
                font.pixelSize: Theme.fontTitle
                font.weight: Font.DemiBold
                color: Theme.text
            }
            IconButton { iconName: "x"; tip: qsTr("Kapat"); onClicked: root.close() }
        }

        // Alıcı
        Rectangle {
            visible: root.receiver !== null
            Layout.fillWidth: true
            implicitHeight: 40
            radius: Theme.radiusSm + 2
            color: Theme.accentSoft
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 4
                Text {
                    Layout.fillWidth: true
                    text: root.receiver ? qsTr("Alıcı: %1").arg(root.receiver.name) : ""
                    elide: Text.ElideRight
                    font.family: Theme.font
                    font.pixelSize: Theme.fontUi
                    color: Theme.text
                }
                IconButton {
                    visible: !root.replyId
                    iconName: "x"
                    tip: qsTr("Alıcıyı değiştir")
                    onClicked: root.receiver = null
                }
            }
        }
        Field {
            id: search
            visible: root.receiver === null
            placeholderText: qsTr("Alıcı ara (öğretmen ya da yönetici adı)…")
            onTextEdited: searchDelay.restart()
        }
        Timer { id: searchDelay; interval: 400; onTriggered: App.searchReceivers(search.text) }
        Repeater {
            model: root.receiver === null ? root.results : []
            delegate: ListRow {
                id: result
                required property var modelData
                required property int index
                showDivider: index > 0
                title: modelData.name
                subtitle: modelData.type
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.receiver = result.modelData
                }
            }
        }

        Field { id: title; placeholderText: qsTr("Konu") }
        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: 160
            TextArea {
                id: body
                placeholderText: qsTr("Mesajın…")
                placeholderTextColor: Theme.textFaint
                wrapMode: TextArea.Wrap
                color: Theme.text
                font.family: Theme.font
                font.pixelSize: Theme.fontUi
                background: Rectangle {
                    radius: Theme.radiusSm + 2
                    color: Theme.surfaceAlt
                    border.width: 1
                    border.color: body.activeFocus ? Theme.accent : Theme.border
                }
            }
        }
        Text {
            visible: root.status.length > 0
            Layout.fillWidth: true
            text: root.status
            wrapMode: Text.WordWrap
            font.family: Theme.font
            font.pixelSize: Theme.fontSmall
            color: root.sent ? Theme.accent : Theme.danger
        }
        OButton {
            Layout.alignment: Qt.AlignRight
            variant: "primary"
            iconName: "arrow-up"
            text: root.sending ? qsTr("Gönderiliyor…") : qsTr("Gönder")
            enabled: !root.sending && !root.sent && root.receiver !== null
                     && title.text.trim().length > 0 && body.text.trim().length > 0
            onClicked: {
                root.status = ""
                root.sending = true
                App.sendMail(title.text, body.text, root.receiver.userType, root.receiver.userId, root.replyId)
            }
        }
    }
}
