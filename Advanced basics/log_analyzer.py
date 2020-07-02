#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys
import os
import re
import gzip
import logging
import argparse

from datetime import datetime
from collections import namedtuple, defaultdict
from string import Template


config = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "LOG_DIR": "./log",
    "LOG_DIR_CURRENT_SCRIPT": None,
    "LOG_LEVEL": "INFO",
    "PERCENT_ERRORS": 1,
    "PATTERN_NAME_LOG": "^(nginx-access-ui.log-)(?P<date>\d{8})(\.gz)?$",
    "TEMPLATE": "report.html",
    "PATTERN_RECORD_LOG": "\"(GET|POST|HEAD|PUT) (?P<url>\S+) \S+\".+ (?P<time>\d+\.\d+)$"

}


def read_conf(path, config):
    """
    Чтение файла конфигурации и перезапиь дефолтной конфигурации
    :param path: путь к файлу конфигурации
    :param config: дефолтный конфиг
    :return: config - фаил конфигурации
    """
    if os.path.isdir(path):
        file_config = os.path.join(path, 'config.conf')
    else:
        file_config = path

    if not os.path.exists(file_config):
        return config

    with open(file_config, 'r') as f:
        for line in f:
            try:
                key, value = line.split(':')
            except ValueError:
                pass

            if key == 'REPORT_SIZE':
                try:
                    config['REPORT_SIZE'] = int(value)
                except ValueError:
                    pass
            elif key == 'REPORT_DIR':
                config['REPORT_DIR'] = value.strip()
            elif key == 'LOG_DIR':
                config['LOG_DIR'] = value.strip()
            elif key == 'LOG_DIR_CURRENT_SCRIPT':
                config['LOG_DIR_CURRENT_SCRIPT'] = value.strip()
            elif key == 'LOG_LEVEL':
                config['LOG_LEVEL'] = value.strip()
            elif key == 'PERCENT_ERRORS':
                try:
                    config['PERCENT_ERRORS'] = int(value)
                except ValueError:
                    pass
    logging.info(f'Слияние данных из файла с дефолтным конфигом выполнено: {config}')
    return config


def search_last_log_file(path, pattern):
    """
        Поиск файла лога с наиболее свежей датой
        :param path: директория с файлами лога
        :param pattern:  одинаковая часть начала имени лога
        :return: namedtuple(name_file, create_date) - объект модуля collections
        """
    if not os.path.exists(path):
        logging.error('Директория с файлами лога не найдена')
        return False

    last_name = None
    last_date = None
    for file in os.listdir(path):
        parsing_obj = re.search(pattern, file)
        if not parsing_obj:
            continue
        if not last_name or last_date < parsing_obj['date']:
            last_name, last_date = parsing_obj.group(), parsing_obj['date']
    if not last_name:
        logging.error('Не найден фаил лога для анализа')
        return False
    logging.info(f'Имя лога для парсинга: {last_name}')
    Data_file = namedtuple('Data_file', 'name date')
    return Data_file(last_name, datetime.strptime(last_date, '%Y%m%d'))


def read_log(name_file, pattern):
    """
    Чтение файла лога
    :param name_file: имя файла
    :return: url и время его обработки при удачном парсинге, иначе None
    """
    open_f = gzip.open if name_file.endswith('.gz') else open
    logging.info(f'Чтение файла лога')
    with open_f(name_file, 'rb') as f:
        for line in f:
            parser_line_obj = re.search(pattern, line.decode('utf-8'))
            if parser_line_obj is None:
                yield None
            else:
                yield parser_line_obj['url'], float(parser_line_obj['time'])


def formation_report(parsed_lines, size, percent_error):
    """
    :param parsed_lines: список всех URL-ов и времени их обработки
    :param size: количество записей в отчете
    :param percent_error:
    :return: список словарей с статистическими данными по каждому URL
    """
    dict_group_queries = defaultdict(list)
    number_errors = 0
    total_entries = 0
    total_time = 0
    for line in parsed_lines:
        total_entries += 1
        if line is None:
            number_errors += 1
            continue
        dict_group_queries[line[0]].append(line[1])
        total_time += line[1]

    if number_errors / total_entries > percent_error / 100:
        logging.error(f'Превышен допустимый процент ошибок парсинга -  {number_errors * 100 / total_entries}')
        return

    report = []
    for url, time_lst in sorted(dict_group_queries.items(), key=lambda k: sum(k[1]), reverse=True)[:size]:
        count_requests = len(time_lst)
        total_request_time = sum(time_lst)
        report_field = {}
        report_field['url'] = url
        report_field['count'] = round(count_requests, 3)
        report_field['count_perc'] = round((count_requests / total_entries) * 100, 3)
        report_field['time_sum'] = round(total_request_time, 3)
        report_field['time_perc'] = round((total_request_time / total_time) * 100, 3)
        report_field['time_avg'] = round(total_request_time / count_requests, 3)
        report_field['time_max'] = round(max(time_lst), 3)
        report_field['time_med'] = round(sorted(time_lst)[count_requests // 2], 3)
        report.append(report_field)

    logging.info(f'Отчет сформирован, количество записей - {len(report)} ')
    del dict_group_queries
    return report


def write_to_file(report, to, template):
    """
    Запись данных в html фаил
    :param report: данные
    :param to: имя отчета
    :param template: шаблон отчета
    """
    logging.info(f'Запись отчета в фаил {to}')
    f = os.path.dirname(to)
    if not os.path.exists(f):
        os.makedirs(f)
    with open(template) as temp, open(to, 'w') as f:
        html = temp.read()
        logging.info(f'Шаблон отчета получен')
        f.write(Template(html).safe_substitute(table_json=report))
        logging.info(f'Фаил отчета создан - {to}')


def main(config):
    logging.info('Запуск скрипта')

    # получение данных о самом свежем файле лога
    data_file = search_last_log_file(config['LOG_DIR'], config['PATTERN_NAME_LOG'])
    if not data_file:
        sys.exit()

    # если отчет существует - завершение скрипта
    file_report = os.path.join(config['REPORT_DIR'], f'report-{data_file.date.strftime("%Y.%m.%d")}.html')
    if os.path.exists(file_report):
        logging.error(f'Фаил отчета {file_report} уже существует')
        sys.exit()

    # относительный путь к фаилу лога
    log_file = os.path.join(config['LOG_DIR'], data_file.name)

    # Формирование сообщения
    report = formation_report(read_log(log_file, config['PATTERN_RECORD_LOG']),
                              config['REPORT_SIZE'],
                              config["PERCENT_ERRORS"])
    if not report:
        sys.stdout.write('Превышено количество ошибок парсинга!')
        sys.exit()

    # имя файла отчета
    name_file_report = os.path.join(config['REPORT_DIR'], f'report-{data_file.date.strftime("%Y.%m.%d")}.html')

    # запись отчета в html фаил
    write_to_file(report, name_file_report, config['TEMPLATE'])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', dest='config', default=None)
    args = parser.parse_args()

    if not read_conf(args.config, config):
        pass
    logging.basicConfig(filename=config['LOG_DIR_CURRENT_SCRIPT'],
                        level=getattr(logging, config['LOG_LEVEL']),
                        format='[%(asctime)s] %(levelname).1s %(message)s',
                        datefmt='%Y.%m.%d %H:%M:%S')
    main(config)
