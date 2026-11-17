# Аккаунты и наработки

Публичная поставка не содержит личных аккаунтов. Создай свой:

```sh
python reel.py account-new my-channel --title "Мой канал" --brief "Концепция и требования"
python reel.py new first-episode --account my-channel --seconds 20
python reel.py accounts
python reel.py list --account my-channel
```

Агент заполняет паспорт из запроса и материалов, затем использует только контекст
выбранного аккаунта. Персонажи, референсы и предпочтения хранятся в его папке.
Правила — [docs/accounts.md](../../docs/accounts.md).
