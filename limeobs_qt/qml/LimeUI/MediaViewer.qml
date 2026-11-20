import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtMultimedia

// Ödev eklerindeki ses ve videoları uygulama içinde oynatır.
// Main.qml bunu bir Loader ile yükler; QtMultimedia yoksa dosyalar harici programda açılır.
Popup {
    id: root
    property string title: ""
    property bool audioOnly: false

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(audioOnly ? 520 : 960, parent ? parent.width - 48 : 960)
    height: audioOnly ? implicitHeight : Math.min(width * 9 / 16 + 130, parent ? parent.height - 48 : 680)
    modal: true
    padding: 18
    background: Rectangle {
        radius: Theme.radiusLg
        color: Theme.elevated
        border.width: 1
        border.color: Theme.border
    }

    function play(url, name, audio) {
        title = name
        audioOnly = audio
        player.source = url
        open()
        player.play()
    }

    onClosed: { player.stop(); player.source = "" }

    function fmt(ms) {
        const s = Math.max(0, Math.floor(ms / 1000))
        const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), sec = s % 60
        const mm = h > 0 ? String(m).padStart(2, "0") : String(m)
        return (h > 0 ? h + ":" : "") + mm + ":" + String(sec).padStart(2, "0")
    }

    MediaPlayer {
        id: player
        videoOutput: video
        audioOutput: AudioOutput { id: audio; volume: volumeSlider.value }
        onErrorOccurred: (error, message) => errorText.text = qsTr("Oynatılamadı: %1").arg(message)
        onSourceChanged: errorText.text = ""
    }

    contentItem: ColumnLayout {
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            Icon { name: root.audioOnly ? "music" : "film"; size: 18; color: Theme.accent }
            Text {
                Layout.fillWidth: true
                text: root.title
                elide: Text.ElideMiddle
                font.family: Theme.font
                font.pixelSize: Theme.fontTitle
                font.weight: Font.DemiBold
                color: Theme.text
            }
            IconButton { iconName: "external"; tip: qsTr("Harici programda aç"); onClicked: { App.openUrl(player.source.toString()); root.close() } }
            IconButton { iconName: "x"; tip: qsTr("Kapat"); onClicked: root.close() }
        }

        Rectangle {
            visible: !root.audioOnly
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Theme.radius
            color: "black"
            clip: true
            VideoOutput {
                id: video
                anchors.fill: parent
            }
            MouseArea {
                anchors.fill: parent
                onClicked: player.playing ? player.pause() : player.play()
                onDoubleClicked: root.close()
            }
        }

        Text {
            id: errorText
            visible: text.length > 0
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            font.family: Theme.font
            font.pixelSize: Theme.fontSmall
            color: Theme.danger
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            AbstractButton {
                id: playButton
                implicitWidth: 40
                implicitHeight: 40
                Accessible.name: player.playing ? qsTr("Duraklat") : qsTr("Oynat")
                onClicked: player.playing ? player.pause() : player.play()
                background: Rectangle { radius: 20; color: playButton.hovered ? Theme.accentHover : Theme.accent }
                contentItem: Item {
                    Icon {
                        anchors.centerIn: parent
                        name: player.playing ? "pause" : "play"
                        size: 18
                        color: Theme.textOnAccent
                    }
                }
            }

            Text {
                text: root.fmt(player.position)
                font.family: Theme.font
                font.pixelSize: Theme.fontSmall
                font.features: { "tnum": 1 }
                color: Theme.textMuted
            }

            Slider {
                id: seek
                Layout.fillWidth: true
                from: 0
                to: Math.max(1, player.duration)
                enabled: player.seekable
                value: pressed ? value : player.position
                onMoved: player.position = value
                background: Rectangle {
                    x: seek.leftPadding
                    y: seek.topPadding + seek.availableHeight / 2 - height / 2
                    width: seek.availableWidth
                    height: 4
                    radius: 2
                    color: Theme.border
                    Rectangle {
                        width: seek.visualPosition * parent.width
                        height: parent.height
                        radius: 2
                        color: Theme.accent
                    }
                }
                handle: Rectangle {
                    x: seek.leftPadding + seek.visualPosition * (seek.availableWidth - width)
                    y: seek.topPadding + seek.availableHeight / 2 - height / 2
                    width: 14
                    height: 14
                    radius: 7
                    color: Theme.accent
                }
            }

            Text {
                text: root.fmt(player.duration)
                font.family: Theme.font
                font.pixelSize: Theme.fontSmall
                font.features: { "tnum": 1 }
                color: Theme.textMuted
            }

            IconButton {
                iconName: audio.muted || volumeSlider.value === 0 ? "volume-x" : "volume"
                tip: audio.muted ? qsTr("Sesi aç") : qsTr("Sessiz")
                onClicked: audio.muted = !audio.muted
            }
            Slider {
                id: volumeSlider
                implicitWidth: 90
                from: 0
                to: 1
                value: 0.9
                background: Rectangle {
                    x: volumeSlider.leftPadding
                    y: volumeSlider.topPadding + volumeSlider.availableHeight / 2 - height / 2
                    width: volumeSlider.availableWidth
                    height: 4
                    radius: 2
                    color: Theme.border
                    Rectangle {
                        width: volumeSlider.visualPosition * parent.width
                        height: parent.height
                        radius: 2
                        color: Theme.textMuted
                    }
                }
                handle: Rectangle {
                    x: volumeSlider.leftPadding + volumeSlider.visualPosition * (volumeSlider.availableWidth - width)
                    y: volumeSlider.topPadding + volumeSlider.availableHeight / 2 - height / 2
                    width: 12
                    height: 12
                    radius: 6
                    color: Theme.text
                }
            }
        }
    }

    // Boşluk: oynat/duraklat, oklar: 5 sn ileri/geri, Esc: kapat (Popup varsayılanı)
    Shortcut { enabled: root.opened; sequence: "Space"; onActivated: player.playing ? player.pause() : player.play() }
    Shortcut { enabled: root.opened; sequence: "Right"; onActivated: player.position = Math.min(player.duration, player.position + 5000) }
    Shortcut { enabled: root.opened; sequence: "Left"; onActivated: player.position = Math.max(0, player.position - 5000) }
}
