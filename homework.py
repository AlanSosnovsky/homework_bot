import logging
import os
from sys import stdout
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_TIME = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}


HOMEWORK_STATUSES = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}


def send_message(bot, message):
    """Отправляем сообщение в Телеграм."""
    tele_message = bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    if tele_message:
        logging.info(f"Бот отправил сообщение: '{tele_message.text}'")
    else:
        logging.error(f"Бот не смог отправить сообщение: '{message}'")


def get_api_answer(current_timestamp):
    """Получаем ответ от API."""
    timestamp = current_timestamp or int(time.time())
    params = {"from_date": timestamp}

    api_response = requests.get(ENDPOINT, headers=HEADERS, params=params)

    if api_response.status_code != HTTPStatus.OK:
        raise RuntimeError(
            f"Эндпойнт недоступен. Код ответа API: {api_response.status_code}"
        )
    response = api_response.json()
    return response


def check_response(response):
    """Проверяем, что ответ от API соответствует ожидаемому."""
    if response and not isinstance(response, dict):
        if isinstance(response[0], dict):
            response = response[0]
    if (
        response
        and (
            "homeworks" in response.keys()
            and "current_date" in response.keys()
        )
        and isinstance(response["homeworks"], list)
    ):
        return response["homeworks"]
    else:
        message = "Ответ от API не соответствует ожидаемому."
        raise RuntimeError(message)


def parse_status(homework):
    """Превращаем код статуса в готовое сообщение."""
    homework_name = homework["homework_name"]
    homework_status = homework["status"]

    verdict = HOMEWORK_STATUSES[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем, что все необходимые токены существуют."""
    return (
        bool(PRACTICUM_TOKEN)
        and bool(TELEGRAM_TOKEN)
        and bool(TELEGRAM_CHAT_ID)
    )


def main():
    """Основная логика работы бота."""
    logging.basicConfig(
        stream=stdout,
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    if not check_tokens():
        message = (
            "Отсутствуют необходимые переменные окружения!"
            "Программа принудительно остановлена."
        )
        logging.critical(message)
        raise RuntimeError(message)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_error = ""
    last_statuses = {}

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                for homework in homeworks:
                    status = parse_status(homework)
                    homework_name = homework["homework_name"]
                    last_status = last_statuses.get(homework["id"])
                    if status != last_status:
                        send_message(bot, status)
                    else:
                        logging.debug(
                            f"Статус работы {homework_name} не изменился"
                        )
                    last_statuses[homework["id"]] = status
            else:
                logging.debug("Нет заданий для проверки.")

            current_timestamp = response["current_date"]
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            logging.error(message)
            if message != last_error:
                send_message(bot, message)
                last_error = message
            time.sleep(RETRY_TIME)
        else:
            ...


if __name__ == "__main__":
    main()
