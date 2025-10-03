import asyncio
import os
import uuid
import asyncpg
import logging

import dotenv
dotenv.load_dotenv()

from workers.db import claim_job, run_wirl, set_state

CONCURRENCY = int(os.getenv("WORKERS", 4))
TASK_TIMEOUT = int(os.getenv("TASK_TIMEOUT_MINUTES", 20)) * 60  # Convert minutes to seconds

logger = logging.getLogger(__name__)


async def worker(pool: asyncpg.pool.Pool, wid: str) -> None:
    while True:
        job = await claim_job(pool, wid)
        if job is None:
            await asyncio.sleep(10)
            continue
        try:
            # Run the workflow with timeout
            new_state, result = await asyncio.wait_for(
                run_wirl(job), 
                timeout=TASK_TIMEOUT
            )
            await set_state(pool, job["id"], new_state, result=result)
        except asyncio.TimeoutError:
            # Task timed out - mark as failed
            logger.info(f"Task timed out after {TASK_TIMEOUT // 60} minutes")
            timeout_msg = f"Task timed out after {TASK_TIMEOUT // 60} minutes"
            await set_state(pool, job["id"], "failed", error=timeout_msg)
        except Exception as exc:  # pragma: no cover - errors in worker
            logger.error(f"Error running job {job}: {exc}")
            await set_state(pool, job["id"], "failed", error=str(exc))


async def main() -> None:
    pool = await asyncpg.create_pool(dsn=os.getenv("DATABASE_URL"))
    tasks = [asyncio.create_task(worker(pool, f"w{uuid.uuid4()}")) for _ in range(CONCURRENCY)]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    finally:
        await pool.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
