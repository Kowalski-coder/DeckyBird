#include <QAction>
#include <QApplication>
#include <QCoreApplication>
#include <QEvent>
#include <QLineEdit>
#include <QMainWindow>
#include <QMenu>
#include <QPointer>
#include <QProcess>
#include <QPushButton>
#include <QStackedWidget>
#include <QString>
#include <QTabBar>
#include <QTimer>
#include <QToolButton>
#include <QUrl>
#include <QUrlQuery>
#include <QWidget>
#include <cstdlib>
#include <dlfcn.h>
#include <string>

static bool is_webapp_mode() {
    static int cached = -1;
    if (cached == -1) {
        const char* env = std::getenv("DECKYBIRD_WEBAPP");
        cached = (env && env[0] == '1') ? 1 : 0;
    }
    return cached == 1;
}

static bool is_gamescope_mode() {
    static int cached = -1;
    if (cached == -1) {
        const char* gs = std::getenv("GAMESCOPE_WAYLAND_DISPLAY");
        const char* desk = std::getenv("XDG_CURRENT_DESKTOP");
        cached = ((gs && gs[0] != '\0') || (desk && std::string(desk) == "gamescope")) ? 1 : 0;
    }
    return cached == 1;
}

static QMenu* get_button_menu(QWidget* w) {
    if (auto* btn = qobject_cast<QToolButton*>(w)) return btn->menu();
    if (auto* pbtn = qobject_cast<QPushButton*>(w)) return pbtn->menu();
    return nullptr;
}

static bool is_chrome_widget(QWidget* w) {
    if (!w) return false;
    QString name = w->objectName();
    if (name == QStringLiteral("LadybirdToolbarContainer") ||
        name == QStringLiteral("LadybirdBookmarksBar") ||
        name == QStringLiteral("LadybirdBookmarksBarContainer") ||
        name == QStringLiteral("LadybirdMenuBar") ||
        name == QStringLiteral("LadybirdNewTabButton") ||
        name == QStringLiteral("LadybirdNavigationToolbar")) {
        return true;
    }
    if (qobject_cast<QTabBar*>(w) != nullptr) {
        return true;
    }
    if (QMenu* m = get_button_menu(w)) {
        if (m->objectName() == QStringLiteral("LadybirdMenu")) {
            return true;
        }
    }
    return false;
}

class WebAppLayoutFilter final : public QObject {
public:
    QPointer<QWidget> page_col;
    QPointer<QWidget> col_parent;
    bool adjusting { false };

    WebAppLayoutFilter(QWidget* col, QWidget* parent)
        : QObject(parent), page_col(col), col_parent(parent) {}

    bool eventFilter(QObject* watched, QEvent* event) override {
        if (!adjusting && page_col && col_parent &&
            (event->type() == QEvent::Resize || event->type() == QEvent::Move || event->type() == QEvent::LayoutRequest)) {
            if (watched == col_parent || watched == page_col) {
                QRect target(0, 0, col_parent->width(), col_parent->height());
                if (page_col->geometry() != target) {
                    adjusting = true;
                    page_col->setGeometry(target);
                    page_col->raise();
                    adjusting = false;
                }
            }
        }
        return QObject::eventFilter(watched, event);
    }
};

static void hide_webapp_chrome(QWidget* root) {
    if (!root) return;
    const auto children = root->findChildren<QWidget*>();
    for (QWidget* child : children) {
        if (!child) continue;
        if (is_chrome_widget(child)) {
            child->setMaximumHeight(0);
            child->hide();
            if (QMenu* m = get_button_menu(child)) {
                if (m->objectName() == QStringLiteral("LadybirdMenu")) {
                    if (QWidget* p = child->parentWidget()) {
                        if (p != root) {
                            p->setMaximumHeight(0);
                            p->hide();
                        }
                    }
                }
            }
        }
    }

    // Collapse m_toolbar_placeholder inside m_page_column and stretch m_page_column to (0, 0, w, h)
    if (auto* stack = root->findChild<QStackedWidget*>()) {
        if (QWidget* page_col = stack->parentWidget()) {
            for (QObject* obj : page_col->children()) {
                if (auto* w = qobject_cast<QWidget*>(obj)) {
                    if (w != stack) {
                        w->setMaximumHeight(0);
                        w->hide();
                    }
                }
            }
            if (QWidget* col_parent = page_col->parentWidget()) {
                for (QObject* obj : col_parent->children()) {
                    if (auto* w = qobject_cast<QWidget*>(obj)) {
                        if (w != page_col && !w->isAncestorOf(stack)) {
                            w->setMaximumHeight(0);
                            w->hide();
                        }
                    }
                }
                if (!col_parent->property("deckybird_layout_filter").toBool()) {
                    col_parent->setProperty("deckybird_layout_filter", true);
                    auto* flt = new WebAppLayoutFilter(page_col, col_parent);
                    col_parent->installEventFilter(flt);
                    page_col->installEventFilter(flt);
                }
                page_col->setGeometry(0, 0, col_parent->width(), col_parent->height());
                page_col->raise();
            }
        }
    }
}

static void open_deckybird_url(const QString& url) {
    QString exe = QCoreApplication::applicationFilePath();
    if (exe.isEmpty()) {
        exe = QStringLiteral("Ladybird");
    }
    QProcess::startDetached(exe, QStringList{url});
}

