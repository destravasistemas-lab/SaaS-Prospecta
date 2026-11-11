"""
Cliente HTTP compartilhado para as APIs externas (Meta, Gemini...).

Criar um httpx.AsyncClient por chamada recarrega os certificados a cada vez
(~280 ms de CPU, travando o event loop para todos os clientes) e abre uma
conexão nova por pedido. Aqui o contexto TLS é criado uma vez e as conexões
são reaproveitadas.
"""
import asyncio
import ssl
from contextlib import asynccontextmanager

import certifi
import httpx

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

# Um cliente por event loop: um cliente não pode ser usado em outro loop (os testes criam vários).
_clients: dict[asyncio.AbstractEventLoop, httpx.AsyncClient] = {}


def shared() -> httpx.AsyncClient:
    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is None or client.is_closed:
        for old in [lp for lp in _clients if lp.is_closed()]:
            _clients.pop(old, None)
        client = httpx.AsyncClient(
            verify=SSL_CONTEXT,
            timeout=20.0,
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=40),
        )
        _clients[loop] = client
    return client


async def close() -> None:
    client = _clients.pop(asyncio.get_running_loop(), None)
    if client:
        await client.aclose()


_METHODS = {"request", "get", "post", "put", "patch", "delete", "head", "stream"}


class _Client:
    """A mesma interface de httpx.AsyncClient usada no app, sobre o cliente compartilhado."""

    def __init__(self, timeout: float):
        self._timeout = timeout

    def __getattr__(self, name):
        method = getattr(shared(), name)
        if name not in _METHODS:
            return method

        def call(*args, **kwargs):
            kwargs.setdefault("timeout", self._timeout)
            return method(*args, **kwargs)

        return call


@asynccontextmanager
async def client(timeout: float = 5.0):
    """Substitui `async with httpx.AsyncClient(timeout=...)` sem abrir conexão nem TLS novos."""
    yield _Client(timeout)
