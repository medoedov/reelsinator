# Проверенная подготовка: звуковой мастеринг

Ранее подготовлено для исходного `skailabinfo/claude-video-harness` на commit `c2686da122cd7755fe4f829f077e5cdcb67369cd`:

- `patches/0001-single-pass-aac-master.patch`: однократное AAC-кодирование мастер-файла из исходного WAV, `faststart`, 48 kHz, корректная обработка тишины и ошибки измерения `loudnorm`.
- `tests/test_master.py`: шесть проверок (обычный звук, тишина, целостность чанков и три ошибочных случая).
- `LICENSE.upstream`: текст лицензии исходного кода.
- `test-results.txt` и `baseline-results.txt`: сохранённые результаты тестов после и до патча.

Тесты ранее прошли с реальными FFmpeg/ffprobe в Linux и с заменой вызова Remotion синтетическими тестовыми видео. **Полная сборка Remotion, macOS и пользовательские исходники этим не проверены.** Код репозитория мог измениться.

При интеграции сначала сравни актуальный `video/scripts/master.sh`, затем при совместимости выполни из корня репозитория:

```bash
git apply --check /path/to/REELINATOR/prework/patches/0001-single-pass-aac-master.patch
git apply /path/to/REELINATOR/prework/patches/0001-single-pass-aac-master.patch
python3 /path/to/REELINATOR/prework/tests/test_master.py --repo "$PWD"
```

При расхождениях перенеси исправление по смыслу и проверь реальный рендер. Патч не решает отдельные проекты, audio-only и отсутствие `footage.mp4`.
