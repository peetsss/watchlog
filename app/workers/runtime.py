from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.workers.db import create_worker_engine, create_worker_sessionmaker


@dataclass
class WorkerRuntime:
    engine: Engine
    sessionmaker: sessionmaker[Session]

    @classmethod
    def from_settings(cls, settings: Settings) -> WorkerRuntime:
        engine = create_worker_engine(settings)
        return cls(engine=engine, sessionmaker=create_worker_sessionmaker(engine))

    def dispose(self) -> None:
        self.engine.dispose()


_runtime: WorkerRuntime | None = None


def init_worker_runtime(settings: Settings) -> WorkerRuntime:
    global _runtime
    if _runtime is not None:
        _runtime.dispose()
    _runtime = WorkerRuntime.from_settings(settings)
    return _runtime


def get_worker_runtime() -> WorkerRuntime:
    if _runtime is None:
        raise RuntimeError("The worker runtime has not been initialized")
    return _runtime


def dispose_worker_runtime() -> None:
    global _runtime
    if _runtime is not None:
        _runtime.dispose()
        _runtime = None
