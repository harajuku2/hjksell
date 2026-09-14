# HJKsell Session Checkpoint

Дата checkpoint: 2026-09-12

## Общие правила продолжения

- Не удалять и не сбрасывать `%LOCALAPPDATA%\HJKsell`.
- Не терять пользовательские данные: database, photos, settings, Telegram configs и telegram_imports.
- Никогда не выводить Telegram Bot Token, credentials или полный Telegram API URL с token.
- Не переделывать UI/design, finance или Analytics в рамках текущего расследования.
- Не возвращаться к одному глобальному Telegram token: конфигурации МОЯ и ДРУГА должны оставаться независимыми.
- Не считать Telegram production flow исправленным только по startup smoke test.
- Перед V1.0 полный `pytest` должен быть на 100% зелёным.
- После подтверждённого исправления последовательность проверки: full pytest → clean ONEDIR build → ручная проверка EXE → проверка обоих реальных Telegram bots/channels → restart test → только затем commit/tag.

## Stage 6: PyInstaller и Windows release

- Создан корневой entry point `run_hjksell.py` с absolute import `from hjksell.app import main`.
- Исправлен первоначальный relative-import startup bug при запуске PyInstaller EXE.
- Исправлен импорт `QDesktopServices`: он должен импортироваться из `PySide6.QtGui`, а не из `PySide6.QtCore`.
- Формат сборки: clean ONEDIR.
- Рабочий EXE:
  `C:\HJKsell\dist\HJKsell\HJKsell.exe`
- ONEDIR EXE запускался успешно.
- Вручную проверялись товары, фото и Analytics.
- Последняя diagnostic ONEDIR build завершилась успешно; последняя ручная проверка этой сборки снова показала crash при Telegram Settings Save.

## Telegram requirement

Портфели МОЯ и ДРУГА используют:

- два разных Telegram Bot Token;
- два разных Telegram channel.

Конфигурации должны быть полностью независимыми: token, offset, channel binding, imports и polling worker одного портфеля не должны перезаписывать или использовать состояние другого портфеля.

## Уже реализовано для двух Telegram configurations

- Модель/таблица `telegram_configs`.
- Portfolio-specific Telegram tokens.
- Portfolio-specific update offsets.
- Portfolio-specific channel bindings.
- `telegram_imports` получил portfolio identity.
- Duplicate protection и соответствующие индексы стали portfolio-specific.
- Добавлена Alembic migration `0005_portfolio_telegram_configs`.
- Существующие данные мигрируются без удаления пользовательской database.
- MainWindow использует отдельные API/import service/worker для каждого настроенного portfolio.
- Запускаются два независимых polling workers, по одному на portfolio.
- Migration status: существующая database была переведена через migration 0005; данные не сбрасывались.
- Последние тесты независимых tokens/offsets/configs проходили до появления текущей lifecycle-проблемы.

## Текущая неисправленная проблема

Реальный production flow:

```text
МОЯ
→ Telegram Settings
→ token
→ Проверить
→ channel успешно определяется
→ Save
→ приложение полностью вылетает
```

Validation проходит успешно, database config сохраняется, но после Save процесс HJKsell завершается.

## Хронология диагностики crash

### 1. Первоначальная validation QThread hypothesis

Сначала предполагалось, что crash связан с validation QThread после успешного `Проверить`, его `quit()/wait()` или закрытием dialog.

Эта гипотеза оказалась недостаточной: после изменения `_validation_finished()` и ожидания validation thread production crash при Save сохранился. Validation QThread не является подтверждённой причиной текущего crash.

### 2. Первая подтверждённая проблема polling lifecycle

Реальный app.log показал:

- dialog accepted;
- telegram config сохранился;
- DB `session.commit()` завершился;
- началась Telegram workers reconfiguration;
- `_stop_telegram_polling()` вызвал `quit()` и `wait(3000)`;
- старые polling QThreads после wait оставались `running=True`;
- reconfiguration продолжалась, ссылки очищались и запускались новые объекты;
- Qt выдал:

```text
QObject::setParent: Cannot set parent, new parent is in a different thread
```

После этого EXE завершался.

### 3. Cooperative shutdown/http client close fix

Был реализован cooperative shutdown:

- polling worker получает stop flag;
- wake event будит loop;
- active API client закрывается для прерывания blocking/long-poll request;
- `_stop_telegram_polling()` проверяет фактическое состояние QThread;
- ссылки не очищаются, если поток всё ещё жив;
- replacement workers не запускаются поверх живых старых workers.

После этого fake tests проходили и diagnostic EXE собирался, но реальный production crash сохранился.

### 4. Свежий реальный diagnostic log после cooperative fix

Последний ручной diagnostic reproduction показал:

- DB commit проходит;
- старые polling QThreads теперь завершаются;
- для обоих workers `running_after=False`;
- active `getUpdates` заканчивается `ReadError`;
- polling loops выходят;
- `finished.emit()` для старых workers выполняется;
- старые QThreads фактически завершаются;
- после этого начинается создание replacement workers.

