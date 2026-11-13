import QtQuick
import QtQuick.Layouts

PageScaffold {
    id: page
    pageName: "schedule"
    title: qsTr("Ders Programı")
    subtitle: qsTr("Bu haftanın dersleri")

    Repeater {
        model: page.ready ? page.pageData.days : []
        delegate: SectionCard {
            id: day
            required property var modelData
            title: modelData.name
            badge: modelData.isToday ? qsTr("Bugün • %1").arg(modelData.date) : modelData.date
            iconName: modelData.isToday ? "sparkle" : "calendar"
            border.color: modelData.isToday ? Theme.accent : Theme.border
            Repeater {
                model: day.modelData.lessons
                delegate: ListRow {
                    required property var modelData
                    required property int index
                    showDivider: index > 0
                    lead: modelData.time
                    title: modelData.lesson
                    subtitle: modelData.teacher
                }
            }
            EmptyText {
                visible: day.modelData.lessons.length === 0
                text: qsTr("Ders yok.")
            }
        }
    }
}
