import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import LimeBackend

// Ödev ayrıntısı: açıklama, öğretmen yorumu ve ek dosyalar.
Popup {
    id: root
    property var detail: null
    property int homeworkId: 0

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(640, parent ? parent.width - 48 : 640)
    height: Math.min(contentItem.implicitHeight + 44, parent ? parent.height - 48 : 600)
    modal: true
    padding: 22
    background: Rectangle {
        radius: Theme.radiusLg
        color: Theme.elevated
        border.width: 1
        border.color: Theme.border
    }

    function show(hwId, title) {
        homeworkId = hwId
        detail = { title: title, lesson: "", teacher: "", end: "", status: "", comment: "", body: qsTr("Yükleniyor…"), files: [] }
        App.openHomework(hwId)
        open()
    }

    Connections {
        target: App
        function onDataChanged(name) {
            if (name === "homeworkDetail" && App.page(name).id === root.homeworkId)
                root.detail = App.page(name)
        }
    }

    contentItem: ColumnLayout {
        spacing: 10
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    Layout.fillWidth: true
                    text: root.detail ? root.detail.title : ""
                    wrapMode: Text.WordWrap
                    font.family: Theme.font
                    font.pixelSize: Theme.fontTitle
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                Text {
                    text: root.detail ? [root.detail.lesson, root.detail.teacher, root.detail.end ? qsTr("Teslim %1").arg(root.detail.end) : ""]
                                        .filter(x => x).join(" • ") : ""
                    font.family: Theme.font
                    font.pixelSize: Theme.fontSmall
                    color: Theme.textMuted
                }
            }
            IconButton { iconName: "x"; tip: qsTr("Kapat"); onClicked: root.close() }
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(bodyText.implicitHeight + 8, 260)
            TextArea {
                id: bodyText
                readOnly: true
                text: root.detail ? (root.detail.body || qsTr("Açıklama yok.")) : ""
                wrapMode: TextArea.Wrap
                color: Theme.text
                font.family: Theme.font
                font.pixelSize: Theme.fontUi
                background: null
                leftPadding: 0
            }
        }

        Rectangle {
            visible: root.detail !== null && root.detail.comment.length > 0
            Layout.fillWidth: true
            implicitHeight: commentText.implicitHeight + 20
            radius: Theme.radius
            color: Theme.accentSoft
            Text {
                id: commentText
                anchors.fill: parent
                anchors.margins: 10
                text: root.detail ? qsTr("Öğretmen yorumu: %1").arg(root.detail.comment) : ""
                wrapMode: Text.WordWrap
                font.family: Theme.font
                font.pixelSize: Theme.fontUi
                color: Theme.text
            }
        }

        Flow {
            visible: root.detail !== null && root.detail.files.length > 0
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: root.detail ? root.detail.files : []
                delegate: OButton {
                    required property var modelData
                    text: modelData.name
                    iconName: "file"
                    onClicked: App.openHomeworkFile(root.homeworkId, modelData)
                }
            }
        }
    }
}
