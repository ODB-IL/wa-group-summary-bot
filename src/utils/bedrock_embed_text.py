import asyncio
import json
from typing import List
import boto3
from functools import partial


class BedrockEmbeddingClient:
    """AWS Bedrock client for Titan Text Embeddings V2"""

    def __init__(self, region_name: str = "eu-central-1"):
        self.client = boto3.client("bedrock-runtime", region_name=region_name)
        self.model_id = "amazon.titan-embed-text-v2:0"

    def _embed_sync(self, texts: List[str]) -> List[List[float]]:
        """
        Synchronous embedding method (runs in executor)
        """
        embeddings = []

        # Titan processes one text at a time
        for text in texts:
            body = json.dumps({"inputText": text})

            response = self.client.invoke_model(
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            embeddings.append(response_body["embedding"])

        return embeddings

    async def embed(
        self, texts: List[str], batch_size: int = 128
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of texts using Bedrock Titan

        Args:
            texts: List of text strings to embed
            batch_size: Number of texts to process at once (Titan supports 1 at a time)

        Returns:
            List of embedding vectors
        """
        # Run synchronous boto3 call in executor to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, partial(self._embed_sync, texts))


async def bedrock_embed_text(
    embedding_client: BedrockEmbeddingClient, input: List[str]
) -> List[List[float]]:
    """
    Embed text using AWS Bedrock Titan embeddings

    Args:
        embedding_client: BedrockEmbeddingClient instance
        input: List of text strings to embed

    Returns:
        List of embedding vectors
    """
    return await embedding_client.embed(input)
