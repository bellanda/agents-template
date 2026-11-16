"""Housekeeping of agent memory (audit 2026-11-13 core-ai-07).

- the retention job prunes superseded checkpoints of IDLE threads only, keeps the newest one and
  keeps blobs still cited by it;
- inline photos of older turns are masked in the model's view (current turn untouched).
"""

from langchain_core.messages import AIMessage, HumanMessage

from api.core.agents.checkpoint_retention import prune_superseded_checkpoints
from api.core.agents.history_window import OLD_IMAGE_PLACEHOLDER, trim_messages_for_llm


class _Pool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        return _Ctx()


async def _checkpoint(conn, thread: str, cid: str, *, age_hours: int, versions: dict):
    await conn.execute(
        """
        INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, checkpoint, created_at)
        VALUES ($1, '', $2, $3::jsonb, now() - ($4::int * INTERVAL '1 hour'))
        """,
        thread,
        cid,
        {"channel_versions": versions},  # the connection's jsonb codec encodes the dict
        age_hours,
    )


async def test_prune_only_touches_idle_threads_and_keeps_the_latest(db_conn):
    # idle thread: 3 checkpoints, newest is 48h old; blob v1 superseded, v3 still cited
    for cid, age, ver in (("1", 50, "v1"), ("2", 49, "v2"), ("3", 48, "v3")):
        await _checkpoint(db_conn, "idle", cid, age_hours=age, versions={"messages": ver})
    for ver in ("v1", "v2", "v3"):
        await db_conn.execute(
            "INSERT INTO checkpoint_blobs (thread_id, channel, version, type) "
            "VALUES ('idle', 'messages', $1, 'x')",
            ver,
        )
    await db_conn.execute(
        "INSERT INTO checkpoint_writes (thread_id, checkpoint_id, task_id, idx, channel) "
        "VALUES ('idle', '1', 't', 0, 'messages'), ('idle', '3', 't', 0, 'messages')"
    )
    # active thread (checkpoint written now): must be untouched even with several rows
    for cid in ("1", "2"):
        await _checkpoint(db_conn, "active", cid, age_hours=0, versions={"messages": f"a{cid}"})

    counts = await prune_superseded_checkpoints(_Pool(db_conn), idle_hours=24)

    assert counts == {"checkpoints": 2, "writes": 1, "blobs": 2}
    idle_left = await db_conn.fetch("SELECT checkpoint_id FROM checkpoints WHERE thread_id='idle'")
    assert [r["checkpoint_id"] for r in idle_left] == ["3"]
    blobs = await db_conn.fetch("SELECT version FROM checkpoint_blobs WHERE thread_id='idle'")
    assert [r["version"] for r in blobs] == ["v3"]
    assert await db_conn.fetchval("SELECT count(*) FROM checkpoints WHERE thread_id='active'") == 2


def test_old_photos_are_masked_but_the_current_turn_keeps_its_image():
    photo = {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}
    old = HumanMessage(content=[{"type": "text", "text": "veja"}, photo])
    now = HumanMessage(content=[{"type": "text", "text": "e esta?"}, photo])
    view = trim_messages_for_llm([old, AIMessage(content="vi"), now])
    assert view[0].content[1] == {"type": "text", "text": OLD_IMAGE_PLACEHOLDER}
    assert view[-1].content[1]["type"] == "image_url"
    assert old.content[1]["type"] == "image_url"  # persisted state is not mutated
