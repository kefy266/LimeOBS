import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Sınavlar: tür filtresi, sınav seçerek ortalama (genel + ders bazında), puan grafiği ve sınav detayı.
PageScaffold {
    id: page
    pageName: "exams"
    title: qsTr("Sınavlar")
    subtitle: qsTr("Sınavları seçerek ortalamalarını görebilirsin")

    property string filter: "deneme"
    property var selected: ({})
    property var detailExam: null

    readonly property var allExams: ready ? pageData.exams : []
    readonly property var shown: allExams.filter(e => filter === "all" || e.kind === filter)
    readonly property var picked: shown.filter(e => selected[e.id])
    readonly property var basis: picked.length > 0 ? picked : shown
    readonly property var stats: computeStats(basis)

    onVisibleChanged: if (!visible) detailExam = null

    function toggle(id) {
        const s = Object.assign({}, selected)
        if (s[id]) delete s[id]; else s[id] = true
        selected = s
    }
    function avg(list, key) {
        return list.length ? list.reduce((t, e) => t + Number(e[key] || 0), 0) / list.length : 0
    }
    function computeStats(list) {
        const lessons = {}
        const order = []
        for (const e of list) {
            for (const l of e.lessons) {
                if (!lessons[l.name]) { lessons[l.name] = { name: l.name, n: 0, net: 0, d: 0, y: 0, b: 0, q: 0 }; order.push(l.name) }
                const a = lessons[l.name]
                a.n += 1; a.net += l.net; a.d += l.d; a.y += l.y; a.b += l.b; a.q += l.q
            }
        }
        return {
            count: list.length,
            point: avg(list, "point"), net: avg(list, "net"),
            dogru: avg(list, "dogru"), yanlis: avg(list, "yanlis"), bos: avg(list, "bos"),
            best: list.length ? Math.max(...list.map(e => e.point)) : 0,
            lessons: order.map(n => {
                const a = lessons[n]
                return { name: n, count: a.n, net: a.net / a.n, d: a.d / a.n, y: a.y / a.n, b: a.b / a.n,
                         rate: a.q ? 100 * a.d / a.q : 0 }
            })
        }
    }
    function fmt1(v) { return Number(v).toFixed(1).replace(/\.0$/, "").replace(".", ",") }
    function fmt(v) { return Number(v).toFixed(2).replace(/\.?0+$/, "").replace(".", ",") }

    RowLayout {
        Layout.fillWidth: true
        spacing: 10
        Segmented {
            model: [{ value: "deneme", label: qsTr("Denemeler") }, { value: "tarama", label: qsTr("Taramalar (DAS)") },
                    { value: "all", label: qsTr("Tümü") }]
            value: page.filter
            onPicked: v => page.filter = v
        }
        Item { Layout.fillWidth: true }
        OButton {
            visible: page.picked.length > 0
            variant: "ghost"
            text: qsTr("Seçimi temizle")
            onClicked: page.selected = ({})
        }
        OButton {
            visible: page.picked.length < page.shown.length
            variant: "ghost"
            text: qsTr("Tümünü seç")
            onClicked: {
                const s = {}
                for (const e of page.shown) s[e.id] = true
                page.selected = s
            }
        }
    }

    // --- Ortalamalar
    SectionCard {
        title: page.picked.length > 0 ? qsTr("Seçilen %1 sınavın ortalaması").arg(page.stats.count)
                                      : qsTr("Tüm %1 sınavın ortalaması").arg(page.stats.count)
        iconName: "chart"
        visible: page.stats.count > 0

        GridLayout {
            Layout.fillWidth: true
            columns: 4
            columnSpacing: 12
            rowSpacing: 12
            StatTile { label: qsTr("Ortalama puan"); value: page.fmt(page.stats.point) }
            StatTile { label: qsTr("Ortalama net"); value: page.fmt(page.stats.net) }
            StatTile {
                label: qsTr("Ort. doğru / yanlış / boş")
                value: page.fmt1(page.stats.dogru) + " / " + page.fmt1(page.stats.yanlis) + " / " + page.fmt1(page.stats.bos)
            }
            StatTile { label: qsTr("En yüksek puan"); value: page.fmt(page.stats.best) }
        }

        Text {
            visible: page.stats.lessons.length > 0
            Layout.topMargin: 14
            text: qsTr("Ders bazında ortalama net")
            font.family: Theme.font
            font.pixelSize: Theme.fontSmall
            font.weight: Font.DemiBold
            color: Theme.textMuted
        }
        Repeater {
            model: page.stats.lessons
            delegate: LessonBar {
                required property var modelData
                required property int index
                showDivider: index > 0
                name: modelData.name
                detail: qsTr("D %1 • Y %2 • B %3%4").arg(page.fmt(modelData.d)).arg(page.fmt(modelData.y))
                        .arg(page.fmt(modelData.b))
                        .arg(modelData.count < page.stats.count ? qsTr(" • %1 sınavda").arg(modelData.count) : "")
                value: page.fmt(modelData.net)
                ratio: modelData.rate / 100
            }
        }
        EmptyText {
            visible: page.stats.lessons.length === 0
            Layout.topMargin: 8
            text: qsTr("Bu sınavların ders bazında karnesi henüz yayınlanmamış.")
        }
    }

    SectionCard {
        visible: page.basis.length > 1
        title: qsTr("Puan gelişimi")
        iconName: "chart"
        PointBars {
            Layout.fillWidth: true
            Layout.preferredHeight: 150
            values: page.basis.slice().reverse().map(e => Math.round(e.point))
        }
    }

    // --- Sınav listesi
    SectionCard {
        title: qsTr("Sınavlar")
        badge: qsTr("Seçmek için kutuya, ayrıntı için satıra tıkla")
        iconName: "list"
        Repeater {
            model: page.shown
            delegate: Item {
                id: examRow
                required property var modelData
                required property int index
                Layout.fillWidth: true
                implicitHeight: rowLayout.implicitHeight + 16

                Rectangle {
                    visible: examRow.index > 0
                    width: parent.width
                    height: 1
                    color: Theme.border
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: page.detailExam = examRow.modelData
                }
                RowLayout {
                    id: rowLayout
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 12
                    OCheckBox {
                        checked: !!page.selected[examRow.modelData.id]
                        onClicked: page.toggle(examRow.modelData.id)
                        Accessible.name: qsTr("%1 sınavını seç").arg(examRow.modelData.name)
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        Text {
                            Layout.fillWidth: true
                            text: examRow.modelData.name
                            elide: Text.ElideRight
                            font.family: Theme.font
                            font.pixelSize: Theme.fontUi
                            color: Theme.text
                        }
                        Text {
                            text: qsTr("%1 • Net %2 • D %3 / Y %4 / B %5").arg(examRow.modelData.date)
                                  .arg(page.fmt(examRow.modelData.net)).arg(examRow.modelData.dogru)
                                  .arg(examRow.modelData.yanlis).arg(examRow.modelData.bos)
                            font.family: Theme.font
                            font.pixelSize: Theme.fontSmall
                            color: Theme.textMuted
                        }
                    }
                    Text {
                        text: qsTr("%1 puan").arg(page.fmt(examRow.modelData.point))
                        font.family: Theme.font
                        font.pixelSize: Theme.fontUi
                        font.weight: Font.DemiBold
                        font.features: { "tnum": 1 }
                        color: Theme.text
                    }
                    Icon { name: "chevron-right"; size: 16; color: Theme.textFaint }
                }
            }
        }
        EmptyText {
            visible: page.shown.length === 0
            text: qsTr("Bu türde sınav yok.")
        }
    }

    ExamDetail {
        exam: page.detailExam
        onClosed: page.detailExam = null
    }
}
