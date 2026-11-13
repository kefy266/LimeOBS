import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// GTK Ana Sayfa'sının bölümleri: selamlama, canlı ders sayacı, çanta hatırlatıcısı,
// yemek ve ödev kartları, günün programı, son denemeler.
PageScaffold {
    id: page
    pageName: "home"
    title: ready ? pageData.title : qsTr("Ana Sayfa")
    subtitle: ready ? pageData.status + "  •  " + pageData.date : ""
    signal navigate(string page)

    property date now: new Date()
    Timer {
        interval: 30000
        repeat: true
        running: page.visible
        triggeredOnStart: true
        onTriggered: page.now = new Date()
    }

    readonly property int nowMinutes: now.getHours() * 60 + now.getMinutes()
    readonly property bool bagTime: nowMinutes >= 16 * 60 + 30 || nowMinutes < 8 * 60 + 30 || now.getDay() === 0 || now.getDay() === 6

    function minutesOf(hhmm) {
        const p = hhmm.split(":")
        return Number(p[0]) * 60 + Number(p[1])
    }

    // Canlı ders / teneffüs durumu: {title, detail, minutes} ya da null
    readonly property var live: {
        if (!ready || now.getDay() === 0 || now.getDay() === 6)
            return null
        const slots = pageData.todaySlots
        if (!slots.length)
            return null
        const t = nowMinutes
        const first = minutesOf(slots[0].start)
        if (t < first)
            return { title: qsTr("Okul başlamadı"), detail: qsTr("İlk ders: %1").arg(slots[0].lesson), minutes: first - t }
        for (let i = 0; i < slots.length; ++i) {
            const s = minutesOf(slots[i].start), e = minutesOf(slots[i].end)
            if (t >= s && t < e)
                return { title: qsTr("Şu anda: %1").arg(slots[i].lesson),
                         detail: i + 1 < slots.length ? qsTr("Teneffüse kalan süre") : qsTr("Günün son dersi"), minutes: e - t }
            if (i + 1 < slots.length && t >= e && t < minutesOf(slots[i + 1].start))
                return { title: qsTr("Teneffüs"), detail: qsTr("Sonraki ders: %1").arg(slots[i + 1].lesson),
                         minutes: minutesOf(slots[i + 1].start) - t }
        }
        return null
    }

    component LinkButton: OButton {
        variant: "ghost"
        Layout.alignment: Qt.AlignLeft
        implicitHeight: 30
        leftPadding: 8
        rightPadding: 8
        font.pixelSize: Theme.fontSmall
    }

    // --- Canlı ders sayacı
    Rectangle {
        visible: page.live !== null
        Layout.fillWidth: true
        implicitHeight: liveRow.implicitHeight + 28
        radius: Theme.radius
        color: Theme.accentSoft
        border.width: 1
        border.color: Theme.accent
        RowLayout {
            id: liveRow
            anchors.fill: parent
            anchors.margins: 14
            anchors.leftMargin: 18
            spacing: 14
            Icon { name: "clock"; size: 22; color: Theme.accent }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    text: page.live ? page.live.title : ""
                    font.family: Theme.font
                    font.pixelSize: Theme.fontBody
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                Text {
                    text: page.live ? page.live.detail : ""
                    font.family: Theme.font
                    font.pixelSize: Theme.fontSmall
                    color: Theme.textMuted
                }
            }
            Rectangle {
                Layout.preferredWidth: countText.implicitWidth + 24
                Layout.preferredHeight: 34
                radius: 17
                color: Theme.accent
                Text {
                    id: countText
                    anchors.centerIn: parent
                    text: page.live ? qsTr("%1 dk").arg(page.live.minutes) : ""
                    font.family: Theme.font
                    font.pixelSize: Theme.fontUi
                    font.weight: Font.Bold
                    color: Theme.textOnAccent
                }
            }
        }
    }

    // --- Çanta hatırlatıcısı
    SectionCard {
        visible: page.ready && page.bagTime && page.pageData.bagLessons.length > 0
        title: page.ready ? qsTr("Çantanı hazırla: %1").arg(page.pageData.bagTitle) : ""
        iconName: "book"
        Flow {
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: page.ready ? page.pageData.bagLessons : []
                delegate: Rectangle {
                    id: chip
                    required property string modelData
                    width: bookText.implicitWidth + 24
                    height: 30
                    radius: 15
                    color: Theme.surfaceAlt
                    border.width: 1
                    border.color: Theme.border
                    Text {
                        id: bookText
                        anchors.centerIn: parent
                        text: "📖 " + chip.modelData
                        font.family: Theme.font
                        font.pixelSize: Theme.fontSmall
                        color: Theme.text
                    }
                }
            }
        }
    }

    // --- Yemek & ödev kartları
    RowLayout {
        Layout.fillWidth: true
        spacing: 14

        SectionCard {
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            title: page.ready ? page.pageData.foodTitle : ""
            iconName: "food"
            Text {
                Layout.fillWidth: true
                text: page.ready && page.pageData.mainDish ? page.pageData.mainDish : qsTr("Menü bulunamadı")
                wrapMode: Text.WordWrap
                font.family: Theme.font
                font.pixelSize: Theme.fontTitle + 2
                font.weight: Font.DemiBold
                color: Theme.text
            }
            Text {
                visible: text.length > 0
                Layout.fillWidth: true
                Layout.topMargin: 4
                text: page.ready ? page.pageData.restMenu : ""
                wrapMode: Text.WordWrap
                font.family: Theme.font
                font.pixelSize: Theme.fontSmall
                color: Theme.textMuted
            }
            LinkButton {
                Layout.topMargin: 6
                text: qsTr("Yemek listesine git →")
                onClicked: page.navigate("food")
            }
        }

        SectionCard {
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 1
            title: qsTr("Aktif ödevler")
            iconName: "book"
            Text {
                text: page.ready ? String(page.pageData.homeworkCount) : ""
                font.family: Theme.font
                font.pixelSize: Theme.fontDisplay + 6
                font.weight: Font.Bold
                font.features: { "tnum": 1 }
                color: Theme.text
            }
            Text {
                Layout.fillWidth: true
                text: page.ready ? page.pageData.homeworkSub : ""
                elide: Text.ElideRight
                font.family: Theme.font
                font.pixelSize: Theme.fontSmall
                color: Theme.textMuted
            }
            LinkButton {
                Layout.topMargin: 6
                text: qsTr("Ödevlere git →")
                onClicked: page.navigate("homework")
            }
        }
    }

    // --- Günün programı
    SectionCard {
        title: page.ready ? page.pageData.scheduleTitle : ""
        badge: page.ready ? page.pageData.scheduleBadge : ""
        iconName: "calendar"
        Repeater {
            model: page.ready ? page.pageData.lessons : []
            delegate: ListRow {
                required property var modelData
                required property int index
                showDivider: index > 0
                lead: modelData.time
                title: modelData.lesson
                subtitle: modelData.teacher
            }
        }
        EmptyText {
            visible: page.ready && page.pageData.lessons.length === 0
            text: qsTr("Ders görünmüyor.")
        }
        LinkButton {
            Layout.topMargin: 6
            text: qsTr("Haftalık programa git →")
            onClicked: page.navigate("schedule")
        }
    }

    // --- Son denemeler
    SectionCard {
        title: qsTr("Sınav karnesi ve başarı gelişimi")
        iconName: "chart"
        Repeater {
            model: page.ready ? page.pageData.exams : []
            delegate: ListRow {
                required property var modelData
                required property int index
                showDivider: index > 0
                lead: modelData.date
                title: modelData.name
                subtitle: qsTr("Net %1 • Doğru %2 • Yanlış %3").arg(modelData.net).arg(modelData.dogru).arg(modelData.yanlis)
                trailing: qsTr("%1 puan").arg(modelData.point.toFixed(1))
            }
        }
        EmptyText {
            visible: page.ready && page.pageData.exams.length === 0
            text: qsTr("Henüz girilen bir deneme sınavı yok.")
        }
        LinkButton {
            Layout.topMargin: 6
            text: qsTr("Tüm sınavlar ve ortalamalar →")
            onClicked: page.navigate("exams")
        }
    }
}
