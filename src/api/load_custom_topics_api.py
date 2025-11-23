import hashlib
import logging
from datetime import datetime
from typing import Annotated, Dict, Any, List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import Group, KBTopicCreate
from models.knowledge_base_topic import KBTopic
from models.upsert import bulk_upsert
from utils.bedrock_embed_text import BedrockEmbeddingClient, bedrock_embed_text
from .deps import get_db_async_session, get_text_embebedding

router = APIRouter()
logger = logging.getLogger(__name__)


class CustomTopic(BaseModel):
    subject: str
    summary: str


@router.post("/load_custom_topics")
async def load_custom_topics_api(
    topics: List[CustomTopic],
    session: Annotated[AsyncSession, Depends(get_db_async_session)],
    embedding_client: Annotated[BedrockEmbeddingClient, Depends(get_text_embebedding)],
) -> Dict[str, Any]:
    """
    Load custom knowledge base topics for all managed groups.
    Accepts a list of topics with subject and summary.
    """
    try:
        logger.info(f"Loading {len(topics)} custom topics via API")

        # Get all managed groups
        groups = await session.exec(select(Group).where(Group.managed == True))  # noqa: E712
        group_list = list(groups.all())

        if not group_list:
            return {
                "status": "error",
                "message": "No managed groups found",
            }

        # Create embeddings for all topics
        documents = [f"# {topic.subject}\n{topic.summary}" for topic in topics]
        topics_embeddings = await bedrock_embed_text(embedding_client, documents)

        total_loaded = 0
        start_time = datetime.now()

        # Load topics for each managed group
        for group in group_list:
            doc_models = [
                KBTopicCreate(
                    id=str(
                        hashlib.sha256(
                            f"{group.group_jid}_{start_time}_{topic.subject}".encode()
                        ).hexdigest()
                    ),
                    embedding=emb,
                    group_jid=group.group_jid,
                    start_time=start_time,
                    speakers="",  # No speakers for custom topics
                    summary=topic.summary,
                    subject=topic.subject,
                )
                for topic, emb in zip(topics, topics_embeddings)
            ]

            await bulk_upsert(session, [KBTopic(**doc.model_dump()) for doc in doc_models])
            total_loaded += len(doc_models)
            logger.info(f"Loaded {len(doc_models)} topics for group {group.group_name}")

        await session.commit()

        logger.info(f"Custom topics loaded successfully: {total_loaded} total")

        return {
            "status": "success",
            "message": f"Loaded {len(topics)} topics for {len(group_list)} groups",
            "topics_count": len(topics),
            "groups_count": len(group_list),
            "total_records": total_loaded,
        }

    except Exception as e:
        logger.error(f"Error loading custom topics: {str(e)}")
        raise
