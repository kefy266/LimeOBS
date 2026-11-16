import QtQuick
import QtQuick.Layouts

// Sohbet mesajı: kullanıcı sağda baloncukta, asistan solda düz metin (Markdown).
Item {
    id: root
    required property string role
    required property string text
    required property bool failed
    readonly property bool isUser: role === "user"

    implicitHeight: isUser ? bubble.height : (failed ? Math.max(failText.implicitHeight, 22) : Math.max(body.implicitHeight, 22))

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

    // Asistan cevabı: Markdown satır satır çözülür; madde işaretleri sabit bir sütunda, metin asılı girintiyle
    // hizalanır (Qt'nin Markdown listeleri 40 px girinti ve kaymış numaralar veriyordu).
    function inline(t) {
        t = t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        return t.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<i>$1</i>")
    }
    readonly property var blocks: {
        if (isUser || failed)
            return []
        const out = []
        for (const raw of text.split("\n")) {
            const indent = raw.match(/^\s*/)[0].length
            const line = raw.trim()
            if (!line.length) {
                if (out.length && out[out.length - 1].kind !== "gap")
                    out.push({ kind: "gap", level: 0, marker: "", html: "" })
                continue
            }
            let m
            if (/^\|.*\|$/.test(line)) {
                const cells = line.slice(1, -1).split("|").map(c => c.trim())
                if (cells.every(c => /^:?-{2,}:?$/.test(c))) {
                    if (out.length && out[out.length - 1].kind === "tr")
                        out[out.length - 1].header = true
                    continue
                }
                out.push({ kind: "tr", level: 0, marker: "", html: "", header: false,
                           cells: cells.map(c => inline(c)), raw: cells })
                continue
            }
            if ((m = line.match(/^#{1,6}\s+(.*)$/)))
                out.push({ kind: "h", level: 0, marker: "", html: inline(m[1]) })
            else if ((m = line.match(/^[-*•]\s+(.*)$/)))
                out.push({ kind: "li", level: indent >= 2 ? 1 : 0, marker: "•", html: inline(m[1]) })
            else if ((m = line.match(/^(\d+)[.)]\s+(.*)$/)))
                out.push({ kind: "li", level: indent >= 2 ? 1 : 0, marker: m[1] + ".", html: inline(m[2]) })
            else
                out.push({ kind: "p", level: indent >= 2 ? 1 : 0, marker: "", html: inline(line) })
        }
        // Tablo sütun genişlikleri: her tablo grubunda en uzun hücreye göre oran
        for (let i = 0; i < out.length; ) {
            if (out[i].kind !== "tr") { ++i; continue }
            let j = i
            const w = []
            while (j < out.length && out[j].kind === "tr") {
                out[j].raw.forEach((c, k) => w[k] = Math.max(w[k] || 0, Math.min(Math.max(c.length, 4), 60)))
                ++j
            }
            for (let k = i; k < j; ++k) {
                out[k].weights = w
                out[k].first = k === i
            }
            i = j
        }
        return out
    }

    Text {
        id: failText
        visible: root.failed
        width: parent.width
        text: root.failed ? root.text : ""
        wrapMode: Text.Wrap
        font.family: Theme.font
        font.pixelSize: Theme.fontBody
        color: Theme.danger
    }

    Column {
        id: body
        visible: !root.isUser && !root.failed && root.text.length > 0
        width: parent.width
        spacing: 4
        Repeater {
            model: root.blocks
            delegate: Loader {
                id: blkLoader
                required property var modelData
                width: body.width
                sourceComponent: modelData.kind === "tr" ? tableRow : textBlock
            }
        }
    }

    Component {
        id: tableRow
        Rectangle {
            id: tr
            readonly property var modelData: parent ? parent.modelData : ({})
            width: parent ? parent.width : 0
            height: cellsRow.implicitHeight + 12
            color: modelData.header ? Theme.accentSoft : "transparent"
            radius: modelData.header ? 6 : 0
            Rectangle {
                visible: !tr.modelData.header
                anchors.bottom: parent.bottom
                width: parent.width
                height: 1
                color: Theme.border
            }
            RowLayout {
                id: cellsRow
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 12
                Repeater {
                    model: tr.modelData.cells || []
                    delegate: Text {
                        required property string modelData
                        required property int index
                        Layout.fillWidth: true
                        Layout.preferredWidth: (tr.modelData.weights || [])[index] || 10
                        Layout.alignment: Qt.AlignTop
                        text: modelData
                        textFormat: Text.StyledText
                        wrapMode: Text.Wrap
                        font.family: Theme.font
                        font.pixelSize: Theme.fontSmall + 1
                        font.weight: tr.modelData.header ? Font.DemiBold : Font.Normal
                        color: Theme.text
                    }
                }
            }
        }
    }

    Component {
        id: textBlock
            Item {
                id: blk
                readonly property var modelData: parent ? parent.modelData : ({ kind: "gap", level: 0, marker: "", html: "" })
                width: parent ? parent.width : 0
                height: modelData.kind === "gap" ? 6 : Math.max(line.implicitHeight, mark.implicitHeight)
                readonly property real indentX: modelData.level * 26 + (modelData.marker ? 26 : 0)
                Text {
                    id: mark
                    visible: blk.modelData.marker.length > 0
                    x: blk.modelData.level * 26
                    width: 22
                    horizontalAlignment: Text.AlignRight
                    text: blk.modelData.marker
                    font.family: Theme.font
                    font.pixelSize: Theme.fontBody
                    font.weight: blk.modelData.marker === "•" ? Font.Normal : Font.DemiBold
                    color: blk.modelData.marker === "•" ? Theme.accent : Theme.textMuted
                }
                Text {
                    id: line
                    visible: blk.modelData.kind !== "gap"
                    x: blk.indentX
                    width: blk.width - x
                    text: blk.modelData.html
                    textFormat: Text.StyledText
                    wrapMode: Text.Wrap
                    lineHeight: 1.15
                    font.family: Theme.font
                    font.pixelSize: blk.modelData.kind === "h" ? Theme.fontBody + 2 : Theme.fontBody
                    font.weight: blk.modelData.kind === "h" ? Font.DemiBold : Font.Normal
                    color: Theme.text
                }
            }
    }
}
