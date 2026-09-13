from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

from config import CHROMA_DB_PATH, COLLECTION_NAME, DATA_DIR

# Optional embedding model
try:
    from chromadb.utils import embedding_functions

    EMBEDDING_FUNCTION = (
        embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    )
except Exception:
    EMBEDDING_FUNCTION = None


# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------

logger = logging.getLogger(__name__)

if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def safe_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chroma metadata only supports primitive values int float bool and strings.
    """

    cleaned = {}

    for key, value in metadata.items():

        if value is None:
            cleaned[key] = ""

        elif isinstance(value, (str, int, float, bool)):
            cleaned[key] = value

        else:
            cleaned[key] = str(value)

    return cleaned


def _get_or_create_collection(client):
    """
    Create or load collection.
    """

    try:

        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=EMBEDDING_FUNCTION,
        )

        logger.info(
            "Loaded existing collection: %s",
            COLLECTION_NAME,
        )

        return collection

    except Exception:

        collection = client.create_collection(
            name=COLLECTION_NAME,
            embedding_function=EMBEDDING_FUNCTION,
            metadata={
                "description": (
                    "Sales and marketing data "
                    "for AI report generation"
                )
            },
        )

        logger.info(
            "Created collection: %s",
            COLLECTION_NAME,
        )

        return collection


# ------------------------------------------------------------------
# Initialization
# ------------------------------------------------------------------

def initialize_chromadb():
    """
    Initialize ChromaDB client and collection.

    Returns:
        (client, collection)
    """

    client = chromadb.PersistentClient(
        path=CHROMA_DB_PATH,
        settings=Settings(
            anonymized_telemetry=False
        ),
    )

    collection = _get_or_create_collection(client)

    # A new deployment starts with an empty persistent directory. Populate it
    # automatically, and repair a partially populated collection after an
    # interrupted write.
    sales_data, marketing_data = load_source_data()
    expected_count = len(sales_data) + len(marketing_data)
    if collection.count() != expected_count:
        indexed = load_data_to_vectordb(collection, sales_data, marketing_data)
        if not indexed:
            raise RuntimeError(
                "The ChromaDB collection is empty and no valid records could be "
                f"loaded from {DATA_DIR}."
            )

    return client, collection


# ------------------------------------------------------------------
# Data Loading
# ------------------------------------------------------------------

def _load_json_list(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required dataset not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError(f"Dataset must contain a JSON array: {path}")

    records = [item for item in data if isinstance(item, dict)]
    if not records:
        raise ValueError(f"Dataset contains no valid records: {path}")
    return records


def load_source_data() -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load and validate the bundled sales and marketing datasets."""
    data_dir = Path(DATA_DIR)
    return (
        _load_json_list(data_dir / "sales_data.json"),
        _load_json_list(data_dir / "marketing_data.json"),
    )

def load_data_to_vectordb(
    collection,
    sales_data: List[Dict[str, Any]],
    marketing_data: List[Dict[str, Any]],
):
    """
    Load sales + marketing records into ChromaDB.
    """
    documents = []
    
    metadatas = []
    ids = []

    # ----------------------------------------------------------
    # Sales records
    # ----------------------------------------------------------

    for index, sale in enumerate(sales_data, start=1):

        documents.append(
            sale.get("description", "")
        )

        metadatas.append(
            safe_metadata(
                {
                    "type": "sales",
                    "id": sale.get("id"),
                    "product": sale.get("product"),
                    "category": sale.get("category"),
                    "revenue": sale.get("revenue"),
                    "units_sold": sale.get("units_sold"),
                    "region": sale.get("region"),
                    "quarter": sale.get("quarter"),
                    "customer_segment": sale.get(
                        "customer_segment"
                    ),
                    "sales_rep": sale.get(
                        "sales_rep"
                    ),
                }
            )
        )

        ids.append(
            f"sales_{sale.get('id') or index}"
        )

    # ----------------------------------------------------------
    # Marketing records
    # ----------------------------------------------------------

    for index, campaign in enumerate(marketing_data, start=1):

        documents.append(
            campaign.get(
                "description",
                "",
            )
        )

        metadatas.append(
            safe_metadata(
                {
                    "type": "marketing",
                    "id": campaign.get("id"),
                    "campaign_name": campaign.get(
                        "campaign_name"
                    ),
                    "channel": campaign.get(
                        "channel"
                    ),
                    "budget": campaign.get(
                        "budget"
                    ),
                    "impressions": campaign.get(
                        "impressions"
                    ),
                    "clicks": campaign.get(
                        "clicks"
                    ),
                    "conversions": campaign.get(
                        "conversions"
                    ),
                    "quarter": campaign.get(
                        "quarter"
                    ),
                    "target_segment": campaign.get(
                        "target_segment"
                    ),
                }
            )
        )

        ids.append(
            f"marketing_{campaign.get('id') or index}"
        )

    if not documents:
        logger.warning(
            "No documents supplied for indexing."
        )
        return 0

    try:

        collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

    except AttributeError:

        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

    logger.info(
        "Indexed %s documents.",
        len(documents),
    )

    return len(documents)


