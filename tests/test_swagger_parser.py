# -*- coding:utf-8 -*-

import pytest
import requests

from copy import deepcopy

from swagger_parser import SwaggerParser


# whatever is defined in the petstore, we should be able to parse the json
def test_validate_petstore_swagger_json():
    complete_json = requests.get("http://petstore.swagger.io/v2/swagger.json").json()
    SwaggerParser(swagger_dict=complete_json, use_example=True)
    SwaggerParser(swagger_dict=complete_json, use_example=False)


# whatever is defined in the petstore, we should be able to parse the yaml
def test_validate_petstore_swagger_yaml():
    complete_yaml = requests.get("http://petstore.swagger.io/v2/swagger.yaml").text
    SwaggerParser(swagger_yaml=complete_yaml, use_example=True)
    SwaggerParser(swagger_yaml=complete_yaml, use_example=False)


def test_inline_examples(inline_parser, inline_example):
    assert inline_parser.generated_operation == inline_example


def test_swagger_file_parser(swagger_file_parser):
    assert swagger_file_parser


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

    # Inline complex
    prop_spec = {
      'type': 'object',
      'properties': {
        'error': {
          'type': 'object',
          'properties': {
            'code': {'type': 'string'},
            'title': {'type': 'string'},
            'detail': {'type': 'string'},
          },
          'required': ['code', 'title', 'detail'],
        },
      },
      'required': ['error'],
    }
    example = swagger_parser.get_example_from_prop_spec(prop_spec)
    assert example == [{'error': {'code': 'string', 'detail': 'string', 'title': 'string'}}]


def test_get_example_from_prop_spec_with_additional_properties(swagger_parser):
    prop_spec = {
      'type': 'object',
      'properties': {
        'error': {
          'type': 'object',
          'properties': {
            'code': {'type': 'string'},
            'title': {'type': 'string'},
            'detail': {'type': 'string'},
          },
          'required': ['code', 'title', 'detail'],
        },
      },
      'required': ['error'],
    }

    # additionalProperties - $ref (complex prop_spec with required keys)
    prop_spec['additionalProperties'] = {'$ref': '#/definitions/Category'}
    example = swagger_parser.get_example_from_prop_spec(prop_spec)
    assert example == {
        'any_prop2': {'id': 42, 'name': 'string'},
        'any_prop1': {'id': 42, 'name': 'string'},
        'error': {'code': 'string', 'detail': 'string', 'title': 'string'},
    }

    # additionalProperties - string (with complex prop_spec without required keys)
    del prop_spec['required']
    prop_spec['additionalProperties'] = {'type': 'string'}
    example = swagger_parser.get_example_from_prop_spec(prop_spec)
    assert example == {
        'any_prop2': 'string',
        'any_prop1': 'string',
    }

    # additionalProperties - integer (prop spec with only additional properties)
    easy_prop_spec = {
        'type': 'object',
        'additionalProperties': {'type': 'integer', 'format': 'int64'},
    }
    example = swagger_parser.get_example_from_prop_spec(easy_prop_spec)
    assert example == {'any_prop1': 42, 'any_prop2': 42}

    # additionalProperties - dict not satisfying any definition
    #  (with complex prop_spec without required keys)
    prop_spec['additionalProperties'] = {
        'type': 'object',
        'properties': {
            'food': {'type': 'string'},
            'drink': {'type': 'number', 'format': 'double'},
            'movies': {'type': 'boolean'},
        }
    }
    example = swagger_parser.get_example_from_prop_spec(prop_spec)
    assert example == {
        'any_prop2': {'food': 'string', 'movies': False, 'drink': 5.5},
        'any_prop1': {'food': 'string', 'movies': False, 'drink': 5.5},
    }

    # additionalProperties - dict satisfying the 'Category' definition
    prop_spec['additionalProperties'] = {
        'type': 'object',
        'properties': {
            'id': {'type': 'integer', 'format': 'int64'},
            'name': {'type': 'string'},
        }
    }
    example = swagger_parser.get_example_from_prop_spec(prop_spec)
    assert example == {
        'any_prop2': {'id': 42, 'name': 'string'},
        'any_prop1': {'id': 42, 'name': 'string'},
    }


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


def test_get_paths_data(swagger_parser, post_put_path_data, get_path_data):
    swagger_parser.get_paths_data()
    assert len(swagger_parser.paths) == 13
    assert swagger_parser.paths['/v2/pets'] == post_put_path_data
    assert swagger_parser.paths['/v2/pets/{petId}']['get'] == get_path_data
    post_pet_id = swagger_parser.paths['/v2/pets/{petId}']['post']['parameters']['petId']
    delete_pet_id = swagger_parser.paths['/v2/pets/{petId}']['delete']['parameters']['petId']
    assert post_pet_id == get_path_data['parameters']['petId']
    assert delete_pet_id == get_path_data['parameters']['petId']


def test_get_definition_name_from_ref(swagger_parser):
    assert swagger_parser.get_definition_name_from_ref('#/definitions/Pet') == 'Pet'


def test_get_path_spec(swagger_parser):
    assert swagger_parser.get_path_spec('/v2/pets')[0] == '/v2/pets'
    assert swagger_parser.get_path_spec('/v2/users/createWithList')[0] == '/v2/users/createWithList'
    assert swagger_parser.get_path_spec('/v2/stores/order/1253')[0] == '/v2/stores/order/{orderId}'
    assert swagger_parser.get_path_spec('/v2/stores/order/1253/123')[0] is None
    assert swagger_parser.get_path_spec('/v2/error')[0] is None


