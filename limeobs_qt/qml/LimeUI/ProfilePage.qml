import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import LimeBackend

PageScaffold {
    id: page
    pageName: "profile"
    title: qsTr("Profil")

    property string passwordMessage: ""
    property bool passwordOk: false
    property bool passwordBusy: false

    // Telefon bildirimleri (Telegram) durumu: App.page("telegram")
    readonly property var tg: tgData
    property var tgData: null
    Component.onCompleted: App.refresh("telegram")

    Connections {
        target: App
        function onDataChanged(name) {
            if (name === "telegram") {
                page.tgData = App.page("telegram")
                return
            }
            if (name !== "password")
                return
            const r = App.page("password")
            page.passwordBusy = false
            page.passwordOk = r.ok
            page.passwordMessage = r.message
            if (r.ok) {
                oldPw.text = ""
                newPw.text = ""
                newPw2.text = ""
            }
        }
    }

    component Field: TextField {
        id: field
        Layout.fillWidth: true
        implicitHeight: 40
        leftPadding: 12
        echoMode: TextInput.Password
        font.family: Theme.font
        font.pixelSize: Theme.fontUi
        color: Theme.text
        placeholderTextColor: Theme.textFaint
        enabled: !page.passwordBusy
        background: Rectangle {
            radius: Theme.radiusSm + 2
            color: Theme.surfaceAlt
            border.width: 1
            border.color: field.activeFocus ? Theme.accent : Theme.border
        }
    }

    // --- Kimlik kartı
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: header.implicitHeight + 40
        radius: Theme.radiusLg
        color: Theme.surface
        border.width: 1
        border.color: Theme.border

        RowLayout {
            id: header
            anchors.fill: parent
            anchors.margins: 20
            spacing: 18

            Avatar {
                size: 84
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                spacing: 4
                Text {
                    Layout.fillWidth: true
                    text: App.profile.name || ""
                    font.family: Theme.font
                    font.pixelSize: Theme.fontHeading
                    font.weight: Font.DemiBold
                    color: Theme.text
                }
                Text {
                    Layout.fillWidth: true
                    text: App.profile.subtitle || ""
                    font.family: Theme.font
                    font.pixelSize: Theme.fontUi
                    color: Theme.textMuted
                }
                Text {
                    Layout.fillWidth: true
                    text: App.profile.school ? App.profile.school + (App.profile.term ? " • " + App.profile.term : "") : ""
                    font.family: Theme.font
                    font.pixelSize: Theme.fontSmall
                    color: Theme.textFaint
                }
            }
        }
    }

    SectionCard {
        title: qsTr("OBS bilgileri")
        iconName: "user"
        Repeater {
            model: App.profile.fields || []
            delegate: ListRow {
                required property var modelData
                required property int index
                showDivider: index > 0
                title: modelData.value
                subtitle: modelData.label
            }
        }
    }

    SectionCard {
        title: qsTr("Telefon bildirimleri")
        iconName: "bell"
        badge: page.tg && page.tg.linked ? qsTr("Telegram bağlı") : ""

        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            font.family: Theme.font
            font.pixelSize: Theme.fontUi
            color: Theme.textMuted
            text: !page.tg ? qsTr("Durum alınıyor…")
                : page.tg.error ? page.tg.error
                : page.tg.waiting ? qsTr("Telegram açıldı. Botun sohbetinde <b>Başlat</b>'a bas; bağlantı kendiliğinden tamamlanacak.")
                : !page.tg.available ? qsTr("Telefon bildirimleri yakında. (Bildirim botu henüz hazır değil.)")
                : page.tg.linked ? qsTr("Yeni ödev, mesaj, duyuru ve sınav sonuçları Telegram'dan telefonuna gelir. Uygulama açıkken %1 dakikada bir kontrol edilir.").arg(page.tg.interval)
                : qsTr("Yeni ödev, mesaj ve sınav sonuçlarını telefonuna Telegram'dan al. Bağlanmak için Telegram yüklü olmalı; kişisel bilgi ya da şifre istenmez.")
            textFormat: Text.StyledText
        }

        // Bildirim türleri
        Flow {
            visible: !!page.tg && page.tg.linked
            Layout.fillWidth: true
            Layout.topMargin: 4
            spacing: 14
            Repeater {
                model: page.tg && page.tg.kinds ? page.tg.kinds : []
                delegate: OCheckBox {
                    required property var modelData
                    text: modelData.label
                    checked: modelData.on
                    onToggled: App.telegramSetKind(modelData.key, checked)
                }
            }
        }

        OCheckBox {
            visible: !!page.tg && page.tg.linked && page.tg.backgroundSupported
            Layout.topMargin: 2
            text: qsTr("Uygulama kapalıyken de kontrol et")
            checked: !!page.tg && page.tg.background
            onToggled: App.telegramSetBackground(checked)
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 6
            spacing: 8
            visible: !!page.tg && !page.tg.error && page.tg.available
            Item { Layout.fillWidth: true }
            Spinner { visible: !!page.tg && page.tg.waiting }
            OButton {
                visible: !!page.tg && page.tg.waiting
                text: qsTr("Vazgeç")
                onClicked: App.telegramCancel()
            }
            OButton {
                visible: !!page.tg && page.tg.linked
                text: qsTr("Bağlantıyı kaldır")
                variant: "danger"
                onClicked: App.telegramDisconnect()
            }
            OButton {
                visible: !!page.tg && page.tg.linked
                text: qsTr("Deneme bildirimi")
                iconName: "bell"
                onClicked: App.telegramTest()
            }
            OButton {
                visible: !!page.tg && !page.tg.linked && !page.tg.waiting
                text: qsTr("Telegram'a bağla")
                iconName: "external"
                variant: "primary"
                onClicked: App.telegramConnect()
            }
        }
    }

    SectionCard {
        title: qsTr("Görünüm")
        iconName: App.themeMode === "dark" ? "moon" : "sun"
        Segmented {
            model: [{ value: "system", label: qsTr("Sistem") }, { value: "light", label: qsTr("Açık") },
                    { value: "dark", label: qsTr("Koyu") }]
            value: App.themeMode
            onPicked: v => App.themeMode = v
        }
    }

    SectionCard {
        title: qsTr("Şifre değiştir")
        iconName: "lock"
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8
            Field { id: oldPw; placeholderText: qsTr("Mevcut şifre") }
            Field { id: newPw; placeholderText: qsTr("Yeni şifre (6-30 karakter)") }
            Field { id: newPw2; placeholderText: qsTr("Yeni şifre (tekrar)"); onAccepted: changeBtn.clicked() }
            Text {
                visible: page.passwordMessage.length > 0
                Layout.fillWidth: true
                text: page.passwordMessage
                wrapMode: Text.WordWrap
                font.family: Theme.font
                font.pixelSize: Theme.fontSmall
                color: page.passwordOk ? Theme.accent : Theme.danger
            }
            OButton {
                id: changeBtn
                Layout.alignment: Qt.AlignRight
                variant: "primary"
                text: page.passwordBusy ? qsTr("Değiştiriliyor…") : qsTr("Şifreyi değiştir")
                enabled: !page.passwordBusy && oldPw.text.length > 0 && newPw.text.length > 0 && newPw2.text.length > 0
                onClicked: {
                    page.passwordMessage = ""
                    page.passwordBusy = true
                    App.changePassword(oldPw.text, newPw.text, newPw2.text)
                }
            }
        }
    }

    OButton {
        Layout.alignment: Qt.AlignLeft
        text: qsTr("Çıkış yap")
        iconName: "logout"
        variant: "danger"
        onClicked: App.logout()
    }
}
