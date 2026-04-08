from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Europe/Moscow")

# ── Конфигурация детекции стресс-эпизодов ──
STRESS_THRESHOLD = 75          # порог: значение >= этого = повышенный стресс
MIN_CONSECUTIVE_POINTS = 2     # сколько точек подряд для открытия эпизода
MIN_EPISODE_DURATION_MIN = 6  # минимальная длительность (минуты) для сохранения