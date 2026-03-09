# Техническое задание
## CRM САУК — Система автоматизации управления клиентами

**Версия:** 1.0  
**Дата:** 09.03.2026  
**Статус:** Черновик  

---

## 1. Общие сведения

### 1.1 Назначение системы

CRM САУК — система управления взаимоотношениями с клиентами, заявками на сервис и ремонт, складом компонентов и изделий. Система является **переработкой и расширением** существующего проекта «Component Warehouse» (Flask/SQLite) с миграцией на Django и добавлением CRM-функциональности.

### 1.2 Технический стек

| Компонент | Технология |
|-----------|-----------|
| Фреймворк | Django 5.x |
| БД (разработка) | SQLite |
| БД (продакшн) | PostgreSQL (рекомендуется) |
| Аутентификация | Django Auth + кастомная модель пользователя |
| Шаблоны | Django Templates (или DRF + Vue.js — на усмотрение) |
| Хэш паролей | Django PBKDF2 (встроенный) |
| Зависимости | django-filter, pillow, openpyxl/pandas (для импорта CSV/Excel) |

### 1.3 Что переносится из существующего проекта

Следующие модули **реализованы** в текущем Flask-проекте и подлежат **переносу/адаптации** на Django:

| Модуль | Статус в Flask | Что сделать |
|--------|---------------|-------------|
| Пользователи и права доступа | Реализовано (20 булевых прав) | Перенести, расширить роли |
| Иерархия компонентов (Группа → Подгруппа → Тип) | Реализовано | Перенести модели |
| Корпуса (Housing) | Реализовано (120+ типоразмеров) | Перенести справочник |
| Библиотека компонентов (эталонные спецификации) | Реализовано | Перенести |
| Склад компонентов (количество, история) | Реализовано | Перенести |
| Заказы на выдачу компонентов | Реализовано (базово) | Расширить |
| BOM-спецификации изделий + импорт CSV | Реализовано (сложный алгоритм автосопоставления) | Перенести алгоритм |
| История изменений компонентов | Реализовано | Перенести |

---

## 2. Модули системы

---

### Модуль 1. Пользователи системы

#### 1.1 Модель пользователя

Расширяет стандартную модель `AbstractUser` Django.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `username` | CharField, unique | Логин |
| `email` | EmailField, unique | Email |
| `first_name` | CharField | Имя |
| `last_name` | CharField | Фамилия |
| `role` | CharField | `user` / `manager` / `admin` / `super_admin` |
| `is_active` | Boolean | Активность аккаунта |
| `date_joined` | DateTime | Дата регистрации |
| `avatar` | ImageField, nullable | Аватар |

#### 1.2 Матрица прав доступа (переносится из текущего проекта)

Гранулярные права через булевы поля (как в текущей реализации) **ИЛИ** через встроенный механизм Django Permissions — нужно выбрать один подход.

**Рекомендация:** использовать Django Groups + Permissions (стандартный механизм), а не 20 булевых полей вручную.

| Объект | Права |
|--------|-------|
| Клиенты | create / edit / delete / view |
| Заказы клиентов | create / edit / delete / view |
| Склад компонентов | create / edit / delete / view |
| Склад изделий | create / edit / delete / view |
| Заявки на ремонт | create / edit / delete / view |
| Библиотека | create / edit / delete / view |
| Приборы | create / edit / delete / view |
| Пользователи | create / edit / delete / view |
| Справочники (группы, типы, корпуса) | create / edit / delete / view |

#### 1.3 Функциональность

- Регистрация, вход, выход, смена пароля
- Управление пользователями (только `admin` / `super_admin`)
- Просмотр активности пользователя (журнал действий)

---

### Модуль 2. Клиенты

#### 2.1 Модель `Client` — Клиент

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `inn` | CharField(12), unique | ИНН |
| `full_name` | CharField(500) | Полное название |
| `short_name` | CharField(200) | Сокращённое название |

**Автозаполнение по ИНН:**

При вводе ИНН система выполняет запрос к открытому API ФНС России (или сервису DaData.ru) и автоматически заполняет поля:
- Полное название
- Сокращённое название

> **Примечание реализации:** API DaData требует токена. Как fallback — официальный сервис egrul.nalog.ru. Реализовать через AJAX: поле ИНН + кнопка «Найти».

#### 2.2 Модель `Contact` — Контакт клиента

