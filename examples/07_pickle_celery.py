"""
Example 07: Pickle & Task Queues (Celery)

Demonstrates that mutation tracking is preserved across pickling.
Useful for passing models to background workers.
"""

import pickle

from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from sqlatypemodel import LazyMutableMixin, ModelType
from sqlatypemodel.util.sqlalchemy import create_engine


# Use LazyMutableMixin for best compatibility with serialization
class WorkerSettings(LazyMutableMixin, BaseModel):
    job_id: str
    log: list[str] = []


class Base(DeclarativeBase):
    pass


class BackgroundJob(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    settings: Mapped[WorkerSettings] = mapped_column(ModelType(WorkerSettings))


def run_example():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # Create
        job = BackgroundJob(settings=WorkerSettings(job_id="task-1"))
        session.add(job)
        session.commit()

        # 1. Simulate passing to a Celery worker via Pickle
        print("Pickling object...")
        data = pickle.dumps(job)

        # 2. Simulate worker side
        print("Unpickling object in worker...")
        job_worker: BackgroundJob = pickle.loads(data)

        # Re-attach to a new session (just like in a real worker)
        worker_session = Session(engine)
        worker_session.add(job_worker)

        # 3. Mutate inside the worker
        job_worker.settings.log.append("Processing started")
        job_worker.settings.log.append("Step 1 complete")

        worker_session.commit()
        print(f"Worker saved logs: {job_worker.settings.log}")


if __name__ == "__main__":
    run_example()
