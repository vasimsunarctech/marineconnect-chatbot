import os
from fastapi import APIRouter, UploadFile, Form, HTTPException,File
from app.services.document_loader import DocumentLoader
from app.services.text_splitter import TextSplitter
from app.services.embedding_model import EmbeddingModel
from app.services.qdrant_vectordb import QdrantVectorDB
from app.langchain.data_extractor import ExtractData
from app.models.vendor import create_vendor,create_vendor_table
import tempfile

router = APIRouter(prefix="/ingest", tags=["Ingestion"])

# Initialize embedding and vector DB service
embedding_model = EmbeddingModel().get()

@router.post("/new")
async def ingest_manual(file: UploadFile = File(...)):
    """
    Ingest a manual PDF into Qdrant.
    - User sends `uuid` and `file` (PDF).
    - No database is queried.
    """
    try:
        if file :
            print(file)

        with tempfile.NamedTemporaryFile(delete=False,suffix= ".pdf") as temp_file:
            temp_file.write(await file.read())
            tmp_path = temp_file.name
        # Save uploaded file temporarily 
        # temp_path = f"/tmp/_{file.filename}"#UUID remove from here 
        # with open(file, "wb") as f:
        #     f.write(await file.read())

        # Initialize pipeline services
        loader = DocumentLoader()
        splitter = TextSplitter()
        vector_db = QdrantVectorDB(collection_name=os.getenv("QDRANT_COLLECTION", "maritime"), embeddings=embedding_model)

        # Load → Split
        docs = loader.load(tmp_path)
        chunks = splitter.split(docs)

        if not chunks:
            import fitz 
            from app.utils.image_to_text import image_to_text
            doc = fitz.open(tmp_path)
            page = doc[0]
            image_info = page.get_images(full=True)[0]
            xref = image_info[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            chunks= image_to_text(image_bytes)
            print(chunks)
        # print(chunks)
        # send chunks to the bot to extract the details from pdf 
        vendor = ExtractData(chunks)
        # print(vendor)
        status = create_vendor(vendor)
        # Add chunks to Qdrant using provided UUID
        # vector_db.add_documents(chunks, document_uuid=uuid)

        return {
            "chunks_added": len(chunks),
            "status": status
        }

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Manual ingestion failed.")

@router.get("/create_vendor")
def create_vendor_in_DB():
    msg=create_vendor_table()
    return msg