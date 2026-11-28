"""
Laço da fila de disparos: quando a rodada falha, o log diz qual tabela ou coluna
(sem o SQL e os telefones) e o worker espera cada vez mais, até 60s.
"""
import asyncio
import logging
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import ProgrammingError

from app.services import broadcast_worker


def _db_error():
    return ProgrammingError(
        "SELECT broadcast_jobs.include_without_opt_in FROM broadcast_jobs WHERE phone = $1",
        ("5583999990000",),
        Exception("column broadcast_jobs.include_without_opt_in does not exist\nHINT: whatever"),
    )


def test_describe_error_names_the_column_but_not_the_sql_or_params():
    msg = broadcast_worker.describe_error(_db_error())
    assert msg == "ProgrammingError: column broadcast_jobs.include_without_opt_in does not exist"
    assert "5583999990000" not in msg and "SELECT" not in msg
    assert broadcast_worker.describe_error(RuntimeError("tel 5583999990000")) == "RuntimeError"


def test_next_delay_backs_off_up_to_a_minute():
    assert [broadcast_worker.next_delay(n) for n in range(7)] == [2, 4, 8, 16, 32, 60, 60]


@pytest.mark.asyncio
async def test_loop_backs_off_on_failure_and_resets_after_success(caplog):
    process = AsyncMock(side_effect=[_db_error(), _db_error(), 0, 0])
    sleep = AsyncMock(side_effect=[None, None, None, asyncio.CancelledError()])
    with patch.object(broadcast_worker, "recover_interrupted", AsyncMock()), \
         patch.object(broadcast_worker, "process_jobs", process), \
         patch.object(broadcast_worker.asyncio, "sleep", sleep), \
         caplog.at_level(logging.INFO, logger=broadcast_worker.__name__):
        with pytest.raises(asyncio.CancelledError):
            await broadcast_worker.broadcast_loop()

    assert [c.args[0] for c in sleep.await_args_list] == [4, 8, 2, 2]
    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 2
    assert "include_without_opt_in does not exist" in errors[0] and "5583999990000" not in errors[0]
    assert any("voltou a funcionar depois de 2 falhas" in r.getMessage() for r in caplog.records)
