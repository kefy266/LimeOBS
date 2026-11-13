import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Tek sınavın karnesi: genel sonuç, sıralamalar ve ders bazında doğru/yanlış/boş/net.
Popup {
    id: root
    property var exam: null
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(620, parent ? parent.width - 48 : 620)
    height: Math.min(contentItem.implicitHeight + 44, parent ? parent.height - 48 : 600)
    modal: true
    onExamChanged: exam ? open() : close()
    padding: 22
    background: Rectangle {
        radius: Theme.radiusLg
        color: Theme.elevated
        border.width: 1
        border.color: Theme.border
    }

    function fmt(v) { return Number(v).toFixed(2).replace(/\.?0+$/, "").replace(".", ",") }

    contentItem: ColumnLayout {
        spacing: 12
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    Layout.fillWidth: true
                    text: root.exam ? root.exam.name : ""
                    wrapMode: Text.WordWrap
                    font.family: Theme.font
                    font.pixelSize: Theme.fontTitle
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                Text {
                    text: root.exam ? root.exam.date : ""
                    font.family: Theme.font
                    font.pixelSize: Theme.fontSmall
                    color: Theme.textMuted
                }
            }
            IconButton { iconName: "x"; tip: qsTr("Kapat"); onClicked: root.close() }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 4
            columnSpacing: 10
            StatTile { label: qsTr("Puan"); value: root.exam ? root.fmt(root.exam.point) : "" }
            StatTile { label: qsTr("Net"); value: root.exam ? root.fmt(root.exam.net) : "" }
            StatTile {
                label: qsTr("Sınıf sırası")
                value: root.exam && root.exam.classRank ? String(root.exam.classRank) : "–"
            }
            StatTile {
                label: qsTr("Okul sırası")
                value: root.exam && root.exam.schoolRank ? String(root.exam.schoolRank) : "–"
            }
        }

        Repeater {
            model: root.exam ? root.exam.lessons : []
            delegate: LessonBar {
                required property var modelData
                required property int index
                showDivider: index > 0
                name: modelData.name
                detail: qsTr("%1 soru • D %2 • Y %3 • B %4").arg(modelData.q).arg(modelData.d).arg(modelData.y).arg(modelData.b)
                value: root.fmt(modelData.net)
                ratio: modelData.q ? modelData.d / modelData.q : 0
            }
        }
        EmptyText {
            visible: root.exam !== null && root.exam.lessons.length === 0
            text: qsTr("Bu sınavın ders bazında karnesi henüz yayınlanmamış.")
        }
    }
}
