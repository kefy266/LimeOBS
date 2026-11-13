import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import LimeBackend

// Sayfa iskeleti: ortalanmış sütun, başlık + yenile, yükleniyor/hata durumları.
// Sayfa verisi App.page(pageName) ile alınır ve App.dataChanged ile tazelenir.
Item {
    id: root
    property string title
    property string subtitle
    property string pageName
    property var pageData: null
    default property alias content: column.data

    readonly property bool loading: App.loadingPages.indexOf(pageName) >= 0
    readonly property string errorText: pageData && pageData.error ? pageData.error : ""
    readonly property bool ready: pageData !== null && pageData !== undefined && !errorText

    function load() {
        pageData = App.page(pageName) || null
        if (pageData === null)
            App.refresh(pageName)
    }

    onVisibleChanged: if (visible) load()
    Component.onCompleted: if (visible) load()

    Connections {
        target: App
        function onDataChanged(name) {
            if (name === root.pageName)
                root.pageData = App.page(name)
        }
    }

    ScrollView {
        id: scroller
        anchors.fill: parent
        contentWidth: availableWidth
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            width: Math.min(scroller.availableWidth - 48, Theme.contentWidth)
            x: (scroller.availableWidth - width) / 2
            spacing: 18

            Item { Layout.preferredHeight: 18 }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        text: root.title
                        font.family: Theme.font
                        font.pixelSize: Theme.fontHeading
                        font.weight: Font.DemiBold
                        color: Theme.text
                    }
                    Text {
                        visible: text.length > 0
                        text: root.subtitle
                        font.family: Theme.font
                        font.pixelSize: Theme.fontSmall
                        color: Theme.textMuted
                    }
                }
                Spinner { visible: root.loading }
                IconButton {
                    iconName: "refresh"
                    tip: qsTr("Yenile")
                    enabled: !root.loading
                    onClicked: App.refresh(root.pageName)
                }
            }

            Rectangle {
                Layout.fillWidth: true
                visible: root.errorText.length > 0
                Layout.preferredHeight: errText.implicitHeight + 24
                radius: Theme.radius
                color: Theme.dangerSoft
                Text {
                    id: errText
                    anchors.fill: parent
                    anchors.margins: 12
                    text: root.errorText
                    wrapMode: Text.WordWrap
                    font.family: Theme.font
                    font.pixelSize: Theme.fontUi
                    color: Theme.danger
                }
            }

            ColumnLayout {
                id: column
                Layout.fillWidth: true
                visible: root.ready
                spacing: 14
            }

            Item { Layout.preferredHeight: 24 }
        }
    }
}
