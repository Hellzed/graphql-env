class GraphQLHTTPError(Exception):
    status_code = 400
    default_detail = None

    def __init__(self, detail=None):
        if detail is None:
            detail = self.default_detail
        super(GraphQLHTTPError, self).__init__(detail)


class BatchEmptyListError(GraphQLHTTPError):
    default_detail = 'Received an empty list in the batch request.'


class BatchNotEnabledError(GraphQLHTTPError):
    default_detail = 'Batch GraphQL requests are not enabled.'


class InvalidJSONError(GraphQLHTTPError):
    default_detail = 'POST body sent invalid JSON.'


class InvalidVariablesJSONError(GraphQLHTTPError):
    default_detail = 'Variables are invalid JSON.'


class HTTPMethodNotAllowed(GraphQLHTTPError):
    default_detail = 'GraphQL only supports GET and POST requests.'


class MissingQueryError(GraphQLHTTPError):
    default_detail = 'Must provide query string.'


class NotADictError(GraphQLHTTPError):
    default_detail = 'GraphQL params should be a dict.'
