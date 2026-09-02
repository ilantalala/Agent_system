from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
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