def test_validate_request(swagger_parser, pet_definition_example):

    def _get_faulty_pet_definition_example():
        faulty_pet_definition_example = deepcopy(pet_definition_example)
        # add item to sublevel dict
        faulty_pet_definition_example['category']['foo'] = 'bar'
        # delete item from toplevel dict
        del faulty_pet_definition_example['status']
        # add item to toplevel dict
        faulty_pet_definition_example['fooo'] = 'baar'
        # change value to wrong type in toplevel dict
        faulty_pet_definition_example['id'] = 'fourtytwo'
        return faulty_pet_definition_example

    # In the given schema.yaml, the expected mime type is "json".
    # Since 'body' is not mandatory, we can send an empty json body {}, too.
    # - '' will be rejected
    # - None will be accepted
    # - Any other string body will be transformed to json and then checked
    # - {} will be accepted

    # wrong endpoint
    assert not swagger_parser.validate_request('/v2/foo', 'get')
    # empty string body (no json format, but in our schema, json is expected)
    assert not swagger_parser.validate_request('/v2/pets', 'post', body='')
    # wrong http method
    assert not swagger_parser.validate_request('/v2/pets', 'foo')
    # bad body - json, but not according to our given schema
    assert not swagger_parser.validate_request(
        '/v2/pets',
        'post',
        body=_get_faulty_pet_definition_example(),
    )
    # bad query - tags should be a list of strings, not a string
    assert not swagger_parser.validate_request('/v2/pets/findByTags', 'get', query={'tags': 'string'})

    # no body (post generally does not require a body, and in our schema, no
    #          parameters in body are required)
    # http://stackoverflow.com/questions/7323958/are-put-and-post-requests-required-expected-to-have-a-request-body
    assert swagger_parser.validate_request('/v2/pets', 'post')
    # empty body (in our schema, no parameters in body are required)
    assert swagger_parser.validate_request('/v2/pets', 'post', body={})
    # valid body
    assert swagger_parser.validate_request(
        '/v2/pets',
        'post',
        body=pet_definition_example,
    )
    # valid query
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


def test_simple_additional_property_handling(swagger_parser):
    # value of type = int
    additional_properties_1 = {'any_prop2': 42, 'any_prop1': 42}
    valid_response_1 = {'aa': 3, 'ssssssss': 1, 'Not available': 6, 'xyz': 1, 'yyy': 2}
    bad_response_1 = {'a': 1, 'b': 222, 35: '23', 'c': False}
    assert swagger_parser.validate_additional_properties(
            additional_properties_1, valid_response_1)
    assert not swagger_parser.validate_additional_properties(
            additional_properties_1, bad_response_1)

    # value of type = string
    additional_properties_2 = {'any_prop2': 'hello', 'any_prop1': 'world'}
    valid_response_2 = {'aa': '3', 'ssssssss': 'one', 'Not available': '6', 555: 'yes', 'yyy': '$$$'}
    bad_response_2 = {'a': '1', 'b': 222, 35: '23', 'c': False}
    assert swagger_parser.validate_additional_properties(additional_properties_2, valid_response_2)
    assert not swagger_parser.validate_additional_properties(additional_properties_2, bad_response_2)


def test_complex_additional_property_handling(swagger_parser):
    # value of type = object/complex
    additional_properties_3 = {
        'any_prop2': {'word': 'hello', 'number': 1},
        'any_prop1': {'word': 'world', 'number': 2},
    }
    valid_response_3 = {
        'aa': {'word': 'hi', 'number': 3},
        5555: {'word': 'one', 'number': 1},
        'Not available': {'word': 'foo', 'number': 6},
    }
    bad_response_3 = {
        'a': {'word': 1, 'number': '1'},
        'b': {'word': 'bar', 'number': 222},
        35: {'word': 'baz', 'number': '23', 'anotherone': 'gna'},
        'c': {'word': 'True', 'number': False},
    }
    assert swagger_parser.validate_additional_properties(additional_properties_3, valid_response_3)
    assert not swagger_parser.validate_additional_properties(additional_properties_3, bad_response_3)


def test_referenced_additional_property_handling(swagger_parser):
    # This example here should match 'Category' definition
    additional_properties = {
       'first_': {'id': 4, 'name': 'blub'},
       'second': {'id': 5, 'name': 'blubblub'},
    }
    valid_response = {
       'somekey_': {'id': 40, 'name': 'blub0'},
       'otherkey': {'id': 50, 'name': 'blubblub0'},
    }
    bad_response = {
       'somekey_': {'badkey': 40, 'name': 'blub0'},
       'otherkey': {'id': 'bad_value', 'name': 'blubblub0'},
       'thirdkey': {'id': 10, 'name': 'meandmyself', 'another': True},
    }
    assert swagger_parser.validate_additional_properties(additional_properties, valid_response)
    assert not swagger_parser.validate_additional_properties(additional_properties, bad_response)


@pytest.mark.skip
def test_list_additional_property_handling(swagger_parser):
    # TODO list handling in additionalProperties is not implemented yet
    additional_properties_4 = {
        'any_prop2': [{'word': 'hello', 'number': 1}, {'word': 'something', 'number': 3}],
        'any_prop1': [{'word': 'world', 'number': 2}],
    }
    valid_response_4 = {
        'aa': [{'word': 'hi', 'number': 3}, {'word': 'salut', 'number': 4}],
        5555: [{'word': 'one', 'number': 1}],
    }
    bad_response_4 = {
        'a': [{'word': 'x', 'number': 1}, {'word': 'y', 'number': 5}],
        35: [{'word': 'baz', 'number': False}],
        'c': 'a string',
        'd': {'name': 'lala', 'number': 333},
        'e': ['one', 2, True]
    }
    assert swagger_parser.validate_additional_properties(additional_properties_4, valid_response_4)
    assert not swagger_parser.validate_additional_properties(additional_properties_4, bad_response_4)
