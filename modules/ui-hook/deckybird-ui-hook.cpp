#include <QAction>
#include <QApplication>
#include <QCoreApplication>
#include <QDir>
#include <QElapsedTimer>
#include <QEvent>
#include <QFileInfo>
#include <QGuiApplication>
#include <QLineEdit>
#include <QMainWindow>
#include <QMenu>
#include <QMouseEvent>
#include <QPointer>
#include <QPointingDevice>
#include <QProcess>
#include <QPushButton>
#include <QStackedWidget>
#include <QString>
#include <QTabBar>
#include <QTimer>
#include <QToolButton>
#include <QTouchEvent>
#include <QUrl>
#include <QUrlQuery>
#include <QWheelEvent>
#include <QWidget>
#include <cmath>
#include <cstdlib>
#include <dlfcn.h>
#include <fcntl.h>
#include <string>
#include <unistd.h>

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

static bool is_internal_browser_url(const QString& url) {
    QString u = url.trimmed().toLower();
    if (u.isEmpty()) return true;
    return u.startsWith(QStringLiteral("about:")) ||
           u.startsWith(QStringLiteral("resource:")) ||
           u.startsWith(QStringLiteral("http://127.0.0.1:8406")) ||
           u.startsWith(QStringLiteral("https://127.0.0.1:8406")) ||
           u.startsWith(QStringLiteral("http://localhost:8406")) ||
           u.startsWith(QStringLiteral("https://localhost:8406"));
}

static bool is_web_content_view(QObject* obj) {
    if (!obj || !obj->isWidgetType()) return false;
    const char* cls = obj->metaObject()->className();
    return cls && std::string(cls).find("WebContentView") != std::string::npos;
}

static bool is_controller_lmb_held() {
    int fd = ::open("/dev/shm/deckybird_ctrl_lmb", O_RDONLY);
    if (fd < 0) return false;
    char ch = '0';
    ssize_t n = ::read(fd, &ch, 1);
    ::close(fd);
    return (n == 1 && ch == '1');
}

class TouchScrollFilter final : public QObject {
public:
    QPointer<QWidget> target;
    QPointF start_pos;
    QPointF last_pos;
    bool active { false };
    bool dragging { false };
    bool mouse_active { false };
    bool mouse_dragging { false };
    bool replaying_mouse { false };
    double accum_x { 0.0 };
    double accum_y { 0.0 };
    double vel_x { 0.0 };
    double vel_y { 0.0 };
    QElapsedTimer move_timer;
    qint64 last_move_ms { 0 };
    QTimer* inertia_timer { nullptr };
    QElapsedTimer inertia_frame_timer;
    Qt::KeyboardModifiers mouse_mods { Qt::NoModifier };

    explicit TouchScrollFilter(QObject* parent = nullptr) : QObject(parent) {
        inertia_timer = new QTimer(this);
        inertia_timer->setInterval(8);
        QObject::connect(inertia_timer, &QTimer::timeout, this, [this]() {
            if (!target || !target->isVisible()) {
                stop_inertia();
                return;
            }
            qint64 dt_ms = inertia_frame_timer.restart();
            if (dt_ms <= 0) dt_ms = 8;
            if (dt_ms > 50) dt_ms = 50;

            double dt = static_cast<double>(dt_ms);
            send_scroll_delta(target, last_pos, QPointF(vel_x * dt, vel_y * dt), Qt::ScrollMomentum);

            double decay = std::exp(-dt / 320.0);
            vel_x *= decay;
            vel_y *= decay;
            if (std::hypot(vel_x, vel_y) < 0.03) {
                stop_inertia();
            }
        });
    }

    void stop_inertia() {
        if (inertia_timer && inertia_timer->isActive()) {
            inertia_timer->stop();
        }
        vel_x = 0.0;
        vel_y = 0.0;
    }

    void reset_velocity() {
        stop_inertia();
        move_timer.restart();
        last_move_ms = 0;
        vel_x = 0.0;
        vel_y = 0.0;
    }

    void record_velocity(const QPointF& delta) {
        qint64 now = move_timer.elapsed();
        qint64 dt = now - last_move_ms;
        last_move_ms = now;
        if (dt > 0 && dt < 120) {
            double inst_vx = delta.x() / static_cast<double>(dt);
            double inst_vy = delta.y() / static_cast<double>(dt);
            vel_x = vel_x * 0.45 + inst_vx * 0.55;
            vel_y = vel_y * 0.45 + inst_vy * 0.55;
        }
    }

    void maybe_start_inertia() {
        qint64 since_last = move_timer.elapsed() - last_move_ms;
        if (since_last <= 80 && std::hypot(vel_x, vel_y) >= 0.15) {
            // Cap max fling speed to avoid extreme jumps
            double max_v = 3.5;
            double speed = std::hypot(vel_x, vel_y);
            if (speed > max_v) {
                vel_x *= (max_v / speed);
                vel_y *= (max_v / speed);
            }
            inertia_frame_timer.restart();
            inertia_timer->start();
        } else {
            stop_inertia();
        }
    }

