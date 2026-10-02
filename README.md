
## Цель

Ответить на практические вопросы о текущем предложении:

- как распределены цены и цена за м²;
- какую долю объявлений покрывает заданный бюджет;
- как доступность меняется в зависимости от числа комнат;
- какие районы отличаются по медианной цене и цене за м²;
- какой бюджет нужен, чтобы покрыть 25%, 50%, 75% и 90% наблюдаемого предложения.

## Структура

```text
spb-cian-market-2026/
├── data/
│   ├── raw/                
│   └── processed/          
├── notebooks/
│   └── spb_cian_market_2026.ipynb
├── scripts/
│   ├── collect_cian.py
│   └── prepare_data.py
├── .gitignore
├── README.md
└── requirements.txt
```

## Установка
```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\\Scripts\\activate       # Windows

pip install -r requirements.txt
playwright install chromium
```

## 1. Сбор данных

Скрипт использует пакет `cian-parser` и собирает отдельно студии и квартиры с 1–5 комнатами, чтобы студии не смешивались с однокомнатными.

Пример для страниц 1–10:

```bash
python scripts/collect_cian.py --start-page 1 --end-page 10
```

Результат сохраняется в:

```text
data/raw/cian_spb_sale_YYYY-MM-DD_HHMM.csv
```

По умолчанию детальные страницы объявлений не открываются. Если у вас есть разрешение и нужны дополнительные признаки здания:

```bash
python scripts/collect_cian.py --start-page 1 --end-page 10 --extra-data
```

## 2. Подготовка

```bash
python scripts/prepare_data.py
```

Скрипт берёт последнюю сырую выгрузку и создаёт очищенный файл:

```text
data/processed/cian_spb_sale_clean.csv
```

Основные поля после подготовки:

| Поле | Смысл |
|---|---|
| `offer_id` | ID объявления |
| `url` | ссылка на объявление |
| `rooms` | 0 = студия, 1–5 = число комнат |
| `total_meters` | общая площадь, м² |
| `price` | цена объявления, ₽ |
| `price_per_m2` | цена за м² |
| `district` | район |
| `underground` | ближайшее метро |
| `floor` | этаж |
| `floors_count` | этажность дома |
| `residential_complex` | ЖК, если определён |
| `author_type` | тип продавца/автора объявления |
| `collected_at` | момент сбора |
