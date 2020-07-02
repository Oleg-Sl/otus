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
# from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from weakref import WeakKeyDictionary

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


class Field:
    def __init__(self, required=True, nullable=True, field=None):
        self.required = required  # True - обязательное поле
        self.nullable = nullable  # True - может быть пустым
        self.field = field
        self.data = WeakKeyDictionary()

    def __get__(self, instance, owner):
        return self.data.get(instance)

    def __set__(self, instance, value):
        if value is None and self.required:
            raise ValueError(f'Поле {self.field} обязательно, но значение не передано')
        if not value and not self.nullable:
            raise ValueError(f'Значение поля {self.field} обязательно')

    def __delete__(self, instance):
        if self.nullable:
            raise ValueError


class CharField(Field):
    def __init__(self, **kwargs):
        super(CharField, self).__init__(**kwargs)

    def __set__(self, instance, value):
        super(CharField, self).__set__(instance, value)
        if value and not isinstance(value, str):
            raise TypeError(f'Поле {self.field} должно быть строкой')
        self.data[instance] = value


class ArgumentsField(Field):
    def __init__(self, **kwargs):
        super(ArgumentsField, self).__init__(**kwargs)

    def __set__(self, instance, value):
        super(ArgumentsField, self).__set__(instance, value)
        if value and not isinstance(value, dict):
            raise ValueError(f'Поле {self.field} должно быть словарем')
        self.data[instance] = value


class EmailField(CharField):
    def __init__(self, **kwargs):
        super(EmailField, self).__init__(**kwargs)

    def __set__(self, instance, value):
        super(CharField, self).__set__(instance, value)
        if value and not re.match('\S+@\S.\S', value):
            raise ValueError(f'Значение поля {self.field} должно быть email')
        self.data[instance] = value


class PhoneField(Field):
    def __init__(self, **kwargs):
        super(PhoneField, self).__init__(**kwargs)

    def __set__(self, instance, value):
        super(PhoneField, self).__set__(instance, value)
        if value and not isinstance(value, (str, int)):
            raise TypeError(f'Значение поля {self.field} должно быть строкой или числом')
        if value and not re.match('^7\d{10}$', str(value)):
            raise ValueError(f'Значение поля {self.field} должно быть одинадцатизначное число начинающееся с 7')
        self.data[instance] = value


class DateField(Field):
    def __init__(self, **kwargs):
        super(DateField, self).__init__(**kwargs)

    def __set__(self, instance, value):
        super(DateField, self).__set__(instance, value)
        if value and not isinstance(value, str):
            raise TypeError(f'Значение поля {self.field} должно быть строкой')
        if value and not re.match('^(0[1-9]|[1,2][0-9]|3[0,1])\.(0[1-9]|1[0-2])\.\d{4}$', value):
            raise ValueError(f'Значение поля {self.field} должно быть в формате "ДД.ММ.ГГГГ"')
        self.data[instance] = value


class BirthDayField(DateField):
    def __init__(self, **kwargs):
        super(BirthDayField, self).__init__(**kwargs)

    def __set__(self, instance, value):
        super(BirthDayField, self).__set__(instance, value)
        if value and not re.match('^(0[1-9]|[1,2][0-9]|3[0,1])\.(0[1-9]|1[0-2])\.(19[5-9][0-9]|20[0-1][0-9]|2020)$', value):
            raise ValueError(f'Значение года в поле {self.field} должен быть не менее 1950')
        self.data[instance] = value


class GenderField(Field):
    def __init__(self, **kwargs):
        super(GenderField, self).__init__(**kwargs)

    def __set__(self, instance, value):
        super(GenderField, self).__set__(instance, value)
        if value and not isinstance(value, int):
            raise TypeError(f'Значение поля {self.field} должно быть числом')
        if value and value not in [UNKNOWN, MALE, FEMALE]:
            raise ValueError(f'Значение поля {self.field} должно быть числом: {UNKNOWN}, {MALE}, {FEMALE}')
        self.data[instance] = value


class ClientIDsField(Field):
    def __init__(self, **kwargs):
        super(ClientIDsField, self).__init__(**kwargs)

    def __set__(self, instance, value):
        super(ClientIDsField, self).__set__(instance, value)
        if value and not isinstance(value, (list, tuple)):
            raise ValueError(f'Поле {self.field} должно быть последовательностью')
        if not all(isinstance(i, int) for i in value):
            raise ValueError(f'Элементы поля {self.field} должны быть числами')
        self.data[instance] = value


