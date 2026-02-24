# Информационный сервис (Django)

## Что уже есть
- Каркас Django-проекта `diplom` и приложения `messenger`.
- Модели: группы, преподаватели, родители, дети, методпакеты, слоты расписания, сообщения.
- Админка с регистрацией всех моделей.
- REST API через DRF c маршрутами `/api/` (groups, teachers, parents, students, method-packages, schedule, messages) + вложенные actions `/api/groups/<id>/schedule/` и `/api/groups/<id>/messages/`.
- JWT-авторизация через `djangorestframework-simplejwt`: получение токена `POST /api/token/`, обновление `POST /api/token/refresh/`.
- Веб-страница входа по адресу `/login/` с запросом JWT и отображением роли пользователя.

## Локальный запуск
1. Создать и активировать виртуальное окружение:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Установить зависимости (нужен доступ к PyPI; сейчас в среде блокируется сертификат SSL):
   ```bash
   pip install -r requirements.txt
   ```
   Если видите `CERTIFICATE_VERIFY_FAILED`, укажите корпоративный сертификат или используйте зеркало PyPI с валидным SSL.
3. Прописать переменные окружения в `.env` (есть шаблон `.env.example`). Для Postgres заполните `POSTGRES_*`. Без них проект переключится на SQLite по умолчанию.
4. Применить миграции и создать суперпользователя:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```
5. Запустить сервер:
   ```bash
   python manage.py runserver
   ```

## Аутентификация (JWT)
- Получить токен: `POST /api/token/` с `{"username": "...", "password": "..."}` (создать пользователя через `createsuperuser` или админку).
- Обновить токен: `POST /api/token/refresh/` с `{"refresh": "<refresh>"}`.
- Передавать в заголовке: `Authorization: Bearer <access>`.
- Страница входа: `http://127.0.0.1:8000/login/` (делает запросы к `/api/token/` и `/api/me/`).

## Минимальная структура данных
- **Group**: название, описание; связывает учеников и преподавателей.
- **Teacher**: ФИО, контакты, многие-ко-многим с группами.
- **Parent**: ФИО, контакты.
- **Student**: ФИО, принадлежит группе, многие-ко-многим с родителями.
- **MethodPackage**: название, описание, ссылка/файл.
- **ScheduleSlot**: группа, день недели, номер занятия (1/2), время, длительность, методпакет.
- **Message**: группа, тип отправителя, имя, текст, время.

## API (через DRF Router)
- `GET/POST /api/groups/` – список/создание групп.
- `GET/PUT/PATCH/DELETE /api/groups/<id>/` – детали.
- `GET /api/groups/<id>/schedule/` – расписание группы.
- `GET/POST /api/groups/<id>/messages/` – последние сообщения группы и отправка нового.
- CRUD для `/api/teachers/`, `/api/parents/`, `/api/students/`, `/api/method-packages/`, `/api/schedule/`, `/api/messages/`.

## Дальшие шаги
- Настроить установку зависимостей (решить SSL для PyPI или предоставить локальные whl).
- Добавить авторизацию (например, JWT через `djangorestframework-simplejwt`) и разграничение ролей.
- Добавить файлохранилище для методматериалов (S3/MinIO/локально) и ограничения доступа.
- Написать миграции и начальные фикстуры групп/ролей.
- Подключить фронтенд (SPA или Django templates) для удобного интерфейса.
