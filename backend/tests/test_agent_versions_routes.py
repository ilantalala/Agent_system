import env  # noqa: F401

import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies import get_current_user
from app.main import app
from app.models import Agent, AgentVersion, User


class AgentVersionRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.Session()

        self.owner = User(
            email="owner@example.com",
            hashed_password="x",
            role="user",
        )
        self.other = User(
            email="other@example.com",
            hashed_password="x",
            role="user",
        )
        self.db.add_all([self.owner, self.other])
        self.db.flush()
        self.agent = Agent(
            name="Demo",
            owner_id=self.owner.id,
            draft_system_prompt="You are version one.",
        )
        self.db.add(self.agent)
        self.db.commit()
        self.db.refresh(self.agent)
        self.db.refresh(self.owner)

        self.current_user = self.owner

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        def override_get_current_user():
            return self.db.merge(self.current_user)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        # No `with` — lifespan must not run (no Postgres).
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def _version_count(self, agent_id: int | None = None) -> int:
        agent_id = agent_id or self.agent.id
        return self.db.scalar(
            select(func.count()).select_from(AgentVersion).where(
                AgentVersion.agent_id == agent_id
            )
        )

    def _reload_agent(self) -> Agent:
        self.db.expire_all()
        return self.db.get(Agent, self.agent.id)

    def test_finalize_creates_v1(self):
        response = self.client.post(f"/agents/{self.agent.id}/finalize")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "approved")
        self.assertEqual(body["live_version_number"], 1)
        self.assertEqual(body["system_prompt"], "You are version one.")
        self.assertEqual(self._version_count(), 1)

    def test_editing_draft_does_not_change_live_or_versions(self):
        self.client.post(f"/agents/{self.agent.id}/finalize")
        agent = self._reload_agent()
        agent.draft_system_prompt = "edited draft"
        self.db.commit()

        response = self.client.get(f"/agents/{self.agent.id}")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["system_prompt"], "You are version one.")
        self.assertEqual(body["draft_system_prompt"], "edited draft")
        self.assertEqual(body["live_version_number"], 1)

        versions = self.client.get(f"/agents/{self.agent.id}/versions").json()
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]["system_prompt"], "You are version one.")

    def test_re_finalize_after_draft_change_creates_v2(self):
        self.client.post(f"/agents/{self.agent.id}/finalize")
        agent = self._reload_agent()
        agent.draft_system_prompt = "You are version two."
        self.db.commit()

        response = self.client.post(f"/agents/{self.agent.id}/finalize")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["live_version_number"], 2)
        self.assertEqual(body["system_prompt"], "You are version two.")
        self.assertEqual(body["status"], "approved")

        versions = self.client.get(f"/agents/{self.agent.id}/versions").json()
        self.assertEqual(
            [(v["number"], v["system_prompt"], v["is_live"]) for v in versions],
            [
                (1, "You are version one.", False),
                (2, "You are version two.", True),
            ],
        )

    def test_finalize_400_with_no_draft(self):
        agent = self._reload_agent()
        agent.draft_system_prompt = None
        self.db.commit()

        response = self.client.post(f"/agents/{self.agent.id}/finalize")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Agent has no draft system prompt to finalize",
        )
        self.assertEqual(self._version_count(), 0)

    def test_finalize_400_when_draft_equals_live(self):
        self.client.post(f"/agents/{self.agent.id}/finalize")
        self.assertEqual(self._version_count(), 1)

        response = self.client.post(f"/agents/{self.agent.id}/finalize")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Draft is identical to the live version",
        )
        self.assertEqual(self._version_count(), 1)

    def test_list_versions_ordered_with_is_live(self):
        self.client.post(f"/agents/{self.agent.id}/finalize")
        agent = self._reload_agent()
        agent.draft_system_prompt = "You are version two."
        self.db.commit()
        self.client.post(f"/agents/{self.agent.id}/finalize")

        response = self.client.get(f"/agents/{self.agent.id}/versions")
        self.assertEqual(response.status_code, 200)
        versions = response.json()
        self.assertEqual([v["number"] for v in versions], [1, 2])
        self.assertEqual([v["is_live"] for v in versions], [False, True])

    def test_activate_v1_after_v2(self):
        self.client.post(f"/agents/{self.agent.id}/finalize")
        agent = self._reload_agent()
        agent.draft_system_prompt = "You are version two."
        self.db.commit()
        self.client.post(f"/agents/{self.agent.id}/finalize")

        response = self.client.post(f"/agents/{self.agent.id}/versions/1/activate")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["live_version_number"], 1)
        self.assertEqual(body["system_prompt"], "You are version one.")

        versions = self.client.get(f"/agents/{self.agent.id}/versions").json()
        self.assertEqual(
            [(v["number"], v["system_prompt"], v["is_live"]) for v in versions],
            [
                (1, "You are version one.", True),
                (2, "You are version two.", False),
            ],
        )

    def test_activate_already_live_is_noop(self):
        self.client.post(f"/agents/{self.agent.id}/finalize")
        agent = self._reload_agent()
        live_id = agent.live_version_id

        response = self.client.post(f"/agents/{self.agent.id}/versions/1/activate")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["live_version_number"], 1)
        self.assertEqual(body["system_prompt"], "You are version one.")

        agent = self._reload_agent()
        self.assertEqual(agent.live_version_id, live_id)
        self.assertEqual(self._version_count(), 1)

    def test_activate_unknown_number_404(self):
        self.client.post(f"/agents/{self.agent.id}/finalize")
        response = self.client.post(f"/agents/{self.agent.id}/versions/99/activate")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Version not found")

    def test_other_user_gets_404_and_nothing_changes(self):
        self.client.post(f"/agents/{self.agent.id}/finalize")
        agent = self._reload_agent()
        agent.draft_system_prompt = "You are version two."
        self.db.commit()
        before_count = self._version_count()
        before_live = agent.live_version_id

        self.current_user = self.other
        for method, path in [
            ("post", f"/agents/{self.agent.id}/finalize"),
            ("get", f"/agents/{self.agent.id}/versions"),
            ("post", f"/agents/{self.agent.id}/versions/1/activate"),
        ]:
            response = getattr(self.client, method)(path)
            self.assertEqual(response.status_code, 404, path)
            self.assertEqual(response.json()["detail"], "Agent not found")

        self.current_user = self.owner
        agent = self._reload_agent()
        self.assertEqual(self._version_count(), before_count)
        self.assertEqual(agent.live_version_id, before_live)
        self.assertEqual(agent.draft_system_prompt, "You are version two.")

    def test_delete_agent_removes_versions(self):
        agent_id = self.agent.id
        self.client.post(f"/agents/{agent_id}/finalize")
        agent = self._reload_agent()
        agent.draft_system_prompt = "You are version two."
        self.db.commit()
        self.client.post(f"/agents/{agent_id}/finalize")
        self.assertEqual(self._version_count(agent_id), 2)

        response = self.client.delete(f"/agents/{agent_id}")
        self.assertEqual(response.status_code, 204)
        self.db.expire_all()
        self.assertEqual(
            self.db.scalars(select(AgentVersion)).all(),
            [],
        )
        self.assertIsNone(self.db.get(Agent, agent_id))


if __name__ == "__main__":
    unittest.main()
