#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys
import os
import re
import gzip
import datetime
import logging

from collections import namedtuple
from string import Template


config = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "LOG_DIR": "./log",
    "LOG_DIR_CURRENT_SCRIPT": "./log_log_analyzer",
    "PERCENT_ERRORS": 1
}


def read_param_command_line():
    """
    Чтение аргументов командной строки, получениие пути к файлу конфигурации.
    :return: 'str' or None - если путь передан возвращается этот путь, если нет - None
    """
    args = sys.argv.__iter__()
    for arg in args:
        if arg == '--config':
            try:
                path = args.__next__()
                log.info(f'Параметры команлной строки path_config = {path}')
                return path
            except StopIteration:
                log.exception(f'Параметры команлной строки не переданы или некорректны')
                return


def read_conf(path, conf_dict):
    """
    Чтение файла конфигурации и перезапиь дефолтной конфигурации
    :param path: путь к файлу конфигурации
    :param conf_dict: дефолтный конфиг
    :return: True - если фаил конфигурации существует, False - если не существует
    """
    log = logging.getLogger('app.log')
    if not os.path.exists(os.path.join(path, 'config.conf')):
        return False
    with open(os.path.join(path, os.listdir(path)[0]), 'r') as f:
        while True:
            d = f.readline().split(':')
            if not d[0]:
                break
            if d[0] == 'REPORT_SIZE':
                try:
                    conf_dict['REPORT_SIZE'] = int(d[1])
                except ValueError:
                    pass
            elif d[0] == 'REPORT_DIR':
                conf_dict['REPORT_DIR'] = d[1].strip()
            elif d[0] == 'LOG_DIR':
                conf_dict['LOG_DIR'] = d[1].strip()
    log.info(f'Слияние конфига из файла и дефолтного конфига выполнено: {config}')
    return True


def search_last_log_file(path, pattern):
    """
        Поиск файла лога с последней датой
        :param path: директория с файлами лога
        :param pattern:  одинаковая часть начала имени лога
        :return: namedtuple(name_file, create_date) - объект модуля collections
        """
    log = logging.getLogger('app.log')
    try:
        log_list = os.listdir(path)
    except FileNotFoundError:
        return False
    last_file = None
    for file in log_list[1:]:
        date = re.search('\d{8}', file)[0]
        if file.startswith(pattern) and (not last_file or last_file[1] < date):
            last_file = file, date

    if not last_file:
        return False
    log.info(f'Фаил лога для парсинга: {file}')
    Data_file = namedtuple('Data_file', 'file date')
    return Data_file(last_file[0], datetime.datetime.strptime(last_file[1], '%Y%m%d'))


def read_log(name_file):
    log = logging.getLogger('app.log')
    total = 0
    parsing_ok = 0
    flag = False
    log.info(f'Чтение файла лога')
    if name_file.endswith('.gz'):
        f = gzip.open(name_file, 'rb')
        flag = True
    else:
        f = open(name_file)

    for line in f:
        if flag:
            data_line = parsing_string_log(line.decode('utf-8').split('"'))
        else:
            data_line = parsing_string_log(line.split('"'))

        total += 1
        if data_line:
            parsing_ok += 1
            yield data_line
    log.info(f'Выполнен парсинг {total} записей файла лога')
    yield 'total', total
    yield 'error', total - parsing_ok
    f.close


def parsing_string_log(string_lst):
    """
    Функция обрабатывает строку лога "string_lst" и добавляет url в список "report_lst"
    :param string_lst: список созданный из строки
    """
    log = logging.getLogger('app.log')
    for el in string_lst:
        if el.startswith('POST') or el.startswith('GET'):
            data = el.split()[1], float(string_lst[-1])
            return data


