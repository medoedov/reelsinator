# REELINATOR — технические решения исследования

Справочник к `TASK.md`, обновлён 7 ноября 2026 года. Фиксирует, **что мы уже выбрали и почему**. Это контекст для разработки, а не дополнительные обязательные этапы или список пакетов для установки. После первоначального ознакомления обращайся к разделу, относящемуся к текущей задаче. Наблюдения по стороннему коду основаны на предыдущем исследовании; перед переносом сверяй актуальный commit и лицензии.

## 1. Основа: что принято

| Область | Решение | Причина / условие |
|---|---|---|
| Основной рендер | [Remotion](https://www.remotion.dev/docs) с существующими компонентами; [официальные skills](https://github.com/remotion-dev/skills) использовать адресно | Программные и редактируемые сцены; единый рендер для большинства форматов |
| Обработка медиа | [FFmpeg/ffprobe](https://ffmpeg.org/documentation.html) | Нарезка, подготовка исходников, звук, кодирование и техническая проверка |
| Дополнительные FFmpeg-операции | [kajisho5/ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill) — **первый кандидат** на типизированный адаптер, если существующих скриптов не хватает | Структурированные аргументы и результаты, меньше непроверенных shell-команд; конкретный `ffmpeg skill` выбран среди одноимённых проектов |
| Монтаж речи | Взять из [Ghost Editor](https://github.com/kurbaitaev/ghost-editor) выбор связных дублей, бережную нарезку речи, титры с учётом лица и приёмы review | Качественный монтаж без механической резки каждой паузы; переносить выбранные приёмы, а не весь Claude-специфичный runtime |
| Показ интерфейсов | Взять выбранные Remotion-приёмы из [Video Shotcraft](https://github.com/Vincentwei1021/video-shotcraft) | Динамичные, но редактируемые демонстрации настоящих интерфейсов, zoom, сравнения и акценты |
| Анализ референсов | [Reelbench video-shots](https://github.com/eternityspring/reelbench-skills/tree/main/skills/video-shots) — кандидат на измерение смены планов и композиции | Превратить «сделай как здесь» в конкретные монтажные решения; качество референса оценивается по доступному материалу |
| Распознавание речи | Сначала имеющийся `whisper.cpp`; на реальной русской речи сравнить с [Parakeet MLX](https://github.com/senstella/parakeet-mlx), используя соответствующую [мультиязычную модель](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3). [mlx-whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) — альтернатива | Выбрать по точности **слов и таймингов**, особенно для русской речи с английскими названиями. Оставить один основной вариант и обоснованный запасной |
| Звуковой дизайн | Принципы cue sheet, учета происхождения звуков и сведения из [opus-sound-layer](https://github.com/Bodila51/opus-sound-layer) | Управляемые звуковые акценты; небольшая проверенная библиотека лучше огромного случайного набора |
| Анимация и 3D | [GSAP](https://github.com/greensock/GSAP) и [Three.js](https://github.com/mrdoob/three.js) через [Remotion GSAP](https://www.remotion.dev/docs/gsap) и [Remotion Three](https://www.remotion.dev/docs/three) при необходимости | Схемы, 2D-motion, трёхмерные объекты и короткие сценки в общем таймлайне |

Дополнительные возможности Remotion, которые стоит **проверить на реальных исходниках**: `Video` из [`@remotion/media`](https://www.remotion.dev/docs/video-and-audio) вместо старого видеокомпонента; бенчмарк конкурентности рендера; [`@remotion/video-matting`](https://www.remotion.dev/docs/video-matting) вместо обязательного CPU-rembg в отдельных сценах. Вывод о скорости и совместимости на целевой машине делается по тесту, все пакеты `@remotion/*` обновляются согласованно. Видео без человека не должно запускать маттинг.

## 2. Дополнять по задаче

| Задача | Кандидат и принятый подход |
|---|---|
| HTML/CSS-анимация, которая измеримо удобнее в отдельном движке | [HyperFrames](https://github.com/heygen-com/hyperframes) — **дополнительный renderer**, не замена основному Remotion |
| Специализированные технические схемы и изометрия | [ManimGX](https://github.com/academa-labs/manimgx), [Anatomy](https://github.com/wheresryan22/anatomy); отдельно решать экспорт в видео |
| Длинные записи и выделение клипов | [auto-editor](https://github.com/WyattBlue/auto-editor) и отдельные приёмы [Claude Shorts](https://github.com/AgriciDaniel/claude-shorts); автоматическая обрезка тишины — черновая операция |
| Съёмка экрана | [OpenScreen](https://github.com/getopenscreen/openscreen), когда доступна графическая сессия и права записи; готовые скринкасты можно импортировать напрямую |
| Получение доступных референсов | [yt-dlp](https://github.com/yt-dlp/yt-dlp); права на просмотр и повторное использование оцениваются отдельно |
| Захват браузерных сцен / покадровые проверки | [Puppeteer](https://github.com/puppeteer/puppeteer) при необходимости; отдельный дублирующий рендерер не нужен |
| Анализ содержания видеоролика | [claude-video/watch](https://github.com/bradautomates/claude-video) — возможная выборка кадров + транскрипт; переиспользовать уже выполненное ASR |
| Музыка и несколько спикеров | [librosa](https://github.com/librosa/librosa), [pyannote-audio](https://github.com/pyannote/pyannote-audio), [mlx-audio](https://github.com/Blaizzy/mlx-audio) при появлении соответствующих исходников |
| Идеи структуры монтажного проекта или автоматизации | [OpenMontage](https://github.com/calesthio/OpenMontage), [Hypit](https://github.com/hypit-ai/hypit), [Explainroo](https://github.com/vincentsch/explainroo) — архитектурные референсы, исходные реализации сначала оценивать по лицензии и состоянию |
| Поиск нового специализированного решения | [awesome-claude-video-skills](https://github.com/zhuyansen/awesome-claude-video-skills) — каталог для адресного поиска |

Оригинальное название «claude shots» однозначно не идентифицировано; **Claude Shorts** и **Video Shotcraft** рассматриваются как разные проекты. Реализация 3D-мультфильмов с постоянными персонажами, сложным риггингом и генеративным кино может развиваться отдельными задачами поверх монтажного ядра.

## 3. Что обнаружено в исходном репозитории

Статический аудит был выполнен на commit [`c2686da`](https://github.com/skailabinfo/claude-video-harness/commit/c2686da122cd7755fe4f829f077e5cdcb67369cd). Эти наблюдения нужно **сверить с текущим состоянием** исходников; это приоритеты проверки, а не повод переписывать всё подряд.

- [`cut.py`](https://github.com/skailabinfo/claude-video-harness/blob/c2686da122cd7755fe4f829f077e5cdcb67369cd/video/scripts/cut.py) и рендер используют общие пути для исходника, титров и результатов: обеспечить изоляцию видеопроектов.
- [`matte.py`](https://github.com/skailabinfo/claude-video-harness/blob/c2686da122cd7755fe4f829f077e5cdcb67369cd/video/scripts/matte.py) доверяет существующему кэшу масок: связать производные файлы с настоящим исходником и параметрами.
- [`refs.py`](https://github.com/skailabinfo/claude-video-harness/blob/c2686da122cd7755fe4f829f077e5cdcb67369cd/video/scripts/refs.py) кэширует референсы по порядковым номерам: идентифицировать по URL/video ID и содержимому; проверять результат внешних команд.
- Унаследованный [`new-video`](https://github.com/skailabinfo/claude-video-harness/blob/c2686da122cd7755fe4f829f077e5cdcb67369cd/.claude/skills/new-video/SKILL.md) допускает правки готового MP4: сохранять решения в редактируемом источнике сборки.
- В исходной композиции встречаются привязки к `footage.mp4`, длительности внутри TSX и пустой дорожке captions. Проверить отдельно работу с audio-only, графикой с нуля и отсутствием речи.
- В [`master.sh`](https://github.com/skailabinfo/claude-video-harness/blob/c2686da122cd7755fe4f829f077e5cdcb67369cd/video/scripts/master.sh) воспроизведены лишнее AAC-кодирование, отсутствие `faststart` у мастера и ошибка нормализации полностью тихой дорожки. **Локальный патч и шесть тестов уже подготовлены**: [`prework/STATUS.md`](prework/STATUS.md). Проверены FFmpeg/ffprobe, но не реальный Remotion-рендер на пользовательской машине.

Структурное решение: **один редактируемый источник проекта** (существующие композиции + минимальные данные о ролике, если нужны), изолированные рабочие каталоги, возможность повторной сборки и точечных правок. Отдельная универсальная EDL/DSL, БД и сложная очередь потребуются только при доказанной необходимости. Сохранять исходники и правки важнее многочисленных промежуточных обёрток.

## 4. Контекст моделей и обслуживание инструкций

- [Anthropic: The new rules of context engineering for Claude 5 generation models](https://claude.com/blog/the-new-rules-of-context-engineering-for-claude-5-generation-models) — сокращение постоянного контекста, устранение конфликтующих и устаревших правил, ясные инструменты и свобода модели. Упомянутые в статье «минус 80%» относятся к их внутреннему эксперименту, не являются нормативом для REELINATOR.
- [Anthropic: Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — достаточно полезного контекста, загрузка сведений по необходимости, узкие непересекающиеся инструменты, небольшое число репрезентативных примеров.
- [Claude Code: memory / AGENTS.md](https://code.claude.com/docs/en/memory) — поддерживает общий `AGENTS.md`; явный `@AGENTS.md` в `CLAUDE.md` обеспечивает общую конфигурацию также в режимах, которые читают только `CLAUDE.md`.

Применение: `AGENTS.md` содержит только длительно полезные правила и подтверждённые команды; `CLAUDE.md` импортирует его; инструкции внешних skills адаптируются к обеим средам. Код и тесты фиксируют механические инварианты, а `TECH_DECISIONS.md` служит справочником. Специальный skill оправдан повторяемой задачей и понятным условием запуска; тестировать его также на задаче, где он не должен включиться.

Соблюдать лицензии по каждому заимствованному фрагменту: исходный harness распространяется по MIT; Remotion имеет собственные условия; OpenMontage — AGPL-3.0; Hypit — модифицированную Apache 2.0 с дополнительными условиями. Лицензия кода сама по себе не покрывает чужие видео, шрифты, голоса и другие ассеты.
