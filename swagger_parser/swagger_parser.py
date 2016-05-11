# -*- coding: utf-8 -*-

import codecs
import datetime
import jinja2
import json
import re
import six
import yaml

try:
    from StringIO import StringIO
except ImportError:  # Python 3
    from io import StringIO

from swagger_spec_validator.validator20 import validate_spec


class SwaggerParser(object):
    """Parse a swagger YAML file.

    Get definitions examples, routes default data, and routes validator.
    This only works with swagger 2.0.

    Attributes:
        specification: dict of the yaml file.
        definitions_example: dict of definition with an example.
        paths: dict of path with their actions, parameters, and responses.
    """

    _HTTP_VERBS = set(['get', 'put', 'post', 'delete', 'options', 'head',
                       'patch'])

    def __init__(self, swagger_path=None, swagger_dict=None, use_example=True):
        """Run parsing from either a file or a dict.

        Args:
            swagger_path: path of the swagger file.
            swagger_dict: swagger dict.
            use_example: Define if we use the example from the YAML when we
                         build definitions example (False value can be useful
                         when making test. Problem can happen if set to True, eg
                         POST {'id': 'example'}, GET /string => 404).

        Raises:
            - ValueError: if no swagger_path or swagger_dict is specified.
                          Or if the given swagger is not valid.
        """
        try:
            if swagger_path is not None:
                # Open yaml file
                arguments = {}
                with codecs.open(swagger_path, 'r', 'utf-8') as swagger_yaml:
                    swagger_template = swagger_yaml.read()
                    swagger_string = jinja2.Template(swagger_template).render(**arguments)
                    self.specification = yaml.load(swagger_string)
                    self.json_specification = json.dumps(self.specification)
            elif swagger_dict is not None:
                self.specification = swagger_dict
                self.json_specification = json.dumps(self.specification)
            else:
                raise ValueError('You must specify a swagger_path or dict')

            validate_spec(self.specification, '')
        except Exception as exc:
            raise ValueError('{0} is not a valid swagger2.0 file: {1}'.format(swagger_path,
                                                                              exc))

        # Run parsing
        self.use_example = use_example
        self.base_path = self.specification.get('basePath', '')
        self.definitions_example = {}
        self.build_definitions_example()
        self.paths = {}
        self.operation = {}
        self.get_paths_data()

    def build_definitions_example(self):
        """Parse all definitions in the swagger specification."""
        for def_name, def_spec in self.specification['definitions'].items():
            self.build_one_definition_example(def_name)

    def build_one_definition_example(self, def_name):
        """Build the example for the given definition.

        Args:
            def_name: Name of the definition.

        Returns:
            True if the example has been created, False if an error occured.
        """
        if def_name in self.definitions_example.keys():  # Already processed
            return True
        elif def_name not in self.specification['definitions'].keys():  # Def does not exist
            return False

        self.definitions_example[def_name] = {}
        def_spec = self.specification['definitions'][def_name]

        # Get properties example value
        for prop_name, prop_spec in def_spec['properties'].items():
            example = self.get_example_from_prop_spec(prop_spec)
            if example is not None:
                self.definitions_example[def_name][prop_name] = example
            else:
                return False

        return True

    @staticmethod
    def check_type(value, type_def):
        """Check if the value is in the type given in type_def.

        Args:
            value: the var to test.
            type_def: string representing the type in swagger.

        Returns:
            True if the type is correct, False otherwise.
        """
        if type_def == 'integer':
            try:
                # We accept string with integer ex: '123'
                int(value)
                return True
            except ValueError:
                return isinstance(value, six.integer_types) and not isinstance(value, bool)
        elif type_def == 'number':
            return isinstance(value, (six.integer_types, float)) and not isinstance(value, bool)
        elif type_def == 'string':
            return isinstance(value, (six.text_type, six.string_types, datetime.datetime))
        elif type_def == 'boolean':
            return isinstance(value, bool) or (isinstance(value, (six.text_type, six.string_types,)) and value.lower() in ['true', 'false'])
        else:
            return False

    def get_example_from_prop_spec(self, prop_spec):
        """Return an example value from a property specification.

        Args:
            prop_spec: the specification of the property.

        Returns:
            An example value
        """
        if 'example' in prop_spec.keys() and self.use_example:  # From example
            return prop_spec['example']
        elif 'default' in prop_spec.keys():  # From default
            return prop_spec['default']
        elif 'enum' in prop_spec.keys():  # From enum
            return prop_spec['enum'][0]
        elif '$ref' in prop_spec.keys():  # From definition
            return self._example_from_definition(prop_spec)
        elif 'type' not in prop_spec:  # Complex type
            return self._example_from_complex_def(prop_spec)
        elif prop_spec['type'] == 'array':  # Array
            return self._example_from_array_spec(prop_spec)
        elif prop_spec['type'] == 'file':  # File
            return (StringIO('my file contents'), 'hello world.txt')
        else:  # Basic types
            if 'format' in prop_spec.keys() and prop_spec['format'] == 'date-time':
                return self._get_example_from_basic_type('datetime')[0]
            elif isinstance(prop_spec['type'], list):  # Type is a list
                return self._get_example_from_basic_type(prop_spec['type'][0])[0]
            else:
                return self._get_example_from_basic_type(prop_spec['type'])[0]

    @staticmethod
    def _get_example_from_basic_type(type):
        """Get example from the given type.

        Args:
            type: the type you want an example of.

        Returns:
            An array with two example values of the given type.
        """
        if type == 'integer':
            return [42, 24]
        elif type == 'number':
            return [5.5, 5.5]
        elif type == 'string':
            return ['string', 'string2']
        elif type == 'datetime':
            return ['2015-08-28T09:02:57.481Z', '2015-08-28T09:02:57.481Z']
        elif type == 'boolean':
            return [False, True]

    def _example_from_definition(self, prop_spec):
        """Get an example from a property specification linked to a definition.

        Args:
            prop_spec: specification of the property you want an example of.

        Returns:
            An example.
        """
        # Get value from definition
        definition_name = self.get_definition_name_from_ref(prop_spec['$ref'])

        if self.build_one_definition_example(definition_name):
            example_dict = self.definitions_example[definition_name]
            if len(example_dict) == 1:
                return example_dict[example_dict.keys()[0]]
            else:
                example = {}
                for example_name, example_value in example_dict.items():
                    example[example_name] = example_value
                return example

    def _example_from_complex_def(self, prop_spec):
        """Get an example from a property specification.

        In case there is no "type" key in the root of the dictionary.

        Args:
            prop_spec: property specification you want an example of.

        Returns:
            An example.
        """
        if 'type' not in prop_spec['schema']:
            definition_name = self.get_definition_name_from_ref(prop_spec['schema']['$ref'])
            if self.build_one_definition_example(definition_name):
                return self.definitions_example[definition_name]
        elif prop_spec['schema']['type'] == 'array':  # Array with definition
            # Get value from definition
            if 'items' in prop_spec.keys():
                definition_name = self.get_definition_name_from_ref(prop_spec['items']['$ref'])
            else:
                definition_name = self.get_definition_name_from_ref(prop_spec['schema']['items']['$ref'])
            return [self.definitions_example[definition_name]]
        else:
            return self.get_example_from_prop_spec(prop_spec['schema'])

    def _example_from_array_spec(self, prop_spec):
        """Get an example from a property specification of an array.

        Args:
            prop_spec: property specification you want an example of.

        Returns:
            An example array.
        """
        # Standard types in array
        if 'type' in prop_spec['items'].keys():
            if 'format' in prop_spec['items'].keys() and prop_spec['items']['format'] == 'date-time':
                return self._get_example_from_basic_type('datetime')
            else:
                return self._get_example_from_basic_type(prop_spec['items']['type'])

        # Array with definition
        elif '$ref' in prop_spec['items'].keys() or '$ref' in prop_spec['schema']['items'].keys():
            # Get value from definition
            definition_name = self.get_definition_name_from_ref(prop_spec['items']['$ref']) or \
                self.get_definition_name_from_ref(prop_spec['schema']['items']['$ref'])
            if self.build_one_definition_example(definition_name):
                example_dict = self.definitions_example[definition_name]
                if len(example_dict) == 1:
                    return example_dict[example_dict.keys()[0]]
                else:
                    return_value = {}
                    for example_name, example_value in example_dict.items():
                        return_value[example_name] = example_value
                    return [return_value]

    def get_dict_definition(self, dict, get_list=False):
        """Get the definition name of the given dict.

        Args:
            dict: dict to test.
            get_list: if set to true, return a list of definition that match the body.
                      if False, only return the first.

        Returns:
            The definition name or None if the dict does not match any definition.
            If get_list is True, return a list of definition_name.
        """
        list_def_candidate = []
        for definition_name in self.specification['definitions'].keys():
            if self.validate_definition(definition_name, dict):
                if get_list:
                    list_def_candidate.append(definition_name)
                else:
                    return definition_name
        if get_list:
            return list_def_candidate
        return None

    def validate_definition(self, definition_name, dict_to_test):
        """Validate the given dict according to the given definition.

        Args:
            definition_name: name of the the definition.
            dict_to_test: dict to test.

        Returns:
            True if the given dict match the definition, False otherwise.
        """
        if definition_name in self.specification['definitions'].keys():
            # Check all required in dict_to_test
            if 'required' in self.specification['definitions'][definition_name] and \
               not all(req in dict_to_test.keys() for req in self.specification['definitions'][definition_name]['required']):
                    return False

            # Check no extra arg & type
            properties_dict = self.specification['definitions'][definition_name]['properties']
            for key, value in dict_to_test.items():
                if value is not None:
                    if key not in properties_dict:  # Extra arg
                        return False
                    else:  # Check type
                        if not self._validate_type(properties_dict[key], value):
                            return False
        else:  # Unknow definition
            return False

        return True

    def _validate_type(self, properties_spec, value):
        """Validate the given value with the given property spec.

        Args:
            properties_dict: specification of the property to check (From definition not route).
            value: value to check.

        Returns:
            True if the value is valid for the given spec.
        """
        if 'type' not in properties_spec.keys():
            # Validate sub definition
            def_name = self.get_definition_name_from_ref(properties_spec['$ref'])
            return self.validate_definition(def_name, value)

        # Validate array
        elif properties_spec['type'] == 'array':
            if not isinstance(value, list):
                return False

            # Check type
            if ('type' in properties_spec['items'].keys() and
                    any(not self.check_type(item, properties_spec['items']['type']) for item in value)):
                return False
            # Check ref
            elif ('$ref' in properties_spec['items'].keys()):
                def_name = self.get_definition_name_from_ref(properties_spec['items']['$ref'])
                if any(not self.validate_definition(def_name, item) for item in value):
                    return False

        else:  # Classic types
            if not self.check_type(value, properties_spec['type']):
                return False

        return True

    def get_paths_data(self):
        """Get data for each paths in the swagger specification.

        Get also the list of operationId.
        """
        for path, path_spec in self.specification['paths'].items():
            path = u'{0}{1}'.format(self.base_path, path)
            self.paths[path] = {}

            # Add path-level parameters
            default_parameters = {}
            if 'parameters' in path_spec:
                self._add_parameters(default_parameters, path_spec['parameters'])

            for action in path_spec.keys():
                if action not in self._HTTP_VERBS:
                    continue

                self.paths[path][action] = {}

                # Add to operation list
                if 'operationId' in path_spec[action].keys():
                    tag = path_spec[action]['tags'][0] if 'tags' in path_spec[action].keys() and path_spec[action]['tags'] else None
                    self.operation[path_spec[action]['operationId']] = (path, action, tag)

                # Get parameters
                self.paths[path][action]['parameters'] = default_parameters.copy()
                if 'parameters' in path_spec[action].keys():
                    self._add_parameters(self.paths[path][action]['parameters'], path_spec[action]['parameters'])

                # Get responses
                self.paths[path][action]['responses'] = path_spec[action]['responses']

    def _add_parameters(self, parameter_map, parameter_list):
        """Populates the given parameter map with the list of parameters provided, resolving any reference objects encountered.

        Args:
            parameter_map: mapping from parameter names to parameter objects
            parameter_list: list of either parameter objects or reference objects
        """
        for parameter in parameter_list:
            if parameter.get('$ref'):
                # expand parameter from $ref if not specified inline
                parameter = self.specification['parameters'].get(parameter.get('$ref').split('/')[-1])
            parameter_map[parameter['name']] = parameter

    @staticmethod
    def get_definition_name_from_ref(ref):
        """Get the definition name of the given $ref value(Swagger value).

        Args:
            ref: ref value (ex: "#/definitions/CustomDefinition")

        Returns:
            The definition name corresponding to the ref.
        """
        p = re.compile('#\/definitions\/(.*)')
        definition_name = re.sub(p, r'\1', ref)
        return definition_name

    def get_path_spec(self, path, action=None):
        """Get the specification matching with the given path.

        Args:
            path: path we want the specification.
            action: get the specification for the given action.

        Returns:
            A tuple with the base name of the path and the specification.
            Or (None, None) if no specification is found.
        """
        # Get the specification of the given path
        path_spec = None
        path_name = None
        for base_path in self.paths.keys():
            if path == base_path:
                path_spec = self.paths[base_path]
                path_name = base_path

        # Path parameter
        if path_spec is None:
            for base_path in self.paths.keys():
                regex_from_path = re.compile(re.sub('{[^/]*}', '([^/]*)', base_path) + r'$')
                if re.match(regex_from_path, path):
                    path_spec = self.paths[base_path]
                    path_name = base_path

        # Test action if given
        if path_spec is not None and action is not None:
            if action not in path_spec.keys():
                return (None, None)
            else:
                path_spec = path_spec[action]

        return (path_name, path_spec)

    def validate_request(self, path, action, body=None, query=None):
        """Check if the given request is valid.

        Args:
            path: path of the request.
            action: action of the request(get, post, delete...).
            body: body of the request.
            query: dict with the query parameters.

        Returns:
            True if the request is valid, False otherwise.
        """
        path_name, path_spec = self.get_path_spec(path)

        if path_spec is not None:
            if action in path_spec.keys():
                action_spec = path_spec[action]
                # Check query
                if query is not None and not self._check_query_parameters(query, action_spec):
                    return False

                # Check body
                if body is not None and not self._check_body_parameters(body, action_spec):
                        return False
            else:  # Undefined action
                return False
        else:  # Unknow path
            return False

        return True

    def _check_query_parameters(self, query, action_spec):
        """Check the query parameter for the action specification.

        Args:
            query: query parameter to check.
            action_spec: specification of the action.

        Returns:
            True if the query is valid.
        """
        processed_params = []
        for param_name, param_value in query.items():
            if param_name in action_spec['parameters'].keys():
                processed_params.append(param_name)

                # Check array
                if action_spec['parameters'][param_name]['type'] == 'array':
                    if not isinstance(param_value, list):  # Not an array
                        return False
                    else:
                        for i in param_value:  # Check type of all elements in array
                            if not self.check_type(i, action_spec['parameters'][param_name]['items']['type']):
                                return False

                elif not self.check_type(param_value, action_spec['parameters'][param_name]['type']):
                    return False

        # Check required
        if not all(param in processed_params for param, spec in action_spec['parameters'].items()
                   if spec['in'] == 'query' and 'required' in spec and spec['required']):
            return False
        return True

    def _check_body_parameters(self, body, action_spec):
        """Check the body parameter for the action specification.

        Args:
            body: body parameter to check.
            action_spec: specification of the action.

        Returns:
            True if the body is valid.
        """
        processed_params = []
        for param_name, param_spec in action_spec['parameters'].items():
            if param_spec['in'] == 'body':
                processed_params.append(param_name)

                # Check type
                if 'type' in param_spec.keys() and not self.check_type(body, param_spec['type']):
                    return False
                # Check schema
                elif 'schema' in param_spec.keys():
                    if 'type' in param_spec['schema'].keys() and param_spec['schema']['type'] == 'array':
                        # It is an array get value from definition
                        definition_name = self.get_definition_name_from_ref(param_spec['schema']['items']['$ref'])
                        if len(body) > 0 and not self.validate_definition(definition_name, body[0]):
                            return False
                    elif 'type' in param_spec['schema'].keys() and not self.check_type(body, param_spec['schema']['type']):
                        # Type but not array
                        return False
                    else:
                        definition_name = self.get_definition_name_from_ref(param_spec['schema']['$ref'])
                        if not self.validate_definition(definition_name, body):
                            return False
        # Check required
        if not all(param in processed_params for param, spec in action_spec['parameters'].items()
                   if spec['in'] == 'body' and 'required' in spec and spec['required']):
            return False
        return True

    def get_response_example(self, resp_spec):
        """Get a response example from a response spec.

        """
        if 'schema' in resp_spec.keys():
            if '$ref' in resp_spec['schema']:  # Standard definition
                definition_name = self.get_definition_name_from_ref(resp_spec['schema']['$ref'])
                return self.definitions_example[definition_name]
            elif 'items' in resp_spec['schema'] and resp_spec['schema']['type'] == 'array':  # Array
                definition_name = self.get_definition_name_from_ref(resp_spec['schema']['items']['$ref'])
                return [self.definitions_example[definition_name]]
            elif 'type' in resp_spec['schema']:
                return self.get_example_from_prop_spec(resp_spec['schema'])
        else:
            return ''

    def get_request_data(self, path, action, body=None):
        """Get the default data and status code of the given path + action request.

        Args:
            path: path of the request.
            action: action of the request(get, post, delete...)
            body: body sent, used to sent it back for post request.

        Returns:
            A tuple with the default response data and status code
            In case of default status_code, use 0
        """
        body = body or ''
        path_name, path_spec = self.get_path_spec(path)
        response = {}

        # Get all status code
        if path_spec is not None and action in path_spec.keys():
            for status_code in path_spec[action]['responses'].keys():
                resp = path_spec[action]['responses'][status_code]
                try:
                    response[int(status_code)] = self.get_response_example(resp)
                except ValueError:
                    response[status_code] = self.get_response_example(resp)

        # If there is no status_code add a default 400
        if response == {}:
            response[400] = ''
        return response

    def get_send_request_correct_body(self, path, action):
        """Get an example body which is correct to send to the given path with the given action.

        Args:
            path: path of the request
            action: action of the request (get, post, put, delete)

        Returns:
            A dict representing a correct body for the request or None if no
            body is required.
        """
        path_name, path_spec = self.get_path_spec(path)

        if path_spec is not None and action in path_spec.keys():
                for name, spec in path_spec[action]['parameters'].items():
                    if spec['in'] == 'body':  # Get body parameter
                        if 'type' in spec.keys():
                            # Get value from type
                            return self.get_example_from_prop_spec(spec)
                        elif 'schema' in spec.keys():
                            if 'type' in spec['schema'].keys() and spec['schema']['type'] == 'array':
                                # It is an array
                                # Get value from definition
                                definition_name = self.get_definition_name_from_ref(spec['schema']['items']['$ref'])
                                return [self.definitions_example[definition_name]]
                            elif 'type' in spec['schema'].keys():
                                # Type but not array
                                return self.get_example_from_prop_spec(spec['schema'])
                            else:
                                # Get value from definition
                                definition_name = self.get_definition_name_from_ref(spec['schema']['$ref'])
                                return self.definitions_example[definition_name]
