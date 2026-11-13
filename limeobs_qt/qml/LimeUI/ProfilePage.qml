import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import LimeBackend

PageScaffold {
    id: page
    pageName: "profile"
    title: qsTr("Profil")

    property string passwordMessage: ""
    property bool passwordOk: false
    property bool passwordBusy: false

    Connections {
        target: App
        function onDataChanged(name) {
            if (name !== "password")
                return
            const r = App.page("password")
            page.passwordBusy = false
            page.passwordOk = r.ok
            page.passwordMessage = r.message
            if (r.ok) {
                oldPw.text = ""
                newPw.text = ""
                newPw2.text = ""
            }
        }
    }

    component Field: TextField {
        id: field
        Layout.fillWidth: true
        implicitHeight: 40
        leftPadding: 12
        echoMode: TextInput.Password
        font.family: Theme.font
        font.pixelSize: Theme.fontUi
        color: Theme.text
        placeholderTextColor: Theme.textFaint
        enabled: !page.passwordBusy
        background: Rectangle {
            radius: Theme.radiusSm + 2
            color: Theme.surfaceAlt
            border.width: 1
            border.color: field.activeFocus ? Theme.accent : Theme.border
        }
    }

    // --- Kimlik kartı
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: header.implicitHeight + 40
        radius: Theme.radiusLg
        color: Theme.surface
        border.width: 1
        border.color: Theme.border

        RowLayout {
            id: header
            anchors.fill: parent
            anchors.margins: 20
            spacing: 18

            Avatar {
                size: 84
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                spacing: 4
                Text {
                    text: App.profile.name || ""
                    font.family: Theme.font
                    font.pixelSize: Theme.fontHeading
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                Text {
                    text: App.profile.subtitle || ""
                    font.family: Theme.font
                    font.pixelSize: Theme.fontUi
                    color: Theme.textMuted
                }
                Text {
                    text: App.profile.school ? App.profile.school + (App.profile.term ? " • " + App.profile.term : "") : ""
                    font.family: Theme.font
                    font.pixelSize: Theme.fontSmall
                    color: Theme.textFaint
                }
            }
        }
    }

    SectionCard {
        title: qsTr("OBS bilgileri")
        iconName: "user"
        Repeater {
            model: App.profile.fields || []
            delegate: ListRow {
                required property var modelData
                required property int index
                showDivider: index > 0
                title: modelData.value
                subtitle: modelData.label
            }
        }
    }

    SectionCard {
        title: qsTr("Görünüm")
        iconName: App.themeMode === "dark" ? "moon" : "sun"
        Segmented {
            model: [{ value: "system", label: qsTr("Sistem") }, { value: "light", label: qsTr("Açık") },
                    { value: "dark", label: qsTr("Koyu") }]
            value: App.themeMode
            onPicked: v => App.themeMode = v
        }
    }

    SectionCard {
        title: qsTr("Şifre değiştir")
        iconName: "lock"
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8
            Field { id: oldPw; placeholderText: qsTr("Mevcut şifre") }
            Field { id: newPw; placeholderText: qsTr("Yeni şifre (6-30 karakter)") }
            Field { id: newPw2; placeholderText: qsTr("Yeni şifre (tekrar)"); onAccepted: changeBtn.clicked() }
            Text {
                visible: page.passwordMessage.length > 0
                Layout.fillWidth: true
                text: page.passwordMessage
                wrapMode: Text.WordWrap
                font.family: Theme.font
                font.pixelSize: Theme.fontSmall
                color: page.passwordOk ? Theme.accent : Theme.danger
            }
            OButton {
                id: changeBtn
                Layout.alignment: Qt.AlignRight
                variant: "primary"
                text: page.passwordBusy ? qsTr("Değiştiriliyor…") : qsTr("Şifreyi değiştir")
                enabled: !page.passwordBusy && oldPw.text.length > 0 && newPw.text.length > 0 && newPw2.text.length > 0
                onClicked: {
                    page.passwordMessage = ""
                    page.passwordBusy = true
                    App.changePassword(oldPw.text, newPw.text, newPw2.text)
                }
            }
        }
    }

    OButton {
        Layout.alignment: Qt.AlignLeft
        text: qsTr("Çıkış yap")
        iconName: "logout"
        variant: "danger"
        onClicked: App.logout()
    }
}
