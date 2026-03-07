# 🗄️ Component Warehouse

Веб-приложение для учёта электронных компонентов на складе. Построено на Flask с применением паттерна Application Factory и Blueprint-архитектуры.

## ✨ Возможности

- **Каталог компонентов** — добавление, редактирование, удаление, поиск и фильтрация по группе/подгруппе/типу
- **Иерархия классификации** — группы → подгруппы → типы → корпуса
- **История изменений** — журнал всех операций с каждым компонентом
- **Архив** — мягкое удаление с возможностью восстановления
- **Заказы** — создание заказов на компоненты с историей
- **Управление пользователями** — роли (`super_admin`, `admin`, `user`) и гранулярные права доступа (создание/редактирование/удаление/просмотр для каждого раздела)
- **Аутентификация** — вход и регистрация через Flask-Login

## 🛠️ Стек технологий

| Компонент | Версия |
|---|---|
| Python | 3.12 |
| Flask | 3.1 |
| Flask-SQLAlchemy | 3.1 |
| Flask-Login | 0.6 |
| Flask-WTF | 1.2 |
| SQLite | — |
| Bootstrap | 5.3.3 |
| Bootstrap Icons | 1.11.3 |
| uv | пакетный менеджер |

## 🚀 Быстрый старт

### Требования
- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Установка

```bash
git clone https://github.com/shmvme-cmd/Component-Warehouse.git
cd Component-Warehouse
uv sync
```

### Инициализация базы данных

```bash
uv run flask init-db
```

Команда создаёт все таблицы, загружает базовую структуру компонентов и создаёт пользователя-администратора:

| Логин | Пароль |
|---|---|
| `super_admin` | `super123` |

### Запуск

```bash
uv run flask run --host=0.0.0.0 --port=5500
```

Откройте браузер: **http://localhost:5500**

## 📁 Структура проекта

```
Component Warehouse/
├── pyproject.toml              # Зависимости (uv)
├── config.py                   # Конфигурация приложения
├── .flaskenv                   # Переменные окружения Flask
└── app/
    ├── __init__.py             # Application Factory (create_app)
    ├── extensions.py           # SQLAlchemy, LoginManager
    ├── models.py               # Модели БД
    ├── forms.py                # WTForms
    ├── cli.py                  # CLI-команда flask init-db
    ├── component_structure.py  # Начальные данные каталога
    ├── blueprints/
    │   ├── auth.py             # Вход / выход / регистрация
    │   ├── users.py            # Управление пользователями
    │   ├── groups.py           # Группы и подгруппы
    │   ├── catalog.py          # Типы и корпуса
    │   ├── components.py       # Компоненты и архив
    │   ├── orders.py           # Заказы
    │   └── api.py              # JSON API для динамических форм
    └── templates/              # Jinja2-шаблоны (Bootstrap 5)
```

## 🔐 Роли и права

| Роль | Описание |
|---|---|
| `super_admin` | Полный доступ ко всему |
| `admin` | Доступ определяется набором прав |
| `user` | Только просмотр (по умолчанию) |

Права настраиваются индивидуально для каждого пользователя в разделе «Пользователи».

## ⚙️ Переменные окружения

Создайте файл `.env` в корне проекта:

```env
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///inventory.db
```