class ClientsInterestsRequest:
    client_ids = ClientIDsField(required=True, nullable=False, field='client_ids')
    date = DateField(required=False, nullable=True, field='date')

    def __init__(self, **kwargs):
        self.client_ids = kwargs.pop('client_ids', None)
        self.date = kwargs.pop('date', None)

    def get_context(self):
        return len(self.client_ids)
        # return {'nclients': len(self.client_ids)}


class OnlineScoreRequest:
    first_name = CharField(required=False, nullable=True, field='first_name')
    last_name = CharField(required=False, nullable=True, field='last_name')
    email = EmailField(required=False, nullable=True, field='email')
    phone = PhoneField(required=False, nullable=True, field='phone')
    birthday = BirthDayField(required=False, nullable=True, field='birthday')
    gender = GenderField(required=False, nullable=True, field='gender')

    def __init__(self, store, **kwargs):
        self.store = store
        self.first_name = kwargs.pop('first_name', None)
        self.last_name = kwargs.pop('last_name', None)
        self.email = kwargs.pop('email', None)
        self.phone = kwargs.pop('phone', None)
        self.birthday = kwargs.pop('birthday', None)
        self.gender = kwargs.pop('gender', None)

    def get_context(self):
        context = []
        if not self.first_name is None:
            context.append('first_name')
        if not self.last_name is None:
            context.append('last_name')
        if not self.email is None:
            context.append('email')
        if not self.phone is None:
            context.append('phone')
        if not self.birthday is None:
            context.append('birthday')
        if not self.gender is None:
            context.append('gender')
        return context

    def validation_field_request(self):
        if not (self.phone is None or self.email is None):
            return
        elif not (self.first_name is None or self.last_name is None):
            return
        elif not (self.gender is None or self.birthday is None):
            return
        else:
            raise ValueError('Необходимо передать минимум два поля: phone и email, first_name и last_name, gender и birthday')

    def get_scoring(self):
        return scoring.get_score(self.store, self.phone, self.email, self.birthday, self.gender, self.first_name, self.last_name)


class MethodRequest:
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    def __init__(self, **kwargs):
        self.account = kwargs.pop('account', None)
        self.login = kwargs.pop('login', None)
        self.token = kwargs.pop('token', None)
        self.arguments = kwargs.pop('arguments', None)
        self.method = kwargs.pop('method', None)

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


def method_handler(request, ctx, store=None):
    try:
        logging.info('Request validation')
        obj_request = MethodRequest(**request['body'])
    except (TypeError, ValueError, AttributeError) as e:
        logging.exception("INVALID_REQUEST - MethodRequest %s" % e)
        return {'code': INVALID_REQUEST, 'error': str(e)}, INVALID_REQUEST

    if not check_auth(obj_request):
        logging.error('Authentication failed')
        return {'code': FORBIDDEN, 'error': ERRORS[FORBIDDEN]}, FORBIDDEN

    if obj_request.method == 'online_score':
        try:
            logging.info('argument validation online_score method')
            response = OnlineScoreRequest(store, **request['body']['arguments'])
            response.validation_field_request()
            ctx['has'] = response.get_context()
            if obj_request.is_admin:
                return {'code': OK, 'score': 42}, OK
            else:
                return {'code': OK, 'score': response.get_scoring()}, OK
        except (TypeError, ValueError) as e:
            logging.exception("INVALID_REQUEST - OnlineScoreRequest %s" % e)
            return {'code': INVALID_REQUEST, 'error': str(e)}, INVALID_REQUEST

    if obj_request.method == 'clients_interests':
        try:
            logging.info('argument validation clients_interests method')
            response = ClientsInterestsRequest(**request['body']['arguments'])
            ctx['nclients'] = response.get_context()
            return {key: scoring.get_interests(store, key) for key in response.client_ids}, OK
        except (TypeError, ValueError) as e:
            logging.exception("INVALID_REQUEST - ClientsInterestsRequest %s" % e)
            return {'code': INVALID_REQUEST, 'error': str(e)}, INVALID_REQUEST


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
