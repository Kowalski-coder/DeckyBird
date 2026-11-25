#include <QString>
#include <dlfcn.h>
#include <cstring>
#include <string>

struct TransEntry {
    const char* en;
    const char* ru;
};

static const TransEntry kTranslations[] = {
    // Navigation & Page Context Menu
    {"Back", "Назад"},
    {"Forward", "Вперёд"},
    {"Reload", "Обновить"},
    {"Reload Without Cache", "Обновить без кэша"},
    {"Stop", "Остановить"},
    {"View Page Source", "Исходный код страницы"},
    {"Inspect Element", "Исследовать элемент"},
    {"Inspect", "Инспектор"},
    {"Take Screenshot...", "Сделать снимок экрана…"},
    {"Take Screenshot…", "Сделать снимок экрана…"},
    {"Report Website Issue...", "Сообщить о проблеме сайта…"},
    {"Report Website Issue…", "Сообщить о проблеме сайта…"},
    {"Full Screen", "На весь экран"},
    {"Exit Full Screen", "Выйти из полноэкранного режима"},

    // Editing
    {"Undo", "Отменить"},
    {"Redo", "Повторить"},
    {"Cut", "Вырезать"},
    {"Copy", "Копировать"},
    {"Paste", "Вставить"},
    {"Paste and Match Style", "Вставить без форматирования"},
    {"Delete", "Удалить"},
    {"Select All", "Выделить всё"},
    {"Look Up", "Найти"},
    {"Ignore Spelling", "Пропустить слово"},
    {"Learn Spelling", "Запомнить слово"},
    {"No Guesses Found", "Вариантов не найдено"},

    // Link / Image / Media Context Menus
    {"Open Link in New Tab", "Открыть ссылку в новой вкладке"},
    {"Open Link in New Window", "Открыть ссылку в новом окне"},
    {"Open Link in Private Window", "Открыть ссылку в приватном окне"},
    {"Copy Link", "Копировать адрес ссылки"},
    {"Copy Email Address", "Копировать email-адрес"},
    {"Copy Phone Number", "Копировать номер телефона"},
    {"Download Linked File", "Скачать файл по ссылке"},
    {"Save Link As...", "Сохранить ссылку как…"},
    {"Save Link As…", "Сохранить ссылку как…"},
    {"Open Image", "Открыть изображение"},
    {"Open Image in New Tab", "Открыть изображение в новой вкладке"},
    {"Copy Image", "Копировать изображение"},
    {"Copy Image Address", "Копировать адрес изображения"},
    {"Save Image As...", "Сохранить изображение как…"},
    {"Save Image As…", "Сохранить изображение как…"},
    {"Open Audio", "Открыть аудио"},
    {"Open Audio in New Tab", "Открыть аудио в новой вкладке"},
    {"Copy Audio Address", "Копировать адрес аудио"},
    {"Open Video", "Открыть видео"},
    {"Open Video in New Tab", "Открыть видео в новой вкладке"},
    {"Copy Video Address", "Копировать адрес видео"},
    {"Play", "Воспроизвести"},
    {"Pause", "Пауза"},
    {"Mute", "Выключить звук"},
    {"Unmute", "Включить звук"},
    {"Loop", "Повтор"},
    {"Show Controls", "Показать элементы управления"},
    {"Hide Controls", "Скрыть элементы управления"},
    {"Picture in Picture", "Картинка в картинке"},
    {"Exit Picture in Picture", "Выйти из режима «Картинка в картинке»"},

    // Main Menu, Tabs, Bookmarks, History, Downloads, Settings
    {"File", "Файл"},
    {"Edit", "Правка"},
    {"View", "Вид"},
    {"History", "История"},
    {"View History", "Показать историю"},
    {"Bookmarks", "Закладки"},
    {"Add Bookmark", "Добавить закладку"},
    {"Bookmark All Tabs...", "Добавить все вкладки в закладки…"},
    {"Bookmark All Tabs…", "Добавить все вкладки в закладки…"},
    {"Tools", "Инструменты"},
    {"Window", "Окно"},
    {"Help", "Справка"},
    {"New Tab", "Новая вкладка"},
    {"New Window", "Новое окно"},
    {"New Private Window", "Новое приватное окно"},
    {"Close Tab", "Закрыть вкладку"},
    {"Close Window", "Закрыть окно"},
    {"Reopen Closed Tab", "Открыть закрытую вкладку"},
    {"Duplicate Tab", "Дублировать вкладку"},
    {"Pin Tab", "Закрепить вкладку"},
    {"Unpin Tab", "Открепить вкладку"},
    {"Mute Tab", "Выключить звук вкладки"},
    {"Unmute Tab", "Включить звук вкладки"},
    {"Reload Tab", "Обновить вкладку"},
    {"Close Other Tabs", "Закрыть другие вкладки"},
    {"Close Tabs to Right", "Закрыть вкладки справа"},
    {"Always on Top", "Поверх всех окон"},
    {"Tab Layout", "Расположение вкладок"},
    {"Tabs on Top", "Вкладки сверху"},
    {"Tabs on the Side", "Вкладки сбоку"},
    {"Everything in the Sidebar", "Всё на боковой панели"},
    {"Downloads", "Загрузки"},
    {"Settings", "Настройки"},
    {"Settings...", "Настройки…"},
    {"Settings…", "Настройки…"},
    {"Quit", "Выход"},
    {"Exit", "Выход"},
    {"Zoom", "Масштаб"},
    {"Zoom In", "Увеличить"},
    {"Zoom Out", "Уменьшить"},
    {"Reset Zoom", "Сбросить масштаб"},
    {"Find in Page...", "Найти на странице…"},
    {"Find in Page…", "Найти на странице…"},
    {"Find Next", "Найти далее"},
    {"Find Previous", "Найти ранее"},
    {"Show Sidebar", "Показать боковую панель"},
    {"Hide Sidebar", "Скрыть боковую панель"},
    {"Show Bookmarks Bar", "Показывать панель закладок"},
    {"Bookmark This Page", "Добавить страницу в закладки"},
    {"Manage Bookmarks", "Управление закладками"},
    {"Show All History", "Показать всю историю"},
    {"Clear Browsing Data", "Очистить данные браузера"},
    {"Clear Browsing Data...", "Очистить данные браузера…"},
    {"Clear Browsing Data…", "Очистить данные браузера…"},
    {"About Ladybird", "О DeckyBird"},
    {"Check for Updates...", "Проверить обновления…"},
    {"Check for Updates…", "Проверить обновления…"},
    {"Open File...", "Открыть файл…"},
    {"Open File…", "Открыть файл…"},
    {"Save Page As...", "Сохранить страницу как…"},
    {"Save Page As…", "Сохранить страницу как…"},
    {"Print...", "Печать…"},
    {"Print…", "Печать…"},
    {"Enable DevTools", "Включить DevTools"},
    {"Disable DevTools", "Отключить DevTools"},
    {"Force Dark Mode", "Принудительная тёмная тема"},
    {"Block Pop-ups", "Блокировать всплывающие окна"},
    {"Enable Scripting", "Включить JavaScript"},
    {"Task Manager", "Диспетчер задач"},
    {"Process Manager", "Диспетчер процессов"},

    // Common Dialog Buttons
    {"OK", "ОК"},
    {"Cancel", "Отмена"},
    {"Close", "Закрыть"},
    {"Save", "Сохранить"},
    {"Open", "Открыть"},
    {"Apply", "Применить"},
    {"Yes", "Да"},
    {"No", "Нет"},
};

