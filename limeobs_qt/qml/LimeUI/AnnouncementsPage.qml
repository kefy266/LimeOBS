import QtQuick
import QtQuick.Layouts

PageScaffold {
    id: page
    pageName: "announcements"
    title: qsTr("Duyuru ve Etkinlikler")

    SectionCard {
        title: qsTr("Duyurular")
        iconName: "info"
        Repeater {
            model: page.ready ? page.pageData.announcements : []
            delegate: ColumnLayout {
                id: ann
                required property var modelData
                required property int index
                Layout.fillWidth: true
                Layout.topMargin: ann.index > 0 ? 10 : 0
                spacing: 4
                Rectangle { visible: ann.index > 0; Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.border }
                Text {
                    Layout.fillWidth: true
                    text: ann.modelData.title
                    wrapMode: Text.WordWrap
                    font.family: Theme.font
                    font.pixelSize: Theme.fontUi
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                Text {
                    visible: text.length > 0
                    text: ann.modelData.date
                    font.family: Theme.font
                    font.pixelSize: Theme.fontCaption
                    color: Theme.textFaint
                }
                Text {
                    visible: text.length > 0
                    Layout.fillWidth: true
                    text: ann.modelData.body
                    wrapMode: Text.WordWrap
                    font.family: Theme.font
                    font.pixelSize: Theme.fontUi
                    color: Theme.textMuted
                }
            }
        }
        EmptyText {
            visible: page.ready && page.pageData.announcements.length === 0
            text: qsTr("Yeni duyuru yok.")
        }
    }

    SectionCard {
        title: qsTr("Etkinlikler")
        iconName: "calendar"
        Repeater {
            model: page.ready ? page.pageData.events : []
            delegate: ListRow {
                required property var modelData
                required property int index
                showDivider: index > 0
                lead: modelData.date
                title: modelData.title
                subtitle: modelData.place
            }
        }
        EmptyText {
            visible: page.ready && page.pageData.events.length === 0
            text: qsTr("Planlanmış etkinlik yok.")
        }
    }
}
