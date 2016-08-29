# -*- coding: utf-8 -*-

import codecs
import datetime
import hashlib
import jinja2
import json
import logging
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
        self.generated_operation = {}
        self.get_paths_data()

    def build_definitions_example(self):
        """Parse all definitions in the swagger specification."""
        for def_name, def_spec in self.specification.get('definitions', {}).items():
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

        if def_spec.get('type') == 'array' and 'items' in def_spec:
            item = self.get_example_from_prop_spec(def_spec['items'])
            self.definitions_example[def_name] = [item]
            return True

        if 'properties' not in def_spec:
            self.definitions_example[def_name] = self.get_example_from_prop_spec(def_spec)
            return True

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
            return (isinstance(value, bool) or
                    (isinstance(value, (six.text_type, six.string_types,)) and
                     value.lower() in ['true', 'false'])
                    )
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
        elif prop_spec['type'] == 'object':  # From properties, without references
            return [self._get_example_from_properties(prop_spec)]
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

    def _get_example_from_properties(self, spec):
        """Get example from the properties of an object defined inline.

        Args:
            prop_spec: property specification you want an example of.

        Returns:
            An example.
        """
        example = {}
        required = spec.get('required', spec['properties'].keys())
        for inner_name, inner_spec in spec['properties'].items():
            if inner_name not in required:
                continue

            partial = self.get_example_from_prop_spec(inner_spec)
            # While get_example_from_prop_spec is supposed to return a list,
            # we don't actually want that when recursing to build from
            # properties
            if isinstance(partial, list):
                partial = partial[0]

            example[inner_name] = partial
        return example

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
            if not isinstance(example_dict, dict):
                return example_dict
            example = dict((example_name, example_value) for example_name, example_value in example_dict.items())
            return example

    def _example_from_complex_def(self, prop_spec):
        """Get an example from a property specification.

        In case there is no "type" key in the root of the dictionary.

        Args:
            prop_spec: property specification you want an example of.

        Returns:
            An example.
        """
        if 'schema' in prop_spec and 'type' not in prop_spec['schema']:
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
        elif ('$ref' in prop_spec['items'].keys() or
              ('schema' in prop_spec and'$ref' in prop_spec['schema']['items'].keys())):
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
        elif 'properties' in prop_spec['items']:
            prop_example = {}
            for prop_name, prop_spec in prop_spec['items']['properties'].items():
                example = self.get_example_from_prop_spec(prop_spec)
                if example is not None:
                    prop_example[prop_name] = example
            return [prop_example]

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
        if definition_name not in self.specification['definitions'].keys():
            # reject unknown definition
            return False

        # Check all required in dict_to_test
        spec_def = self.specification['definitions'][definition_name]
        all_required_keys_present = all(req in dict_to_test.keys() for req in spec_def.get('required', {}))
        if 'required' in spec_def and not all_required_keys_present:
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

            for http_method in path_spec.keys():
                if http_method not in self._HTTP_VERBS:
                    continue

                self.paths[path][http_method] = {}

                # Add to operation list
                action = path_spec[http_method]
                tag = action['tags'][0] if 'tags' in action.keys() and action['tags'] else None
                if 'operationId' in action.keys():
                    self.operation[action['operationId']] = (path, http_method, tag)
                else:
                    # Note: the encoding chosen below isn't very important in this
                    #       case; what matters is a byte string that is unique.
                    #       URL paths and http methods should encode to UTF-8 safely.
                    h = hashlib.sha256()
                    h.update(("{0}|{1}".format(http_method, path)).encode('utf-8'))
                    self.generated_operation[h.hexdigest()] = (path, http_method, tag)

                # Get parameters
                self.paths[path][http_method]['parameters'] = default_parameters.copy()
                if 'parameters' in action.keys():
                    self._add_parameters(self.paths[path][http_method]['parameters'], action['parameters'])

                # Get responses
                self.paths[path][http_method]['responses'] = action['responses']

                # Get mime types for this action
                if 'consumes' in action.keys():
                    self.paths[path][http_method]['consumes'] = action['consumes']

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
           Validates the body and the query

           # Rules to validate the BODY:
           # Let's limit this to mime types that either contain 'text' or 'json'
           # 1. if body is None, there must not be any required parameters in
           #    the given schema
           # 2. if the mime type contains 'json', body must not be '', but can
           #    be {}
           # 3. if the mime type contains 'text', body can be any string
           # 4. if no mime type ('consumes') is given.. DISALLOW
           # 5. if the body is empty ('' or {}), there must not be any required parameters
           # 6. if there is something in the body, it must adhere to the given schema
           #    -> will call the validate body function

        Args:
            path: path of the request.
            action: action of the request(get, post, delete...).
            body: body of the request.
            query: dict with the query parameters.

        Returns:
            True if the request is valid, False otherwise.

        TODO:
            - For every http method, we might want to have some general checks
               before we go deeper into the parameters
            - Check form data parameters
        """
        path_name, path_spec = self.get_path_spec(path)

        if path_spec is None:  # reject unknown path
            logging.warn("there is no path")
            return False

        if action not in path_spec.keys():  # reject unknown http method
            logging.warn("this http method is unknown '%s'" % (action, ))
            return False

        action_spec = path_spec[action]

        # check general post body guidelines (body + mime type)
        if action == 'post':
            is_ok, msg = self._validate_post_body(body, action_spec)
            if not is_ok:
                logging.warn("the general post body did not validate due to '%s'" % (msg, ))
                return False

        # If the body is empty and it validated so far, we can return here
        # unless there is something in the query parameters we need to check
        body_is_empty = (body is None or body == '' or body == {})
        if body_is_empty and query is None:
            return True

        # Check body parameters
        is_ok, msg = self._validate_body_parameters(body, action_spec)
        if not is_ok:
            logging.warn("the parameters in the body did not validate due to '%s'" % (msg, ))
            return False

        # Check query parameters
        if query is not None and not self._validate_query_parameters(query, action_spec):
            return False

        return True

    def _validate_post_body(self, actual_request_body, body_specification):
        """ returns a tuple (boolean, msg)
            to indicate whether the validation passed
            if False then msg contains the reason
            if True then msg is empty
        """

        # Are there required parameters? - there is only ONE body, so we check that one
        parameters_required = body_specification['parameters']['body']['required']

        # What if it says 'required' but there is no schema ? - we reject it
        schema_present = body_specification['parameters']['body'].get('schema', None)
        if parameters_required and not schema_present:
            msg = "there is no schema given, but it says there are required parameters"
            return False, msg

        # What is the mime type ?
        text_is_accepted = any('text' in item for item in body_specification.get('consumes', []))
        json_is_accepted = any('json' in item for item in body_specification.get('consumes', []))

        if actual_request_body is '' and not text_is_accepted:
            msg = "post body is an empty string, but text is not an accepted mime type"
            return False, msg

        if actual_request_body == {} and not json_is_accepted:
            msg = "post body is an empty dict, but json is not an accepted mime type"
            return False, msg

        # If only json is accepted, but the body is a string, we transform the
        # string to json and check it then (not sure if the server would accept
        # that string, though)
        if (json_is_accepted and not
                text_is_accepted and
                type(actual_request_body).__name__ == 'str'):
            actual_request_body = json.loads(actual_request_body)

        # Handle empty body
        body_is_empty = (actual_request_body is None or
                         actual_request_body == '' or
                         actual_request_body == {})
        if body_is_empty:
            if parameters_required:
                msg = "there is no body, but it says there are required parameters"
                return False, msg
            else:
                return True, ""

        return True, ""

    def _validate_query_parameters(self, query, action_spec):
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

    def _validate_body_parameters(self, body, action_spec):
        """Check the body parameter for the action specification.

        Args:
            body: body parameter to check.
            action_spec: specification of the action.

        Returns:
            True if the body is valid.
            A string containing an error msg in case the body did not validate,
            otherwise the string is empty
        """
        processed_params = []
        for param_name, param_spec in action_spec['parameters'].items():
            if param_spec['in'] == 'body':
                processed_params.append(param_name)

                # Check type
                if 'type' in param_spec.keys() and not self.check_type(body, param_spec['type']):
                    msg = "Check type did not validate for %s and %s" % (param_spec['type'], body)
                    return False, msg
                # Check schema
                elif 'schema' in param_spec.keys():
                    if 'type' in param_spec['schema'].keys() and param_spec['schema']['type'] == 'array':
                        # It is an array get value from definition
                        definition_name = self.get_definition_name_from_ref(param_spec['schema']['items']['$ref'])
                        if len(body) > 0 and not self.validate_definition(definition_name, body[0]):
                            msg = "The body did not validate against its definition"
                            return False, msg
                    elif ('type' in param_spec['schema'].keys() and not
                          self.check_type(body, param_spec['schema']['type'])):
                        # Type but not array
                        msg = "Check type did not validate for %s and %s" % (param_spec['schema']['type'], body)
                        return False, msg
                    else:
                        definition_name = self.get_definition_name_from_ref(param_spec['schema']['$ref'])
                        if not self.validate_definition(definition_name, body):
                            msg = "The body did not validate against its definition"
                            return False, msg
        # Check required
        if not all(param in processed_params for param, spec in action_spec['parameters'].items()
                   if spec['in'] == 'body' and 'required' in spec and spec['required']):
            msg = "Not all required parameters were present"
            return False, msg

        return True, ""

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
