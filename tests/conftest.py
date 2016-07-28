# -*- coding: utf-8 -*-
import pytest

from swagger_parser import SwaggerParser


@pytest.fixture
def swagger_parser():
    return SwaggerParser('tests/swagger.yaml')


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
def path_data_example():
    return {'put': {'responses': {
        '200': {'description': 'Created', 'schema': {'x-scope': [''],
                                                     '$ref': '#/definitions/Pet'}},
        '405': {'description': 'Validation exception'},
        '404': {'description': 'Pet not found'},
        '400': {'description': 'Invalid ID supplied'},
    }, 'parameters': {'body': {
        'required': False,
        'in': 'body',
        'description': u'Pet object that needs to be added to the store',
        'name': 'body',
        'schema': {'x-scope': [''], '$ref': '#/definitions/Pet'},
    }}}, 'post': {'responses': {'201': {'description': 'Created',
                                        'schema': {'x-scope': [''],
                                                   '$ref': '#/definitions/Pet'}},
                                '405': {'description': 'Invalid input'}},
                  'parameters': {'body': {
                      'required': False,
                      'in': 'body',
                      'description': u'Pet object that needs to be added to the store (it may be a µPig or a Smørebröd)',
                      'name': 'body',
                      'schema': {'x-scope': [''], '$ref': '#/definitions/Pet'},
                  }}}}

@pytest.fixture
def swagger_array_parser():
    return SwaggerParser('tests/swagger_arrays.yaml')