static void extract_current_page_info(QWidget* ctx_widget, QString& out_url, QString& out_title) {
    QWidget* win = ctx_widget ? ctx_widget->window() : nullptr;
    if (!win) win = QApplication::activeWindow();
    if (!win) return;

    out_title = win->windowTitle();
    const auto edits = win->findChildren<QLineEdit*>();
    for (QLineEdit* edit : edits) {
        if (!edit || !edit->isVisible()) continue;
        QString txt = edit->text().trimmed();
        if (!txt.isEmpty()) {
            out_url = txt;
            break;
        }
    }
}

static void inject_ladybird_menu_actions(QMenu* menu) {
    if (!menu) return;
    if (menu->objectName() != QStringLiteral("LadybirdMenu")) return;
    if (menu->property("deckybird_ui_injected").toBool()) return;
    menu->setProperty("deckybird_ui_injected", true);

    QAction* anchor = nullptr;
    for (QAction* act : menu->actions()) {
        if (!act) continue;
        QString t = act->text();
        if (t.contains(QStringLiteral("Settings")) || t.contains(QStringLiteral("Настройки"))) {
            anchor = act;
            break;
        }
    }

    auto* sep = new QAction(menu);
    sep->setSeparator(true);

    auto* act_create_webapp = new QAction(QString::fromUtf8("Создать веб-приложение…"), menu);
    QObject::connect(act_create_webapp, &QAction::triggered, menu, [menu]() {
        QString cur_url, cur_title;
        extract_current_page_info(menu->parentWidget(), cur_url, cur_title);
        QUrl target(QStringLiteral("http://127.0.0.1:8406/webapps"));
        QUrlQuery q;
        if (!cur_url.isEmpty() && !cur_url.startsWith(QStringLiteral("about:")) && !cur_url.startsWith(QStringLiteral("http://127.0.0.1:8406"))) {
            q.addQueryItem(QStringLiteral("url"), cur_url);
        }
        if (!cur_title.isEmpty()) {
            q.addQueryItem(QStringLiteral("title"), cur_title);
        }
        target.setQuery(q);
        open_deckybird_url(target.toString());
    });

    auto* act_webapps = new QAction(QString::fromUtf8("Веб-приложения"), menu);
    QObject::connect(act_webapps, &QAction::triggered, menu, []() {
        open_deckybird_url(QStringLiteral("http://127.0.0.1:8406/webapps?tab=list"));
    });

    auto* act_extensions = new QAction(QString::fromUtf8("Расширения"), menu);
    QObject::connect(act_extensions, &QAction::triggered, menu, []() {
        open_deckybird_url(QStringLiteral("http://127.0.0.1:8406/extensions"));
    });

    if (anchor) {
        menu->insertAction(anchor, act_create_webapp);
        menu->insertAction(anchor, act_webapps);
        menu->insertAction(anchor, act_extensions);
        menu->insertAction(anchor, sep);
    } else {
        menu->addAction(sep);
        menu->addAction(act_create_webapp);
        menu->addAction(act_webapps);
        menu->addAction(act_extensions);
    }
}

extern "C" {

void _ZN7QWidget10setVisibleEb(void* self, bool visible) {
    using Fn = void (*)(void*, bool);
    static Fn orig = reinterpret_cast<Fn>(dlsym(RTLD_NEXT, "_ZN7QWidget10setVisibleEb"));
    if (!orig) return;

    static thread_local bool in_hook = false;
    if (in_hook) {
        orig(self, visible);
        return;
    }

    if (visible && is_webapp_mode() && self) {
        QWidget* w = reinterpret_cast<QWidget*>(self);
        if (is_chrome_widget(w)) {
            in_hook = true;
            w->setMaximumHeight(0);
            orig(self, false);
            in_hook = false;
            return;
        }
        orig(self, true);
        if (auto* mw = qobject_cast<QMainWindow*>(w)) {
            if (mw->isWindow() && !mw->property("deckybird_webapp_init").toBool()) {
                mw->setProperty("deckybird_webapp_init", true);
                QPointer<QMainWindow> safe_mw(mw);
                QTimer::singleShot(100, mw, [safe_mw]() {
                    if (!safe_mw) return;
                    in_hook = true;
                    hide_webapp_chrome(safe_mw);
                    if (is_gamescope_mode() && !safe_mw->isFullScreen()) {
                        safe_mw->showFullScreen();
                    }
                    in_hook = false;
                });
            }
        }
        return;
    }
    orig(self, visible);
}

void _ZN5QMenu5popupERK6QPointP7QAction(void* self, const QPoint& p, void* atAction) {
    using Fn = void (*)(void*, const QPoint&, void*);
    static Fn orig = reinterpret_cast<Fn>(dlsym(RTLD_NEXT, "_ZN5QMenu5popupERK6QPointP7QAction"));
    if (!orig) return;
    if (self && !is_webapp_mode()) {
        inject_ladybird_menu_actions(reinterpret_cast<QMenu*>(self));
    }
    orig(self, p, atAction);
}

QAction* _ZN5QMenu4execERK6QPointP7QAction(void* self, const QPoint& p, void* action) {
    using Fn = QAction* (*)(void*, const QPoint&, void*);
    static Fn orig = reinterpret_cast<Fn>(dlsym(RTLD_NEXT, "_ZN5QMenu4execERK6QPointP7QAction"));
    if (!orig) return nullptr;
    if (self && !is_webapp_mode()) {
        inject_ladybird_menu_actions(reinterpret_cast<QMenu*>(self));
    }
    return orig(self, p, action);
}

}
