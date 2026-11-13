import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import LimeBackend

Rectangle {
    id: root
    color: Theme.bg
    property string error: ""

    Connections {
        target: App
        function onLoginFailed(message) { root.error = message }
    }

    component Field: TextField {
        id: field
        Layout.fillWidth: true
        implicitHeight: 44
        leftPadding: 14
        font.family: Theme.font
        font.pixelSize: Theme.fontBody
        color: Theme.text
        placeholderTextColor: Theme.textFaint
        selectionColor: Theme.accentSoft
        enabled: !App.busy
        background: Rectangle {
            radius: Theme.radius
            color: Theme.surface
            border.width: 1
            border.color: field.activeFocus ? Theme.accent : Theme.border
        }
    }

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(380, parent.width - 48)
        spacing: 14

        Image {
            Layout.alignment: Qt.AlignHCenter
            source: "logo.png"
            sourceSize: Qt.size(64, 64)
            Layout.preferredWidth: 64
            Layout.preferredHeight: 64
            Accessible.ignored: true
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("LimeOBS'a hoş geldin")
            font.family: Theme.font
            font.pixelSize: Theme.fontHeading + 4
            font.weight: Font.DemiBold
            color: Theme.text
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.bottomMargin: 10
            text: qsTr("Okulunun OBS bilgileriyle giriş yap")
            font.family: Theme.font
            font.pixelSize: Theme.fontUi
            color: Theme.textMuted
        }

        Field {
            id: tc
            placeholderText: qsTr("T.C. kimlik numarası")
            inputMethodHints: Qt.ImhDigitsOnly
            maximumLength: 11
            focus: true
            onAccepted: password.forceActiveFocus()
        }
        Field {
            id: password
            placeholderText: qsTr("Şifre")
            echoMode: TextInput.Password
            onAccepted: if (loginBtn.enabled) loginBtn.clicked()
        }
        OCheckBox {
            id: remember
            checked: true
            enabled: !App.busy
            text: qsTr("Beni hatırla")
            font.family: Theme.font
            font.pixelSize: Theme.fontUi
        }
        Text {
            visible: root.error.length > 0
            Layout.fillWidth: true
            text: root.error
            wrapMode: Text.WordWrap
            font.family: Theme.font
            font.pixelSize: Theme.fontSmall
            color: Theme.danger
        }
        OButton {
            id: loginBtn
            Layout.fillWidth: true
            implicitHeight: 44
            variant: "primary"
            text: App.busy ? qsTr("Giriş yapılıyor…") : qsTr("Giriş yap")
            enabled: !App.busy && tc.text.length > 0 && password.text.length > 0
            onClicked: { root.error = ""; App.login(tc.text, password.text, remember.checked) }
        }
    }
}
