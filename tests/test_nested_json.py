import unittest
from copy import deepcopy

from parameterized import parameterized

from flask_request_validator.exceptions import *
from flask_request_validator import JsonParam, Enum, CompositeRule, Min, Max, IsEmail, Number, MinLength


class TestJsonParam(unittest.TestCase):
    LIST_SCHEMA = JsonParam(
        {
            'person': JsonParam(
                {
                    'info': JsonParam({
                        'contacts': JsonParam({
                            'phones': JsonParam([Enum('+375', '+49')], as_list=True),
                            'networks': JsonParam(
                                {'name': [Enum('facebook', 'telegram')]},
                                as_list=True,
                            ),
                            'emails': JsonParam([IsEmail()], as_list=True),
                            'addresses': JsonParam({'street': []},  required=False),
                        }),
                    }),
                },
            ),
        },
    )

    DICT_SCHEMA = JsonParam(
        {
            'street': CompositeRule(Enum('Jakuba Kolasa')),
            'meta': JsonParam(
                {
                    'description': JsonParam({
                        'color': [Enum('green', 'yellow', 'blue')],
                    }, ),
                    'buildings': JsonParam({
                        'warehouses': JsonParam({
                            'small': JsonParam({
                                'count': CompositeRule(Min(0), Max(99)),
                            }),
                            'large': [Min(1), Max(10)]
                        }),
                    }),
                    'not_required': JsonParam({'text': []}, required=False),
                },
            ),
        },
    )

    @parameterized.expand([
        # invalid
        (
            DICT_SCHEMA,
            {
                'street': 'Rampische',
                'meta': {'buildings': {'warehouses': {'small': {'count': 100, }, 'large': 0, }, }, },
            },
            [
                [
                    ['root', 'meta', 'buildings', 'warehouses', 'small'],
                    {'count': [ValueMaxError]},
                ],
                [
                    ['root', 'meta', 'buildings', 'warehouses'],
                    {'large': [ValueMinError]},
                ],
                [
                    ['root', 'meta'],
                    {'description': RequiredJsonKeyError},
                ],
                [
                    ['root'],
                    {'street': [ValueEnumError], },
                ],
            ],
        ),
        # valid
        (
            DICT_SCHEMA,
            {
                'country': 'Belarus',
                'city': 'Minsk',
                'street': 'Jakuba Kolasa',
                'meta': {
                    'buildings': {
                        'warehouses': {
                            'small': {'count': 99, },
                            'large': 1,
                        },
                    },
                    'description': {
                        'color': 'green',
                    },
                },
            },
            {},
        )
    ])
    def test_dict(self, param: JsonParam, data, exp):
        value, errors = param.validate(data)
        for ix, json_error in enumerate(errors):  # type: list, JsonError
            self.assertTrue(isinstance(json_error, JsonError))
            exp_depth, epx_errors_map = exp[ix]  # type: list, dict
            self.assertListEqual(json_error.depth, exp_depth)
            for key, error in json_error.errors.items():
                if isinstance(error, RulesError):
                    self.assertEqual(len(error.errors), len(epx_errors_map))
                    for ix_rule, rule_err in enumerate(error.errors):
                        self.assertTrue(isinstance(rule_err, epx_errors_map[key][0]))
                else:
                    self.assertTrue(isinstance(error, epx_errors_map[key]))

    @parameterized.expand([
        # invalid
        (
            LIST_SCHEMA,
            {
                'person': {
                    'info': {
                        'contacts': {
                            'phones': [
                                '+375',
                                '+49',
                                {'code': '+420'},
                                {'code': '+10000'}
                            ],
                            'emails': [{'work': 'bad_type1'}, {'work': 'bad_type2'}, 'bad_mail'],
                            'networks': [
                                {'name': 'facebook'},
                                {'name': 'insta'},
                                {'name': 'linkedin'},
                            ],
                        },
                    },
                },
            },
            [
                [
                    ['root', 'person', 'info', 'contacts', 'phones'],
                    {
                        2: JsonListItemTypeError,
                        3: JsonListItemTypeError,
                    },
                ],
                [
                    ['root', 'person', 'info', 'contacts', 'networks'],
                    {
                        1: {'name': [ValueEnumError], },
                        2: {'name': [ValueEnumError], },
                    },
                ],
                [
                    ['root', 'person', 'info', 'contacts', 'emails'],
                    {
                        0: JsonListItemTypeError,
                        1: JsonListItemTypeError,
                        2: [ValueEmailError],
                    },
                ],
            ],
        ),
        # valid
        (
            LIST_SCHEMA,
            {
                'person': {
                    'info': {
                        'contacts': {
                            'phones': ['+375', '+49'],
                            'networks': [
                                {'name': 'facebook'},
                                {'name': 'telegram'},
                                {'name': 'telegram'},
                                {'name': 'facebook'},
                            ],
                            'emails': ['test@gmail.com'],
                        },
                    },
                },
            },
            [],
        ),
    ])
    def test_list(self, param: JsonParam, data, exp):
        value, errors = param.validate(data)
        self.assertEqual(len(exp), len(errors))
        for err_ix, json_er in enumerate(errors):  # type: int, JsonError
            exp_err = exp[err_ix]
            exp_rule_err = exp_err[1]
            self.assertListEqual(json_er.depth, exp_err[0])
            self.assertEqual(len(exp_err[1]), len(json_er.errors))
            for rules_ix, rules_err in exp_rule_err.items():
                json_rules = json_er.errors[rules_ix]  # type: dict or list or RulesError
                if isinstance(exp_rule_err[rules_ix], list):
                    self.assertTrue(isinstance(json_rules, RulesError))
                    for k, rule_err in enumerate(json_rules.errors):
                        self.assertTrue(isinstance(rule_err, exp_rule_err[rules_ix][k]))
                else:
                    if isinstance(rules_err, dict):
                        self.assertTrue(len(json_rules), len(rules_err))
                    else:
                        # RulesError
                        self.assertTrue(isinstance(json_er.errors[rules_ix], rules_err))

    @parameterized.expand([
        (
            [
                {'age': 10, 'name': 'test'},
                {'age': 20, 'name': 'test2'},
                {'age': 30, 'name': 'test3'},
            ],
        ),
        (
            [
                {'age': 10, 'name': 'test', 'tags': [{'name': 'green'}, {'name': 'light'}]},
                {'age': 20, 'name': 'test2'},
                {'age': 30, 'name': 'test3', 'tags': [{'name': 'cat'}, {'name': 'dog'}]},
            ],
        ),
    ])
    def test_root_list_valid(self, value):
        param = JsonParam({
            'age': [Number()],
            'name': [MinLength(1), ],
            'tags': JsonParam({'name': [MinLength(1)]}, required=False, as_list=True)
        }, as_list=True)

        valid_value, errors = param.validate(deepcopy(value))
        self.assertListEqual(value, valid_value)
        self.assertEqual(0, len(errors))

    def test_root_list_invalid(self):
        param = JsonParam({
            'age': [Number()],
            'name': [MinLength(1), ],
            'tags': JsonParam({'name': [MinLength(1)]}, required=False, as_list=True)
        }, as_list=True)
        # invalid values
        _, errors = param.validate([
            {'age': 'ab', 'name': 'test'},
            {'age': 'c', 'name': ''},
            {'age': 15, 'name': 'good'},
        ])

        self.assertEqual(1, len(errors))
        self.assertTrue(isinstance(errors[0], JsonError))
        error = errors[0]
        self.assertListEqual(['root'], error.depth)
        self.assertTrue(2, len(error.errors))
        self.assertTrue(error.errors[0], 1)
        self.assertTrue(error.errors[1], 2)

        self.assertTrue(isinstance(error.errors[0]['age'].errors[0], NumberError))
        self.assertTrue(isinstance(error.errors[1]['age'].errors[0], NumberError))
        self.assertTrue(isinstance(error.errors[1]['name'].errors[0], ValueMinLengthError))
        # invalid type - dict instead list
        _, errors = param.validate({'age': 18, 'name': 'test'})
        self.assertEqual(1, len(errors))
        self.assertListEqual(['root'], errors[0].depth)
        self.assertTrue(isinstance(errors[0], JsonListExpectedError))
        # invalid type - nested string instead list
        _, errors = param.validate([
            {'age': 27, 'name': 'test'},
            {'age': 15, 'name': 'good', 'tags': 'bad_type'},
        ])

        self.assertEqual(1, len(errors))
        self.assertListEqual(['root', 'tags'], errors[0].depth)
        self.assertTrue(isinstance(errors[0], JsonListExpectedError))
