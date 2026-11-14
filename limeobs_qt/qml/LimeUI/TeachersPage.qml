import QtQuick
import QtQuick.Layouts

PageScaffold {
    id: page
    pageName: "teachers"
    title: qsTr("Öğretmenlerim")
    subtitle: ready ? qsTr("%1 öğretmen").arg(pageData.teachers.length) : ""

    SectionCard {
        Repeater {
            model: page.ready ? page.pageData.teachers : []
            delegate: Item {
                id: teacherRow
                required property var modelData
                required property int index
                Layout.fillWidth: true
                implicitHeight: row.implicitHeight + 16
                Rectangle {
                    visible: teacherRow.index > 0
                    width: parent.width
                    height: 1
                    color: Theme.border
                }
                RowLayout {
                    id: row
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 12
                    Rectangle {
                        Layout.preferredWidth: 34
                        Layout.preferredHeight: 34
                        radius: 17
                        color: Theme.accentSoft
                        Text {
                            anchors.centerIn: parent
                            text: teacherRow.modelData.name.slice(0, 1)
                            font.family: Theme.font
                            font.pixelSize: Theme.fontUi
                            font.weight: Font.DemiBold
                            color: Theme.accent
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        Text {
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                            text: teacherRow.modelData.name
                            font.family: Theme.font
                            font.pixelSize: Theme.fontUi
                            color: Theme.text
                        }
                        Text {
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                            text: teacherRow.modelData.lesson
                            font.family: Theme.font
                            font.pixelSize: Theme.fontSmall
                            color: Theme.textMuted
                        }
                    }
                    OButton {
                        text: qsTr("Mesaj gönder")
                        iconName: "mail"
                        variant: "ghost"
                        onClicked: compose.openFor(teacherRow.modelData.name, "")
                    }
                }
            }
        }
    }

    ComposeDialog { id: compose }
}
