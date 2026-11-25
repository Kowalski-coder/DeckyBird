# Руководство по обновлению и публикации DeckyBird

## Схема версионирования

Версия релиза всегда строится по шаблону:

```text
<версия_оригинала_Ladybird>.<номер_ревизии_DeckyBird>
```

Примеры:
- `2026.47.8.1` — первый релиз DeckyBird на базе Ladybird `2026.47.8`
- `2026.47.8.2` — обновление только наших модулей/настроек поверх той же версии `2026.47.8`
- `2026.48.0.1` — обновление до новой версии Ladybird `2026.48.0`

---

## Пошаговый процесс обновления

### 1. Скачать новую версию оригинального Ladybird
Перейдите в папку `Update/` и выполните:
```bash
cd Update
./download_original.sh
```
Скрипт очистит `Update/Original/`, получит актуальную версию с `https://download.ladybird.org/releases.json`, скачает пакет `ubuntu24.04_amd64.deb` (совместимый по GLIBC со SteamOS) и сохранит номер версии в `Update/Original/VERSION`.

*(При необходимости скачать конкретную версию: `./download_original.sh 2026.47.8`.)*

### 2. Наложить модули DeckyBird и собрать `DeckyBird.AppImage`
```bash
./Patch_setup.sh 1
```
*(Где `1` — номер нашей ревизии; если вы обновляете модули повторно на том же оригинале, укажите `2`, `3` и т.д.)*

Скрипт:
1. Берёт оригинал из `Update/Original/`.
2. Подкладывает модули из `modules/` (`controller`, `torrent`, `certs`, `decky-bridge`, `i18n`, `startpage`, `defaults`) и оверлей из `overlay/` (`AppRun`, `.desktop`, логотип).
3. Упаковывает готовый `Update/DeckyBird/DeckyBird.AppImage` и записывает итоговую версию в `Update/DeckyBird/VERSION`.

### 3. Проверить перед публикацией
Рекомендуется перед публикацией проверить собранный образ на Steam Deck или локально:
- запуск стартовой страницы, адаптивная тема и логотипы;
- работа `deckyloader.ru` (инъекция моста, установка/удаление плагинов);
- работа TorrentWolf (`http://127.0.0.1:8404`);
- управление с геймпада (стики, трекпад, `L1/R1`, `B/X/Y`, `L2/R2`).

---

## Публикация релиза

Исходный код модулей и скриптов хранится в двух репозиториях (папка `ForSteamUI/` и бинарники в Git не коммитятся):
- **GitHub:** `https://github.com/Kowalski-coder/DeckyBird`
- **MosHub:** `https://hub.mos.ru/Kowalski-coder/DeckyBird`

### 1. Отправка изменений кода
```bash
git add .
git commit -m "Update to $(cat Update/DeckyBird/VERSION)"
git push origin master
git push moshub master
```

### 2. Публикация релиза с `DeckyBird.AppImage`
- **GitHub (через `gh` CLI):**
  ```bash
  VER="$(cat Update/DeckyBird/VERSION)"
  gh release create "$VER" Update/DeckyBird/DeckyBird.AppImage \
    --repo Kowalski-coder/DeckyBird \
    --title "DeckyBird $VER" \
    --notes "Релиз DeckyBird $VER на базе Ladybird $(cat Update/Original/VERSION)"
  ```
- **MosHub (GitLab Releases API):**
  1. Загрузить `Update/DeckyBird/DeckyBird.AppImage` как Generic Package в реестр пакетов проекта (`/api/v4/projects/<id>/packages/generic/DeckyBird/<VER>/DeckyBird.AppImage`).
  2. Создать тег и релиз через `/api/v4/projects/<id>/releases`, прикрепив ссылку на загруженный пакет.
