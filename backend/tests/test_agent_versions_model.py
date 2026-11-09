import env  # noqa: F401
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Agent, AgentVersion, User
from app.schemas import AgentRead, AgentVersionRead


class AgentVersionModelTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        owner = User(email="owner@example.com", hashed_password="x")
        self.agent = Agent(name="Demo", owner=owner, draft_system_prompt="draft")
        self.db.add(self.agent)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def add_version(self, number: int, prompt: str) -> AgentVersion:
        version = AgentVersion(agent=self.agent, number=number, system_prompt=prompt)
        self.db.add(version)
        self.db.flush()
        return version

    def test_new_agent_has_no_live_version(self):
        read = AgentRead.model_validate(self.agent)
        self.assertIsNone(read.system_prompt)
        self.assertIsNone(read.live_version_number)

    def test_system_prompt_follows_the_live_version(self):
        v1 = self.add_version(1, "one")
        v2 = self.add_version(2, "two")
        self.agent.live_version = v2
        self.db.commit()
        self.assertEqual(AgentRead.model_validate(self.agent).system_prompt, "two")
        self.agent.live_version = v1
        self.db.commit()
        read = AgentRead.model_validate(self.agent)
        self.assertEqual((read.system_prompt, read.live_version_number), ("one", 1))

    def test_version_read_marks_only_the_live_one(self):
        self.add_version(1, "one")
        self.agent.live_version = self.add_version(2, "two")
        self.db.commit()
        reads = [AgentVersionRead.model_validate(v) for v in self.agent.versions]
        self.assertEqual([(r.number, r.is_live) for r in reads], [(1, False), (2, True)])

    def test_deleting_the_agent_deletes_its_versions(self):
        self.agent.live_version = self.add_version(1, "one")
        self.db.commit()
        self.db.delete(self.agent)
        self.db.commit()
        self.assertEqual(self.db.scalars(select(AgentVersion)).all(), [])


if __name__ == "__main__":
    unittest.main()
