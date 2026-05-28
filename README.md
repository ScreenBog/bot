# Geometry Dash Offline AI Bot (Python 3.11+)

Безопасный учебный каркас для одиночных офлайн-экспериментов с Geometry Dash: чтение заранее настроенных адресов памяти, запись/повтор нажатий и простая заменяемая логика `jump/no jump`.

> **Важно:** проект предназначен только для офлайн/одиночной игры, локального обучения и экспериментов. Он не обходит античиты, не скрывает запуск, не сканирует память автоматически и не предназначен для онлайн-режимов, соревнований или получения нечестного преимущества.

## Возможности

- Подключение к процессу `GeometryDash.exe` через `pymem`.
- Чтение RAM-полей, если вы явно указали адреса/offsets в `gd_ai_bot/config.json`:
  - `player_x`, `player_y`;
  - `speed`;
  - `on_ground`;
  - `level_percent`;
  - `player_mode`.
- Настраиваемые адреса, типы и pointer-chain offsets.
- Управление прыжком через WinAPI, `keyboard` или `pyautogui`.
- Аварийная остановка клавишей из конфига, по умолчанию `Esc`.
- `record`/`replay` маршрутов в JSON по проценту уровня или координате `X`.
- Базовый `AI mode` с простой эвристикой, который можно заменить PyTorch-моделью.
- Логи состояния и действий в консоль, ошибки — в `logs/gd_ai_bot_errors.log`.

## Структура проекта

```text
gd_ai_bot/
  __init__.py
  main.py              # CLI: state / record / replay / ai
  memory_reader.py     # подключение к процессу и чтение настроенных адресов
  input_controller.py  # WinAPI / keyboard / pyautogui ввод
  recorder.py          # запись нажатий игрока в route JSON
  replay.py            # воспроизведение route JSON
  ai_agent.py          # эвристический агент и runner
  config.py            # загрузка и проверка config.json
  config.json          # пример конфигурации с заглушками адресов
routes/                # сохраненные маршруты
logs/                  # файл ошибок и событий
requirements.txt
README.md
```

## Установка на Windows

1. Установите Python 3.11 или новее.
2. Создайте виртуальное окружение:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Установите зависимости:

```powershell
pip install -r requirements.txt
```

Некоторым backend'ам ввода (`keyboard`) может потребоваться запуск терминала от имени администратора, потому что Windows ограничивает глобальный keyboard hook.

## Запуск

Показать один снимок состояния RAM:

```powershell
python -m gd_ai_bot.main state
```

Записать маршрут до нажатия `Esc`:

```powershell
python -m gd_ai_bot.main record --output routes/my_level.json
```

Записать 30 секунд:

```powershell
python -m gd_ai_bot.main record --output routes/my_level.json --duration 30
```

Воспроизвести маршрут по координате/проценту из RAM:

```powershell
python -m gd_ai_bot.main replay --route routes/my_level.json
```

Воспроизвести маршрут по времени, если адреса RAM еще не настроены:

```powershell
python -m gd_ai_bot.main replay --route routes/my_level.json --time
```

Запустить базовый AI mode:

```powershell
python -m gd_ai_bot.main ai
```

## Настройка `config.json`

Файл `gd_ai_bot/config.json` уже содержит все нужные ключи, но адреса памяти стоят как `null`:

```json
"player_x": {
  "base": null,
  "offsets": [],
  "type": "float"
}
```

Пока `base` равен `null`, модуль чтения памяти возвращает безопасные значения по умолчанию. После того как вы нашли адрес для вашей версии игры, замените `null` на адрес:

```json
"player_x": {
  "base": "0x12345678",
  "offsets": [],
  "type": "float"
}
```

Если значение лежит по pointer chain, укажите базовый адрес или RVA и offsets:

```json
"player_x": {
  "base": "0x01ABCDEF",
  "offsets": ["0x10", "0x24", "0x8"],
  "type": "float"
}
```

Правило чтения такое:

1. `base` меньше `0x10000000` считается RVA относительно модуля `GeometryDash.exe`.
2. Если `offsets` пустой, значение читается прямо из `base`.
3. Если offsets есть, бот разыменовывает все offsets, кроме последнего, а последний прибавляет как финальное смещение значения.
4. Поддерживаемые типы: `float`, `double`, `int`, `uint`, `bool`, `byte`.

### Как найти адреса и подставить их позже

Этот проект не содержит автоматического memory scanner. Для офлайн-исследований обычно используют отдельный отладчик/анализатор памяти и находят адреса вручную для конкретной версии Geometry Dash:

- координаты `X/Y` часто меняются плавно во время движения;
- `level_percent` растет от `0` до `100`;
- `on_ground` часто выглядит как `0/1` или `false/true` и меняется при прыжке;
- `player_mode` может быть числом, которое меняется при порталах режима.

После нахождения стабильного адреса или pointer chain внесите его в `gd_ai_bot/config.json`, затем проверьте:

```powershell
python -m gd_ai_bot.main state
```

Если поле остается `0`/`False`, проверьте версию игры, тип значения, размер pointer (`memory.pointer_size`) и offsets.

## Record / Replay

`record` сохраняет события вида:

```json
{
  "action": "press",
  "coordinate": 42.5,
  "time_seconds": 12.345,
  "state": {
    "player_x": 1234.0,
    "level_percent": 42.5
  }
}
```

- `coordinate_source: "percent"` — запись и повтор по `level_percent`.
- `coordinate_source: "x"` — запись и повтор по `player_x`.
- Если адреса RAM не настроены, используйте `replay --time`; координатный replay без RAM-данных не сможет попасть в события.

## AI mode и замена на PyTorch

`gd_ai_bot/ai_agent.py` содержит класс `HeuristicAgent` с методом:

```python
def decide(self, state: GameState) -> bool:
    ...
```

Чтобы заменить эвристику на модель:

1. Создайте класс с тем же методом `decide(state) -> bool`.
2. Преобразуйте `GameState` в тензор признаков.
3. Верните `True`, если модель решила нажать прыжок.
4. Подставьте новый класс в `AiRunner`.

## Безопасные ограничения

- Нет обхода античитов.
- Нет скрытого запуска.
- Нет инъекции кода в процесс игры.
- Нет автоматического поиска адресов или сигнатур.
- Проект читает только те адреса, которые вы явно указали в конфигурации.
- Используйте только в офлайн/одиночной игре.
