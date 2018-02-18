import json
import six

from ...params import GraphQLParams
from .exceptions import InvalidVariablesJSONError, MissingQueryError


def execution_result_to_dict(execution_result, format_error):
    data = {}
    if execution_result.errors:
        data['errors'] = [
            format_error(error) for error in execution_result.errors
        ]
    if execution_result.data and not execution_result.invalid:
        data['data'] = execution_result.data
    return data


def graphql_params_from_data(query_params, data=None):
    data = data or {}
    variables = data.get('variables') or query_params.get('variables')
    if isinstance(variables, six.string_types):
        try:
            variables = json.loads(variables)
        except:
            raise InvalidVariablesJSONError()

    return GraphQLParams(
        query=data.get('query') or query_params.get('query'),
        query_id=data.get('queryId') or query_params.get('queryId'),
        operation_name=data.get('operationName') or
        query_params.get('operationName'),
        variables=variables)
