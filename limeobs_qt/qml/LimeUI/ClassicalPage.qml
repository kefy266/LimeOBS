import QtQuick
import QtQuick.Layouts
import LimeBackend

PageScaffold {
    id: page
    pageName: "classical"
    title: qsTr("Yazılı Sınavlar")
    subtitle: qsTr("Dönem yazılı ve sözlü notların")

    property string period: "period1"

    RowLayout {
        Layout.fillWidth: true
        Segmented {
            model: [{ value: "period1", label: qsTr("1. Dönem") }, { value: "period2", label: qsTr("2. Dönem") }]
            value: page.period
            onPicked: v => page.period = v
        }
        Item { Layout.fillWidth: true }
        OButton {
            visible: page.ready && page.pageData.calendarUrl.length > 0
            text: qsTr("Sınav takvimini aç")
            iconName: "calendar"
            onClicked: App.openUrl(page.pageData.calendarUrl)
        }
    }

    SectionCard {
        readonly property var rows: page.ready ? page.pageData[page.period] : []
        id: grades
        title: qsTr("Notlar")
        iconName: "book"
        Repeater {
            model: grades.rows
            delegate: ListRow {
                required property var modelData
                required property int index
                showDivider: index > 0
                title: modelData.lesson
                subtitle: qsTr("1. yazılı %1 • 2. yazılı %2 • 3. yazılı %3 • Sözlü %4")
                          .arg(modelData.e1).arg(modelData.e2).arg(modelData.e3).arg(modelData.oral)
                trailing: qsTr("Ort. %1").arg(modelData.avg)
            }
        }
        EmptyText {
            visible: grades.rows.length === 0
            text: page.ready && page.pageData.message ? page.pageData.message : qsTr("Bu dönem için not girilmemiş.")
        }
    }
}
