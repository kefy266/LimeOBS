import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import LimeBackend

PageScaffold {
    id: page
    pageName: "library"
    title: qsTr("Kütüphane")
    subtitle: qsTr("Ödünç aldığın kitaplar ve okul kataloğu")

    property var search: null

    Connections {
        target: App
        function onDataChanged(name) {
            if (name === "librarySearch")
                page.search = App.page("librarySearch")
        }
    }

    SectionCard {
        title: qsTr("Ödünç aldıkların")
        iconName: "book"
        Repeater {
            model: page.ready ? page.pageData.books : []
            delegate: ListRow {
                required property var modelData
                required property int index
                showDivider: index > 0
                title: modelData.name
                subtitle: (modelData.author ? modelData.author + " • " : "") + qsTr("Alış %1").arg(modelData.borrowed)
                trailing: modelData.done ? qsTr("Teslim edildi") : qsTr("İade: %1").arg(modelData.returned || "–")
                highlight: !modelData.done
            }
        }
        EmptyText {
            visible: page.ready && page.pageData.books.length === 0
            text: qsTr("Şu an ödünç aldığın kitap yok.")
        }
    }

    SectionCard {
        title: qsTr("Katalogda ara")
        iconName: "search"
        TextField {
            id: query
            Layout.fillWidth: true
            implicitHeight: 40
            leftPadding: 12
            placeholderText: qsTr("Kitap adı ya da yazar…")
            placeholderTextColor: Theme.textFaint
            color: Theme.text
            font.family: Theme.font
            font.pixelSize: Theme.fontUi
            background: Rectangle {
                radius: Theme.radiusSm + 2
                color: Theme.surfaceAlt
                border.width: 1
                border.color: query.activeFocus ? Theme.accent : Theme.border
            }
            onTextEdited: searchDelay.restart()
            onAccepted: App.searchLibrary(text)
        }
        Timer {
            id: searchDelay
            interval: 450
            onTriggered: App.searchLibrary(query.text)
        }
        Repeater {
            model: page.search && page.search.query === query.text ? page.search.results : []
            delegate: ListRow {
                required property var modelData
                required property int index
                showDivider: true
                title: modelData.name
                subtitle: modelData.author
                trailing: modelData.available
            }
        }
        EmptyText {
            visible: page.search !== null && page.search.query === query.text && query.text.length > 0
                     && page.search.results.length === 0
            Layout.topMargin: 8
            text: qsTr("Sonuç bulunamadı.")
        }
    }
}
