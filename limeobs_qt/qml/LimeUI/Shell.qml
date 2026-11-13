import QtQuick
import QtQuick.Layouts

// Giriş sonrası ana düzen: kenar çubuğu + sayfalar.
RowLayout {
    id: root
    spacing: 0
    property string current: "home"
    property bool sidebarOpen: true
    readonly property var pages: ["home", "assistant", "schedule", "homework", "exams", "food", "messages", "profile"]

    Sidebar {
        visible: root.sidebarOpen
        Layout.preferredWidth: Theme.sidebarWidth
        Layout.fillHeight: true
        current: root.current
        onNavigate: page => root.current = page
        onCollapse: root.sidebarOpen = false
    }

    Rectangle {
        Layout.fillWidth: true
        Layout.fillHeight: true
        color: Theme.bg

        StackLayout {
            anchors.fill: parent
            currentIndex: root.pages.indexOf(root.current)
            HomePage { onNavigate: page => root.current = page }
            AssistantPage {}
            SchedulePage {}
            HomeworkPage {}
            ExamsPage {}
            FoodPage {}
            MessagesPage {}
            ProfilePage {}
        }

        IconButton {
            visible: !root.sidebarOpen
            x: 10
            y: 10
            iconName: "sidebar"
            tip: qsTr("Kenar çubuğunu göster")
            onClicked: root.sidebarOpen = true
        }
    }
}
