import QtQuick
import QtQuick.Effects
import LimeBackend

// Yuvarlak profil fotoğrafı; fotoğraf yoksa ya da yüklenmediyse baş harf.
Item {
    id: root
    property int size: 30
    implicitWidth: size
    implicitHeight: size
    Accessible.role: Accessible.Graphic
    Accessible.name: App.profile.name || qsTr("Profil")

    Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: Theme.accent
        visible: photo.status !== Image.Ready
        Text {
            anchors.centerIn: parent
            text: App.profile.initial || "?"
            font.family: Theme.font
            font.pixelSize: root.size * 0.42
            font.weight: Font.DemiBold
            color: Theme.textOnAccent
        }
    }
    Image {
        id: photo
        anchors.fill: parent
        source: App.profile.photoUrl || ""
        sourceSize: Qt.size(root.size * 2, root.size * 2)
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        visible: false
    }
    MultiEffect {
        anchors.fill: parent
        source: photo
        visible: photo.status === Image.Ready
        maskEnabled: true
        maskSource: mask
    }
    Rectangle {
        id: mask
        anchors.fill: parent
        radius: width / 2
        visible: false
        layer.enabled: true
    }
}
