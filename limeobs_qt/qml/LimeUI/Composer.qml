import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Effects

// Orbital tarzı yazı kartı: büyüyen metin alanı ve gönder butonu. Enter gönderir, Shift+Enter alt satır.
Item {
    id: root
    property bool large: false
    property bool busy: false
    readonly property bool canSend: input.text.trim().length > 0 && !busy
    signal submitted(string text)

    implicitHeight: card.height

    function focusInput() { input.forceActiveFocus() }
    function send() {
        if (!canSend)
            return
        submitted(input.text.trim())
        input.text = ""
    }

    RectangularShadow {
        anchors.fill: card
        radius: card.radius
        blur: 24
        spread: -4
        offset.y: 6
        color: Qt.alpha("#000000", Theme.dark ? 0.35 : 0.08)
    }

    Rectangle {
        id: card
        width: parent.width
        height: column.implicitHeight + 20
        radius: 24
        color: Theme.surface
        border.width: 1
        border.color: input.activeFocus ? Theme.borderStrong : Theme.border
        Behavior on border.color { ColorAnimation { duration: Theme.fast } }

        ColumnLayout {
            id: column
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 10
            anchors.leftMargin: 12
            spacing: 6

            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(Math.max(input.implicitHeight, root.large ? 64 : 28), 200)
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                TextArea {
                    id: input
                    placeholderText: qsTr("Asistana bir şey sor…")
                    placeholderTextColor: Theme.textFaint
                    wrapMode: TextArea.Wrap
                    font.family: Theme.font
                    font.pixelSize: Theme.fontBody
                    color: Theme.text
                    selectionColor: Theme.accentSoft
                    selectedTextColor: Theme.text
                    leftPadding: 6
                    rightPadding: 6
                    topPadding: 6
                    background: null
                    Keys.onReturnPressed: event => {
                        if (event.modifiers & Qt.ShiftModifier)
                            event.accepted = false
                        else
                            root.send()
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Text {
                    Layout.fillWidth: true
                    Layout.leftMargin: 6
                    text: qsTr("OBS verilerinle cevap verir")
                    font.family: Theme.font
                    font.pixelSize: Theme.fontCaption
                    color: Theme.textFaint
                }
                AbstractButton {
                    id: sendBtn
                    implicitWidth: 34
                    implicitHeight: 34
                    enabled: root.canSend
                    hoverEnabled: true
                    Accessible.name: qsTr("Gönder")
                    onClicked: root.send()
                    background: Rectangle {
                        radius: width / 2
                        color: sendBtn.enabled ? (sendBtn.hovered ? Theme.accentHover : Theme.accent) : Theme.selected
                    }
                    contentItem: Item {
                        Icon {
                            anchors.centerIn: parent
                            name: "arrow-up"
                            size: 17
                            color: sendBtn.enabled ? Theme.textOnAccent : Theme.textFaint
                        }
                    }
                }
            }
        }
    }
}
