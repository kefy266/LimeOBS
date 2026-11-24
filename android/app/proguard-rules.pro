# Jsoup'un isteğe bağlı re2j bağımlılığı ve OkHttp'nin isteğe bağlı TLS sağlayıcıları
-dontwarn com.google.re2j.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
-keepattributes Signature, InnerClasses, EnclosingMethod
# PDFBox-Android (yemek listesi): isteğe bağlı JPEG2000 çözücüsü yok; yazı tipi/kodlama sınıfları yansımayla yüklenir
-dontwarn com.gemalto.jp2.**
-keep class com.tom_roush.pdfbox.** { *; }
-keep class com.tom_roush.fontbox.** { *; }