# ------------------------------------------------------------------
# Querying
# ------------------------------------------------------------------

def query_vectordb(
    collection,
    query_text: str,
    n_results: int = 5,
    filter_dict: Optional[Dict[str, Any]] = None,
    where: Optional[Dict[str, Any]] = None,
):
    """
    Query ChromaDB.

    Supports both:
        filter_dict=
        where=

    Compatible with enhanced rag_retrieval.py
    """

    effective_filter = (
        filter_dict or where
    )

    collection_size = collection.count()
    if collection_size <= 0:
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    query_params = {
        "query_texts": [query_text],
        "n_results": max(1, min(int(n_results), collection_size)),
    }

    if effective_filter:
        query_params["where"] = (
            effective_filter
        )

    results = collection.query(
        **query_params
    )

    return results


# ------------------------------------------------------------------
# Statistics
# ------------------------------------------------------------------
# Tells How many documents are in the collection
def get_collection_stats(collection):
    """
    Basic collection stats.
    """

    count = collection.count()

    return {
        "collection_name": collection.name,
        "total_documents": count,
    }

# How many belong to each category
def get_collection_breakdown(collection):
    """
    Counts docs by type.
    """

    data = collection.get(
        include=["metadatas"]
    )

    sales_count = 0
    marketing_count = 0

    for meta in data.get(
        "metadatas",
        [],
    ):

        if (
            meta.get("type")
            == "sales"
        ):
            sales_count += 1

        elif (
            meta.get("type")
            == "marketing"
        ):
            marketing_count += 1

    return {
        "sales_documents": sales_count,
        "marketing_documents": marketing_count,
        "total_documents": (
            sales_count
            + marketing_count
        ),
    }


# ------------------------------------------------------------------
# Maintenance
# ------------------------------------------------------------------
# Then The delete older than 30 days
def clear_collection(
    client,
    collection_name,
):
    """
    Delete collection.
    """

    try:

        client.delete_collection(
            name=collection_name
        )

        logger.info(
            "Deleted collection: %s",
            collection_name,
        )

    except Exception as e:

        logger.warning(
            "Unable to delete collection %s: %s",
            collection_name,
            e,
        )


# ------------------------------------------------------------------
# Debugging
# ------------------------------------------------------------------

def search_and_preview(
    collection,
    query,
    n_results=5,
):
    """
    Print retrieved docs for debugging.
    """

    results = query_vectordb(
        collection,
        query,
        n_results=n_results,
    )

    docs = (
        results.get(
            "documents",
            [[]],
        )[0]
        if results
        else []
    )

    print("\nRetrieved Documents")
    print("-" * 60)

    for i, doc in enumerate(
        docs,
        start=1,
    ):

        preview = (
            doc[:300]
            if isinstance(doc, str)
            else str(doc)[:300]
        )

        print(f"{i}. {preview}")

    return results


# ------------------------------------------------------------------
# Test
# ------------------------------------------------------------------

if __name__ == "__main__":

    client, collection = (
        initialize_chromadb()
    )

    print(
        "\nCollection Stats:"
    )
    print(
        get_collection_stats(
            collection
        )
    )

    print(
        "\nCollection Breakdown:"
    )
    print(
        get_collection_breakdown(
            collection
        )
    )
