from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.agents import schemas as agent_schemas
from app.agents import service
from app.agents.llm import ModelAdapter, default_model_adapter
from app.shared.auth import CurrentUser
from app.shared.db import DbSession
from app.shared.errors import success
from app.shared.schemas import AgentConfig, AgentRun, AgentRunRequest

router = APIRouter(tags=["agents"])


def get_model_adapter(request: Request) -> ModelAdapter | None:
    """Injectable: tests set `app.state.model_adapter` (adapter, or None = not configured)."""
    if hasattr(request.app.state, "model_adapter"):
        return request.app.state.model_adapter
    return default_model_adapter()


ModelAdapterDep = Annotated[ModelAdapter | None, Depends(get_model_adapter)]


@router.get("/agent-assignments")
def list_agent_assignments(user: CurrentUser, db: DbSession):
    return success(service.list_assignments(db, user))


@router.post("/agent-assignments")
def create_agent_assignment(user: CurrentUser, db: DbSession,
                            payload: agent_schemas.AgentAssignmentWrite):
    return success(service.create_assignment(db, user, payload))


@router.put("/agent-assignments/{assignment_id}")
def update_agent_assignment(user: CurrentUser, db: DbSession, assignment_id: int,
                            payload: agent_schemas.AgentAssignmentWrite):
    return success(service.update_assignment(db, user, assignment_id, payload))


@router.post("/agent-assignments/{assignment_id}/publish")
def publish_agent_assignment(user: CurrentUser, db: DbSession, assignment_id: int):
    return success(service.publish_assignment(db, user, assignment_id))


@router.get("/agents")
def list_agents(user: CurrentUser, db: DbSession):
    return success(service.list_drafts(db, user))


@router.post("/agents")
def create_agent(user: CurrentUser, db: DbSession, payload: AgentConfig):
    return success(service.create_draft(db, user, payload))


@router.put("/agents/{agent_id}")
def save_agent(user: CurrentUser, db: DbSession, agent_id: int, payload: AgentConfig):
    return success(service.save_draft_version(db, user, agent_id, payload))


@router.get("/agents/{agent_id}/versions")
def list_agent_versions(user: CurrentUser, db: DbSession, agent_id: int):
    return success(service.list_draft_versions(db, user, agent_id))


@router.post("/agent-runs")
def create_agent_run(user: CurrentUser, db: DbSession, payload: AgentRunRequest,
                     adapter: ModelAdapterDep):
    return success(service.create_run(db, user, payload, adapter))


@router.get("/agent-runs")
def list_agent_runs(user: CurrentUser, db: DbSession,
                    agent_id: int | None = None, submission_id: int | None = None,
                    limit: int = Query(default=50, ge=1, le=100)):
    return success(service.list_runs(db, user, agent_id=agent_id,
                                     submission_id=submission_id, limit=limit))


@router.post("/agent-submissions")
def create_agent_submission(user: CurrentUser, db: DbSession,
                            payload: agent_schemas.AgentSubmissionWrite):
    return success(service.create_submission(db, user, payload))


@router.get("/agent-submissions")
def list_agent_submissions(user: CurrentUser, db: DbSession,
                           assignment_id: int | None = None):
    return success(service.list_submissions(db, user, assignment_id=assignment_id))


@router.post("/agent-submissions/{submission_id}/review")
def review_agent_submission(user: CurrentUser, db: DbSession, submission_id: int,
                            payload: agent_schemas.AgentSubmissionReview):
    return success(service.review_submission(db, user, submission_id, payload))


@router.post("/agent-submissions/{submission_id}/publish")
def publish_agent_submission(user: CurrentUser, db: DbSession, submission_id: int):
    return success(service.publish_submission(db, user, submission_id))


@router.get("/agent-publications")
def list_agent_publications(user: CurrentUser, db: DbSession):
    return success(service.list_publications(db, user))


@router.post("/agent-publications/{publication_id}/preview")
def preview_agent_publication(user: CurrentUser, db: DbSession, publication_id: int,
                              payload: agent_schemas.AgentPublicationPreview,
                              adapter: ModelAdapterDep):
    return success(service.preview_publication(db, user, publication_id, payload, adapter))
