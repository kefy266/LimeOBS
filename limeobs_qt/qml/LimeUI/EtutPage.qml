import QtQuick
import QtQuick.Layouts

PageScaffold {
    id: page
    pageName: "etut"
    title: qsTr("Etüt ve Birebir")
    subtitle: qsTr("Kayıtlı etüt, birebir ve rehberlik görüşmelerin")

    RowLayout {
        Layout.fillWidth: true
        spacing: 12
        StatTile { label: qsTr("Etüt (bu ay)"); value: page.ready ? String(page.pageData.etutMonth) : "" }
        StatTile { label: qsTr("Etüt (bu yıl)"); value: page.ready ? String(page.pageData.etutYear) : "" }
        StatTile { label: qsTr("Birebir (bu ay)"); value: page.ready ? String(page.pageData.birebirMonth) : "" }
        StatTile { label: qsTr("Birebir (bu yıl)"); value: page.ready ? String(page.pageData.birebirYear) : "" }
    }

    SectionCard {
        title: qsTr("Kayıtların")
        iconName: "calendar"
        Repeater {
            model: page.ready ? page.pageData.items : []
            delegate: ListRow {
                required property var modelData
                required property int index
                showDivider: index > 0
                lead: modelData.date
                title: modelData.lesson + (modelData.teacher ? " — " + modelData.teacher : "")
                subtitle: modelData.time + (modelData.place ? " • " + modelData.place : "")
                trailing: modelData.kind
            }
        }
        EmptyText {
            visible: page.ready && page.pageData.items.length === 0
            text: qsTr("Kayıtlı etüt veya birebir dersin yok.")
        }
    }
}
