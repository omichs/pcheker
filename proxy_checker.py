import requests
import threading
from concurrent.futures import ThreadPoolExecutor
import logging
from tqdm import tqdm
import functools

# Настройка логирования для чистого вывода
logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger()

# URL для проверки и таймаут
TEST_URL = 'https://api.ipify.org?format=json'
TIMEOUT = 15

# Глобальные объекты для синхронизации потоков
file_lock = threading.Lock()
stop_event = threading.Event()

def check_proxy(proxy):
    """
    Проверяет один прокси по протоколам SOCKS5, SOCKS4, HTTP.
    Прекращает работу, если установлен флаг stop_event.
    """
    if stop_event.is_set():
        return

    proxy_protocols = {
        'socks5': f'socks5h://{proxy}',
        'socks4': f'socks4h://{proxy}',
        'http': f'http://{proxy}',
    }

    for proto_name, proxy_url in proxy_protocols.items():
        # Проверяем снова перед каждым запросом, чтобы остановить как можно быстрее
        if stop_event.is_set():
            return
            
        proxies = {'http': proxy_url, 'https': proxy_url}
        
        try:
            response = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT)
            response.raise_for_status()

            if 'ip' in response.json():
                with file_lock: # Блокируем, чтобы вывод не смешивался с прогресс-баром
                    log.info(f"\n✅ [РАБОТАЕТ] {proxy} как {proto_name.upper()}")
                save_proxy(proxy, proto_name)
                return
        
        # Ошибки обрабатываются тихо, чтобы не засорять вывод.
        # Вывод можно раскомментировать для отладки.
        except (requests.exceptions.ProxyError, requests.exceptions.Timeout, requests.exceptions.RequestException):
            # log.debug(f"[-] {proxy} не сработал как {proto_name.upper()}")
            pass
        except Exception:
            # log.debug(f"[!] Неизвестная ошибка с {proxy} ({proto_name.upper()})")
            pass

def save_proxy(proxy, proxy_type):
    """Сохраняет рабочий прокси в соответствующий файл."""
    filename = f"{proxy_type}_proxies.txt"
    with file_lock:
        with open(filename, 'a') as f:
            f.write(proxy + '\n')

def main():
    """Основная функция для запуска проверки с прогресс-баром и возможностью остановки."""
    try:
        with open('proxies.txt', 'r') as f:
            proxies_to_check = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        log.error("Ошибка: Файл 'proxies.txt' не найден.")
        log.error("Пожалуйста, создайте 'proxies.txt' и добавьте в него список прокси.")
        return

    if not proxies_to_check:
        log.warning("Файл 'proxies.txt' пуст. Нечего проверять.")
        return

    log.info(f"Начинаем проверку {len(proxies_to_check)} прокси... (Нажмите Ctrl+C для остановки)")

    try:
        with ThreadPoolExecutor(max_workers=25) as executor:
            # Создаем обертку tqdm для итератора, чтобы видеть прогресс-бар
            results = list(tqdm(executor.map(check_proxy, proxies_to_check), 
                                total=len(proxies_to_check), 
                                desc="Проверка прокси",
                                unit="proxy"))
    except KeyboardInterrupt:
        log.info("\n\n🛑 Проверка остановлена пользователем. Завершение...")
        stop_event.set()
        # Даем потокам время завершиться
        # executor.shutdown(wait=True) # Эта строка не всегда нужна, т.к. with сам вызовет shutdown
    except Exception as e:
        log.error(f"\nПроизошла критическая ошибка: {e}")


    log.info("\n✅ Проверка завершена.")
    log.info("Рабочие прокси сохранены в файлы: http_proxies.txt, socks4_proxies.txt, socks5_proxies.txt")


if __name__ == "__main__":
    main()
