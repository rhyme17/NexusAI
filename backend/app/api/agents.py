from fastapi import APIRouter, Depends, Query, status

from fastapi import HTTPException

from ..models.agent import Agent, AgentRegister, AgentStatusUpdate
from ..services.store import get_store
from ..services.store_contract import StoreContract

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("", response_model=Agent, status_code=status.HTTP_201_CREATED, summary="Register Agent")
def register_agent(
    payload: AgentRegister,
    store: StoreContract = Depends(get_store),
) -> Agent:
    return store.register_agent(payload)


@router.get("", response_model=list[Agent], summary="List Agents")
def list_agents(
    skill: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    store: StoreContract = Depends(get_store),
) -> list[Agent]:
    agents = store.list_agents()
    if status_filter:
        normalized_status = status_filter.strip().lower()
        agents = [agent for agent in agents if agent.status.value == normalized_status]
    if skill:
        normalized_skill = skill.strip().lower()
        if normalized_skill:
            agents = [
                agent
                for agent in agents
                if any(normalized_skill in candidate.lower() for candidate in agent.skills)
            ]
    return agents


@router.patch("/{agent_id}/status", response_model=Agent, summary="Update Agent Status")
def update_agent_status(
    agent_id: str,
    payload: AgentStatusUpdate,
    store: StoreContract = Depends(get_store),
) -> Agent:
    updated = store.update_agent_status(agent_id, payload.status)
    if not updated:
        raise HTTPException(status_code=404, detail="Agent not found")
    return updated