    static QPointingDevice* touch_pad_device() {
        static QPointingDevice* dev = new QPointingDevice(
            QStringLiteral("DeckyBirdTouchScroll"),
            0,
            QInputDevice::DeviceType::TouchPad,
            QPointingDevice::PointerType::Finger,
            QInputDevice::Capability::Position | QInputDevice::Capability::Scroll,
            1,
            0
        );
        return dev;
    }

    void send_scroll_delta(QWidget* w, const QPointF& pos, const QPointF& delta, Qt::ScrollPhase phase = Qt::ScrollUpdate) {
        accum_x += delta.x();
        accum_y += delta.y();
        int dx = static_cast<int>(std::trunc(accum_x));
        int dy = static_cast<int>(std::trunc(accum_y));
        accum_x -= dx;
        accum_y -= dy;
        if (dx == 0 && dy == 0) return;

        QPointF gpos = w->mapToGlobal(pos);
        static bool const is_wayland = QGuiApplication::platformName().startsWith(QStringLiteral("wayland"));
        if (is_wayland) {
            // On Wayland, Ladybird multiplies angleDelta by (4 / 12) = 1/3 when source != MouseEventNotSynthesized.
            QWheelEvent we(
                pos,
                gpos,
                QPoint(0, 0),
                QPoint(dx * 3, dy * 3),
                Qt::NoButton,
                Qt::NoModifier,
                phase,
                false,
                Qt::MouseEventSynthesizedByApplication,
                touch_pad_device()
            );
            QCoreApplication::sendEvent(w, &we);
        } else {
            // On X11/Gamescope, TouchPad pointingDevice + pixelDelta triggers precise_wheel_delta() with 0 animation lag.
            QWheelEvent we(
                pos,
                gpos,
                QPoint(dx, dy),
                QPoint(0, 0),
                Qt::NoButton,
                Qt::NoModifier,
                phase,
                false,
                Qt::MouseEventNotSynthesized,
                touch_pad_device()
            );
            QCoreApplication::sendEvent(w, &we);
        }
    }

