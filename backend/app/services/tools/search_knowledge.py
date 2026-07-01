"""Search knowledge tool — ChromaDB semantic search over company policy documents."""

import logging

from pydantic import BaseModel, Field

from app.services.tools.base import BaseTool

logger = logging.getLogger(__name__)


class SearchKnowledgeInput(BaseModel):
    query: str = Field(..., description="Search query (e.g. '餐饮报销标准', 'office supplies policy')")


class SearchKnowledgeTool(BaseTool):
    name = "search_knowledge"
    description = (
        "Search company reimbursement policy knowledge base using semantic search. "
        "Use this to look up policy rules BEFORE making reimbursement decisions. "
        "Always search for the specific category (e.g. 'meals', 'travel', 'office_supplies') "
        "and compare the invoice amount against policy limits."
    )
    args_schema = SearchKnowledgeInput

    def _run(self, query: str) -> dict:
        from app.database import SessionLocal
        from app.services.knowledge_service import KnowledgeService

        logger.info(f"[search_knowledge] query='{query}'")

        db = SessionLocal()
        try:
            svc = KnowledgeService(db)

            # Count active knowledge bases first
            bases = svc.list_bases(only_active=True)
            kb_count = len(bases)
            doc_count = 0
            for kb in bases:
                doc_count += svc.get_document_count(kb.id)

            logger.info(f"[search_knowledge] active KBs={kb_count}, total docs={doc_count}")

            if kb_count == 0:
                return {
                    "total_results": 0,
                    "results": [],
                    "hint": "没有可用的知识库。请先在管理后台创建知识库并上传报销政策文档。",
                }

            results = svc.search(query)
            logger.info(f"[search_knowledge] top result scores: {[r.get('score', 0) for r in results[:5]]}")

            return {
                "total_results": len(results),
                "results": [
                    {
                        "chunk_id": r["chunk_id"],
                        "snippet": r["snippet"],
                        "kb_name": r["kb_name"],
                        "filename": r["filename"],
                        "score": r["score"],
                    }
                    for r in results[:5]
                ],
            }
        except Exception as e:
            logger.exception(f"[search_knowledge] error: {e}")
            return {"total_results": 0, "results": [], "error": str(e)}
        finally:
            db.close()
