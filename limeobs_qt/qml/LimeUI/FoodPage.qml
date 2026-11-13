import QtQuick
import QtQuick.Layouts

PageScaffold {
    id: page
    pageName: "food"
    title: qsTr("Yemek Listesi")
    subtitle: qsTr("Okulun aylık menüsü")

    property int week: -1
    readonly property var weeks: ready ? pageData.weeks : []
    readonly property int shownWeek: week >= 0 && week < weeks.length ? week : (ready ? pageData.current : 0)

    Segmented {
        visible: page.weeks.length > 1
        model: page.weeks.map((w, i) => ({ value: String(i), label: w.title }))
        value: String(page.shownWeek)
        onPicked: v => page.week = Number(v)
    }

    Repeater {
        model: page.weeks.length ? page.weeks[page.shownWeek].days : []
        delegate: SectionCard {
            id: day
            required property var modelData
            title: modelData.date
            badge: modelData.isToday ? qsTr("Bugün") : ""
            iconName: "food"
            border.color: modelData.isToday ? Theme.accent : Theme.border
            Text {
                Layout.fillWidth: true
                text: day.modelData.meals.join(" • ")
                wrapMode: Text.WordWrap
                lineHeight: 1.3
                font.family: Theme.font
                font.pixelSize: Theme.fontUi
                color: Theme.text
            }
        }
    }

    EmptyText {
        visible: page.weeks.length === 0
        text: qsTr("Bu ayın yemek listesi henüz yayınlanmamış.")
    }
}
