#!/usr/bin/env python
# -*- coding: utf-8 -*-

import abc
import json
import datetime
import logging
import hashlib
import uuid
import re
from optparse import OptionParser
from http.server import HTTPServer, BaseHTTPRequestHandler

import scoring

SALT = "Otus"
ADMIN_LOGIN = "admin"
ADMIN_SALT = "42"
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
ERRORS = {
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}


class InvalidValue(Exception):
    """ Ревалидное значение поля """


class Field(abc.ABC):
    def __init__(self, required=True, nullable=True):
        self.required = required  # True - обязательное поле
        self.nullable = nullable  # True - может быть пустым

    def __set_name__(self, owner, field):
        self.field = field

    def __set__(self, instance, value):
        if value is None and self.required:
            raise InvalidValue(f'Поле {self.field} обязательно, но значение не передано')
        if not value and not self.nullable:
            raise InvalidValue(f'Значение поля {self.field} обязательно')
        value = self.validate(value)
        instance.__dict__[self.field] = value

    @abc.abstractmethod
    def validate(self, value):
        """Возвращает проверенное значение или возбуждает исключение ValueError"""


class CharField(Field):
    def validate(self, value):
        if value and not isinstance(value, str):
            raise InvalidValue(f'Поле {self.field} должно быть строкой')
        return value


class ArgumentsField(Field):
    def validate(self, value):
        if value and not isinstance(value, dict):
            raise InvalidValue(f'Поле {self.field} должно быть словарем')
        return value


class EmailField(CharField):
    def validate(self, value):
        if value and not re.match('\S+@\S.\S', value):
            raise InvalidValue(f'Значение поля {self.field} должно быть email')
        return value


class PhoneField(Field):
    def validate(self, value):
        if value and not isinstance(value, (str, int)):
            raise InvalidValue(f'Значение поля {self.field} должно быть строкой или числом')
        if value and not re.match('^7\d{10}$', str(value)):
            raise InvalidValue(f'Значение поля {self.field} должно быть одинадцатизначное число начинающееся с 7')
        return value


class DateField(Field):
    def validate(self, value):
        if value and not isinstance(value, str):
            raise InvalidValue(f'Значение поля {self.field} должно быть строкой')
        if value and not re.match('^(0[1-9]|[1,2][0-9]|3[0,1])\.(0[1-9]|1[0-2])\.\d{4}$', value):
            raise InvalidValue(f'Значение поля {self.field} должно быть в формате "ДД.ММ.ГГГГ"')
        return value


class BirthDayField(Field):
    def validate(self, value):
        if value and not isinstance(value, str):
            raise InvalidValue(f'Значение поля {self.field} должно быть строкой')
        if value and not re.match('^(0[1-9]|[1,2][0-9]|3[0,1])\.(0[1-9]|1[0-2])\.(19[5-9][0-9]|20[0-1][0-9]|2020)$', value):
            raise InvalidValue(f'Значение года в поле {self.field} должен быть не менее 1950')
        return value


class GenderField(Field):
    def validate(self, value):
        if value and not isinstance(value, int):
            raise InvalidValue(f'Значение поля {self.field} должно быть числом')
        if value and value not in [UNKNOWN, MALE, FEMALE]:
            raise InvalidValue(f'Значение поля {self.field} должно быть числом: {UNKNOWN}, {MALE}, {FEMALE}')
        return value


class ClientIDsField(Field):
    def validate(self, value):
        if value and not isinstance(value, (list, tuple)):
            raise InvalidValue(f'Поле {self.field} должно быть последовательностью')
        if not all(isinstance(i, int) for i in value):
            raise InvalidValue(f'Элементы поля {self.field} должны быть числами')
        return value


class ClientMeta(type):
    def __new__(mcs, name, bases, attr_dict):
        fields = []
        for key, value in attr_dict.items():
            if isinstance(value, property):
                continue
            if key.startswith('__'):
                continue
            if hasattr(value, '__call__'):
                continue
            fields.append(key)
        attr_dict['fields'] = fields
        return super(ClientMeta, mcs).__new__(mcs, name, bases, attr_dict)


class ClientsInterestsRequest(metaclass=ClientMeta):
    client_ids = ClientIDsField(required=True, nullable=False)
    date = DateField(required=False, nullable=True)

    def __init__(self, **kwargs):
        for field in self.fields:
            setattr(self, field, kwargs.pop(field, None))

    def get_context(self):
        return len(self.client_ids)


