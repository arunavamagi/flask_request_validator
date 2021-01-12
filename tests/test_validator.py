from unittest import TestCase
from urllib.parse import urlencode

import flask
from flask_restful import Api
from parameterized import parameterized

from flask_request_validator import GET, Param, ValidRequest, validate_params
from flask_request_validator.rules import *
from flask_request_validator.validator import FORM, HEADER, PATH

_app = flask.Flask(__name__)
_test_api = Api(_app, '/v1')

_app.testing = True
_VALID_HEADERS = {
    'Authorization': 'Bearer token',
    'Custom header': 'custom value',
}


@_app.route('/form/<string:key>/<string:uuid>', methods=['POST'])
@validate_params(
    Param('Authorization', HEADER, str, rules=[Enum('Bearer token')]),
    Param('Custom header', HEADER, str, rules=[Enum('custom value')]),
    Param('key', PATH, str, rules=[Enum('key1', 'key2')]),
    Param('uuid', PATH, str, rules=CompositeRule(Pattern(r'^[a-z-_.]{8,10}$'), MinLength(6))),
    Param('sure', GET, bool, True),
    Param('music', GET, list, True),
    Param('cities', GET, dict, True),
    Param('price', GET, float, True),
    Param('cost', GET, int, True),
    Param('default1', GET, int, False, 10),
    Param('flag', FORM, bool, True),
    Param('bands', FORM, list, True),
    Param('countries', FORM, dict, True),
    Param('number', FORM, float, True),
    Param('count', FORM, int, True),
    Param('default2', FORM, int, False, 20),
)
def route_form(valid: ValidRequest, key: str, uuid: str):
    return flask.jsonify({
        FORM: valid.get_form(),
        GET: valid.get_params(),
        PATH: valid.get_path_params(),
    })


class TestRoutes(TestCase):
    @parameterized.expand([
        # empty
        (
            {},
            '/form/bad_key/bad_uid',
            {},
            {
                GET: {
                    'sure': RequiredValueError,
                    'music': RequiredValueError,
                    'cities': RequiredValueError,
                    'price': RequiredValueError,
                    'cost': RequiredValueError,
                },
                PATH: {
                    'key': [RulesError, [ValueEnumError]],
                    'uuid': [RulesError, [ValuePatterError, ValueMinLengthError]],
                },
                FORM: {
                    'flag': RequiredValueError,
                    'bands': RequiredValueError,
                    'countries': RequiredValueError,
                    'number': RequiredValueError,
                    'count': RequiredValueError,
                },
            },
            {},
        ),
        # wrong types
        (
            {
                'sure': 'bad_bool',
                'cities': 'wrong_dict',
                'price': 'string',
                'cost': 'string',
                'music': None,
            },
            '/form/key1/qwerty1234',
            {
                'flag': 'bad_bool',
                'countries': 'wrong_dict',
                'number': 'string',
                'count': 'string',
                'bands': None,
            },
            {
                GET: {
                    'price': TypeConversionError,
                    'cost': TypeConversionError,
                },
                FORM: {
                    'bands': TypeConversionError,
                    'number': TypeConversionError,
                    'count': TypeConversionError,
                },
            },
            {},
        ),
        # valid
        (
            {
                'sure': '1',
                'cities': 'Germany:Dresden,Belarus:Grodno',
                'price': 1.01,
                'cost': 2,
                'music': 'sigur ros,yndi halda',
            },
            '/form/key1/test_test',
            {
                'flag': 'False',
                'countries': 'Belarus:Minsk,Germany:Berlin',
                'number': 2.03,
                'count': 3,
                'bands': 'mono,calm blue sea',
            },
            {},
            {
                FORM: {
                    'bands': ['mono', 'calm blue sea'],
                    'count': 3,
                    'countries': {'Belarus': 'Minsk', 'Germany': 'Berlin'},
                    'default2': 20,
                    'flag': False,
                    'number': 2.03,
                },
                GET: {
                    'cities': {'Germany': 'Dresden', 'Belarus': 'Grodno'},
                    'cost': 2,
                    'default1': 10,
                    'music': ['sigur ros', 'yndi halda'],
                    'price': 1.01,
                    'sure': True,
                },
                PATH: {'key': 'key1', 'uuid': 'test_test'},
            }
        ),
    ])
    def test_form_with_headers(self, get, route, form, exp, response):
        with _app.test_client() as client:
            try:
                result = client.post(
                    route + '?' + urlencode(get, doseq=True),
                    data=form,
                    headers=_VALID_HEADERS,
                ).json
            except InvalidRequestError as e:
                for k, exception in e.errors.items():
                    if isinstance(exception, RulesError):
                        for rule_ix in range(len(exception.errors)):
                            self.assertTrue(isinstance(exception.errors[rule_ix], exp[k][rule_ix]))
                return
        self.assertEqual(response, result)

    @parameterized.expand([
        # invalid
        (
            {},
            {
                'Authorization': RequiredValueError,
                'Custom header': RequiredValueError,
            },
        ),
        (
            {
                'Authorization': 'Bearer token',
            },
            {
                'Custom header': RequiredValueError,
            },
        ),
        (
            {
                'Custom header': 'custom value',
            },
            {
                'Authorization': RequiredValueError,
            },
        ),
        # valid headers
        (_VALID_HEADERS, {}, ),
    ])
    def test_from_without_headers(self, headers, exp):
        with _app.test_client() as client:
            try:
                client.post('/form/key1/test_test', headers=headers)
            except InvalidHeadersError as e:
                self.assertEqual(len(exp), len(e.errors))
                for k, err in e.errors.items():
                    self.assertTrue(isinstance(err, exp[k]))
            except InvalidRequestError:
                return