    bool eventFilter(QObject* watched, QEvent* event) override {
        if (replaying_mouse || !is_web_content_view(watched)) {
            return QObject::eventFilter(watched, event);
        }
        auto* w = static_cast<QWidget*>(watched);
        switch (event->type()) {
            case QEvent::TouchBegin: {
                auto* te = static_cast<QTouchEvent*>(event);
                if (te->points().size() == 1) {
                    target = w;
                    start_pos = te->points().first().position();
                    last_pos = start_pos;
                    active = true;
                    dragging = false;
                    accum_x = 0.0;
                    accum_y = 0.0;
                    reset_velocity();
                    te->accept();
                    return true;
                }
                active = false;
                break;
            }
            case QEvent::TouchUpdate: {
                if (!active || target != w) break;
                auto* te = static_cast<QTouchEvent*>(event);
                if (te->points().size() != 1) {
                    active = false;
                    break;
                }
                QPointF pos = te->points().first().position();
                if (!dragging) {
                    QPointF total = pos - start_pos;
                    if (std::hypot(total.x(), total.y()) >= 8.0) {
                        dragging = true;
                        last_pos = pos;
                        move_timer.restart();
                        last_move_ms = 0;
                    }
                } else {
                    QPointF delta = pos - last_pos;
                    last_pos = pos;
                    record_velocity(delta);
                    send_scroll_delta(w, pos, delta);
                }
                te->accept();
                return true;
            }
            case QEvent::TouchEnd:
            case QEvent::TouchCancel: {
                if (!active || target != w) break;
                auto* te = static_cast<QTouchEvent*>(event);
                bool was_dragging = dragging;
                QPointF end_pos = te->points().isEmpty() ? last_pos : te->points().first().position();
                active = false;
                dragging = false;
                if (was_dragging && event->type() == QEvent::TouchEnd) {
                    maybe_start_inertia();
                } else if (!was_dragging && event->type() == QEvent::TouchEnd) {
                    QPointF gpos = w->mapToGlobal(end_pos);
                    replaying_mouse = true;
                    QMouseEvent press_ev(QEvent::MouseButtonPress, end_pos, gpos, Qt::LeftButton, Qt::LeftButton, Qt::NoModifier);
                    QMouseEvent release_ev(QEvent::MouseButtonRelease, end_pos, gpos, Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
                    QCoreApplication::sendEvent(w, &press_ev);
                    QCoreApplication::sendEvent(w, &release_ev);
                    replaying_mouse = false;
                }
                te->accept();
                return true;
            }
            case QEvent::MouseButtonPress: {
                if (!is_gamescope_mode()) break;
                auto* me = static_cast<QMouseEvent*>(event);
                if (me->button() == Qt::LeftButton && !is_controller_lmb_held()) {
                    target = w;
                    start_pos = me->position();
                    last_pos = start_pos;
                    mouse_mods = me->modifiers();
                    mouse_active = true;
                    mouse_dragging = false;
                    accum_x = 0.0;
                    accum_y = 0.0;
                    reset_velocity();
                    me->accept();
                    return true;
                }
                break;
            }
            case QEvent::MouseMove: {
                if (!mouse_active || target != w) break;
                auto* me = static_cast<QMouseEvent*>(event);
                if (!(me->buttons() & Qt::LeftButton)) {
                    mouse_active = false;
                    mouse_dragging = false;
                    break;
                }
                QPointF pos = me->position();
                if (!mouse_dragging) {
                    QPointF total = pos - start_pos;
                    if (std::hypot(total.x(), total.y()) >= 8.0) {
                        mouse_dragging = true;
                        last_pos = pos;
                        move_timer.restart();
                        last_move_ms = 0;
                    }
                } else {
                    QPointF delta = pos - last_pos;
                    last_pos = pos;
                    record_velocity(delta);
                    send_scroll_delta(w, pos, delta);
                }
                me->accept();
                return true;
            }
            case QEvent::MouseButtonRelease: {
                if (!mouse_active || target != w) break;
                auto* me = static_cast<QMouseEvent*>(event);
                if (me->button() == Qt::LeftButton) {
                    bool was_dragging = mouse_dragging;
                    QPointF end_pos = me->position();
                    mouse_active = false;
                    mouse_dragging = false;
                    if (was_dragging) {
                        maybe_start_inertia();
                    } else {
                        QPointF gpos = w->mapToGlobal(end_pos);
                        replaying_mouse = true;
                        QMouseEvent press_ev(QEvent::MouseButtonPress, end_pos, gpos, Qt::LeftButton, Qt::LeftButton, mouse_mods);
                        QMouseEvent release_ev(QEvent::MouseButtonRelease, end_pos, gpos, Qt::LeftButton, Qt::NoButton, mouse_mods);
                        QCoreApplication::sendEvent(w, &press_ev);
                        QCoreApplication::sendEvent(w, &release_ev);
                        replaying_mouse = false;
                    }
                    me->accept();
                    return true;
                }
                break;
            }
            default:
                break;
        }
        return QObject::eventFilter(watched, event);
    }
};

static void ensure_touch_scroll_installed() {
    static bool installed = false;
    if (installed) return;
    if (QCoreApplication* app = QCoreApplication::instance()) {
        installed = true;
        app->installEventFilter(new TouchScrollFilter(app));
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
    QObject::connect(menu, &QMenu::aboutToShow, menu, [menu, act_create_webapp]() {
        QString cur_url, cur_title;
        extract_current_page_info(menu->parentWidget(), cur_url, cur_title);
        act_create_webapp->setEnabled(!is_internal_browser_url(cur_url));
    });
    QObject::connect(act_create_webapp, &QAction::triggered, menu, [menu]() {
        QString cur_url, cur_title;
        extract_current_page_info(menu->parentWidget(), cur_url, cur_title);
        if (is_internal_browser_url(cur_url)) return;
        QUrl target(QStringLiteral("http://127.0.0.1:8406/webapps"));
        QUrlQuery q;
        q.addQueryItem(QStringLiteral("url"), cur_url);
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

static void ensure_deckybird_desktop_file_name() {
    static bool done = false;
    if (done) return;
    done = true;

    if (is_webapp_mode()) {
        const char* webapp_id = std::getenv("DECKYBIRD_WEBAPP_ID");
        if (webapp_id && webapp_id[0] != '\0') {
            QGuiApplication::setDesktopFileName(QStringLiteral("deckybird-webapp-") + QString::fromUtf8(webapp_id));
            return;
        }
    }

    QString apps_mgr_desktop = QDir::homePath() + QStringLiteral("/.local/share/applications/deckybird.desktop");
    if (QFileInfo::exists(apps_mgr_desktop)) {
        QGuiApplication::setDesktopFileName(QStringLiteral("deckybird"));
    } else {
        QGuiApplication::setDesktopFileName(QStringLiteral("net.deckybird.DeckyBird"));
    }
}

extern "C" {

void _ZN7QWidget10setVisibleEb(void* self, bool visible) {
    using Fn = void (*)(void*, bool);
    static Fn orig = reinterpret_cast<Fn>(dlsym(RTLD_NEXT, "_ZN7QWidget10setVisibleEb"));
    if (!orig) return;

    if (visible) {
        ensure_deckybird_desktop_file_name();
        ensure_touch_scroll_installed();
        if (self) {
            QWidget* w = reinterpret_cast<QWidget*>(self);
            if (is_web_content_view(w) && !w->testAttribute(Qt::WA_AcceptTouchEvents)) {
                w->setAttribute(Qt::WA_AcceptTouchEvents, true);
            }
        }
    }

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
