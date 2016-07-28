#!/usr/bin/env python
# -*- coding: utf-8 -*-


def test_build_definitions_example(swagger_parser, pet_definition_example):
    # Test definitions_example
    swagger_parser.build_definitions_example()
    assert len(swagger_parser.definitions_example) == 5
    assert swagger_parser.definitions_example['Pet'] == pet_definition_example

    # Test wrong definition
    swagger_parser.specification['definitions']['Pet']['properties']['category']['$ref'] = '#/definitions/Error'
    del swagger_parser.definitions_example['Pet']
    assert not swagger_parser.build_one_definition_example('Pet')

    # Test wrong def name
    assert not swagger_parser.build_one_definition_example('Error')


def test_check_type(swagger_parser):
    # Test int
    assert swagger_parser.check_type(int(5), 'integer')
    assert swagger_parser.check_type(int(5), 'number')
    assert swagger_parser.check_type('5', 'integer')
    assert not swagger_parser.check_type(int(5), 'string')
    assert not swagger_parser.check_type(int(5), 'boolean')

    # Test float
    assert swagger_parser.check_type(5.5, 'number')
    assert not swagger_parser.check_type(5.5, 'string')
    assert not swagger_parser.check_type(5.5, 'boolean')

    # Test string
    assert not swagger_parser.check_type('test', 'integer')
    assert not swagger_parser.check_type('test', 'number')
    assert swagger_parser.check_type('test', 'string')
    assert not swagger_parser.check_type('test', 'boolean')

    # Test boolean
    assert not swagger_parser.check_type(False, 'number')
    assert not swagger_parser.check_type(False, 'string')
    assert swagger_parser.check_type(False, 'boolean')

    # Test other
    assert not swagger_parser.check_type(swagger_parser, 'string')


def test_get_example_from_prop_spec(swagger_parser):
    prop_spec = {}

    # Primitive types
    prop_spec['type'] = 'integer'
    assert swagger_parser.get_example_from_prop_spec(prop_spec) == 42
    prop_spec['type'] = 'number'
    assert swagger_parser.get_example_from_prop_spec(prop_spec) == 5.5
    prop_spec['type'] = 'string'
    assert swagger_parser.get_example_from_prop_spec(prop_spec) == 'string'
    prop_spec['type'] = 'boolean'
    assert not swagger_parser.get_example_from_prop_spec(prop_spec)

    # Array
    prop_spec['type'] = 'array'
    prop_spec['items'] = {}

    # Primitive types
    prop_spec['items']['type'] = 'integer'
    assert swagger_parser.get_example_from_prop_spec(prop_spec) == [42, 24]
    prop_spec['items']['type'] = 'number'
    assert swagger_parser.get_example_from_prop_spec(prop_spec) == [5.5, 5.5]
    prop_spec['items']['type'] = 'string'
    assert swagger_parser.get_example_from_prop_spec(prop_spec) == ['string', 'string2']
    prop_spec['items']['type'] = 'boolean'
    assert swagger_parser.get_example_from_prop_spec(prop_spec) == [False, True]

    # definition
    del prop_spec['items']['type']
    prop_spec['items']['$ref'] = '#/definitions/Tag'
    assert swagger_parser.get_example_from_prop_spec(prop_spec) == [{'id': 42, 'name': 'string'}]


def test_get_dict_definition(swagger_parser, pet_definition_example):
    assert swagger_parser.get_dict_definition(pet_definition_example) == 'Pet'
    assert swagger_parser.get_dict_definition({'error': 'error'}) is None


def test_validate_definition(swagger_parser, pet_definition_example):
    # Check good
    assert swagger_parser.validate_definition('Pet', pet_definition_example)

    # Check missing required
    del pet_definition_example['name']
    assert not swagger_parser.validate_definition('Pet', pet_definition_example)

    # Check extra arg
    pet_definition_example['name'] = 'string'
    pet_definition_example['extra'] = 'extra'
    assert not swagger_parser.validate_definition('Pet', pet_definition_example)

    # Check wrong type
    del pet_definition_example['extra']
    pet_definition_example['name'] = 2
    assert not swagger_parser.validate_definition('Pet', pet_definition_example)


def test_get_paths_data(swagger_parser, path_data_example):
    swagger_parser.get_paths_data()
    assert len(swagger_parser.paths) == 12
    assert swagger_parser.paths['/v2/pets'] == path_data_example
    pet_id_param = {
        'name': 'petId',
        'in': 'path',
        'pattern': '^[a-zA-Z0-9-]+$',
        'required': True,
        'type': 'string',
        'description': "Pet's Unique identifier",
    }
    assert swagger_parser.paths['/v2/pets/{petId}']['get'] == \
        {'responses': {'200': {'description': u'successful µ-øperätioñ',
                               'schema': {'x-scope': [''], '$ref': '#/definitions/Pet'}},
                       '404': {'description': 'Pet not found'},
                       '400': {'description': 'Invalid ID supplied'}},
         'parameters': {'petId': pet_id_param}}
    assert swagger_parser.paths['/v2/pets/{petId}']['post']['parameters']['petId'] == pet_id_param
    assert swagger_parser.paths['/v2/pets/{petId}']['delete']['parameters']['petId'] == pet_id_param


def test_get_definition_name_from_ref(swagger_parser):
    assert swagger_parser.get_definition_name_from_ref('#/definitions/Pet') == 'Pet'


def test_get_path_spec(swagger_parser):
    assert swagger_parser.get_path_spec('/v2/pets')[0] == '/v2/pets'
    assert swagger_parser.get_path_spec('/v2/users/createWithList')[0] == '/v2/users/createWithList'
    assert swagger_parser.get_path_spec('/v2/stores/order/1253')[0] == '/v2/stores/order/{orderId}'
    assert swagger_parser.get_path_spec('/v2/stores/order/1253/123')[0] is None
    assert swagger_parser.get_path_spec('/v2/error')[0] is None


def test_validate_request(swagger_parser, pet_definition_example):
    assert not swagger_parser.validate_request('error', 'get')
    assert not swagger_parser.validate_request('/v2/pets', 'error')
    assert not swagger_parser.validate_request('/v2/pets', 'post', body={})

    assert swagger_parser.validate_request('/v2/pets', 'post', body=pet_definition_example)

    assert not swagger_parser.validate_request('/v2/pets/findByTags', 'get', query={'tags': 'string'})
    assert swagger_parser.validate_request('/v2/pets/findByTags', 'get', query={'tags': ['string']})


def test_get_request_data(swagger_parser, pet_definition_example):
    assert swagger_parser.get_request_data('error', 'get') == {400: ''}
    assert swagger_parser.get_request_data('/v2/pets/123', 'get') == {200: pet_definition_example, 400: '', 404: ''}
    assert swagger_parser.get_request_data('/v2/pets/123', 'error') == {400: ''}


def test_get_send_request_correct_body(swagger_parser, pet_definition_example):
    assert swagger_parser.get_send_request_correct_body('/v2/pets', 'post') == pet_definition_example
    assert swagger_parser.get_send_request_correct_body('/v2/pets/findByStatus', 'get') is None
    assert swagger_parser.get_send_request_correct_body('/v2/users/username', 'put') == 'string'

def test_array_definitions(swagger_array_parser):
    swagger_array_parser.build_definitions_example()

    stringArray = swagger_array_parser.definitions_example['StringArray']
    widgetArray = swagger_array_parser.definitions_example['WidgetArray']
    widget = swagger_array_parser.definitions_example['Widget']

    assert isinstance(stringArray, list)
    assert stringArray[0] == 'string'

    assert isinstance(widgetArray, list)
    assert widgetArray[0] == widget
