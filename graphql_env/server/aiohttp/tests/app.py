from aiohttp.web import Application, run_app
from asyncio import get_event_loop
from graphql.execution.executors.asyncio import AsyncioExecutor

from ..graphql_view import GraphQLView
from .schema import Schema
from graphql_env import GraphQLEnvironment, GraphQLCoreBackend


def create_app(path='/graphql', environment=None, **kwargs):
    loop = get_event_loop()

    app = Application()
    app['graphql_env'] = GraphQLEnvironment(
        schema=Schema,
        backend=GraphQLCoreBackend(
            executor=AsyncioExecutor(loop=loop)
        )
    )
    app.router.add_view(path, GraphQLView)
    return app


if __name__ == '__main__':
    app = create_app()
    run_app(app)
