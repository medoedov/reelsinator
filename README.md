# REELINATOR

Создание и монтаж видео обычными словами через **Codex или Claude Code**.
Агент работает с редактируемыми Remotion-сценами; общий Python CLI готовит медиа,
собирает видео через Chromium и выполняет FFmpeg-мастеринг.

[Готовый ролик из идеи](examples/idea-to-film/final-master.mp4) ·
[Превью](examples/idea-to-film/preview.mp4) ·
[Исходник сцен](video/projects/idea-to-film/Composition.tsx) ·
[Фактические проверки](examples/ACCEPTANCE.md)

![Кадр ролика](examples/idea-to-film/edit.png)

## Запуск

Требуются Node.js 22+, Python 3.11+ и FFmpeg/ffprobe 7+ в PATH.
Проверены Windows, Node 22.20.0, Python 3.13.7, FFmpeg 9.0.2 и Remotion 4.0.503.
macOS/Linux пока не проверялись. Для Python без команды `python` используйте `python3`.

```sh
git clone https://github.com/medoedov/reelsinator.git
cd reelsinator
npm ci --prefix video
python reel.py doctor
python reel.py render idea-to-film
```

Remotion при первом запуске скачивает Chrome Headless Shell. На Windows можно распаковать
[FFmpeg Essentials](https://www.gyan.dev/ffmpeg/builds/) в `.tools/ffmpeg/`:
CLI находит `**/bin/ffmpeg.exe` и `ffprobe.exe` автоматически. Другой путь задаётся
переменными `FFMPEG` и `FFPROBE`. Бинарники, модели и `node_modules` в Git не входят.
В ограниченной Windows-песочнице Codex Chromium может требовать разрешения на локальный запуск.

Откройте каталог в Codex или Claude Code и, например, напишите:

> Сделай 20-секундное видео о том, как работает солнечная батарея. Нужны понятная схема,
> русские подписи и спокойная анимация, без озвучки.

Или:

> Смонтируй C:/media/take.mov: сохрани связное объяснение, убери неудачные дубли,
> добавь субтитры. В финале оставь паузу.

`AGENTS.md` — общий источник инструкций; `CLAUDE.md` импортирует только его.
Канонические навыки — в `skills/`, одинаковые копии — в `.agents/skills/` и `.claude/skills/`.
После изменения навыков: `python scripts/sync-skills.py`.

## Создание и монтаж

```sh
# Создать рабочую стартовую композицию; сцены под идею разрабатывает агент
python reel.py new my-film --title "Новая история" --idea "Как рождается идея" --seconds 12
python reel.py studio my-film

# Импортировать и нарезать запись по исходным секундам
python reel.py cut my-film --source "C:/media/take.mov" --keep "0.2:5.1,7.0:12.4" --fit cover

# Или получить черновую нарезку длинных пауз для проверки
python reel.py cut my-film --source "C:/media/take.mov" --auto

# Распознать речь локально, если установлены whisper-cli и многоязычная модель
python reel.py transcribe my-film --language ru --model "C:/models/ggml-model.bin"

# Импортировать изображение, дополнительное видео, музыку или звук; затем подключить в TSX
python reel.py import my-film "C:/media/image.png"

# Измерить видеореференс и получить контактный лист; для URL нужен yt-dlp
python reel.py reference my-film "C:/media/reference.mp4"
```

Одна папка `video/projects/<id>/` содержит собственные исходники, композицию,
монтажные решения, расшифровку, кэш и результаты. Размер, fps и длительность графики
задаются в `project.json`. Для вертикали передайте `--width 1080 --height 1920` при создании.
Аудиозапись без видео также подходит для `cut`; видео без речи и графика не требуют ASR.

`whisper-cli` берётся из PATH или `WHISPER_CLI`, модель — из `--model` или `WHISPER_MODEL`.
Можно использовать исправленную расшифровку без ASR. Слова в `transcript.json`
имеют формат `{"w":"Слово","s":0.4,"e":0.8,"em":1}` во **времени исходника**.
После нарезки тайминги пересчитываются автоматически. Граница внутри слова останавливает
подготовку и требует корректировки. Повторное распознавание заменяет исправления только с `--replace`.

## Правка и экспорт

> В проекте my-film сделай субтитры крупнее и замени только финальный заголовок.

Агент изменяет `Composition.tsx`, `project.json` или `transcript.json`.
Для удаления фразы меняются интервалы `edit.json`. Новая сборка воспроизводит эти решения.

```sh
python reel.py prepare my-film
python reel.py check my-film
python reel.py still my-film --frame 60
python reel.py preview my-film
python reel.py render my-film --concurrency 2
python reel.py verify my-film
```

Мастер и превью сохраняются в `out/runs/<версия>/`. `out/latest.json` указывает на последнюю
успешную сборку. Ошибка оставляет предыдущий результат доступным, журнал остаётся в `cache/`.
Отдельная команда `preview` делает черновик в половинном разрешении без мастеринга в `cache/`.
Изображение рендерится чанками по 800 кадров, звук — одним PCM-проходом; мастер получает
однократное AAC-кодирование, 48 кГц, двухпроходный loudnorm и faststart.
Тихие ролики сохраняют тишину. По умолчанию 2 рендер-процесса — проверенное значение,
а не заявленный оптимум для любой машины.

Версия содержит технический `checks.json`, журнал и снимок кода. Полное декодирование,
число кадров, fps, размеры и длительности потоков проверяются до публикации версии.
Визуальный просмотр, синхронность слов и прослушивание отмечаются отдельно.
Для переноса проекта нужны репозиторий и исходные медиа из `public/assets/`.

Подробнее: [операции и устройство проекта](docs/workflow.md),
[технические решения](TECH_DECISIONS.md).

## Проверки реализации

```sh
npm run lint --prefix video
python -m unittest discover -s tests -v
python scripts/sync-skills.py --check
python reel.py check idea-to-film
```

Технический пример нарезки с синтетическим сигналом воспроизводится локально:

```sh
python scripts/make-fixtures.py
python reel.py render media-check
```

Эта команда заново создаёт тестовый источник и расшифровку `media-check`.
Она проверяет монтажную механику и **не является примером реальной речи**.
Выбор записи речи пользователь отложил. В текущей сессии подтверждены работа Codex,
реальный экспорт и точечная правка; Claude Code установлен, но не авторизован,
поэтому продолжение в нём пока не проверено. Подробности — [в отчёте приёмки](examples/ACCEPTANCE.md).

## Основа и лицензии

Основа — [claude-video-harness](https://github.com/skailabinfo/claude-video-harness), commit `c2686da`.
Сохранены полезные компоненты и MIT-лицензия, звуковой патч применён.
Унаследованный пример в `video/src/` оставлен для сравнения; новые проекты используют `reel.py`.
Remotion имеет собственную лицензию. [Происхождение и условия инструментов](docs/UPSTREAM.md).