static std::string strip_mnemonic(const char* src) {
    std::string out;
    if (!src) return out;
    for (size_t i = 0; src[i] != '\0'; ++i) {
        if (src[i] == '&') {
            if (src[i + 1] == '&') {
                out.push_back('&');
                ++i;
            }
            continue;
        }
        out.push_back(src[i]);
    }
    return out;
}

static const char* lookup_translation(const char* src) {
    if (!src || !*src) return nullptr;
    std::string clean = strip_mnemonic(src);
    if (clean.empty()) return nullptr;
    for (const auto& item : kTranslations) {
        if (clean == item.en) {
            return item.ru;
        }
    }
    return nullptr;
}

static QString translate_qstring(const QString& text) {
    QByteArray utf8 = text.toUtf8();
    const char* ru = lookup_translation(utf8.constData());
    if (ru) {
        return QString::fromUtf8(ru);
    }
    return text;
}

extern "C" {

void _ZN7QAction7setTextERK7QString(void* self, const QString& text) {
    using Fn = void (*)(void*, const QString&);
    static Fn orig = reinterpret_cast<Fn>(dlsym(RTLD_NEXT, "_ZN7QAction7setTextERK7QString"));
    if (!orig) return;
    QString tr = translate_qstring(text);
    orig(self, tr);
}

void _ZN7QActionC1ERK7QStringP7QObject(void* self, const QString& text, void* parent) {
    using Fn = void (*)(void*, const QString&, void*);
    static Fn orig = reinterpret_cast<Fn>(dlsym(RTLD_NEXT, "_ZN7QActionC1ERK7QStringP7QObject"));
    if (!orig) return;
    QString tr = translate_qstring(text);
    orig(self, tr, parent);
}

void _ZN7QActionC2ERK7QStringP7QObject(void* self, const QString& text, void* parent) {
    using Fn = void (*)(void*, const QString&, void*);
    static Fn orig = reinterpret_cast<Fn>(dlsym(RTLD_NEXT, "_ZN7QActionC2ERK7QStringP7QObject"));
    if (!orig) return;
    QString tr = translate_qstring(text);
    orig(self, tr, parent);
}

void _ZN5QMenu8setTitleERK7QString(void* self, const QString& title) {
    using Fn = void (*)(void*, const QString&);
    static Fn orig = reinterpret_cast<Fn>(dlsym(RTLD_NEXT, "_ZN5QMenu8setTitleERK7QString"));
    if (!orig) return;
    QString tr = translate_qstring(title);
    orig(self, tr);
}

void _ZN5QMenuC1ERK7QStringP7QWidget(void* self, const QString& title, void* parent) {
    using Fn = void (*)(void*, const QString&, void*);
    static Fn orig = reinterpret_cast<Fn>(dlsym(RTLD_NEXT, "_ZN5QMenuC1ERK7QStringP7QWidget"));
    if (!orig) return;
    QString tr = translate_qstring(title);
    orig(self, tr, parent);
}

void _ZN5QMenuC2ERK7QStringP7QWidget(void* self, const QString& title, void* parent) {
    using Fn = void (*)(void*, const QString&, void*);
    static Fn orig = reinterpret_cast<Fn>(dlsym(RTLD_NEXT, "_ZN5QMenuC2ERK7QStringP7QWidget"));
    if (!orig) return;
    QString tr = translate_qstring(title);
    orig(self, tr, parent);
}

void _ZN15QAbstractButton7setTextERK7QString(void* self, const QString& text) {
    using Fn = void (*)(void*, const QString&);
    static Fn orig = reinterpret_cast<Fn>(dlsym(RTLD_NEXT, "_ZN15QAbstractButton7setTextERK7QString"));
    if (!orig) return;
    QString tr = translate_qstring(text);
    orig(self, tr);
}

void _ZN6QLabel7setTextERK7QString(void* self, const QString& text) {
    using Fn = void (*)(void*, const QString&);
    static Fn orig = reinterpret_cast<Fn>(dlsym(RTLD_NEXT, "_ZN6QLabel7setTextERK7QString"));
    if (!orig) return;
    QString tr = translate_qstring(text);
    orig(self, tr);
}

void _ZN6QLabelC1ERK7QStringP7QWidget6QFlagsIN2Qt10WindowTypeEE(void* self, const QString& text, void* parent, unsigned int flags) {
    using Fn = void (*)(void*, const QString&, void*, unsigned int);
    static Fn orig = reinterpret_cast<Fn>(dlsym(RTLD_NEXT, "_ZN6QLabelC1ERK7QStringP7QWidget6QFlagsIN2Qt10WindowTypeEE"));
    if (!orig) return;
    QString tr = translate_qstring(text);
    orig(self, tr, parent, flags);
}

void _ZN6QLabelC2ERK7QStringP7QWidget6QFlagsIN2Qt10WindowTypeEE(void* self, const QString& text, void* parent, unsigned int flags) {
    using Fn = void (*)(void*, const QString&, void*, unsigned int);
    static Fn orig = reinterpret_cast<Fn>(dlsym(RTLD_NEXT, "_ZN6QLabelC2ERK7QStringP7QWidget6QFlagsIN2Qt10WindowTypeEE"));
    if (!orig) return;
    QString tr = translate_qstring(text);
    orig(self, tr, parent, flags);
}

}
