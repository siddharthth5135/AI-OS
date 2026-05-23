import os
import json
import httpx
from dataclasses import dataclass
from typing import List, Optional, Union, Dict
import sqlalchemy as sa
from app.db.database import engine
from app.core.config.settings import settings

@dataclass
class PointStruct:
    id: Union[str, int]
    vector: List[float]
    payload: Dict

class PgVectorService:
    def __init__(self):
        pass

    async def initialize(self):
        """
        Connect to database and ensure vector tables are created and indexed.
        """
        await self.ensure_collections()

    async def ensure_collections(self):
        """
        Create vector tables and indices for user_memory, documents, and chats.
        """
        async with engine.begin() as conn:
            # Enable vector extension
            try:
                await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector;"))
            except Exception:
                pass

            collections = ["user_memory", "documents", "chats"]
            for col in collections:
                table_name = f"vector_{col}"
                # Create table
                await conn.execute(sa.text(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id TEXT PRIMARY KEY,
                        vector vector(384),
                        payload JSONB
                    );
                """))
                
                # Create HNSW index for fast cosine search
                try:
                    await conn.execute(sa.text(f"""
                        CREATE INDEX IF NOT EXISTS {table_name}_cosine_idx 
                        ON {table_name} USING hnsw (vector vector_cosine_ops);
                    """))
                except Exception:
                    pass

            # Mirror collection creation in Qdrant (for external port 6333 verification)
            qdrant_url = f"http://{settings.pgvector_host}:{settings.pgvector_port}"
            async with httpx.AsyncClient() as client:
                for col in collections:
                    try:
                        res = await client.get(f"{qdrant_url}/collections/{col}", timeout=2.0)
                        if res.status_code != 200:
                            await client.put(f"{qdrant_url}/collections/{col}", json={
                                "vectors": {
                                    "size": 384,
                                    "distance": "Cosine"
                                }
                            }, timeout=2.0)
                    except Exception:
                        pass

    async def upsert_points(self, collection: str, points: List[PointStruct]):
        """
        Upsert a batch of points directly to the database table and mirror to Qdrant, chunked in batches of 100.
        """
        table_name = f"vector_{collection}"
        batch_size = 100
        
        for idx in range(0, len(points), batch_size):
            batch = points[idx:idx + batch_size]
            
            # DB Transaction for this batch
            async with engine.begin() as conn:
                for p in batch:
                    # Format vector as postgres array string e.g. '[0.1, 0.2, ...]'
                    vector_str = "[" + ",".join(map(str, p.vector)) + "]"
                    await conn.execute(sa.text(f"""
                        INSERT INTO {table_name} (id, vector, payload)
                        VALUES (:id, CAST(:vector AS vector), CAST(:payload AS jsonb))
                        ON CONFLICT (id) DO UPDATE 
                        SET vector = EXCLUDED.vector, payload = EXCLUDED.payload;
                    """), {
                        "id": str(p.id),
                        "vector": vector_str,
                        "payload": json.dumps(p.payload)
                    })

            # Mirror batch to Qdrant
            qdrant_url = f"http://{settings.pgvector_host}:{settings.pgvector_port}"
            qdrant_points = []
            for p in batch:
                qdrant_points.append({
                     "id": str(p.id),
                     "vector": p.vector,
                     "payload": p.payload
                })
            try:
                async with httpx.AsyncClient() as client:
                    await client.put(
                        f"{qdrant_url}/collections/{collection}/points?wait=true",
                        json={"points": qdrant_points},
                        timeout=5.0
                    )
            except Exception:
                pass

    async def search(
        self, 
        collection: str, 
        vector: List[float], 
        limit: int = 5, 
        filter: Optional[Dict] = None, 
        score_threshold: float = 0.3
    ) -> List[Dict]:
        """
        Perform vector semantic search directly using postgres cosine operator (<=>).
        """
        table_name = f"vector_{collection}"
        vector_str = "[" + ",".join(map(str, vector)) + "]"
        
        async with engine.connect() as conn:
            query = f"""
                SELECT id, payload, CAST((1 - (vector <=> CAST(:query_vector AS vector))) AS float) as score
                FROM {table_name}
            """
            params = {
                "query_vector": vector_str,
                "threshold": score_threshold,
                "limit": limit
            }
            
            conditions = []
            if filter:
                for i, (k, v) in enumerate(filter.items()):
                    conditions.append(f"payload->>'{k}' = :val_{i}")
                    params[f"val_{i}"] = str(v)
            
            conditions.append(f"CAST((1 - (vector <=> CAST(:query_vector AS vector))) AS float) >= :threshold")
            
            query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY vector <=> CAST(:query_vector AS vector) LIMIT :limit"
            
            res = await conn.execute(sa.text(query), params)
            rows = res.fetchall()
            
            results = []
            for row in rows:
                payload_val = row[1]
                if isinstance(payload_val, str):
                    payload_val = json.loads(payload_val)
                results.append({
                    "id": row[0],
                    "payload": payload_val,
                    "score": row[2]
                })
            return results

    async def delete_by_filter(self, collection: str, filter: Dict):
        """
        Delete vector points matching the payload filter keys and values from PG and Qdrant.
        """
        table_name = f"vector_{collection}"
        async with engine.begin() as conn:
            query = f"DELETE FROM {table_name}"
            params = {}
            if filter:
                conditions = []
                for i, (k, v) in enumerate(filter.items()):
                    conditions.append(f"payload->>'{k}' = :val_{i}")
                    params[f"val_{i}"] = str(v)
                query += " WHERE " + " AND ".join(conditions)
            await conn.execute(sa.text(query), params)

        # Mirror delete to Qdrant
        qdrant_url = f"http://{settings.pgvector_host}:{settings.pgvector_port}"
        try:
            async with httpx.AsyncClient() as client:
                filter_conditions = []
                for k, v in filter.items():
                    filter_conditions.append({
                        "key": k,
                        "match": {"value": v}
                    })
                await client.post(
                    f"{qdrant_url}/collections/{collection}/points/delete",
                    json={
                        "filter": {
                            "must": filter_conditions
                        }
                    },
                    timeout=5.0
                )
        except Exception:
            pass

    async def count(self, collection: str, filter: Optional[Dict] = None) -> int:
        """
        Count vector points matching an optional payload filter.
        """
        table_name = f"vector_{collection}"
        async with engine.connect() as conn:
            query = f"SELECT count(*) FROM {table_name}"
            params = {}
            if filter:
                conditions = []
                for i, (k, v) in enumerate(filter.items()):
                    conditions.append(f"payload->>'{k}' = :val_{i}")
                    params[f"val_{i}"] = str(v)
                query += " WHERE " + " AND ".join(conditions)
            res = await conn.execute(sa.text(query), params)
            return res.scalar() or 0

_pgvector_service = PgVectorService()

def get_pgvector_service() -> PgVectorService:
    return _pgvector_service
