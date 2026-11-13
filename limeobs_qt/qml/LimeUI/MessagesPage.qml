import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import LimeBackend

PageScaffold {
    id: page
    pageName: "messages"
    title: qsTr("Gelen Kutusu")
    subtitle: ready ? qsTr("%1 mesaj").arg(pageData.inbox.length) : ""

    property string box: "inbox"
    property var openMail: null
    onOpenMailChanged: openMail ? reader.open() : reader.close()
    onVisibleChanged: if (!visible) openMail = null

    Connections {
        target: App
        function onDataChanged(name) {
            if (name === "mail")
                page.openMail = App.page("mail")
        }
    }

    Segmented {
        model: [{ value: "inbox", label: qsTr("Gelen") }, { value: "sent", label: qsTr("Gönderilen") }]
        value: page.box
        onPicked: v => { page.box = v; page.openMail = null }
    }

    SectionCard {
        id: list
        readonly property var items: page.ready ? page.pageData[page.box] : []
        Repeater {
            model: list.items
            delegate: ListRow {
                id: mailRow
                required property var modelData
                required property int index
                showDivider: index > 0
                lead: modelData.date
                title: modelData.title
                subtitle: modelData.who + (modelData.preview ? " — " + modelData.preview : "")
                highlight: modelData.unread
                trailing: modelData.unread ? qsTr("Yeni") : ""
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        page.openMail = { title: mailRow.modelData.title, who: mailRow.modelData.who, body: qsTr("Yükleniyor…") }
                        App.openMail(mailRow.modelData.id)
                    }
                }
            }
        }
        EmptyText {
            visible: list.items.length === 0
            text: qsTr("Mesaj yok.")
        }
    }

    Popup {
        id: reader
        parent: Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(640, parent.width - 48)
        height: Math.min(560, parent.height - 48)
        modal: true
        onClosed: page.openMail = null
        padding: 22
        background: Rectangle {
            radius: Theme.radiusLg
            color: Theme.elevated
            border.width: 1
            border.color: Theme.border
        }
        contentItem: ColumnLayout {
            spacing: 10
            RowLayout {
                Layout.fillWidth: true
                Text {
                    Layout.fillWidth: true
                    text: page.openMail ? page.openMail.title : ""
                    wrapMode: Text.WordWrap
                    font.family: Theme.font
                    font.pixelSize: Theme.fontTitle
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                IconButton { iconName: "x"; tip: qsTr("Kapat"); onClicked: reader.close() }
            }
            Text {
                text: page.openMail ? page.openMail.who : ""
                font.family: Theme.font
                font.pixelSize: Theme.fontSmall
                color: Theme.textMuted
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                TextArea {
                    readOnly: true
                    text: page.openMail ? page.openMail.body : ""
                    wrapMode: TextArea.Wrap
                    font.family: Theme.font
                    font.pixelSize: Theme.fontBody
                    color: Theme.text
                    background: null
                }
            }
        }
    }
}
