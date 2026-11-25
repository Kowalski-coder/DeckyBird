# Модули DeckyBird

Каждый подкаталог в `modules/` отвечает за одну изолированную фичу:

- `controller/` — внешний демон управления геймпадом (портируется из `DeckyWolf/overlay/usr/bin/deckywolf-controller`). Не требует изменений в C++-коде Ladybird.
- `torrent/` — фоновый торрент-сервис + плагин для DeckyLoader (портируется из `DeckyWolf`). Открывается как веб-интерфейс (например, `http://127.0.0.1:8404`), magnet-ссылки перехватываются через XDG/ExternalURLHandler.
- `certs/` — корневые сертификаты Минцифры + генерация объединённого CA-бандла (`SSL_CERT_FILE`), который подхватывается `RequestServer` (libcurl/OpenSSL) без правки C++-кода.
- `startpage/` — кастомная стартовая страница, заменяющая `Base/res/ladybird/about-pages/newtab.html` (в AppImage лежит на диске в `usr/share/Lagom/ladybird/about-pages/newtab.html`).
- `defaults/` — шаблоны `Settings.json` и `Bookmarks.json`, которые `AppRun` разворачивает при первом запуске в `~/.config/Ladybird/`.
- `decky-bridge/` — тонкий C++/JS-мост для интеграции с `https://deckyloader.ru` (так как в Ladybird нет WebExtensions/JSWindowActor), а также опциональные точечные UI-хуки.
