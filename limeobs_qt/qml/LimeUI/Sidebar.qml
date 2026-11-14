import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import LimeBackend

// Sol sütun: logo, gezinme ve hesap satırı (Orbital kenar çubuğu).
Rectangle {
    id: root
    property string current: "home"
    signal navigate(string page)
    signal collapse()

    readonly property var items: [
        { page: "home", icon: "home", label: qsTr("Ana Sayfa") },
        { page: "assistant", icon: "sparkle", label: qsTr("Asistan") },
        { page: "schedule", icon: "calendar", label: qsTr("Ders Programı") },
        { page: "etut", icon: "clock", label: qsTr("Etüt ve Birebir") },
        { page: "attendance", icon: "check", label: qsTr("Devamsızlık") },
        { page: "homework", icon: "book", label: qsTr("Ödevler") },
        { page: "classical", icon: "pencil", label: qsTr("Yazılı Sınavlar") },
        { page: "exams", icon: "chart", label: qsTr("Deneme Sınavları") },
        { page: "food", icon: "food", label: qsTr("Yemek Listesi") },
        { page: "library", icon: "list", label: qsTr("Kütüphane") },
        { page: "announcements", icon: "info", label: qsTr("Duyuru ve Etkinlik") },
        { page: "teachers", icon: "user", label: qsTr("Öğretmenlerim") },
        { page: "messages", icon: "mail", label: qsTr("Gelen Kutusu") },
    ]

    color: Theme.sidebar

    Rectangle {
        anchors.right: parent.right
        width: 1
        height: parent.height
        color: Theme.border
    }

    component NavRow: AbstractButton {
        id: nav
        property string iconName
        property bool active: false
        Layout.fillWidth: true
        implicitHeight: 34
        hoverEnabled: true
        Accessible.role: Accessible.PageTab
        Accessible.name: text
        background: Rectangle {
            radius: Theme.radiusSm
            color: nav.active ? Theme.selected : nav.hovered ? Theme.hover : "transparent"
        }
        contentItem: RowLayout {
            spacing: 10
            Icon { Layout.leftMargin: 10; name: nav.iconName; size: 17; color: nav.active ? Theme.accent : Theme.textMuted }
            Text {
                Layout.fillWidth: true
                text: nav.text
                font.family: Theme.font
                font.pixelSize: Theme.fontUi
                font.weight: nav.active ? Font.Medium : Font.Normal
                color: Theme.text
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        anchors.rightMargin: 11
        spacing: 2

        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 6
            Layout.bottomMargin: 10
            spacing: 9
            Image {
                source: "logo.png"
                sourceSize: Qt.size(22, 22)
                Layout.preferredWidth: 22
                Layout.preferredHeight: 22
                Accessible.ignored: true
            }
            Text {
                Layout.fillWidth: true
                text: "LimeOBS"
                font.family: Theme.font
                font.pixelSize: Theme.fontTitle
                font.weight: Font.DemiBold
                color: Theme.text
            }
            IconButton { iconName: "sidebar"; tip: qsTr("Kenar çubuğunu gizle"); onClicked: root.collapse() }
        }

        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentHeight: navColumn.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            clip: contentHeight > height
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            ColumnLayout {
                id: navColumn
                width: parent.width
                spacing: 2
                Repeater {
                    model: root.items
                    delegate: NavRow {
                        required property var modelData
                        text: modelData.label
                        iconName: modelData.icon
                        active: root.current === modelData.page
                        onClicked: root.navigate(modelData.page)
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            Layout.leftMargin: 10
            Layout.bottomMargin: 6
            text: App.profile.school ? App.profile.school + (App.profile.term ? " • " + App.profile.term : "") : ""
            elide: Text.ElideRight
            font.family: Theme.font
            font.pixelSize: Theme.fontCaption
            color: Theme.textFaint
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 4

            AbstractButton {
                id: account
                Layout.fillWidth: true
                implicitHeight: 46
                hoverEnabled: true
                Accessible.name: qsTr("Profil")
                onClicked: root.navigate("profile")
                background: Rectangle {
                    radius: Theme.radiusSm
                    color: root.current === "profile" ? Theme.selected : account.hovered ? Theme.hover : "transparent"
                }
                contentItem: RowLayout {
                    spacing: 10
                    Avatar {
                        Layout.leftMargin: 6
                        size: 30
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Text {
                            Layout.fillWidth: true
                            text: App.profile.name || qsTr("Yükleniyor…")
                            elide: Text.ElideRight
                            font.family: Theme.font
                            font.pixelSize: Theme.fontUi
                            color: Theme.text
                        }
                        Text {
                            Layout.fillWidth: true
                            text: App.profile.subtitle || ""
                            elide: Text.ElideRight
                            font.family: Theme.font
                            font.pixelSize: Theme.fontCaption
                            color: Theme.textMuted
                        }
                    }
                }
            }

            IconButton {
                iconName: "settings"
                tip: qsTr("Ayarlar")
                onClicked: settingsMenu.open()
                SettingsMenu { id: settingsMenu; y: -height - 6 }
            }
        }
    }
}
