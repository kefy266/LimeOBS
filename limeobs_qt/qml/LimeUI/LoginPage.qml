import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import LimeBackend

Rectangle {
    id: root
    color: Theme.bg
    property string error: ""
    property bool editingSchool: false

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
            text: qsTr("Okulunun OBS bilgileriyle giriş yap • %1").arg(App.schoolUrl)
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

        // Akbim OBS kullanan başka bir okul için sunucu adresi
        Text {
            visible: !root.editingSchool
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 4
            text: qsTr("Başka okul mu? Adresi değiştir")
            font.family: Theme.font
            font.pixelSize: Theme.fontSmall
            font.underline: schoolLink.containsMouse
            color: Theme.accent
            MouseArea {
                id: schoolLink
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: { schoolField.text = App.schoolUrl; root.editingSchool = true; schoolField.forceActiveFocus() }
            }
        }
        ColumnLayout {
            visible: root.editingSchool
            Layout.fillWidth: true
            spacing: 8
            Text {
                Layout.fillWidth: true
                text: qsTr("Okulunun OBS adresi (tarayıcıda OBS'e girdiğin adres)")
                wrapMode: Text.WordWrap
                font.family: Theme.font
                font.pixelSize: Theme.fontSmall
                color: Theme.textMuted
            }
            Field {
                id: schoolField
                placeholderText: qsTr("ör. okuladiobs.com")
                inputMethodHints: Qt.ImhUrlCharactersOnly
                onAccepted: saveSchool.clicked()
            }
            RowLayout {
                Layout.fillWidth: true
                OButton {
                    Layout.fillWidth: true
                    text: qsTr("Vazgeç")
                    onClicked: root.editingSchool = false
                }
                OButton {
                    id: saveSchool
                    Layout.fillWidth: true
                    variant: "primary"
                    text: qsTr("Kaydet")
                    enabled: schoolField.text.trim().length > 3
                    onClicked: { root.error = ""; App.setSchoolUrl(schoolField.text); root.editingSchool = false }
                }
            }
        }
    }
}
