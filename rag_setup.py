import chromadb
import json
from sentence_transformers import SentenceTransformer

embedder = SentenceTransformer('all-MiniLM-L6-v2')
client = chromadb.PersistentClient(path="./chroma_storage")


def create_collection(name):
    # Create or get a collection
    collection = client.get_or_create_collection(name)

def enter_information(collection_name,ocr_text,json,ids):
    embedding = embedder.encode([ocr_text])[0]
    collection = client.get_or_create_collection(collection_name)
    collection.add(
    ids=[ids],
    documents=[ocr_text],
    embeddings=[embedding],
    metadatas=[json]  
    )


def clear_collection(client, collection_name):
    try:
        # Get the collection (create if doesn't exist, optional)
        collection = client.get_or_create_collection(name=collection_name)
        
        # Get all document IDs
        results = collection.get()
        ids = results['ids']

        if not ids:
            print(f"Collection '{collection_name}' is already empty.")
            return False

        # Delete all documents by IDs
        collection.delete(ids=ids)
        print(f"All documents deleted from collection '{collection_name}'.")
        return True

    except Exception as e:
        print(f"Error clearing collection '{collection_name}': {e}")
        return False
    

def comparison(new_ocr_text,collection_name):
    new_embedding = embedder.encode([new_ocr_text])[0]

    # Query similar invoices
    collection = client.get_or_create_collection(name=collection_name)
    results = collection.query(
        query_embeddings=[new_embedding],
        n_results=3
    )
    return results

def view_collection(collection_name):
    collection = client.get_or_create_collection(name=collection_name)
    results = collection.get()
    print("IDs:", results['ids'])



    






