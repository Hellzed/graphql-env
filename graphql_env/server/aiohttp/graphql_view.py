from collections import MutableMapping, namedtuple

from aiohttp.web import json_response, Response, View
from graphql.error import GraphQLError, format_error as format_graphql_error
from graphql.execution import ExecutionResult
from promise import Promise

from ..common.exceptions import (BatchEmptyListError, BatchNotEnabledError,
                                 InvalidJSONError, NotADictError)
from ..common.utils import execution_result_to_dict, graphql_params_from_data

GraphQLResponse = namedtuple('GraphQLResponse', 'result,status_code')

GRAPHQL_ENV = 'graphql_env'
GET_ALLOWED_OPERATIONS = set(("query", ))
POST_ALLOWED_OPERATIONS = set(("query", "mutation", "subscription"))


def default_format_error(error):
    if isinstance(error, GraphQLError):
        return format_graphql_error(error)

    return {'message': str(error)}


def can_display_graphiql(request):
    if 'raw' in dict(request.query):
        return False

    accept = request.headers.get('accept', {})

    return any([
        'text/html' in accept,
        '*/*' in accept
    ])


async def parse_body(request):
    content_type = request.content_type
    data = {}

    if content_type == 'application/graphql':
        text = await request.text()
        data = {'query': text}
    elif content_type == 'application/json':
        try:
            data = await request.json()
        except:
            raise InvalidJSONError()
    else:
        form = await request.post()
        data = dict(form)

    return data


async def get_result(request, params, allowed_operations):
    graphql_env = request.app[GRAPHQL_ENV]
    middleware = graphql_env.middleware
    execute = graphql_env

    try:
        return execute(
            params,
            root=None,
            context=request,
            middleware=middleware,
            allowed_operations=allowed_operations
        )
    except Exception as error:
        return ExecutionResult(errors=[error])


def format_one_result(result, format_error):
    status_code = 200

    if result:
        response = execution_result_to_dict(result, format_error)
        status_code = 400 if result.invalid else 200
    else:
        response = None

    return GraphQLResponse(response, status_code)


def format_many_results(results, format_error):
    responses = [
        format_one_result(result, format_error)
        for result in results
    ]
    formatted_results, status_codes = zip(*responses)
    status_code = max(status_codes)

    return formatted_results, status_code


def graphql_json_response(results, format_error=default_format_error,
                          is_batch=False):
    if is_batch:
        response, status_code = format_many_results(results, format_error)
    else:
        response, status_code = format_one_result(results, format_error)

    return json_response(response, status=status_code)


class GraphQLView(View):
    async def get(self):
        allowed_operations = GET_ALLOWED_OPERATIONS
        params = graphql_params_from_data(dict(self.request.query))
        result = await Promise.resolve(
            get_result(self.request, params, allowed_operations)
        )

        return graphql_json_response(result)

    async def post(self):
        batch_enabled = True

        allowed_operations = POST_ALLOWED_OPERATIONS
        body_data = await parse_body(self.request)

        is_batch = isinstance(body_data, list)

        if not is_batch:
            if not isinstance(body_data, (dict, MutableMapping)):
                raise NotADictError(
                    'GraphQL params should be a dict. Received {}.'
                    .format(body_data)
                )
            body_data = [body_data]
        elif not batch_enabled:
            raise BatchNotEnabledError()

        if not body_data:
            raise BatchEmptyListError()

        # If is a batch request, don't consume the data from the query
        query_data = {} if is_batch else dict(self.request.query)

        params_batch = [graphql_params_from_data(query_data, entry)
                        for entry in body_data]

        result = await Promise.all(
            [get_result(self.request, params, allowed_operations)
             for params in params_batch]
        )
        if not is_batch:
            result = result[0]

        return graphql_json_response(result, is_batch=is_batch)

    async def options(self):
        """ Preflight request support
        https://www.w3.org/TR/cors/#resource-preflight-requests
        """
        headers = self.request.headers
        origin = headers.get('Origin', '')
        method = headers.get('Access-Control-Request-Method', '').upper()

        accepted_methods = ['GET', 'POST', 'PUT', 'DELETE']
        if method and method in accepted_methods:
            return Response(
                status=200,
                headers={
                    'Access-Control-Allow-Origin': origin,
                    'Access-Control-Allow-Methods': ', '.join(accepted_methods),
                    'Access-Control-Max-Age': str(86400),
                }
            )
        return Response(status=400)