class TestParam(TestCase):
    @parameterized.expand([
        # param_type
        (GET, None, False, None, None),
        (PATH, None, True, None, None),
        (FORM, None, False, None, None),
        (FORM, None, True, None, None),
        (HEADER, None, False, None, None),
        ('undefined', None, True, None, True),
        # value_type
        (FORM, str, False, None, None),
        (FORM, bool, True, None, None),
        (FORM, int, False, None, None),
        (FORM, float, True, None, None),
        (GET, dict, False, None, None),
        (GET, list, True, None, None),
        (GET, object, False, None, True),
        (GET, 'bad_type', True, None, True),
        # required
        (FORM, str, True, '1', True),
        (FORM, list, True, lambda x: [1, 2, 3], True),
    ])
    def test_init_wrong_usage(self, param_type, value_type, required, default, err):
        if err:
            self.assertRaises(WrongUsageError, Param, param_type, value_type, required, default)
            return
        Param('name', param_type, value_type, required, default, [])

    @parameterized.expand([
        # GET
        (Param('test', GET, int), 1, '1'),
        (Param('test', GET, bool), True, 'true'),
        (Param('test', GET, bool), True, 'True'),
        (Param('test', GET, bool), False, '0'),
        (Param('test', GET, bool), False, 'false'),
        (Param('test', GET, bool), False, 'False'),
        (Param('test', GET, list), ['Minsk', 'Prague', 'Berlin'], 'Minsk, Prague, Berlin'),
        (
            Param('test', GET, dict),
            {'country': 'Belarus', 'capital': 'Minsk'},
            'country: Belarus, capital: Minsk',
        ),
        # FORM
        (Param('test', FORM, int), 1, '1'),
        (Param('test', FORM, list), ['Minsk', 'Prague', 'Berlin'], 'Minsk, Prague, Berlin'),
        (
            Param('test', FORM, dict),
            {'country': 'Belarus', 'capital': 'Minsk'},
            'country: Belarus, capital: Minsk',
        ),
        (Param('test', FORM, bool), True, 'true'),
        (Param('test', FORM, bool), True, 'True'),
        (Param('test', FORM, bool), False, '0'),
        (Param('test', FORM, bool), False, 'false'),
        (Param('test', FORM, bool), False, 'False'),
    ])
    def test_value_to_type(self, param, expected, value):
        self.assertEqual(param.value_to_type(value), expected)


# class TestNestedJson(TestCase):
#
#     def test_nested_json(self):
#         with app.test_client() as client:
#             client.post(
#                 '/nested_json',
#                 data=json.dumps({
#                     'country': 'Germany',
#                     'city': 'Dresden',
#                     'street': 'Rampische',
#                     'meta': {
#                         'buildings': {
#                             'warehouses': {
#                                 'small': {'count': 100, },
#                                 'large': 0,
#                             },
#                         },
#                     },
#                 }),
#                 content_type='application/json'
#             )
