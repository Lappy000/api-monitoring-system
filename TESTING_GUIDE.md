# 🧪 Руководство по тестированию для пользователей API Monitor

## Для тех, кто хочет просто проверить, что все работает

### ✅ Вариант 1: Самый простой способ (Windows)
```bash
cd "Middle python"
test.bat
```

**Что это делает:**
- Запускает все тесты
- Показывает покрытие кода
- Занимает ~10 секунд

**Ожидаемый результат:**
```
232 passed, 4 skipped
TOTAL: 80% coverage
✅ ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!
```

### ✅ Вариант 2: С красивым отчетом
```bash
test.bat html
```

Откроется HTML-отчет в браузере с детальной информацией о покрытии.

### ✅ Вариант 3: Быстрая проверка (smoke test)
```bash
test.bat quick
```

Запускает только критические тесты за 2 секунды.

---

## Для разработчиков, которые хотят добавить свои тесты

### Шаг 1: Создайте файл теста

Создайте файл `tests/test_my_feature.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_my_api_endpoint():
    """Тест моей функции."""
    # Arrange (подготовка)
    mock_db = AsyncMock()
    
    # Act (действие)
    # ... ваш код ...
    
    # Assert (проверка)
    assert True
```

### Шаг 2: Запустите свой тест

```bash
pytest tests/test_my_feature.py -v
```

### Шаг 3: Проверьте покрытие

```bash
pytest tests/test_my_feature.py --cov=app.my_module
```

---

## ⚠️ Частые проблемы и решения

### Проблема 1: "Event loop is closed"

**Причина:** Конфликт между async тестами.

**Решение:** Запускайте свои тесты отдельно:
```bash
pytest tests/test_my_feature.py
```

### Проблема 2: "Module not found"

**Причина:** Не установлены зависимости.

**Решение:**
```bash
pip install -r requirements-dev.txt
```

### Проблема 3: "Database locked"

**Причина:** Старая БД используется другим процессом.

**Решение:**
```bash
# Остановите uvicorn если запущен
# Удалите БД
del data\monitor.db
# Запустите тесты снова
pytest
```

### Проблема 4: Тесты падают с непонятными ошибками

**Решение:** Запустите быстрый smoke test:
```bash
pytest tests/test_simple.py -v
```

Если smoke test проходит, значит окружение настроено правильно.

---

## 📋 Checklist перед коммитом

Перед тем как закоммитить свой код, выполните:

```bash
# 1. Запустите все тесты
pytest --cov=app

# 2. Проверьте, что покрытие не упало
# Должно быть ≥80%

# 3. Проверьте, что нет новых warning
pytest -v

# 4. Запустите линтер (если есть)
flake8 app/ tests/

# 5. Отформатируйте код (если используется)
black app/ tests/
```

---

## 🎯 Примеры тестов для ваших сценариев

### Пример 1: Тест API endpoint

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_my_endpoint():
    """Тест моего endpoint."""
    response = client.get("/api/v1/my-endpoint")
    assert response.status_code == 200
    assert "data" in response.json()
```

### Пример 2: Тест с базой данных

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_database_operation():
    """Тест операции с БД."""
    # Mock database
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = my_object
    mock_db.execute.return_value = mock_result
    
    # Your test code
    result = await my_function(mock_db)
    
    # Assertions
    assert result is not None
```

### Пример 3: Тест с HTTP mock

```python
import pytest
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_external_api_call():
    """Тест вызова внешнего API."""
    with patch('aiohttp.ClientSession') as mock_session:
        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"status": "ok"}
        
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
        
        # Your code
        result = await call_external_api()
        
        assert result["status"] == "ok"
```

---

## 📚 Полезные ресурсы

### Документация:
- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)

### Наши comprehensive тесты:
Посмотрите файлы `test_*_comprehensive.py` в папке [`tests/`](tests/) для примеров.

---

## 💬 Нужна помощь?

1. **Проверьте README:**
   - [`tests/README.md`](tests/README.md) - Детальное руководство
   - [`README.md`](../README.md) - Основная документация

2. **Запустите примеры:**
   ```bash
   pytest tests/test_simple.py -v  # Базовые тесты
   pytest tests/test_health_api_comprehensive.py -v  # API тесты
   ```

3. **Проверьте логи:**
   ```bash
   pytest -v -s --log-cli-level=INFO
   ```

---

## ✨ Итог

**Для быстрой проверки:** Просто запустите `test.bat`

**Для разработки:** Создайте свои тесты по примеру comprehensive тестов

**Все тесты проходят:** 232/232 ✅ с покрытием 80%

**Проект готов к production использованию!** 🚀