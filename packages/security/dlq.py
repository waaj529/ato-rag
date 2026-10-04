"""Durable PostgreSQL-backed Dead-Letter Queue (DLQ) with replay mechanism."""

import json
from typing import Callable

import psycopg


class DeadLetterQueue:
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def enqueue(
        self, job_id: str, task_name: str, payload: dict, error_message: str
    ) -> None:
        self.connection.execute(
            """INSERT INTO dead_letter_queue (job_id, task_name, payload, error_message, status)
               VALUES (%s, %s, %s, %s, 'FAILED')
               ON CONFLICT (job_id) DO UPDATE SET
                   status = 'FAILED',
                   error_message = EXCLUDED.error_message,
                   retry_count = dead_letter_queue.retry_count + 1,
                   updated_at = NOW()""",
            (job_id, task_name, json.dumps(payload), error_message),
        )

    def fetch_failed(self, limit: int = 50) -> list[dict]:
        rows = self.connection.execute(
            """SELECT job_id, task_name, payload, error_message, retry_count, status
               FROM dead_letter_queue WHERE status = 'FAILED'
               ORDER BY created_at ASC LIMIT %s""",
            (limit,),
        ).fetchall()
        return [
            {
                "job_id": r[0], "task_name": r[1],
                "payload": r[2] if isinstance(r[2], dict) else json.loads(r[2]),
                "error_message": r[3], "retry_count": r[4], "status": r[5],
            }
            for r in rows
        ]

    def replay(self, job_id: str, handler: Callable[[dict], None]) -> bool:
        row = self.connection.execute(
            "SELECT payload FROM dead_letter_queue WHERE job_id = %s", (job_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"DLQ job '{job_id}' not found.")
        payload = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        try:
            handler(payload)
            self.connection.execute(
                """UPDATE dead_letter_queue
                   SET status = 'COMPLETED', updated_at = NOW()
                   WHERE job_id = %s""",
                (job_id,),
            )
            return True
        except Exception as exc:
            self.connection.execute(
                """UPDATE dead_letter_queue
                   SET error_message = %s, retry_count = retry_count + 1, updated_at = NOW()
                   WHERE job_id = %s""",
                (str(exc), job_id),
            )
            return False
