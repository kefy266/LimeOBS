import QtQuick
import QtQuick.Layouts

PageScaffold {
    id: page
    pageName: "homework"
    title: qsTr("Ödevler")
    subtitle: ready ? qsTr("%1 ödev bekliyor").arg(pageData.pending.length) : ""

    property string tab: "pending"

    Segmented {
        model: [{ value: "pending", label: qsTr("Bekleyen") }, { value: "past", label: qsTr("Geçmiş") }]
        value: page.tab
        onPicked: v => page.tab = v
    }

    SectionCard {
        id: list
        readonly property var items: page.ready ? page.pageData[page.tab] : []
        Repeater {
            model: list.items
            delegate: ListRow {
                id: hwRow
                required property var modelData
                required property int index
                showDivider: index > 0
                lead: modelData.end
                title: modelData.title
                subtitle: modelData.lesson + (modelData.teacher ? " • " + modelData.teacher : "")
                trailing: page.tab === "pending" ? modelData.due : modelData.status
                highlight: page.tab === "pending" && modelData.daysLeft <= 1
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: detail.show(hwRow.modelData.id, hwRow.modelData.title)
                }
            }
        }
        EmptyText {
            visible: list.items.length === 0
            text: page.tab === "pending" ? qsTr("Bekleyen ödev yok 🎉") : qsTr("Geçmiş ödev yok.")
        }
    }

    HomeworkDetail { id: detail }
}
