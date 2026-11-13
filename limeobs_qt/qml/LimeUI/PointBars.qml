import QtQuick
import QtQuick.Layouts

// Basit sütun grafiği: en yüksek değer vurgu rengiyle, değerler sütunun üstünde.
Item {
    id: root
    property var values: []
    readonly property real maxValue: values.length ? Math.max(...values) : 1
    readonly property real minValue: values.length ? Math.min(...values) : 0
    readonly property real floor: Math.max(0, minValue - (maxValue - minValue) * 0.6 - 10)

    Accessible.role: Accessible.Chart
    Accessible.name: qsTr("Deneme puanları: %1").arg(values.join(", "))

    RowLayout {
        anchors.fill: parent
        spacing: 10
        Repeater {
            model: root.values
            delegate: ColumnLayout {
                id: bar
                required property real modelData
                required property int index
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 4
                Item { Layout.fillHeight: true }
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: bar.modelData.toFixed(0)
                    font.family: Theme.font
                    font.pixelSize: Theme.fontCaption
                    font.features: { "tnum": 1 }
                    color: Theme.textMuted
                }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.maximumWidth: 56
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredHeight: Math.max(6, (root.height - 44) * (bar.modelData - root.floor)
                                                         / Math.max(1, root.maxValue - root.floor))
                    radius: 6
                    color: bar.modelData === root.maxValue ? Theme.accent : Theme.selected
                }
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: qsTr("%1.").arg(bar.index + 1)
                    font.family: Theme.font
                    font.pixelSize: Theme.fontCaption
                    color: Theme.textFaint
                }
            }
        }
    }
}