Каждый клиент может иметь **несколько контактов**.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `client` | FK → Client | |
| `first_name` | CharField(100) | Имя |
| `last_name` | CharField(100) | Фамилия |
| `patronymic` | CharField(100), nullable | Отчество |
| `email` | EmailField, nullable | Почта |
| `telegram_username` | CharField(100), nullable | @username в Telegram |
| `telegram_id` | BigIntegerField, nullable | ID в Telegram |

#### 2.3 Модель `Phone` — Телефоны контакта

Каждый контакт может иметь **несколько телефонов**.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `contact` | FK → Contact | |
| `number` | CharField(30) | Номер телефона |
| `description` | CharField(200), nullable | Пример: «мобильный», «рабочий», «WhatsApp» |

#### 2.4 Модель `ClientAddress` — Адрес клиента

Каждый клиент может иметь **несколько адресов**.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `client` | FK → Client | |
| `address` | TextField | Адрес |
| `description` | TextField, nullable | Описание адреса |

#### 2.5 Модель `Tag` — Метки (фильтр-метки)

Справочная таблица меток. Метки используются для фильтрации и группировки клиентов.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `name` | CharField(100), unique | Название метки |
| `color` | CharField(7) | HEX-цвет (#RRGGBB) |
| `tag_type` | CharField | `filter` / `password` |

**Связь:** `Client` ↔ `Tag` — ManyToMany  

- **Фильтр-метки** (`filter`): видны всем, используются для поиска/группировки
- **Пароль-метки** (`password`): видны только пользователям с правом `view_passwords`

#### 2.6 Функциональность модуля «Клиенты»

- Поиск клиентов по ИНН / названию / метке
- Добавление клиента вручную или по ИНН (с автозаполнением)
- Карточка клиента: контакты, адреса, метки, связанные заказы, приборы, заявки
- Быстрое добавление контакта прямо из карточки клиента
- История изменений карточки клиента
- Экспорт списка клиентов (CSV, Excel)

---

### Модуль 3. Заказы

Два принципиально разных типа заказов:

#### 3.1 Заказ клиента (`CustomerOrder`)

Заказ изделий/работ для клиента.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `number` | CharField, unique | Номер заказа (авто или ручной) |
| `client` | FK → Client | |
| `status` | CharField | `draft` / `confirmed` / `in_production` / `ready` / `shipped` / `closed` / `cancelled` |
| `created_at` | DateTimeField | |
| `deadline` | DateField, nullable | Срок выполнения |
| `notes` | TextField, nullable | |
| `created_by` | FK → User | |
| `total_amount` | DecimalField | Итоговая сумма |

#### 3.2 Позиция заказа клиента (`CustomerOrderItem`)

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `order` | FK → CustomerOrder | |
| `product` | FK → Product, nullable | Изделие из библиотеки |
| `name` | CharField | Наименование (если нет в библиотеке) |
| `quantity` | IntegerField | Количество |
| `price` | DecimalField, nullable | Цена за единицу |
| `notes` | TextField, nullable | |

#### 3.3 Заказ компонентов на склад (`StockOrder`) 

Заказ компонентов у поставщика для пополнения склада.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `number` | CharField, unique | Номер заказа |
| `supplier` | CharField, nullable | Поставщик |
| `status` | CharField | `draft` / `ordered` / `in_transit` / `received` / `cancelled` |
| `created_at` | DateTimeField | |
| `expected_date` | DateField, nullable | Ожидаемая дата поставки |
| `actual_date` | DateField, nullable | Фактическая дата получения |
| `notes` | TextField | |
| `created_by` | FK → User | |

> **Примечание:** При получении заказа (`status = received`) автоматически увеличивать `Component.quantity` для каждой позиции.

#### 3.4 Позиция заказа компонентов (`StockOrderItem`)

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `order` | FK → StockOrder | |
| `component` | FK → Component, nullable | Если есть в склад |
| `library_item` | FK → ComponentLibrary, nullable | Если из библиотеки |
| `name` | CharField | Наименование (fallback) |
| `quantity` | IntegerField | Заказанное количество |
| `received_quantity` | IntegerField, default=0 | Фактически полученное |
| `price` | DecimalField, nullable | Цена за единицу |

---

### Модуль 4. Библиотека

> **Статус:** Частично реализована в текущем Flask-проекте. Переносится с расширением.

#### 4.1 Иерархия классификации компонентов (переносится)

Трёхуровневая структура — **реализована в текущем проекте:**

```
Группа (Group)
  └── Подгруппа (Subgroup)  [+ допустимые единицы измерения]
        └── Тип (ComponentType)
```

Предустановленные данные (120+ корпусов, полное дерево классификации) — перенести из `component_structure.py`.

#### 4.2 Библиотека компонентов `ComponentLibrary` (переносится)

Эталонные спецификации компонентов без учёта остатков:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `name` | CharField(200) | Артикул / наименование |
| `type` | FK → ComponentType | |
| `housing` | FK → Housing, nullable | |
| `manufacturer` | CharField(100) | |
| `nominal_value` | FloatField, nullable | Числовой номинал |
| `unit` | CharField(20) | Единица измерения |
| `parameters` | JSONField | Дополнительные параметры |
| `description` | TextField, nullable | |
| `datasheet_url` | URLField, nullable | Ссылка на даташит |

#### 4.3 Библиотека изделий `Product` (переносится)

Изделия с BOM-спецификацией:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `name` | CharField(200), unique | Наименование |
| `description` | TextField | |
| `version` | CharField(20), nullable | Версия изделия |
| `created_by` | FK → User | |
| `created_at` | DateTimeField | |

#### 4.4 BOM-спецификация `BomItem` (переносится)

Строки спецификации изделия — модель и алгоритм **автосопоставления** переносятся из текущего проекта полностью.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `product` | FK → Product | |
| `bom_id` | CharField(20) | ID из EasyEDA/JLCPCB |
| `name` | CharField(200) | Наименование |
| `designator` | CharField(500) | Позиционные обозначения |
| `footprint` | CharField(200) | Корпус из CAD |
| `quantity` | IntegerField | Кол-во на изделие |
| `manufacturer_part` | CharField(200) | Артикул производителя |
| `manufacturer` | CharField(200) | |
| `component` | FK → Component, nullable | Сопоставленный компонент на складе |
| `match_confidence` | FloatField | Уверенность сопоставления 0..1 |

**Переносимые алгоритмы:**
- `_auto_match` — 6-уровневое автосопоставление BOM → склад
- `_parse_value` — парсер номиналов (4k7, 100n, 0.1uF, пФ, кОм, мкФ…)
- `_find_bom_duplicates` — анализ дубликатов в BOM
- Импорт CSV (UTF-8/UTF-16, форматы EasyEDA и JLCPCB)

---

### Модуль 5. Склад

> **Статус:** Реализован в текущем Flask-проекте. Переносится с расширением.

#### 5.1 Склад компонентов `Component` (переносится + расширяется)

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `unique_id` | UUIDField, unique | Глобальный UUID |
| `name` | CharField(100) | Наименование |
| `type` | FK → ComponentType | |
| `housing` | FK → Housing, nullable | |
| `manufacturer` | CharField(100) | |
| `quantity` | IntegerField | Текущий остаток |
| `min_quantity` | IntegerField, default=0 | Минимальный остаток (для уведомлений) |
| `price` | DecimalField, nullable | Последняя цена поступления |
| `arrival_date` | DateTimeField, nullable | |
| `location` | CharField(100) | Место хранения |
| `nominal_value` | FloatField, nullable | Числовой номинал |
| `unit` | CharField(20) | Единица измерения |
| `parameters` | JSONField | Дополнительные параметры |
| `created_by` | FK → User | |
| `is_archived` | BooleanField | Мягкое удаление |

#### 5.2 Склад изделий `ProductStock`

Учёт остатков готовой продукции.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `product` | FK → Product | |
| `quantity` | IntegerField | Текущий остаток |
| `location` | CharField(100), nullable | Место хранения |
| `serial_numbers` | TextField, nullable | Серийные номера (по одному в строке) |
| `updated_at` | DateTimeField | |

#### 5.3 История склада `ComponentHistory` (переносится)

История всех изменений количества и параметров компонентов.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `component` | FK → Component | |
| `user` | FK → User | |
| `action` | CharField | `create` / `update` / `writeoff` / `receive` / `archive` |
| `field_changed` | CharField, nullable | Изменённое поле |
| `old_value` | TextField, nullable | |
| `new_value` | TextField, nullable | |
| `timestamp` | DateTimeField | |
| `quantity_delta` | IntegerField, nullable | Изменение количества (+/-) |
| `notes` | TextField, nullable | Комментарий |

#### 5.4 Функциональность склада

- Список компонентов с фильтрами по дереву классификации
- Поиск по наименованию, производителю, типу, корпусу
- Карточка компонента с историей изменений
- Мягкое удаление и архив
- Отчёт по дефициту (остаток < `min_quantity`)
- Операция «Списание» для производства N изделий по BOM
- Операция «Приёмка» из заказа на пополнение

---

### Модуль 6. Приборы

Учёт конкретных экземпляров изделий, находящихся у клиентов.

#### 6.1 Модель `DeviceModel` — Модель прибора

Справочник моделей приборов.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `name` | CharField(200), unique | Название модели |
| `product` | FK → Product, nullable | Связь с изделием из библиотеки |
| `description` | TextField, nullable | |
| `created_at` | DateTimeField | |

#### 6.2 Модель `Firmware` — Прошивка

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `device_model` | FK → DeviceModel | |
| `version` | CharField(50) | Версия прошивки |
| `release_date` | DateField, nullable | |
| `file` | FileField, nullable | Файл прошивки |
| `changelog` | TextField, nullable | Список изменений |
| `is_stable` | BooleanField | Стабильная/тестовая |

#### 6.3 Модель `DeviceConfiguration` — Комплектация

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `device_model` | FK → DeviceModel | |
| `name` | CharField(200) | Название комплектации |
| `description` | TextField, nullable | |
| `bom_product` | FK → Product, nullable | BOM-спецификация для этой комплектации |

#### 6.4 Модель `Device` — Экземпляр прибора

Конкретный физический прибор у клиента.

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `serial_number` | CharField(100), unique | Серийный номер |
| `device_model` | FK → DeviceModel | |
| `configuration` | FK → DeviceConfiguration, nullable | |
| `firmware` | FK → Firmware, nullable | Установленная прошивка |
| `client` | FK → Client, nullable | Текущий владелец |
| `customer_order` | FK → CustomerOrder, nullable | Заказ, по которому продан |
| `manufacture_date` | DateField, nullable | Дата производства |
| `sale_date` | DateField, nullable | Дата продажи |
| `status` | CharField | `in_stock` / `sold` / `in_repair` / `written_off` |
| `notes` | TextField, nullable | |

#### 6.5 Модель `DiagnosticResult` — Результаты диагностики

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `device` | FK → Device | |
| `service_request` | FK → ServiceRequest, nullable | Связанная заявка |
| `performed_by` | FK → User | |
| `performed_at` | DateTimeField | |
| `result` | TextField | Описание результата |
| `parameters` | JSONField, nullable | Числовые параметры диагностики |
| `conclusion` | CharField | `ok` / `needs_repair` / `unrepairable` |
| `attachments` | FileField, nullable | Фото, файлы |

---

### Модуль 7. Заявки на ремонт

#### 7.1 Модель `ServiceRequest` — Заявка на ремонт

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `number` | CharField(50), unique | Номер заявки (авто) |
| `client` | FK → Client | |
| `device` | FK → Device | |
| `status` | CharField | см. п. 7.2 |
| `priority` | CharField | `low` / `normal` / `high` / `urgent` |
| `description` | TextField | Описание неисправности от клиента |
| `created_at` | DateTimeField | |
| `updated_at` | DateTimeField | |
| `deadline` | DateField, nullable | Срок выполнения |
| `assigned_to` | FK → User, nullable | Ответственный исполнитель |
| `created_by` | FK → User | |
| `resolution` | TextField, nullable | Описание выполненных работ |
| `closed_at` | DateTimeField, nullable | |
| `warranty_case` | BooleanField | Гарантийный случай |

#### 7.2 Статусы заявки

| Код | Описание |
|-----|----------|
| `new` | Новая заявка |
| `accepted` | Принята в работу |
| `diagnostics` | На диагностике |
| `waiting_parts` | Ожидание комплектующих |
| `in_repair` | В ремонте |
| `testing` | Тестирование |
| `ready` | Готово к выдаче |
| `closed` | Закрыта |
| `cancelled` | Отменена |

#### 7.3 Модель `ServiceRequestComment` — Комментарии к заявке

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | PK | |
| `service_request` | FK → ServiceRequest | |
| `user` | FK → User | |
| `text` | TextField | |
| `created_at` | DateTimeField | |
| `is_internal` | BooleanField | Внутренний (не виден клиенту) |
| `attachment` | FileField, nullable | Вложение |

#### 7.4 Функциональность модуля

- Список заявок с фильтрами по статусу, приоритету, ответственному, клиенту
- Карточка заявки: история статусов, комментарии, связанная диагностика
- Смена статуса с комментарием (журнал переходов)
- Автоматическое создание заказа на компоненты из заявки (если нужны запчасти)
- Уведомление при изменении статуса (email — опционально)

---

## 3. Связи между модулями

```
User (пользователь системы)
  ├── создаёт клиентов, заказы, заявки
  └── назначается исполнителем заявок

Client (клиент)
  ├── Contact[] (контакты)
  │     └── Phone[] (телефоны)
  ├── ClientAddress[] (адреса)
  ├── Tag[] (M2M метки)
  ├── CustomerOrder[] (заказы клиента)
  │     └── CustomerOrderItem[] (позиции)
  ├── Device[] (приборы клиента)
  └── ServiceRequest[] (заявки на ремонт)

Device (прибор/экземпляр)
  ├── DeviceModel
  │     ├── Firmware[]
  │     └── DeviceConfiguration[]
  ├── CustomerOrder (из которого продан)
  ├── Client (владелец)
  ├── DiagnosticResult[]
  └── ServiceRequest[]

Склад компонентов
  Component (Group → Subgroup → Type → Housing)
  ├── ComponentHistory[]
  ├── StockOrderItem[] (заказы на пополнение)
  └── BomItem[] (вхождение в спецификации)

Склад изделий
  Product
  ├── BomItem[] (спецификация)
  ├── ProductStock (остатки)
  └── CustomerOrderItem[] (вхождение в заказы)
```

---

## 4. Нефункциональные требования

### 4.1 Безопасность

- Аутентификация через Django Session Auth
- Декоратор `@login_required` на всех защищённых представлениях
- Проверка прав на уровне view и шаблонов
- CSRF-защита (встроенная в Django)
- Хэширование паролей PBKDF2 (стандарт Django)
- Пароль-метки клиентов — отдельная проверка права `view_passwords`
- Экранирование вывода в шаблонах (автоэкранирование Django Templates)

### 4.2 Производительность

- Использовать `select_related` / `prefetch_related` для предотвращения N+1 запросов
- Пагинация для всех списков (20 записей по умолчанию)
- Индексы на полях поиска: `inn`, `serial_number`, `order_number`

### 4.3 Интерфейс

- Адаптивный веб-интерфейс (Bootstrap 5 или аналог)
- AJAX-поиск при вводе ИНН
- Каскадные зависимые списки (Группа → Подгруппа → Тип) — как в текущем проекте
- Фильтрация и поиск в каждом списке
- Быстрые действия из карточки (добавить контакт, создать заявку, создать заказ)

---

## 5. Открытые вопросы

| № | Вопрос | Примечание |
|---|--------|-----------|
| 1 | API DaData или egrul.nalog.ru для поиска по ИНН? | DaData — платный, но удобный. Наlog.ru — бесплатный, но ограниченный. |
| 2 | Система прав: Django Permissions или булевы поля? | Рекомендуется Django Permissions. |
| 3 | Нужен ли REST API (DRF) или только web-интерфейс? | Актуально если планируется мобильное приложение. |
| 4 | Уведомления по email при смене статуса заявки? | Требует настройки SMTP. |
| 5 | Нужен ли экспорт данных (PDF, Excel)? | Для заявок, актов — вероятно да. |
| 6 | Миграция данных из текущей SQLite БД Flask-проекта? | Если нужна — потребуется скрипт миграции. |

---

## 6. Очерёдность разработки (предлагаемая)

1. **Этап 1** — Базовая инфраструктура: Django-проект, кастомный User, аутентификация
2. **Этап 2** — Справочники: Группы, Подгруппы, Типы, Корпуса (перенос из Flask)
3. **Этап 3** — Склад компонентов + библиотека (перенос логики из Flask)
4. **Этап 4** — Клиенты: модель, контакты, адреса, метки, поиск по ИНН
5. **Этап 5** — Заказы клиентов и заказы на склад
6. **Этап 6** — Приборы: модели, прошивки, комплектации, экземпляры
7. **Этап 7** — Заявки на ремонт: статусы, комментарии, диагностика
8. **Этап 8** — BOM: перенос алгоритма автосопоставления и импорта CSV
9. **Этап 9** — Дашборд, отчёты, экспорт
