pragma Singleton
import QtQuick
import LimeBackend

// Orbital'in sıcak nötr paleti (açık + koyu), tek vurgu rengi: LimeOBS yeşili.
QtObject {
    readonly property bool dark: App.themeMode === "dark"
                                 || (App.themeMode === "system" && Application.styleHints.colorScheme === Qt.ColorScheme.Dark)

    readonly property color bg:           dark ? "#262624" : "#faf9f5"
    readonly property color sidebar:      dark ? "#1f1e1d" : "#f3f1ea"
    readonly property color surface:      dark ? "#30302e" : "#ffffff"
    readonly property color surfaceAlt:   dark ? "#2b2b29" : "#f5f4ef"
    readonly property color elevated:     dark ? "#353533" : "#ffffff"
    readonly property color userBubble:   dark ? "#3a3936" : "#efede5"
    readonly property color hover:        dark ? "#2f2f2c" : "#ebe9e1"
    readonly property color selected:     dark ? "#3a3936" : "#e5e2d8"
    readonly property color border:       dark ? "#3e3d3a" : "#e4e1d6"
    readonly property color borderStrong: dark ? "#55534e" : "#cfcbbd"

    readonly property color text:      dark ? "#f2f1ec" : "#1f1e1d"
    readonly property color textMuted: dark ? "#bfbdb4" : "#5e5d58"
    readonly property color textFaint: dark ? "#8e8c84" : "#8d8b84"

    readonly property color accent:      dark ? "#8fd37e" : "#3f8f34"
    readonly property color accentHover: dark ? "#a3de94" : "#357a2b"
    readonly property color accentSoft:  dark ? "#2a3a25" : "#e8f3e2"
    readonly property color textOnAccent: dark ? "#14210f" : "#ffffff"
    readonly property color danger:      dark ? "#f08a7a" : "#c2412d"
    readonly property color dangerSoft:  dark ? "#3a2622" : "#fbeae6"
    readonly property color warning:     dark ? "#e8c06a" : "#a8700f"

    function firstFamily(candidates, fallback) {
        const installed = Qt.fontFamilies()
        for (const f of candidates)
            if (installed.indexOf(f) >= 0)
                return f
        return fallback
    }
    readonly property string font: firstFamily(["Inter", "Segoe UI Variable Text", "Segoe UI", ".AppleSystemUIFont",
                                                "SF Pro Text", "Noto Sans", "Cantarell"], Qt.application.font.family)
    readonly property int fontCaption: 12
    readonly property int fontSmall:   13
    readonly property int fontUi:      14
    readonly property int fontBody:    16
    readonly property int fontTitle:   18
    readonly property int fontHeading: 22
    readonly property int fontDisplay: 30

    readonly property int radiusSm: 8
    readonly property int radius:   12
    readonly property int radiusLg: 20
    readonly property int contentWidth: 820
    readonly property int sidebarWidth: 256

    readonly property int fast: 120
    readonly property int normal: 220
}