Несмотря на это, приложение снова полностью вылетает.

## Самые последние подтверждённые thread-affinity факты

Qt error:

```text
QObject::setParent: Cannot set parent, new parent is in a different thread
```

Последний diagnostic log зафиксировал его в старом polling thread portfolio 1:

- Python thread ID: `24964`;
- Qt current thread identity соответствовал старому polling QThread portfolio 1.

В этом же thread выполнялись:

- polling loop portfolio 1;
- `getUpdates`;
- обработка `ReadError`;
- выход polling loop;
- `finished.emit()`.

GUI thread имел Python thread ID `11376` и выполнял:

- остановку workers;
- `TelegramImportService.stop()`;
- `TelegramApiClient.close()`;
- `thread.quit()`;
- `thread.wait()`;
- очистку dictionaries;
- создание replacement workers.

Подтверждено:

- старые polling QThreads теперь завершаются (`running_after=False`);
- active `getUpdates` прерывается и заканчивается `ReadError`;
- Qt error возникает в старом polling thread portfolio 1;
- Qt error возникает ДО создания replacement workers;
- replacement `moveToThread()` и `thread.start()` не являются непосредственным источником этого конкретного Qt error;
- validation thread не является источником;
- `QObject::setParent` error не является следствием оставшегося живым старого QThread;
- конкретная Qt operation/object, вызывающая `QObject::setParent`, всё ещё не идентифицирована.

Текущая thread-affinity схема до corrective fix:

- `TelegramApiClient` создаётся в GUI thread, используется polling thread.
- `httpx.Client` создаётся в GUI thread, используется polling thread.
- `TelegramImportService` создаётся в GUI thread, используется polling thread.
- `TelegramQtWorker` создаётся в GUI thread и затем перемещается в polling QThread.
- `QThread` создаётся и управляется из GUI thread; его worker code выполняется в отдельном OS thread.

Нельзя считать такую схему безопасной для Qt/client lifecycle без подтверждения конкретного вызова.

## Следующий запланированный диагностический шаг

Инструментировать ТОЛЬКО цепочку после `ReadError`:

```text
ReadError
→ diagnostics/error callback/signal
→ _telegram_diagnostics/UI callback
```

Цель — определить, не вызывается ли UI/Qt operation напрямую из polling QThread. Нужны минимальные markers непосредственно вокруг:

- `diagnostics.emit(values)`;
- callback/error callback;
- `_telegram_diagnostics()`;
- связанных Qt signal/slot переходов.

Каждый marker должен сохранять thread context, но не token/credentials.

До подтверждения конкретной Qt operation corrective fix делать нельзя. Нельзя маскировать проблему `try/except`, отключать polling или подавлять Qt messages.

## Состояние тестов

Последний полный запуск pytest НЕ зелёный:

```text
42 passed, 1 failed
```

Упавший тест:

```text
test_two_polling_workers_stop_independently
```

Контекст failure:

- fake blocking workers;
- общая SQLite `StaticPool`;
- в captured output появлялись `ResourceClosedError`/связанные ошибки контекста fake blocking worker;
- в одном из запусков второй fake worker не успевал установить `started` за 1 секунду.

Этот failure нельзя автоматически считать безобидным. Перед V1.0 полный pytest обязан быть 100% green; нужно отдельно понять и исправить/стабилизировать причину тестового failure, не скрывая его.

## Git status на момент checkpoint

Git commit/tag после незавершённых изменений не сделаны. Изменения не откатывались, не stash/reset.

Текущий `git status --short`:

```text
 M hjksell/__init__.py
 M hjksell/app.py
 M hjksell/database/connection.py
 M hjksell/database/models.py
 M hjksell/repositories/telegram_repository.py
 M hjksell/services/telegram.py
 M hjksell/ui/main_window.py
 M requirements.txt
 M tests/test_stage4_telegram.py
?? alembic/versions/0005_portfolio_telegram_configs.py
?? build.ps1
?? hjksell/database/migrations.py
?? run_hjksell.py
```

В modified/untracked files входят:

- `hjksell/__init__.py`
- `hjksell/app.py`
- `hjksell/database/connection.py`
- `hjksell/database/models.py`
- `hjksell/repositories/telegram_repository.py`
- `hjksell/services/telegram.py`
- `hjksell/ui/main_window.py`
- `requirements.txt`
- `tests/test_stage4_telegram.py`
- `alembic/versions/0005_portfolio_telegram_configs.py`
- `build.ps1`
- `hjksell/database/migrations.py`
- `run_hjksell.py`

Нельзя выполнять `git reset`, `git checkout`, удаление, stash или commit без отдельного явного решения владельца проекта.

## NEXT ACTION

Первое действие завтра: добавить минимальную instrumentation вокруг цепочки `diagnostics/error callback` после `ReadError`, включая вход/выход `diagnostics.emit`, callback и `_telegram_diagnostics()` с Python/Qt thread IDs; затем пересобрать diagnostic EXE и выполнить один ручной reproduction `Проверить → Save`.

До получения этой трассировки не применять corrective fix.