def formation_report(parsed_lines, size, percent_error):
    """
    :param parsed_lines: список всех URL-ов и времени их обработки
    :param size: количество записей в отчете
    :param percent_error:
    :return: список словарей с статистическими данными по каждому URL
    """
    log = logging.getLogger('app.log')
    log.info(f'Формирование статистического отчета')
    d = {}
    for line in parsed_lines:
        if line[0] in d:
            d[line[0]].append(line[1])
        else:
            d[line[0]] = [line[1], ]

    total = d.pop('total')[0]
    error = d.pop('error')[0]
    if error / total > percent_error / 100:
        log.error(f'Превышен допустимый процент ошибок парсинга -  {error * 100 / total}')
        return

    report_lst = list(d.items())
    total_time = sum([sum(s[1]) for s in report_lst])
    del d

    if len(report_lst) < size:
        lst = sorted(report_lst, key=lambda report_lst: sum(report_lst[1]), reverse=True)
    else:
        lst = sorted(report_lst, key=lambda report_lst: sum(report_lst[1]), reverse=True)[:size]

    del report_lst
    report = []
    for url, time_lst in lst:
        d = {}
        d['url'] = url
        d['count'] = round(len(time_lst), 3)
        d['count_perc'] = round((d['count'] / total) * 100, 3)
        d['time_sum'] = round(sum(time_lst), 3)
        d['time_perc'] = round((sum(time_lst) / total_time) * 100, 3)
        d['time_avg'] = round(sum(time_lst) / len(time_lst), 3)
        d['time_max'] = round(max(time_lst), 3)
        d['time_med'] = round(sorted(time_lst)[len(time_lst) // 2], 3)
        report.append(d)
    log.info(f'Отчет сформирован, количество записей - {len(report)} ')
    del lst
    return report


def write_to_file(report, path, date):
    """
    Запись данных в html фаил
    :param report: данные
    :param path: директория хранения отчетов
    :param date: дата файла лога
    """
    log = logging.getLogger('app.log')
    name = os.path.join(path, f'report-{date.year}.{date.month}.{date.day}.html')
    log.info(f'Запись отчета в фаил {name}')
    if not os.path.exists(path):
        os.makedirs(path)
    with open('report.html') as f:
        html = f.read()
        log.info(f'Шаблон отчета получен')
    with open(name, 'w') as f:
        f.write(Template(html).safe_substitute(table_json=report))
        log.info(f'Фаил шаблона создан - {name}')


def main(config):
    log.info('Запуск скрипта')
    # чтение параметров командной строки
    path_to_config = read_param_command_line()

    # перезапись словаря с конфигурацией
    if path_to_config and not read_conf(path_to_config, config):
        log.error(f'Файла конфигурации "{os.path.join(path_to_config, "config.conf")}" не существует')
        sys.stderr.write('Фаил конфигурации не найден.')
        sys.exit()

    # получение данных о последнем файле лога
    data_log = search_last_log_file(config['LOG_DIR'], 'nginx-access-ui.log')
    if not data_log:
        log.error(f'Фаил лога не найден')
        sys.stdout.write('Фаил лога не найден')
        sys.exit()

    # если отчет существует - завершение скрипта
    path = os.path.join(config['REPORT_DIR'], f'report-{data_log.date.year}.{data_log.date.month}.{data_log.date.day}.html')
    if os.path.exists(path):
        log.error(f'Фаил отчета существует: {path}')
        sys.stdout.write('Отчет уже существует!')
        sys.exit()

    # путь к файлу лога
    path_to_file = os.path.join(config['LOG_DIR'], data_log.file)

    # Формирование сообщения
    report = formation_report(read_log(path_to_file), config['REPORT_SIZE'], config["PERCENT_ERRORS"])
    if not report:
        sys.stdout.write('Превышено количество ошибок парсинга!')
        sys.exit()

    # запись отчета в html фаил
    write_to_file(report, config['REPORT_DIR'], data_log.date)


def logger(config):
    """
    Создание объекта логирования
    :param config: объект конфигурации
    """
    log = logging.getLogger('app.log')
    _format = logging.Formatter(fmt='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d %H:%M:%S')

    if 'LOG_DIR_CURRENT_SCRIPT' in config:
        path_to_file = os.path.join(config['LOG_DIR_CURRENT_SCRIPT'], 'app.log')
        if not os.path.exists(config['LOG_DIR_CURRENT_SCRIPT']):
            os.makedirs(config['LOG_DIR_CURRENT_SCRIPT'])
        f = logging.FileHandler(path_to_file, encoding='utf-8')
        f.setFormatter(_format)
    else:
        f = logging.StreamHandler(sys.stdout)
        f.setFormatter(_format)

    log.addHandler(f)
    log.setLevel(logging.INFO)
    return log


if __name__ == "__main__":
    log = logger(config)
    main(config)
