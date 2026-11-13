import QtQuick
import QtQuick.Layouts

// Sohbet mesajı: kullanıcı sağda baloncukta, asistan solda düz metin (Markdown).
Item {
    id: root
    required property string role
    required property string text
    required property bool failed
    readonly property bool isUser: role === "user"

    implicitHeight: isUser ? bubble.height : Math.max(body.implicitHeight, 22)

    Rectangle {
        id: bubble
        visible: root.isUser
        anchors.right: parent.right
        width: Math.min(userText.implicitWidth + 32, parent.width * 0.8)
        height: userText.implicitHeight + 22
        radius: 18
        color: Theme.userBubble
        Text {
            id: userText
            anchors.fill: parent
            anchors.margins: 11
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            text: root.text
            wrapMode: Text.WordWrap
            font.family: Theme.font
            font.pixelSize: Theme.fontBody
            color: Theme.text
        }
    }

    Spinner {
        visible: !root.isUser && root.text.length === 0
        anchors.left: parent.left
    }

    TextEdit {
        id: body
        visible: !root.isUser && root.text.length > 0
        width: parent.width
        readOnly: true
        selectByMouse: true
        text: root.text
        textFormat: root.failed ? TextEdit.PlainText : TextEdit.MarkdownText
        wrapMode: TextEdit.Wrap
        font.family: Theme.font
        font.pixelSize: Theme.fontBody
        color: root.failed ? Theme.danger : Theme.text
        selectionColor: Theme.accentSoft
        selectedTextColor: Theme.text
    }
}
