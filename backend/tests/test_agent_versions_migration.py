import env  # noqa: F401
import io
from pathlib import Path
import unittest

from alembic import command
from alembic.config import Config


class AgentVersionsMigrationTests(unittest.TestCase):
    def migration_sql(self, *, upgrade: bool) -> str:
        output = io.StringIO()
        config = Config(
            str(Path(__file__).resolve().parents[1] / "alembic.ini"),
            stdout=output,
            output_buffer=output,
        )
        if upgrade:
            command.upgrade(config, "300716e8c355:head", sql=True)
        else:
            command.downgrade(config, "a1c3e5f7b9d2:300716e8c355", sql=True)
        return " ".join(output.getvalue().split())

    def test_upgrade_creates_versions_and_backfills_before_dropping_prompt(self) -> None:
        sql = self.migration_sql(upgrade=True)
        for statement in (
            "CREATE TABLE agent_versions",
            "UNIQUE (agent_id, number)",
            "FOREIGN KEY(agent_id) REFERENCES agents (id) ON DELETE CASCADE",
            "CREATE INDEX ix_agent_versions_agent_id ON agent_versions (agent_id)",
            "ALTER TABLE agents ADD COLUMN live_version_id INTEGER",
            "CONSTRAINT agents_live_version_id_fkey FOREIGN KEY(live_version_id) "
            "REFERENCES agent_versions (id) ON DELETE SET NULL",
        ):
            self.assertIn(statement, sql)
        insert = (
            "INSERT INTO agent_versions (agent_id, number, system_prompt) "
            "SELECT id, 1, system_prompt FROM agents WHERE system_prompt IS NOT NULL"
        )
        update = (
            "UPDATE agents SET live_version_id = v.id FROM agent_versions v "
            "WHERE v.agent_id = agents.id AND v.number = 1"
        )
        self.assertLess(sql.index(insert), sql.index(update))
        self.assertLess(sql.index(update), sql.index("ALTER TABLE agents DROP COLUMN system_prompt"))

    def test_downgrade_restores_live_prompt_before_dropping_versions(self) -> None:
        sql = self.migration_sql(upgrade=False)
        statements = (
            "ALTER TABLE agents ADD COLUMN system_prompt TEXT",
            "UPDATE agents SET system_prompt = v.system_prompt FROM agent_versions v "
            "WHERE v.id = agents.live_version_id",
            "ALTER TABLE agents DROP CONSTRAINT agents_live_version_id_fkey",
            "ALTER TABLE agents DROP COLUMN live_version_id",
            "DROP INDEX ix_agent_versions_agent_id",
            "DROP TABLE agent_versions",
        )
        positions = [sql.index(statement) for statement in statements]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
