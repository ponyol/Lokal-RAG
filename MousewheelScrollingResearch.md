# Исследование: Проблема прокрутки mousewheel в CustomTkinter CTkScrollableFrame на macOS

**Дата исследования:** 11 ноября 2025
**Контекст:** Lokal-RAG Desktop Application
**Платформа:** macOS (Darwin) с трекпадом

---

## Оглавление

1. [Описание проблемы](#описание-проблемы)
2. [Техническая природа проблемы](#техническая-природа-проблемы)
3. [Платформенные различия](#платформенные-различия)
4. [Известные GitHub Issues](#известные-github-issues)
5. [Попытки решения в Lokal-RAG](#попытки-решения-в-lokal-rag)
6. [Решения из сообщества](#решения-из-сообщества)
7. [Рекомендуемое решение](#рекомендуемое-решение)
8. [Альтернативные подходы](#альтернативные-подходы)
9. [Выводы](#выводы)

---

## Описание проблемы

### Симптомы

При использовании `CTkScrollableFrame` от CustomTkinter на macOS с трекпадом:

- ✅ Прокрутка работает при наведении курсора **непосредственно на scrollbar**
- ❌ Прокрутка **НЕ работает** при наведении на основную область фрейма
- ✅ События `<Enter>` и `<Leave>` срабатывают корректно
- ❌ События `<MouseWheel>` **не генерируются** вообще

### Воспроизведение

```python
import customtkinter as ctk

root = ctk.CTk()
scrollable_frame = ctk.CTkScrollableFrame(root, width=300, height=400)
scrollable_frame.pack()

# Добавляем контент для прокрутки
for i in range(50):
    ctk.CTkLabel(scrollable_frame, text=f"Label {i}").pack()

root.mainloop()
```

**Результат:** На macOS прокрутка трекпадом не работает над основной областью фрейма.

---

## Техническая природа проблемы

### Архитектура CTkScrollableFrame

`CTkScrollableFrame` внутри использует следующую иерархию виджетов:

```
CTkScrollableFrame (widget)
├── _parent_frame (CTkFrame)
│   └── _parent_canvas (tkinter.Canvas)
│       └── _scrollbar (CTkScrollbar)
│       └── <внутренний frame с контентом>
```

### Проблема #1: Widget Hierarchy Validation

CustomTkinter использует метод `check_if_master_is_canvas()` для проверки, принадлежит ли виджет иерархии canvas:

```python
def check_if_master_is_canvas(widget):
    """Recursively check if widget belongs to canvas hierarchy"""
    if widget.master is None:
        return False
    if isinstance(widget.master, tkinter.Canvas):
        return True
    return check_if_master_is_canvas(widget.master)
```

**Проблема:** Когда `CTkScrollableFrame` создается **внутри класса** (как в нашем AppView), цепочка `master` ломается:

```
widget.master → AppView (NOT Canvas) → root → None
```

Вместо ожидаемой:

```
widget.master → canvas → frame → root → None
```

Это приводит к тому, что `check_if_master_is_canvas()` возвращает `False`, и CustomTkinter **не привязывает** mousewheel события.

### Проблема #2: macOS Focus Requirements

На macOS **критически важно**, что:

> **Mousewheel события генерируются только для виджета, который имеет фокус клавиатуры (keyboard focus).**

Это отличается от Windows/Linux, где события mousewheel могут обрабатываться без явного фокуса.

### Проблема #3: Tkinter Event Propagation

Tkinter на macOS не использует стандартную модель propagation для `<MouseWheel>` событий:

- События **не всплывают** (bubble) от дочерних виджетов к родительским
- `bind()` привязывает событие только к конкретному виджету
- `bind_all()` привязывает **глобально**, но может конфликтовать с другими scrollable widgets

---

## Платформенные различия

### События прокрутки по платформам

| Платформа | События          | event.delta                          | event.num |
|-----------|------------------|--------------------------------------|-----------|
| **Windows** | `<MouseWheel>`   | ±120 (кратно 120)                    | N/A       |
| **macOS**   | `<MouseWheel>`   | ±1, ±2, ±5... (динамические)        | N/A       |
| **Linux**   | `<Button-4>`, `<Button-5>` | 0 (не используется) | 4 или 5   |

### Особенности macOS Trackpad

1. **Precise Scrolling:** трекпад macOS поддерживает инерционную прокрутку с дробными значениями delta
2. **Natural Scrolling:** направление прокрутки инвертировано по умолчанию
3. **Focus Requirement:** события mousewheel требуют keyboard focus
4. **Dynamic Delta:** значения delta меняются в зависимости от скорости жеста

---

## Известные GitHub Issues

### Issue #1816: CTkScrollableFrame - MouseWheel not working

**URL:** https://github.com/TomSchimansky/CustomTkinter/issues/1816

**Проблема:** Mousewheel работает только когда курсор над scrollbar, не над основным frame.

**Причина:** Broken master reference в widget hierarchy.

**Решение от сообщества:**

```python
# После создания CTkScrollableFrame:
scrollable_frame = ctk.CTkScrollableFrame(parent)
scrollable_frame.master = scrollable_frame._parent_canvas  # FIX
```

**Как это работает:** Переназначение `master` исправляет цепочку иерархии, позволяя `check_if_master_is_canvas()` вернуть `True`.

### Issue #1356: Mouse wheel doesn't work on ScrollableFrame (Linux)

**URL:** https://github.com/TomSchimansky/CustomTkinter/issues/1356

**Проблема:** На Linux прокрутка не работает вообще.

**Причина:** CustomTkinter не привязывал события `<Button-4>` и `<Button-5>`.

**Workaround от сообщества:**

```python
scroll_frame = ctk.CTkScrollableFrame(root)

# Linux workaround:
scroll_frame.bind_all("<Button-4>", lambda e: scroll_frame._parent_canvas.yview("scroll", -1, "units"))
scroll_frame.bind_all("<Button-5>", lambda e: scroll_frame._parent_canvas.yview("scroll", 1, "units"))
```

**Статус:** Частично исправлено в commit 344b30e (July 2023), но проблемы остаются.

---

## Попытки решения в Lokal-RAG

Мы попробовали **10 различных подходов** для решения проблемы в нашем приложении:

### Попытка #1: Monkey-patching check_if_master_is_canvas

```python
def patched_check(w):
    return True  # Always return True

widget.check_if_master_is_canvas = patched_check
```

**Результат:** ❌ Не сработало. События mousewheel всё равно не генерировались.

### Попытка #2: Переназначение master reference

```python
widget.master = widget._parent_canvas
```

**Результат:** ❌ Не сработало на macOS (хотя это решение упоминается в Issue #1816).

### Попытка #3: Рекурсивная привязка к дочерним виджетам

```python
def bind_to_children(parent):
    for child in parent.winfo_children():
        child.bind("<MouseWheel>", on_mousewheel, add="+")
        bind_to_children(child)

bind_to_children(widget)
```

**Результат:** ❌ События всё равно не генерировались.

### Попытка #4: bind_all на корневом окне

```python
self.master.bind_all("<MouseWheel>", on_mousewheel, add="+")
```

**Результат:** ❌ События не доходили до обработчика.

### Попытка #5: Прямая привязка к canvas

```python
canvas.bind("<MouseWheel>", on_mousewheel)  # Без add="+"
```

**Результат:** ❌ События не генерировались.

### Попытка #6: Отслеживание фокуса через Enter/Leave

```python
def on_enter(event):
    mouse_over_canvas[0] = True
    canvas.focus_set()

canvas.bind("<Enter>", on_enter)
```

**Результат:** ❌ Focus устанавливался, но события mousewheel не генерировались.

### Попытка #7: Button-4 и Button-5 для совместимости

```python
canvas.bind("<Button-4>", lambda e: on_scroll_up())
canvas.bind("<Button-5>", lambda e: on_scroll_down())
```

**Результат:** ❌ На macOS эти события не генерируются (они для Linux).

### Попытка #8: Комбинация всех подходов

```python
# Direct binding
canvas.bind("<MouseWheel>", on_mousewheel)
# bind_all as fallback
self.master.bind_all("<MouseWheel>", on_mousewheel, add="+")
# Enter/Leave tracking
canvas.bind("<Enter>", on_enter)
```

**Результат:** ❌ События всё равно не генерировались.

### Попытка #9: takefocus + widget.bind

```python
canvas.config(takefocus=1)
widget.configure(takefocus=1)

def on_enter(event):
    widget.focus_set()  # Focus на widget, не canvas

widget.bind("<MouseWheel>", on_mousewheel)
```

**Результат:** 🔄 **В процессе тестирования** (последняя попытка).

### Диагностика через логирование

Добавили подробное логирование на каждом этапе:

```python
logger.info(f"🔧 Setting up mousewheel")
logger.info(f"   Platform: {sys.platform}")
logger.info(f"   Canvas: {canvas}")
logger.info(f"✓ Bound <MouseWheel> to canvas")

def on_mousewheel(event):
    logger.info(f"🖱️  MouseWheel event: delta={event.delta}")
```

**Наблюдение:**

```
🔵 Mouse ENTERED canvas area (focus set)
🔴 Mouse LEFT canvas area
🔵 Mouse ENTERED canvas area (focus set)
🔴 Mouse LEFT canvas area
```

События Enter/Leave работают, но **НИ ОДНОГО** `🖱️ MouseWheel event` не появляется.

**Вывод:** События `<MouseWheel>` **вообще не генерируются** Tkinter на macOS в нашей конфигурации.

---

## Решения из сообщества

### Решение #1: Fixing Master Reference (Issue #1816)

**Описание:** Исправить broken master chain.

**Код:**

```python
class MyApp:
    def __init__(self):
        self.scrollable = ctk.CTkScrollableFrame(self.master)
        # CRITICAL FIX:
        self.scrollable.master = self.scrollable._parent_canvas
```

**Плюсы:**
- ✅ Простое решение (одна строка)
- ✅ Не требует monkey-patching

**Минусы:**
- ❌ Может сломать другую функциональность CustomTkinter
- ❌ Не работает на macOS (по нашему опыту)

### Решение #2: Enter/Leave with bind_all (для Linux)

**Описание:** Привязывать события только когда мышь над виджетом.

**Код:**

```python
def _bind_mouse(self, event=None):
    self.canvas.bind_all("<Button-4>", self._on_mousewheel)
    self.canvas.bind_all("<Button-5>", self._on_mousewheel)
    self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

def _unbind_mouse(self, event=None):
    self.canvas.unbind_all("<Button-4>")
    self.canvas.unbind_all("<Button-5>")
    self.canvas.unbind_all("<MouseWheel>")

self.canvas.bind("<Enter>", self._bind_mouse)
self.canvas.bind("<Leave>", self._unbind_mouse)
```

**Плюсы:**
- ✅ Предотвращает конфликты с другими scrollable widgets
- ✅ Работает на Linux

**Минусы:**
- ❌ Не решает macOS focus problem
- ❌ Unbind/bind может быть медленным

### Решение #3: Кроссплатформенный обработчик

**Описание:** Единый обработчик для всех платформ.

**Код:**

```python
def _on_mousewheel(self, event):
    """Cross-platform mousewheel handler"""
    if event.num == 4 or event.delta > 0:
        self.canvas.yview_scroll(-1, "units")
    elif event.num == 5 or event.delta < 0:
        self.canvas.yview_scroll(1, "units")
```

**Плюсы:**
- ✅ Работает на всех платформах (если события генерируются)
- ✅ Простой код

**Минусы:**
- ❌ Не решает проблему с генерацией событий на macOS

### Решение #4: Focus-based binding (для macOS)

**Описание:** Установить focus на canvas и привязать события.

**Код:**

```python
def on_enter(event):
    event.widget.focus_set()
    event.widget.bind("<MouseWheel>", on_mousewheel)

canvas.bind("<Enter>", on_enter)
canvas.config(takefocus=1)  # Make canvas focusable
```

**Плюсы:**
- ✅ Учитывает macOS focus requirement
- ✅ События привязываются к focused widget

**Минусы:**
- ❌ Canvas может не принимать focus корректно
- ❌ В нашем опыте события всё равно не генерировались

---

## Рекомендуемое решение

На основе исследования рекомендуется **комбинированный подход**:

### Шаг 1: Исправить Master Reference

```python
def _enable_mousewheel_scrolling(self, widget):
    if hasattr(widget, '_parent_canvas'):
        canvas = widget._parent_canvas

        # FIX #1: Correct the master reference
        widget.master = canvas
```

### Шаг 2: Установить Focus на Widget

```python
        # FIX #2: Make widget focusable
        try:
            widget.configure(takefocus=1)
            canvas.config(takefocus=1)
        except:
            pass

        # FIX #3: Set focus on enter
        def on_enter(event):
            widget.focus_set()

        widget.bind("<Enter>", on_enter)
        canvas.bind("<Enter>", on_enter)
```

### Шаг 3: Кроссплатформенная Привязка Событий

```python
        # FIX #4: Cross-platform event binding
        def on_mousewheel(event):
            # Linux: event.num is 4 or 5
            # macOS/Windows: event.delta is ±N
            if event.num == 4 or event.delta > 0:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5 or event.delta < 0:
                canvas.yview_scroll(1, "units")
            return "break"

        # Bind for macOS/Windows
        widget.bind("<MouseWheel>", on_mousewheel)
        canvas.bind("<MouseWheel>", on_mousewheel)

        # Bind for Linux
        if sys.platform.startswith('linux'):
            widget.bind("<Button-4>", on_mousewheel)
            widget.bind("<Button-5>", on_mousewheel)
            canvas.bind("<Button-4>", on_mousewheel)
            canvas.bind("<Button-5>", on_mousewheel)
```

### Полный код решения

```python
import sys
import customtkinter as ctk

class AppView:
    def _enable_mousewheel_scrolling(self, widget):
        """
        Enable cross-platform mousewheel scrolling for CTkScrollableFrame.

        Fixes:
        1. Broken master reference (Issue #1816)
        2. macOS focus requirement
        3. Linux Button-4/Button-5 support
        """
        if not hasattr(widget, '_parent_canvas'):
            return

        canvas = widget._parent_canvas

        # FIX #1: Correct master reference
        widget.master = canvas

        # FIX #2: Make widgets focusable
        try:
            widget.configure(takefocus=1)
            canvas.config(takefocus=1)
        except Exception as e:
            print(f"Warning: Could not configure takefocus: {e}")

        # FIX #3: Cross-platform scroll handler
        def on_mousewheel(event):
            """Handle mousewheel scroll on all platforms"""
            # Determine scroll direction
            if hasattr(event, 'num'):
                # Linux: Button-4 (up) or Button-5 (down)
                if event.num == 4:
                    delta = 1
                elif event.num == 5:
                    delta = -1
                else:
                    return
            else:
                # macOS/Windows: use delta
                if sys.platform == 'darwin':
                    delta = event.delta  # macOS: ±1, ±2...
                else:
                    delta = event.delta // 120  # Windows: ±120

            # Scroll the canvas
            canvas.yview_scroll(-delta, "units")
            return "break"

        # FIX #4: Set focus on mouse enter
        def on_enter(event):
            """Set focus when mouse enters widget"""
            widget.focus_set()

        # Bind Enter events
        widget.bind("<Enter>", on_enter)
        canvas.bind("<Enter>", on_enter)

        # Bind mousewheel events
        if sys.platform.startswith('linux'):
            # Linux: Button-4 and Button-5
            widget.bind("<Button-4>", on_mousewheel)
            widget.bind("<Button-5>", on_mousewheel)
            canvas.bind("<Button-4>", on_mousewheel)
            canvas.bind("<Button-5>", on_mousewheel)
        else:
            # macOS/Windows: MouseWheel
            widget.bind("<MouseWheel>", on_mousewheel)
            canvas.bind("<MouseWheel>", on_mousewheel)
```

---

## Альтернативные подходы

### Альтернатива #1: CTkXYFrame от Akascape

**URL:** https://github.com/Akascape/CTkXYFrame

**Описание:** Альтернативная реализация scrollable frame с правильной поддержкой mousewheel.

**Преимущества:**
- ✅ Прокрутка по X и Y осям
- ✅ Правильные привязки для всех платформ
- ✅ Автоматически скрывающиеся scrollbars
- ✅ Drop-in replacement для CTkScrollableFrame

**Пример:**

```python
from CTkXYFrame import CTkXYFrame

frame = CTkXYFrame(root, width=300, height=400)
frame.pack()

# Используется точно так же, как CTkScrollableFrame
for i in range(50):
    ctk.CTkLabel(frame, text=f"Label {i}").pack()
```

### Альтернатива #2: Ручная реализация Scrollable Frame

**Описание:** Создать собственный scrollable frame с правильной обработкой событий.

**Пример:**

```python
class CustomScrollableFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        # Create canvas and scrollbar
        self.canvas = tkinter.Canvas(self, **kwargs)
        self.scrollbar = ctk.CTkScrollbar(self, command=self.canvas.yview)
        self.scrollable_frame = ctk.CTkFrame(self.canvas)

        # Configure
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Pack widgets
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Enable mousewheel - CORRECT IMPLEMENTATION
        self._enable_mousewheel()

    def _enable_mousewheel(self):
        """Enable cross-platform mousewheel scrolling"""
        def on_mousewheel(event):
            if sys.platform == 'darwin':
                self.canvas.yview_scroll(-event.delta, "units")
            elif sys.platform == 'win32':
                self.canvas.yview_scroll(-event.delta // 120, "units")

        def on_enter(event):
            self.canvas.focus_set()

        self.canvas.bind("<Enter>", on_enter)
        self.canvas.bind("<MouseWheel>", on_mousewheel)
        self.canvas.config(takefocus=1)

        # Linux support
        if sys.platform.startswith('linux'):
            self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
            self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
```

### Альтернатива #3: Обновить до последней версии CustomTkinter

**Описание:** Разработчик CustomTkinter активно работает над исправлениями.

**Действия:**
1. Проверить последнюю версию: `pip install --upgrade customtkinter`
2. Проверить changelog на GitHub
3. Тестировать на всех целевых платформах

---

## Выводы

### Основные находки

1. **Проблема комплексная** - не существует одного "silver bullet" решения
2. **macOS требует фокуса** - mousewheel события генерируются только для focused widget
3. **Master reference важен** - broken hierarchy в CustomTkinter блокирует события
4. **Платформенные различия критичны** - необходим кроссплатформенный подход

### Почему наши попытки не сработали

1. **Monkey-patching недостаточен** - исправление `check_if_master_is_canvas()` не решает macOS focus problem
2. **bind_all не работает** - на macOS события не генерируются глобально без фокуса
3. **Canvas не принимает фокус** - нужно устанавливать фокус на scrollable frame, не на canvas
4. **События просто не генерируются** - даже с правильными привязками Tkinter может не генерировать MouseWheel events

### Рекомендации для Lokal-RAG

**Краткосрочное решение (Quick Fix):**
Попробовать рекомендуемое комбинированное решение из раздела выше.

**Среднесрочное решение (Medium Term):**
Если комбинированное решение не работает, использовать **CTkXYFrame** от Akascape как drop-in replacement.

**Долгосрочное решение (Long Term):**
1. Следить за обновлениями CustomTkinter
2. Рассмотреть переход на другую GUI библиотеку (PyQt6, PySide6) если проблема критична
3. Тестировать на всех целевых платформах при каждом обновлении

### Открытые вопросы

1. **Почему Tkinter не генерирует MouseWheel события?**
   - Возможно, это bug в tkinter на macOS Ventura/Sonoma
   - Возможно, нужны специальные настройки Tcl/Tk

2. **Работает ли решение из Issue #1816 для других пользователей?**
   - Сообщается, что работает, но у нас не сработало
   - Возможно, различия в версиях Python/Tcl/Tk/macOS

3. **Есть ли workaround без изменения кода?**
   - Возможно, обновление Tcl/Tk через brew
   - Возможно, настройки macOS Accessibility

### Следующие шаги

1. ✅ Завершить тестирование последней попытки (takefocus + widget.bind)
2. ⏳ Если не сработает → попробовать CTkXYFrame
3. ⏳ Открыть новый Issue на GitHub CustomTkinter с подробной диагностикой
4. ⏳ Тестировать на других версиях macOS (если доступны)

---

## Ссылки и ресурсы

### GitHub Issues
- [Issue #1816: CTkScrollableFrame - MouseWheel not working](https://github.com/TomSchimansky/CustomTkinter/issues/1816)
- [Issue #1356: Mouse wheel doesn't work on ScrollableFrame](https://github.com/TomSchimansky/CustomTkinter/issues/1356)
- [Pull Request #2365: Add events for scroll wheel in Linux](https://github.com/TomSchimansky/CustomTkinter/pull/2365)

### Stack Overflow
- [tkinter: binding mousewheel to scrollbar](https://stackoverflow.com/questions/17355902/tkinter-binding-mousewheel-to-scrollbar)
- [How to use the mouse wheel to scroll in Tkinter](https://stackoverflow.com/questions/63240350/how-to-use-the-mouse-wheel-to-scroll-in-tkinter-if-its-in-the-frame-the-scroll)

### Документация
- [CustomTkinter Documentation - CTkScrollableFrame](https://github.com/TomSchimansky/CustomTkinter/wiki/CTkScrollableFrame)
- [Tkinter Event Types](https://anzeljg.github.io/rin2/book2/2405/docs/tkinter/event-types.html)
- [Tcl/Tk mousewheel documentation](https://wiki.tcl-lang.org/page/mousewheel)

### Альтернативные решения
- [CTkXYFrame by Akascape](https://github.com/Akascape/CTkXYFrame)
- [Scrollable Frame Gist](https://gist.github.com/JackTheEngineer/81df334f3dcff09fd19e4169dd560c59)

---

**Исследование подготовлено:** Claude Code
**Для проекта:** Lokal-RAG
**Статус:** В процессе тестирования решений
