# Модули DeckyBird

Каждый подкаталог в `modules/` отвечает за одну изолированную фичу:

- `controller/` — внешний демон управления геймпадом (портируется из `DeckyWolf/overlay/usr/bin/deckywolf-controller`). Не требует изменений в C++-коде Ladybird.
- `torrent/` — фоновый торрент-сервис + плагин для DeckyLoader (портируется из `DeckyWolf`). Открывается как веб-интерфейс (например, `http://127.0.0.1:8404`), magnet-ссылки перехватываются через XDG/ExternalURLHandler.
- `certs/` — корневые сертификаты Минцифры + генерация объединённого CA-бандла (`SSL_CERT_FILE`), который подхватывается `RequestServer` (libcurl/OpenSSL) без правки C++-кода.
- `startpage/` — кастомная стартовая страница, заменяющая `Base/res/ladybird/about-pages/newtab.html` (в AppImage лежит на диске в `usr/share/Lagom/ladybird/about-pages/newtab.html`).
- `defaults/` — шаблоны `Settings.json` и `Bookmarks.json`, которые `AppRun` разворачивает при первом запуске в `~/.config/Ladybird/`.
- `decky-bridge/` — тонкий C++/JS-мост для интеграции с `https://deckyloader.ru` (так как в Ladybird нет WebExtensions/JSWindowActor), а также локальный API и прокси-движок расширений.
- `webapps/` — менеджер веб-приложений (добавление ярлыков в Steam в раздел «Сторонние» с автоматической раскладкой Steam Input, запуск в изолированном профиле без адресной строки и вкладок, синхронизация списка со Steam).
- `extensions/` — рантайм расширений и пользовательских скриптов: встроенные `[VOT] - Voice Over Translation`, `uBlock Origin`, `Decentraleyes`, `GhostPrint`, `Privacy Badger`, а также менеджер пользовательских скриптов `.user.js` (бета) по принципу Tampermonkey с автообновлением и встроенным редактором кода.
- `ui-hook/` — изолированный `LD_PRELOAD`-хук Qt6 (`deckybird-ui-hook.so`) для добавления пунктов меню «Создать веб-приложение…», «Веб-приложения», «Расширения», скрытия панели вкладок/адреса в режиме веб-приложения (`DECKYBIRD_WEBAPP=1`), корректного `desktopFileName` в KDE и тач-прокрутки свайпами с инерцией.
