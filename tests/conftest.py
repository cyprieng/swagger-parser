# -*- coding: utf-8 -*-

import pytest

from swagger_parser import SwaggerParser


@pytest.fixture
def swagger_parser():
    return SwaggerParser('tests/swagger.yaml')


@pytest.fixture
def inline_parser():
    return SwaggerParser('tests/inline.yaml')


@pytest.fixture(scope="module",
                params=['tests/no_properties.yaml',
                        'tests/object_no_schema.yaml',
                        'tests/allof.yaml',
                        'tests/array_ref_simple.yaml',
                        'tests/null_type.yaml',
                        'tests/array_items_list.yaml',
                        'tests/type_list.yaml',
                        ])
def swagger_file_parser(request):
    return SwaggerParser(request.param)


@pytest.fixture
def pet_definition_example():
    return {
        'category': {
            'id': 42,
            'name': 'string'
        },
        'status': 'string',
        'name': 'doggie',
        'tags': [
            {
                'id': 42,
                'name': 'string'
            }
        ],
        'photoUrls': [
            'string',
            'string2'
        ],
        'id': 42
    }


@pytest.fixture
def inline_example():
    return {
        '3bd818fb7d55daf2fb8bf3354c061f9ba7f8cece39b30bdcb7e05551053ec2e8': ('/test', 'post', None)
    }


@pytest.fixture
def get_path_data():
    pet_get = {
        'description': "Pet's Unique identifier",
        'name': 'petId',
        'in': 'path',
        'pattern': '^[a-zA-Z0-9-]+$',
        'required': True,
        'type': 'string',
    }
    get_responses = {
        '200': {
            'description': u'successful \xb5-\xf8per\xe4tio\xf1',
            'schema': {
                '$ref': '#/definitions/Pet',
                'x-scope': ['']
            }
        },
        '400': {'description': 'Invalid ID supplied'},
        '404': {'description': 'Pet not found'}
    }
    expected_get_pet_path = {
        'parameters': {'petId': pet_get},
        'responses': get_responses
    }
    return expected_get_pet_path


@pytest.fixture
def post_put_path_data():
    pet_post = {
        'description': u'Pet object that needs to be added to the store (it may be a \xb5Pig or a Sm\xf8rebr\xf6d)',
        'in': 'body',
        'name': 'body',
        'required': False,
        'schema': {
            '$ref': '#/definitions/Pet',
            'x-scope': ['']
        }
    }
    pet_put = pet_post.copy()
    pet_put['description'] = 'Pet object that needs to be added to the store'
    schema_created = {
        'description': 'Created',
        'schema': {
            '$ref': '#/definitions/Pet',
            'x-scope': ['']
        }
    }
    expected_post_put_paths = {
        'post': {
            'consumes': ['application/json'],
            'parameters': {'body': pet_post},
            'responses': {
                '201': schema_created,
                '405': {'description': 'Invalid input'}
            }
        },
        'put': {
            'consumes': ['application/json'],
            'parameters': {'body': pet_put},
            'responses': {
                '200': schema_created,
                '400': {'description': 'Invalid ID supplied'},
                '404': {'description': 'Pet not found'},
                '405': {'description': 'Validation exception'}
            }
        }
    }
    return expected_post_put_paths


@pytest.fixture
def swagger_array_parser():
    return SwaggerParser('tests/swagger_arrays.yaml')
