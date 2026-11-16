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
        id: tgCard
        title: qsTr("Telefon bildirimleri")
        iconName: "bell"
        badge: page.tg && page.tg.linked ? "Telegram • @" + page.tg.bot : ""

        component Step: RowLayout {
            id: step
            property int number
            property string text
            Layout.fillWidth: true
            spacing: 10
            Rectangle {
                Layout.alignment: Qt.AlignTop
                implicitWidth: 22
                implicitHeight: 22
                radius: 11
                color: Theme.accentSoft
                Text {
                    anchors.centerIn: parent
                    text: step.number
                    font.family: Theme.font
                    font.pixelSize: Theme.fontSmall
                    font.weight: Font.DemiBold
                    color: Theme.accent
                }
            }
            Text {
                Layout.fillWidth: true
                text: step.text
                textFormat: Text.StyledText
                wrapMode: Text.WordWrap
                font.family: Theme.font
                font.pixelSize: Theme.fontUi
                color: Theme.text
                lineHeight: 1.1
            }
        }

        // --- Bağlı değil: kendi botunu oluşturma talimatları
        ColumnLayout {
            visible: !!page.tg && !page.tg.linked && !page.tg.waiting
            Layout.fillWidth: true
            spacing: 10
            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                font.family: Theme.font
                font.pixelSize: Theme.fontUi
                color: Theme.textMuted
                text: qsTr("Yeni ödev, mesaj, duyuru ve sınav sonuçlarını telefonuna Telegram'dan al. Kendi botunu oluşturursun; anahtarı yalnızca bu bilgisayarın anahtarlığında saklanır, kimseyle paylaşılmaz.")
            }
            Step { number: 1; text: qsTr("Telegram'da <b>@BotFather</b>'ı aç (aşağıdaki düğme).") }
            Step { number: 2; text: qsTr("<b>/newbot</b> yaz. Bota bir ad ver (örn. <i>LimeOBS Bildirim</i>), sonra sonu <b>bot</b> ile biten bir kullanıcı adı seç (örn. <i>ayse_limeobs_bot</i>).") }
            Step { number: 3; text: qsTr("BotFather'ın verdiği anahtarı kopyala. <i>123456789:AAE…</i> gibi görünür.") }
            Step { number: 4; text: qsTr("Anahtarı aşağıya yapıştır ve <b>Bağla</b>'ya bas. Açılan bot sohbetinde <b>Başlat</b>'a dokun.") }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 4
                spacing: 8
                TextField {
                    id: tokenField
                    Layout.fillWidth: true
                    implicitHeight: 40
                    leftPadding: 12
                    echoMode: TextInput.Password
                    placeholderText: qsTr("Bot anahtarı")
                    font.family: Theme.font
                    font.pixelSize: Theme.fontUi
                    color: Theme.text
                    placeholderTextColor: Theme.textFaint
                    onAccepted: connectBtn.clicked()
                    background: Rectangle {
                        radius: Theme.radiusSm + 2
                        color: Theme.surfaceAlt
                        border.width: 1
                        border.color: tokenField.activeFocus ? Theme.accent : Theme.border
                    }
                }
                OButton {
                    text: qsTr("BotFather'ı aç")
                    iconName: "external"
                    onClicked: App.openUrl("https://t.me/BotFather")
                }
                OButton {
                    id: connectBtn
                    text: qsTr("Bağla")
                    variant: "primary"
                    enabled: tokenField.text.trim().length > 20
                    onClicked: {
                        App.telegramConnect(tokenField.text)
                        tokenField.text = ""
                    }
                }
            }
        }

        // --- Bağlanıyor: Başlat'a basılmasını bekle
        RowLayout {
            visible: !!page.tg && page.tg.waiting
            Layout.fillWidth: true
            spacing: 12
            Spinner {}
            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                textFormat: Text.StyledText
                font.family: Theme.font
                font.pixelSize: Theme.fontUi
                color: Theme.text
                text: page.tg ? qsTr("Telegram'da <b>@%1</b> sohbeti açıldı. <b>Başlat</b>'a dokun ya da bir mesaj yaz; bağlantı kendiliğinden tamamlanacak.").arg(page.tg.waitingBot) : ""
            }
            OButton {
                text: qsTr("Vazgeç")
                onClicked: App.telegramCancel()
            }
        }

        // --- Bağlı
        ColumnLayout {
            visible: !!page.tg && page.tg.linked
            Layout.fillWidth: true
            spacing: 8
            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                font.family: Theme.font
                font.pixelSize: Theme.fontUi
                color: Theme.textMuted
                text: page.tg ? qsTr("Bildirimler @%1 botundan telefonuna geliyor. Uygulama açıkken %2 dakikada bir kontrol edilir.").arg(page.tg.bot).arg(page.tg.interval) : ""
            }
            Flow {
                Layout.fillWidth: true
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
                visible: !!page.tg && page.tg.backgroundSupported
                text: qsTr("Uygulama kapalıyken de kontrol et")
                checked: !!page.tg && page.tg.background
                onToggled: App.telegramSetBackground(checked)
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item { Layout.fillWidth: true }
                OButton {
                    text: qsTr("Bağlantıyı kaldır")
                    variant: "danger"
                    onClicked: App.telegramDisconnect()
                }
                OButton {
                    text: qsTr("Deneme bildirimi")
                    iconName: "bell"
                    onClicked: App.telegramTest()
                }
            }
        }

        Text {
            visible: !page.tg
            text: qsTr("Durum alınıyor…")
            font.family: Theme.font
            font.pixelSize: Theme.fontUi
            color: Theme.textMuted
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
