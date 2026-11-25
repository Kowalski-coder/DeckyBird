# Архитектура DeckyBird и оценка модульности

## 1. Что из себя представляет Ladybird

В отличие от LibreWolf (Firefox/Gecko), где весь интерфейс браузера (XHTML/JS/CSS), настройки, политики и расширения лежат в распаковываемом `omni.ja`, **Ladybird** — это нативный многопроцессный браузер на **C++23 + Qt 6.10+ + Rust** с собственной системой сборки (CMake + vcpkg + Ninja):

- **UI и оболочка (`UI/Qt/`)**: нативные виджеты и окна на Qt6 (`Application.cpp`, `BrowserWindow.cpp`, `TabBar.cpp`, `WindowToolbar.cpp`, `BookmarkStore.cpp`, `ExternalURLHandler.cpp`).
- **Настройки и WebUI (`Libraries/LibWebView/`)**: настройки хранятся в JSON (`Settings.json` в каталоге профиля `profile().paths().config`), внутренние страницы `about:*` (`WebUI`, `SettingsUI`) общаются с бэкендом через IPC.
- **Ресурсы (`Base/res/ladybird/about-pages/`)**: HTML/CSS/JS файлы (`newtab.html`, `welcome.html`, `settings.html`, `bookmarks.html` и др.) устанавливаются на диск (`usr/share/Lagom/ladybird/about-pages/`) — согласно `UI/cmake/ResourceFiles.cmake`, они **не вшиваются в бинарник**, их можно подменять прямо в `AppDir`.
- **Сеть и TLS (`Services/RequestServer/`)**: использует **libcurl** (`Request.cpp`, `WebSocketImplCurl.cpp`) и OpenSSL. В `Libraries/LibWebView/Process.cpp` переменные окружения `SSL_CERT_FILE` и `SSL_CERT_DIR` явно пробрасываются в дочерние процессы.
- **Расширения**: поддержка WebExtensions / JSWindowActor в Ladybird **отсутствует**.
- **Официальная сборка AppImage**: в репозитории уже есть `Meta/package-appimage.sh` и CI-пайплайн `.github/workflows/build-release.yml` на базе `ubuntu:24.04`.

---

## 2. Критическое требование для SteamOS (GLIBC и Gamescope)

1. **Совместимость GLIBC**:
   - На текущей хост-системе (CachyOS/Arch) установлена **GLIBC 2.44**. Бинарники, собранные на ней, **не запустятся на SteamOS** (SteamOS 3.5/3.6 использует GLIBC 2.38, SteamOS 3.7+ — 2.39/2.40).
   - **Решение**: собирать Ladybird внутри Docker-контейнера `ubuntu:24.04` (как делает официальный CI Ladybird в `.github/workflows/build-release.yml`) или переиспользовать официальные предсобранные AppImage-релизы Ladybird для тех случаев, когда C++-патчи не менялись.
2. **SteamOS Game Mode (Gamescope)**:
   - В `DeckyWolf` (`overlay/root/AppRun`) для Gamescope принудительно отключается Wayland (`unset WAYLAND_DISPLAY`) и используется X11 + EGL, так как Gamescope не реализует все десктопные протоколы Wayland.
   - В Ladybird есть и `WaylandWindow.cpp`, и `X11Window.cpp` (Qt6). Поведение в Gamescope нужно будет протестировать и при необходимости задать переменные окружения (`QT_QPA_PLATFORM=xcb` и др.) в нашем `AppRun`.

---

## 3. Можно ли сделать фичи в виде отдельного модуля (без переборки кода)?

**Ответ: Да, почти полностью (~85–90% функционала), по двухслойной схеме.**

### Слой 1: Внешний overlay + `AppRun` (НЕ требует пересборки C++ Ladybird)

Эти фичи можно «подкидывать» скриптом как поверх свежесобранного `AppDir`, так и поверх готового AppImage от разработчиков Ladybird:

1. **Управление с геймпада (`modules/controller/`)**
   - В `DeckyWolf` это автономный Python-демон `deckywolf-controller` (читает геймпад и эмулирует мышь/клавиатуру/скролл), запускаемый из `AppRun`.
   - Полностью переносится без правки кода Ladybird.
