from collections import MutableMapping, namedtuple

from aiohttp.web import json_response, Response, View
from graphql.error import format_error as default_format_error
from graphql.execution import ExecutionResult
from promise import Promise

from ..common.exceptions import (BatchEmptyListError, BatchNotEnabledError,
                                 GraphQLHTTPError, InvalidJSONError,
                                 NotADictError)
from ..common.utils import execution_result_to_dict, graphql_params_from_data

GRAPHQL_ENV = 'graphql_env'
GET_ALLOWED_OPERATIONS = set(("query", ))
POST_ALLOWED_OPERATIONS = set(("query", "mutation", "subscription"))

GraphQLHTTPResponse = namedtuple('GraphQLHTTPResponse', 'result,status_code')


def display_graphiql(request):
    if 'raw' in dict(request.query):
        return False

    accept = request.headers.get('accept', {})

    return any([
        'text/html' in accept,
        '*/*' in accept
    ])


async def parse_body(request):
    content_type = request.content_type

    if content_type == 'application/graphql':
        return {'query': await request.text()}
    elif content_type == 'application/json':
        try:
            return await request.json()
        except:
            raise InvalidJSONError()
    else:
        return dict(await request.post())


async def get_graphql_http_response(request, params, allowed_operations):
    graphql_env = request.app[GRAPHQL_ENV]
    middleware = graphql_env.middleware
    execute = graphql_env
    status = 200

    try:
        execution_result = await Promise.resolve(execute(
            params,
            root=None,
            context=request,
            middleware=middleware,
            allowed_operations=allowed_operations
        ))
    except Exception as error:
        if isinstance(error, GraphQLHTTPError):
            status = error.status_code
        execution_result = ExecutionResult(errors=[error])

    return GraphQLHTTPResponse(execution_result, status)


class GraphQLView(View):
    async def get(self):
        allowed_operations = GET_ALLOWED_OPERATIONS
        params = graphql_params_from_data(dict(self.request.query))
        result, status = await get_graphql_http_response(self.request, params, allowed_operations)

        awaited_execution_result = await Promise.all([result])
        return json_response(execution_result_to_dict(awaited_execution_result[0], default_format_error), status=status)

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

        responses = [get_graphql_http_response(
                self.request,
                params,
                allowed_operations)
            for params in params_batch]

        awaited_execution_results = await Promise.all(responses)

        results, status_codes = zip(*awaited_execution_results)
        status = max(status_codes)

        final_result = [execution_result_to_dict(result, default_format_error)
                        for result in results]

        if not is_batch:
            final_result = final_result[0]

        return json_response(final_result, status=status)

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
