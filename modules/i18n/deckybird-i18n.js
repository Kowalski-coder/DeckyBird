(function () {
    "use strict";
    if (window._deckyBirdI18nInstalled) return;
    window._deckyBirdI18nInstalled = true;

    const DICT = {
        // Common & Settings Tabs
        "Settings": "Настройки",
        "Search settings": "Поиск в настройках",
        "Appearance": "Внешний вид",
        "Search": "Поиск",
        "Browsing": "Просмотр",
        "Memory": "Память",
        "Privacy": "Приватность",
        "Privacy & Security": "Приватность и защита",
        "Permissions": "Разрешения",
        "Blocking": "Блокировка",
        "Content": "Содержимое",
        "Feedback": "Обратная связь",
        "Advanced": "Дополнительно",
        "Startup and browsing": "Запуск и просмотр",
        "Privacy and security": "Приватность и защита",
        "Content blocking": "Блокировка контента",
        "Languages": "Языки",
        "Network": "Сеть",
        "Startup": "Запуск",
        "Services": "Сервисы",
        "Tabs": "Вкладки",
        "Downloads": "Загрузки",
        "Bookmarks": "Закладки",
        "History": "История",
        "Crash Reports": "Отчёты о сбоях",
        "About Ladybird": "О DeckyBird",
        "Version": "Версия",

        // Appearance
        "Theme": "Тема оформления",
        "Interface theme": "Тема интерфейса",
        "Website color scheme": "Цветовая схема сайтов",
        "Accent color": "Акцентный цвет",
        "The colors of tabs, toolbars, menus and highlights.": "Цвета вкладок, панелей, меню и выделений.",
        "Websites": "Веб-сайты",
        "Whether websites are asked to show their light or dark design.": "Запрашивать у сайтов светлое или тёмное оформление.",
        "Darken web pages that don't provide a dark theme of their own.": "Затемнять веб-страницы без собственной тёмной темы.",
        "Layout": "Макет",
        "Tabs on top": "Вкладки сверху",
        "Tabs on the side": "Вкладки сбоку",
        "Everything in the sidebar": "Всё на боковой панели",
        "Only when hovering the navigation toolbar": "Только при наведении на панель навигации",
        "None": "Нет",
        "System": "Системная",
        "Light": "Светлая",
        "Dark": "Тёмная",
        "Force dark mode": "Принудительная тёмная тема",
        "Force dark mode on websites": "Принудительная тёмная тема для сайтов",
        "Enable force dark mode": "Включить принудительную тёмную тему",
        "Tab bar": "Панель вкладок",
        "Tab layout": "Расположение вкладок",
        "Horizontal tabs": "Горизонтальные вкладки",
        "Vertical tabs": "Вертикальные вкладки",
        "Vertical tabs (icons only)": "Вертикальные вкладки (только иконки)",
        "Expand on hover": "Раскрывать при наведении",
        "Sidebar position": "Позиция боковой панели",
        "Left": "Слева",
        "Right": "Справа",
        "Toolbars": "Панели инструментов",
        "Show system menu bar": "Показывать системную строку меню",
        "Show bookmarks bar": "Показывать панель закладок",
        "Always": "Всегда",
        "Never": "Никогда",
        "On hover": "При наведении",
        "On new tab": "На новой вкладке",
        "Default page zoom": "Масштаб страниц по умолчанию",
        "Zoom": "Масштаб",

        // Startup & Search
        "On startup": "При запуске",
        "New tab page": "Страница новой вкладки",
        "New tab page URL": "Адрес новой вкладки",
        "Restore previous session": "Восстанавливать предыдущую сессию",
        "Restore previous windows and tabs": "Восстанавливать предыдущие окна и вкладки",
        "Open a new tab page": "Открывать страницу новой вкладки",
        "Website languages": "Языки сайтов",
        "Languages that websites are asked to use, in order of preference.": "Предпочитаемые языки для отображения сайтов.",
        "Edit...": "Изменить…",
        "Edit…": "Изменить…",
        "Use autoscrolling": "Использовать автопрокрутку",
        "Scroll pages by pressing the middle mouse button and moving the mouse.": "Прокрутка страниц нажатием средней кнопки мыши и движением курсора.",
        "Paste with the middle mouse button": "Вставка средней кнопкой мыши",
        "Paste text from the clipboard when the middle mouse button is clicked.": "Вставлять текст из буфера обмена по нажатию средней кнопки мыши.",
        "Default search engine": "Поисковая система по умолчанию",
        "Search engine": "Поисковая система",
        "Custom search engines…": "Пользовательские поисковики…",
        "Custom search engines": "Пользовательские поисковики",
        "Show search suggestions": "Показывать поисковые подсказки",
        "Search suggestions": "Поисковые подсказки",
        "Add": "Добавить",
        "Save": "Сохранить",
        "Save changes": "Сохранить изменения",
        "Cancel": "Отмена",
        "Delete": "Удалить",
        "Remove": "Удалить",
        "Edit": "Изменить",
        "Close": "Закрыть",
        "Reset": "Сбросить",
        "Clear": "Очистить",
        "Clear...": "Очистить…",
        "Clear…": "Очистить…",
        "Name": "Название",
        "URL": "Адрес (URL)",

        // Privacy, Blocking & Feedback
        "Browsing data": "Данные браузера",
        "Clear browsing data": "Очистить данные браузера",
        "Global Privacy Control": "Global Privacy Control",
        "Tell websites not to sell or share your data.": "Сообщать сайтам не продавать и не передавать ваши данные.",
        "Automatic connections": "Автоматические подключения",
        "Allow automatic service connections": "Разрешить фоновые подключения сервисов",
        "Filter list updates": "Обновление списков фильтров",
        "Update checks": "Проверка обновлений",
        "Block ads, trackers and more": "Блокировать рекламу, трекеры и прочее",
        "Filter lists": "Списки фильтров",
        "Update enabled lists": "Обновить активные списки",
        "Add filter list...": "Добавить список…",
        "Add filter list…": "Добавить список…",
        "Show language-specific lists": "Показать региональные списки",
        "Custom filters": "Пользовательские фильтры",
        "Show Feedback button in toolbar": "Показывать кнопку отзыва на панели",
        "Ask me": "Спрашивать меня",
        "Never send": "Никогда не отправлять",
        "Nothing is kept": "Ничего не сохраняется",
        "Open folder": "Открыть папку",
        "Ladybird cannot determine or set the default browser on this system.": "Не удалось определить или назначить браузер по умолчанию в этой системе.",

        // Browsing & Memory
        "Scrolling": "Прокрутка",
        "Enable autoscroll": "Включить автопрокрутку",
        "Enable primary paste": "Вставка средней кнопкой мыши",
        "Tab discarding": "Выгрузка неактивных вкладок",
        "Discard hidden tabs after": "Выгружать скрытые вкладки через",
        "minutes": "минут",

        // Privacy & Permissions & Blocking
        "Tracking prevention": "Защита от отслеживания",
        "Send Global Privacy Control": "Отправлять сигнал Global Privacy Control",
        "Crash reporting": "Отчёты о сбоях",
        "Autoplay": "Автовоспроизведение",
        "Geolocation": "Геолокация",
        "Microphone": "Микрофон",
        "Notifications": "Уведомления",
        "Ask": "Спрашивать",
        "Allow": "Разрешить",
        "Block": "Блокировать",
        "Allow all": "Разрешать всё",
        "Block audio": "Блокировать звук",
        "Block all": "Блокировать всё",
        "Content blocking": "Блокировка контента",
        "Enable content blocking": "Включить блокировщик контента",
        "Built-in filter lists": "Встроенные списки фильтров",
        "Custom filter lists": "Пользовательские списки",
        "Disabled sites": "Исключения (сайты)",

        // Network & Advanced
        "DNS": "DNS",
        "Proxy": "Прокси",
        "Updates": "Обновления",
        "Check for updates": "Проверять обновления",
        "Background networking": "Фоновая сеть",
        "Default browser": "Браузер по умолчанию",
        "Make default": "Сделать по умолчанию",
        "Set as default": "Назначить по умолчанию",
        "Ladybird is your default browser": "DeckyBird выбран браузером по умолчанию",
        "Ladybird is not your default browser": "DeckyBird не выбран браузером по умолчанию",

        // Bookmarks / History / Downloads
        "Search bookmarks": "Поиск в закладках",
        "Add bookmark": "Добавить закладку",
        "New folder": "Новая папка",
        "Import bookmarks": "Импорт закладок",
        "Export bookmarks": "Экспорт закладок",
        "Search history": "Поиск в истории",
        "Clear history": "Очистить историю",
        "Today": "Сегодня",
        "Yesterday": "Вчера",
        "Search downloads": "Поиск в загрузках",
        "Clear downloads": "Очистить список загрузок",
        "Open": "Открыть",
        "Show in folder": "Показать в папке",
        "Retry": "Повторить",
        "No downloads yet": "Загрузок пока нет",
        "No bookmarks yet": "Закладок пока нет",
        "No history yet": "История пуста"
    };

    // Case-insensitive lookup helper
    const LOWER_DICT = {};
    for (const [k, v] of Object.entries(DICT)) {
        LOWER_DICT[k.toLowerCase()] = v;
    }

    function translateStr(s) {
        if (!s) return s;
        const trimmed = s.trim();
        if (!trimmed) return s;
        const hit = DICT[trimmed] || LOWER_DICT[trimmed.toLowerCase()];
        if (!hit) return s;
        return s.replace(trimmed, hit);
    }

    function translateNode(root) {
        if (!root) return;
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        let node;
        while ((node = walker.nextNode())) {
            const p = node.parentElement;
            if (!p || p.tagName === "SCRIPT" || p.tagName === "STYLE" || p.tagName === "CODE") continue;
            const t = translateStr(node.nodeValue);
            if (t !== node.nodeValue) node.nodeValue = t;
        }
        if (root.querySelectorAll) {
            root.querySelectorAll("[placeholder], [title], [aria-label]").forEach((el) => {
                for (const attr of ["placeholder", "title", "aria-label"]) {
                    const val = el.getAttribute(attr);
                    if (val) {
                        const t = translateStr(val);
                        if (t !== val) el.setAttribute(attr, t);
                    }
                }
            });
        }
    }

    function init() {
        translateNode(document.body || document.documentElement);
        if (document.title) document.title = translateStr(document.title);
        const obs = new MutationObserver((mutations) => {
            for (const m of mutations) {
                for (const n of m.addedNodes) {
                    if (n.nodeType === 1) translateNode(n);
                    else if (n.nodeType === 3 && n.parentElement) translateNode(n.parentElement);
                }
            }
        });
        obs.observe(document.documentElement, { childList: true, subtree: true });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
