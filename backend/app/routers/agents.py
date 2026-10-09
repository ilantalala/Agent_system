from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.dependencies import get_current_user, get_owned_agent
from app.models import Agent, User
from app.schemas import AgentCreate, AgentRead

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
    if agent.draft_system_prompt is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent has no draft system prompt to finalize",
        )
    if agent.status == "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent is already approved",
        )    
    agent.system_prompt = agent.draft_system_prompt
    agent.status = "approved"
    db.commit()
    db.refresh(agent)
    return agent    