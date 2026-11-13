from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.dependencies import get_current_user, get_owned_agent
from app.models import Agent, AgentVersion, User
from app.schemas import AgentCreate, AgentRead, AgentVersionRead

router=APIRouter(prefix="/agents", tags=["agents"])


@router.post("",response_model=AgentRead, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent = Agent(name=payload.name, owner_id=current_user.id)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent

@router.get("", response_model=list[AgentRead])
def list_agents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agents = db.scalars(
        select(Agent).
        where(Agent.owner_id == current_user.id)
        .order_by(Agent.id)
    ).all()
    return agents

@router.get("/{agent_id}", response_model=AgentRead)
def get_agent(agent: Agent = Depends(get_owned_agent)):
    return agent

@router.delete("/{agent_id}",status_code= status.HTTP_204_NO_CONTENT)
def delete_agent(
    agent: Agent = Depends(get_owned_agent),
    db: Session = Depends(get_db),
):
    db.delete(agent)
    db.commit()

@router.post("/{agent_id}/finalize", response_model=AgentRead)
def finalize_agent(
    agent: Agent = Depends(get_owned_agent),
    db: Session = Depends(get_db),
):
    agent = db.scalars(
        select(Agent)
        .where(Agent.id == agent.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()

    if agent.draft_system_prompt is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent has no draft system prompt to finalize",
        )
    if (
        agent.live_version is not None
        and agent.draft_system_prompt == agent.live_version.system_prompt
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Draft is identical to the live version",
        )

    max_number = db.scalar(
        select(func.max(AgentVersion.number)).where(
            AgentVersion.agent_id == agent.id
        )
    )
    next_number = (max_number or 0) + 1

    version = AgentVersion(
        agent=agent,
        number=next_number,
        system_prompt=agent.draft_system_prompt,
    )
    agent.live_version = version
    agent.status = "approved"
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/{agent_id}/versions", response_model=list[AgentVersionRead])
def list_versions(agent: Agent = Depends(get_owned_agent)):
    return agent.versions


@router.post(
    "/{agent_id}/versions/{number}/activate",
    response_model=AgentRead,
)
def activate_version(
    number: int,
    agent: Agent = Depends(get_owned_agent),
    db: Session = Depends(get_db),
):
    version = db.scalar(
        select(AgentVersion).where(
            AgentVersion.agent_id == agent.id,
            AgentVersion.number == number,
        )
    )
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )
    if agent.live_version_id == version.id:
        return agent

    agent.live_version = version
    db.commit()
    db.refresh(agent)
    return agent
