from concurrent.futures import Executor

from fastapi import Request

from app.analyzers.base import Analyzer


def get_executor(request: Request) -> Executor:
    return request.app.state.executor


def get_analyzers(request: Request) -> list[Analyzer]:
    return request.app.state.analyzers
