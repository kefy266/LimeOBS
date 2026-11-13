import QtQuick

// Temaya göre renklendirilen SVG ikon (Python'daki "icon" görüntü sağlayıcısı üretir).
Image {
    property string name
    property color color: "#000000"
    property int size: 18

    width: size
    height: size
    sourceSize: Qt.size(size * Screen.devicePixelRatio, size * Screen.devicePixelRatio)
    source: name ? "image://icon/" + name + "?" + color : ""
    smooth: true
    cache: true
    Accessible.ignored: true
}