2. **Встроенный торрент-клиент + плагин DeckyLoader (`modules/torrent/`)**
   - В `DeckyWolf` это автономный сервис `deckywolf-torrent-service` (systemd user unit) + архив плагина `TorrentWolf.zip` для DeckyLoader + веб-интерфейс на `http://127.0.0.1:8404`.
   - Работает независимо от движка браузера. Для `magnet:`-ссылок `ExternalURLHandler.cpp` в Ladybird использует `gio` (`GAppInfo`), поэтому достаточно зарегистрировать `.desktop`-обработчик `x-scheme-handler/magnet` из `AppRun`.
3. **Сертификаты Минцифры (`modules/certs/`)**
   - Так как `Libraries/LibWebView/Process.cpp` пробрасывает `SSL_CERT_FILE` в `RequestServer`, мы можем генерировать объединённый PEM-бандл (системные CA + сертификаты Минцифры) и управлять его подключением через переменную `SSL_CERT_FILE` в `AppRun` (или обёртке запуска).
   - *Корректировка относительно DeckyWolf*: в `DeckyWolf` режим «Белый Лис» имел отдельную кнопку на тулбаре и изолированный профиль. Если нужен переключатель прямо в окне браузера без перезапуска — потребуется небольшой C++-хук (Слой 2); если достаточно переключателя в стартовой странице / отдельном ярлыке / конфиге — работает без C++.
4. **Собственная стартовая страница (`modules/startpage/`)**
   - Замена `usr/share/Lagom/ladybird/about-pages/newtab.html` (и сопутствующих CSS/JS/иконок) прямо в `AppDir`.
   - Можно разместить на ней быстрые ссылки на торрент-клиент, `deckyloader.ru`, поиск и статус контроллера.
5. **Дефолтные настройки и закладки (`modules/defaults/`)**
   - Шаблоны `Settings.json` и `Bookmarks.json`, которые `AppRun` копирует в `~/.config/Ladybird/` при первом запуске (если файлы ещё не созданы пользователем).

### Слой 2: Тонкий C++-модуль (`modules/decky-bridge/` + `patches/`)

Единственная фича, которую **нельзя** сделать чисто снаружи без изменений в коде браузера (или изменения протокола самого сайта):

1. **Управление плагинами DeckyLoader через сайт `deckyloader.ru`**:
   - В `DeckyWolf` используется `JSWindowActor` (`DeckySiteIntegrationChild.sys.mjs`), который инжектирует обработчик `window.postMessage` на страницу `deckyloader.ru` и проксирует запросы в локальный сервис.
   - В Ladybird **нет системы расширений / WebExtensions**.
   - **Два варианта решения**:
     - **Вариант А (рекомендуемый — тонкий модуль `decky-bridge`)**: добавить в Ladybird минимальный изолированный C++-модуль (`modules/decky-bridge/`), который подключается одним-двумя вызовами из `LibWebView`/`WebContent` (через небольшой patch в `patches/`) и:
       1. Инжектирует JS-мост только для доверенного origin `https://deckyloader.ru`.
       2. Принимает `deckywolf-*` / `deckybird-*` сообщения и отправляет их по локальному HTTP/Unix-сокету в наш демон.
     - **Вариант Б (без C++-патчей)**: если сайт `deckyloader.ru` сам умеет обращаться напрямую на `http://127.0.0.1:<port>` (CORS + localhost), то мост в браузере вообще не нужен. Но если сайт общается только через `window.postMessage` (как в `DeckySiteIntegrationChild.sys.mjs`), то нужен Вариант А.
2. **Опционально (для удобства обновления)**:
   - Ребрендинг (`DeckyBird` вместо `Ladybird`, своя иконка и `.desktop` ID `net.deckybird.DeckyBird`) — делается на этапе упаковки AppImage в `overlay/` и/или минимальным патчем `BrandColors.h` / `CMakeLists.txt`.

---

## 4. Итоговый пайплайн обновления Ladybird

```
[Выходит обновление Ladybird]
        │
        ▼
1. ./scripts/update-upstream.sh     # git pull в ladybird/
        │
        ▼
2. ./scripts/apply-modules.sh       # подкидывает modules/decky-bridge и patches/ в ladybird/
        │
        ▼
3. ./scripts/build-docker.sh        # сборка в Ubuntu 24.04 (совместимо со SteamOS)
        │                             (или пропуск, если C++ не менялся и есть готовый AppImage)
        ▼
4. ./scripts/build-appimage.sh      # накладывает overlay/ + modules/{controller,torrent,certs,startpage,defaults}
        │                             и собирает DeckyBird-x86_64.AppImage
        ▼
[Готовый DeckyBird.AppImage для SteamOS]
```