class OnlineScoreRequest(metaclass=ClientMeta):
    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    phone = PhoneField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)

    def __init__(self, store, **kwargs):
        self.store = store
        for field in self.fields:
            setattr(self, field, kwargs.pop(field, None))

    def get_context(self):
        context = []
        for field in self.fields:
            if getattr(self, field, None) is not None:
                context.append(field)
        return context

    def validation_field_request(self):
        if not (self.phone is None or self.email is None):
            return
        elif not (self.first_name is None or self.last_name is None):
            return
        elif not (self.gender is None or self.birthday is None):
            return
        else:
            raise InvalidValue('Необходимо передать минимум два поля: phone и email, first_name и last_name, gender и birthday')

    def get_scoring(self):
        return scoring.get_score(self.store, *[getattr(self, field, None) for field in self.fields])


class MethodRequest(metaclass=ClientMeta):
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    def __init__(self, **kwargs):
        for field in self.fields:
            setattr(self, field, kwargs.pop(field, None))

    @property
    def is_admin(self):
        return self.login == ADMIN_LOGIN


def check_auth(request):
    if request.is_admin:
        digest = hashlib.sha512((datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT).encode('utf-8')).hexdigest()
    else:
        digest = hashlib.sha512((request.account + request.login + SALT).encode('utf-8')).hexdigest()
    if digest == request.token:
        return True
    return False


def method_handler_online_score(obj_request, request, ctx, store):
    try:
        logging.info('argument validation online_score method')
        response = OnlineScoreRequest(store, **request['body']['arguments'])
        response.validation_field_request()
        ctx['has'] = response.get_context()
        score = 42 if obj_request.is_admin else response.get_scoring()
        return {'code': OK, 'score': score}, OK
    except (TypeError, ValueError, InvalidValue) as e:
        logging.exception("INVALID_REQUEST - ClientsInterestsRequest %s" % e)
        return str(e), INVALID_REQUEST


def method_handler_clients_interests(obj_request, request, ctx, store):
    try:
        logging.info('argument validation clients_interests method')
        response = ClientsInterestsRequest(**request['body']['arguments'])
        ctx['nclients'] = response.get_context()
        return {key: scoring.get_interests(store, key) for key in response.client_ids}, OK
    except (TypeError, ValueError, InvalidValue) as e:
        logging.exception("INVALID_REQUEST - ClientsInterestsRequest %s" % e)
        return str(e), INVALID_REQUEST


def method_handler(request, ctx, store=None):
    try:
        logging.info('Request validation')
        obj_request = MethodRequest(**request['body'])
    except (TypeError, ValueError, AttributeError, InvalidValue) as e:
        logging.exception("INVALID_REQUEST - MethodRequest %s" % e)
        return str(e), INVALID_REQUEST
    if not check_auth(obj_request):
        logging.error('Authentication failed')
        return ERRORS[FORBIDDEN], FORBIDDEN

    if obj_request.method == 'online_score':
        return method_handler_online_score(obj_request, request, ctx, store)

    if obj_request.method == 'clients_interests':
        return method_handler_clients_interests(obj_request, request, ctx, store)


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {
        "method": method_handler
    }
    store = None

    def get_request_id(self, headers):
        return headers.get('HTTP_X_REQUEST_ID', uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        request = None
        try:
            k = self.headers['Content-Length']
            data_string = self.rfile.read(int(k))
            request = json.loads(data_string)
        except:
            code = BAD_REQUEST

        if request:
            path = self.path.strip("/")
            logging.info("%s: %s %s" % (self.path, data_string, context["request_id"]))
            if path in self.router:
                try:
                    response, code = self.router[path]({"body": request, "headers": self.headers}, context, self.store)
                    print(response, code)
                except Exception as e:
                    logging.exception(f"Unexpected error: {e}")
                    code = INTERNAL_ERROR
            else:
                code = NOT_FOUND

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {"error": response or ERRORS.get(code, "Unknown Error"), "code": code}
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r).encode('utf-8'))
        return


if __name__ == "__main__":
    op = OptionParser()
    op.add_option("-p", "--port", action="store", type=int, default=8080)
    op.add_option("-l", "--log", action="store", default=None)
    (opts, args) = op.parse_args()
    logging.basicConfig(filename=opts.log, level=logging.INFO,
                        format='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d %H:%M:%S')
    server = HTTPServer(("localhost", opts.port), MainHTTPHandler)
    logging.info("Starting server at %s" % opts.port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
