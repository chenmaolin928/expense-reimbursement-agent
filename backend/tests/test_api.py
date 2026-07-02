"""API integration tests — verify HTTP endpoints."""


class TestAuthAPI:
    """Authentication endpoints."""

    def test_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_login_admin(self, admin_token):
        assert admin_token.startswith("sim_admin_")

    def test_login_employee(self, employee_token):
        assert employee_token.startswith("sim_employee_")

    def test_login_wrong_password(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_register(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "newuser", "password": "pass123", "role": "employee"
        })
        assert resp.status_code == 201
        assert resp.json()["role"] == "employee"

    def test_register_duplicate(self, client, admin_token):
        resp = client.post("/api/v1/auth/register", json={
            "username": "admin", "password": "pass123", "role": "employee"
        })
        assert resp.status_code == 409


class TestKnowledgeAPI:
    """Knowledge base endpoints."""

    def test_create_kb_admin(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.post("/api/v1/knowledge/bases", json={
            "name": "Test KB", "description": "test"
        }, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["name"] == "Test KB"

    def test_create_kb_employee_forbidden(self, client, employee_token):
        headers = {"Authorization": f"Bearer {employee_token}"}
        resp = client.post("/api/v1/knowledge/bases", json={
            "name": "Hack", "description": "should fail"
        }, headers=headers)
        assert resp.status_code == 403

    def test_list_kbs(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        # Create one
        client.post("/api/v1/knowledge/bases", json={"name": "A", "description": ""}, headers=headers)
        resp = client.get("/api/v1/knowledge/bases")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_upload_document(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        client.post("/api/v1/knowledge/bases", json={"name": "Doc KB", "description": ""}, headers=headers)
        resp = client.post(
            "/api/v1/knowledge/bases/1/documents",
            files={"file": ("test.txt", b"Company policy: meals max 300 CNY per meal. "
                                      b"Travel: hotel max 500 CNY per night. "
                                      b"Office supplies: max 2000 CNY per month.")},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["filename"] == "test.txt"

    def test_search(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        client.post("/api/v1/knowledge/bases", json={"name": "S KB", "description": ""}, headers=headers)
        client.post(
            "/api/v1/knowledge/bases/1/documents",
            files={"file": ("p.txt", b"Meals allowance: breakfast 30, lunch 60, dinner 100. "
                                      b"Travel allowance: hotel 500 per night. "
                                      b"Office supplies: up to 2000 per month.")},
            headers=headers,
        )
        resp = client.get("/api/v1/knowledge/search?q=meals")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestChatAPI:
    """Chat and session endpoints."""

    def test_create_session(self, client, employee_token):
        headers = {"Authorization": f"Bearer {employee_token}"}
        resp = client.post("/api/v1/chat/sessions", json={"title": "Test"}, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["title"] == "Test"

    def test_list_sessions(self, client, employee_token):
        headers = {"Authorization": f"Bearer {employee_token}"}
        client.post("/api/v1/chat/sessions", json={"title": "S1"}, headers=headers)
        client.post("/api/v1/chat/sessions", json={"title": "S2"}, headers=headers)
        resp = client.get("/api/v1/chat/sessions", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_chat_simple(self, client, employee_token):
        """Send a simple message without invoice — should get text response."""
        headers = {"Authorization": f"Bearer {employee_token}"}
        r = client.post("/api/v1/chat/sessions", json={"title": "Chat"}, headers=headers)
        sid = r.json()["id"]

        resp = client.post("/api/v1/chat", json={
            "session_id": sid,
            "message": "What can you do?",
        }, headers=headers)
        assert resp.status_code == 200
        body = resp.text
        # Starlette test client encodes SSE data — check key markers
        assert "data:" in body
        assert ("message" in body or "done" in body)

    def test_chat_with_invoice(self, client, employee_token):
        """Send invoice — should trigger tool calls."""
        headers = {"Authorization": f"Bearer {employee_token}"}
        r = client.post("/api/v1/chat/sessions", json={"title": "Invoice"}, headers=headers)
        sid = r.json()["id"]

        resp = client.post("/api/v1/chat", json={
            "session_id": sid,
            "message": "reimburse this",
            "attachments": ["receipt.png"],
        }, headers=headers)
        assert resp.status_code == 200
        body = resp.text
        # Should contain scan_invoice tool call
        assert "scan_invoice" in body
        assert '"type": "done"' in body

    def test_chat_policy_query_uses_tool_and_returns_final_answer(self, client, employee_token):
        headers = {"Authorization": f"Bearer {employee_token}"}
        r = client.post("/api/v1/chat/sessions", json={"title": "Policy"}, headers=headers)
        sid = r.json()["id"]

        resp = client.post("/api/v1/chat", json={
            "session_id": sid,
            "message": "What meal expenses can be reimbursed?",
        }, headers=headers)
        assert resp.status_code == 200
        body = resp.text
        assert "search_knowledge" in body
        assert '"type": "message"' in body
        # Plan JSON is correctly encapsulated in a "plan" event (not leaked into chat bubbles)
        assert '"type": "plan"' in body
        assert '"type": "done"' in body

    def test_delete_session(self, client, employee_token):
        headers = {"Authorization": f"Bearer {employee_token}"}
        r = client.post("/api/v1/chat/sessions", json={"title": "Del me"}, headers=headers)
        sid = r.json()["id"]
        resp = client.delete(f"/api/v1/chat/sessions/{sid}", headers=headers)
        assert resp.status_code == 204

    def test_upload_file(self, client, employee_token):
        headers = {"Authorization": f"Bearer {employee_token}"}
        r = client.post("/api/v1/chat/sessions", json={"title": "Upload"}, headers=headers)
        sid = r.json()["id"]
        resp = client.post(
            f"/api/v1/chat/sessions/{sid}/upload",
            files={"file": ("invoice.png", b"fake image data")},
            headers=headers,
        )
        assert resp.status_code == 200
        assert "file_path" in resp.json()

    def test_correct_search_applies_rule_engine_flags(self, client, employee_token, monkeypatch):
        import json
        from app.api import chat as chat_api
        from app.services.knowledge_service import KnowledgeService

        # Seed a published policy in DB for DatabaseBackend
        from app.database import SessionLocal
        from app.infrastructure.orm import Policy, PolicyVersion
        from app.domain.enums import PolicyStatus
        from datetime import datetime

        db = SessionLocal()
        try:
            policy = Policy(
                name="Test Policy",
                description="",
                policy_type="expense",
                status=PolicyStatus.PUBLISHED,
                enterprise="default",
                created_by=0,
            )
            db.add(policy)
            db.flush()

            policy_json = {
                "doc_id": "",
                "title": "Test Policy",
                "version": "1.0",
                "domains": [{
                    "id": "entertainment",
                    "name": "商务招待",
                    "rules": [
                        {
                            "id": "ent_ratio",
                            "type": "ratio",
                            "title": "比例",
                            "scope": {"role": None, "region": None, "amount_range": None},
                            "condition": "",
                            "value": 0.5,
                            "unit": "percent",
                            "raw_text": "商务招待报销比例 50%",
                        },
                        {
                            "id": "ent_approval",
                            "type": "approval",
                            "title": "审批阈值",
                            "scope": {"role": None, "region": None, "amount_range": None},
                            "condition": "超过500元",
                            "value": 500,
                            "unit": "yuan",
                            "raw_text": "商务招待超过500元需审批",
                        },
                    ],
                }],
            }
            version = PolicyVersion(
                policy_id=policy.id,
                version_number=1,
                status=PolicyStatus.PUBLISHED,
                policy_json=policy_json,
                created_by=0,
                published_at=datetime.utcnow(),
            )
            db.add(version)
            db.flush()
            policy.current_version_id = version.id
            db.commit()
        finally:
            db.close()

        monkeypatch.setattr(
            KnowledgeService,
            "search",
            lambda self, query, kb_id=None, top_k=5: [{
                "chunk_id": "c1",
                "snippet": "商务招待超过500元需审批",
                "kb_name": "政策库",
                "filename": "policy.pdf",
                "score": 0.98,
            }],
        )

        headers = {"Authorization": f"Bearer {employee_token}"}
        r = client.post("/api/v1/chat/sessions", json={"title": "Correct Search"}, headers=headers)
        sid = r.json()["id"]

        resp = client.post(
            f"/api/v1/chat/sessions/{sid}/correct-search",
            json={
                "invoice_path": "receipt.png",
                "corrected_fields": {
                    "category": "entertainment",
                    "vendor": "VIP Club",
                    "amount": 1200,
                },
            },
            headers=headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "需主管审批" in data["summary"]
        assert data["breakdown"]["rule_flags"]["need_approval"] is True


class TestReimbursementAPI:
    """Reimbursement approval endpoints."""

    def test_approve_nonexistent(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.post("/api/v1/reimbursements/999/approve", json={}, headers=headers)
        assert resp.status_code == 404

    def test_timeline(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.get("/api/v1/reimbursements/1/timeline", headers=headers)
        # May return empty or 200 depending on DB state
        assert resp.status_code in (200, 404)


class TestAdminAPI:
    """Admin endpoints."""

    def test_stats(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.get("/api/v1/admin/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_reports" in data
        assert "total_employees" in data
        assert "total_users" in data

    def test_employees(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.get("/api/v1/admin/employees", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_pii_cleanup(self, client, admin_token):
        headers = {"Authorization": f"Bearer {admin_token}"}
        resp = client.post("/api/v1/admin/pii/cleanup", json={}, headers=headers)
        assert resp.status_code == 200
        assert "deleted_count" in resp.json()


class TestEmployeeAPI:
    """Employee endpoints."""

    def test_list_employees(self, client):
        resp = client.get("/api/v1/employees")
        assert resp.status_code == 200

    def test_get_employee(self, client, admin_token):
        resp = client.get("/api/v1/employees/1")
        assert resp.status_code in (200, 404)
