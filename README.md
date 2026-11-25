# DeckyBird 🐦🎮

Форк браузера [Ladybird](https://github.com/LadybirdBrowser/ladybird) для **Steam Deck / SteamOS** в формате **AppImage**, построенный по модульному принципу (по аналогии с DeckyWolf).

## Структура проекта

```
DeckyBird/
├── ladybird/                  # Чистый upstream-репозиторий Ladybird (не смешивается с нашими фичами)
├── modules/                   # Изолированные модули DeckyBird
│   ├── controller/            # Управление с геймпада (порт deckywolf-controller)
│   ├── torrent/               # Торрент-клиент + плагин DeckyLoader
│   ├── certs/                 # Сертификаты Минцифры (изолированный бандл через SSL_CERT_FILE)
│   ├── startpage/             # Собственная стартовая страница (about:newtab)
│   ├── defaults/              # Дефолтные настройки (Settings.json) и закладки (Bookmarks.json)
│   └── decky-bridge/          # Модуль интеграции с deckyloader.ru и тонкими C++/WebUI хуками
├── overlay/                   # Файлы для наложения в AppDir (AppRun, .desktop, иконки, бинарники)
├── patches/                   # Минимальные патчи к upstream ladybird/ (только там, где нельзя иначе)
├── scripts/                   # Скрипты обновления upstream, наложения модулей и сборки AppImage
├── docker/                    # Контейнер Ubuntu 24.04 для сборки AppImage, совместимого со SteamOS
└── docs/
    └── ARCHITECTURE.md        # Архитектурный разбор, модульность и план адаптации фич
```

## Быстрый старт (следующие шаги)

1. Изучите [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — там разобрано устройство Ladybird, какие фичи подключаются без пересборки C++ (через `overlay/` и `AppRun`), а какие требуют тонкого C++-модуля.
2. Для сборки под SteamOS потребуется Docker (сборка в `ubuntu:24.04` для совместимости GLIBC, так как на хосте GLIBC 2.44).
3. Подробности по скриптам — в `scripts/`.
