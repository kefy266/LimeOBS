import QtQuick
import QtQuick.Layouts

PageScaffold {
    id: page
    pageName: "attendance"
    title: qsTr("Devamsızlık")
    subtitle: ready ? pageData.period : ""

    function count(name) {
        const c = ready ? pageData.counts.find(x => x.name === name) : null
        return c ? c.value : 0
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 12
        StatTile { label: qsTr("Geldi"); value: String(page.count("Geldi")); note: qsTr("ders saati") }
        StatTile { label: qsTr("Özürsüz"); value: String(page.count("Gelmedi (Özürsüz)")) }
        StatTile { label: qsTr("Özürlü"); value: String(page.count("Gelmedi (Özürlü)")) }
        StatTile { label: qsTr("Geç geldi"); value: String(page.count("Geç geldi")) }
    }

    SectionCard {
        title: qsTr("Devamsızlık kayıtları")
        iconName: "list"
        Repeater {
            model: page.ready ? page.pageData.absences : []
            delegate: ListRow {
                required property var modelData
                required property int index
                showDivider: index > 0
                lead: modelData.date
                title: modelData.lesson + (modelData.no ? qsTr(" (%1. ders)").arg(modelData.no) : "")
                subtitle: modelData.teacher + (modelData.note ? " — " + modelData.note : "")
                trailing: modelData.kind
            }
        }
        EmptyText {
            visible: page.ready && page.pageData.absences.length === 0
            text: qsTr("Bu dönem hiç devamsızlığın yok 🎉")
        }
    }

    SectionCard {
        visible: page.ready && page.pageData.lessons.length > 0
        title: qsTr("Ders bazında katılım")
        iconName: "book"
        Repeater {
            model: page.ready ? page.pageData.lessons : []
            delegate: LessonBar {
                required property var modelData
                required property int index
                showDivider: index > 0
                name: modelData.name
                value: "%" + Math.round(modelData.rate)
                ratio: modelData.rate / 100
            }
        }
    }

    SectionCard {
        visible: page.ready && page.pageData.teachers.length > 0
        title: qsTr("Öğretmen bazında katılım")
        iconName: "user"
        Repeater {
            model: page.ready ? page.pageData.teachers : []
            delegate: LessonBar {
                required property var modelData
                required property int index
                showDivider: index > 0
                name: modelData.name
                value: "%" + Math.round(modelData.rate)
                ratio: modelData.rate / 100
            }
        }
    }
}
