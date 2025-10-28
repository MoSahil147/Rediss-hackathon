from fastapi import FastAPI, HTTPException, Request, UploadFile
# from flask import Flask, request, jsonify
from mistralai import Mistral
from groq import Groq
import openai
import boto3
# import asyncpg, asyncio
# from sshtunnel import SSHTunnelForwarder
import os
import io
import tempfile
import shutil
from dotenv import load_dotenv
import json
import time
from fastapi.responses import JSONResponse
import logging
from typing import Optional, Any, Dict, Tuple
import re
import requests
from pathlib import Path
import base64, hashlib
import google.generativeai as genai
import cohere
import time
import pandas as pd
try:
    from cohere_utils import cohere_generate_text, extract_text_from_pdf
except Exception:
    cohere_generate_text = None
    # Fallback: reuse existing plumber_extract to get text from PDF
    def extract_text_from_pdf(file_path: str) -> str:
        try:
            return plumber_extract(file_path)
        except Exception:
            return ""


# from pprint import pprint



# Pydantic is a Python library for data validation and data parsing.
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # You can change to DEBUG, WARNING, etc.
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# # PostgreSQL Connection Pool, Tunnel Forwarder & DB Configuration
# db_pool: asyncpg.pool.Pool = None
# tunnel: SSHTunnelForwarder = None

# # SSH config
# SSH_HOST = "43.205.167.74"
# SSH_PORT = 22
# SSH_USER = "ec2-user"
# SSH_PEM_FILE = r"/home/prathamesh/Downloads/odex-rds-2-0.pem"

# # DB config (private inside AWS VPC)
# DB_HOST = "odexdbinstance.c7vjncpo5lsx.ap-south-1.rds.amazonaws.com"
# DB_PORT = 5432
# DB_NAME = "odextest"
# DB_USER = "postgres"
# DB_PASS = "your_db_password"


# file imports
import json_mapper
from prompts import get_invoice_prompt, do_prompt, pop_prompt,rag_invoice_prompt,rag_do_prompt, bl_prompt, bl_splitting_prompt, groq_bl_splitting_prompt, bl_prompt_groq
from document_processing_services import plumber_extract, mistral_ocr
from document_processing_services import tessaract_ocr
from classification import detect_document_type #detect_bl_document_type
from json_mapper import mapper,  sanitize_json_dict, sanitize_json, reverse_transform_json
from excel_generator import excel_template_downlaoder, process_json_to_excel, upload_to_s3
# from rapid_ocr import run_rapidocr #, pdf_utils, ocr_rapid, layout
from src import run_rapid4
# from RAPID_OCR_FINAL import run_rapid4

# Load environment variables (.env file contains AWS credentials and API Keys)
load_dotenv()

# Initialize AWS S3 client and API Key (Loading from .env file)
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
region_name = os.getenv("REGION_NAME")
api_key = os.getenv("API_KEY")
bucket_name_1=os.getenv("BUCKET_NAME")

GEMINI_API_KEY=os.getenv("GEMINI_API_KEY")



# Initialize FastAPI app
app = FastAPI()

# Initialize S3 client
s3_client = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=region_name,
)

# # Startup event to establish SSH tunnel and create PostgreSQL connection pool
# @app.on_event("startup")
# async def startup_event():
#     global db_pool, tunnel

#     # Start SSH tunnel using PEM key
#     tunnel = SSHTunnelForwarder(
#         (SSH_HOST, SSH_PORT),
#         ssh_username=SSH_USER,
#         ssh_pkey=SSH_PEM_FILE,
#         remote_bind_address=(DB_HOST, DB_PORT),
#         local_bind_address=('localhost', 6543)  # local port for asyncpg
#     )
#     tunnel.start()
#     logging.info(f"SSH tunnel established: localhost:{tunnel.local_bind_port} -> {DB_HOST}:{DB_PORT}")

#     # Create asyncpg connection pool through tunnel
#     db_pool = await asyncpg.create_pool(
#         host='localhost',
#         port=tunnel.local_bind_port,
#         user=DB_USER,
#         password=DB_PASS,
#         database=DB_NAME,
#         min_size=1,
#         max_size=10
#     )
#     logging.info("PostgreSQL connection pool created.")

# @app.on_event("shutdown")
# async def shutdown_event():
#     global db_pool, tunnel
#     if db_pool:
#         await db_pool.close()
#         logging.info("PostgreSQL connection pool closed.")
#     if tunnel:
#         tunnel.stop()
#         logging.info("SSH tunnel closed.")

# Processing the S3 URL to extract bucket name and object key. S3 URLs typically look like "s3://bucket-name/object-key"
# This link comes from POST API Request as "pdfPath" : "s3://bucket-name/object-key"
def parse_s3_url(s3_url):
    """
    Processing the S3 URL to extract bucket name and object key. S3 URLs typically look like "s3://bucket-name/object-key".
    This link comes from POST API Request as "pdfPath" : "s3://bucket-name/object-key"
    """

    # Remove extra slashes if they exist
    s3_url = s3_url.lstrip("/")

    # Split the URL into bucket name and object key at the first '/'
    bucket_name, object_key = s3_url.split("/", 1)

    return bucket_name, object_key

# get_prompt function will extract text from the PDF file using plumber_extract and OCR methods.
# It will then call the appropriate prompt function based on the type of document (INV for Invoice, DO for Delivery Order).
def get_prompt(pdf_path, type : Optional[str], email_body : Optional[str] = ""):
    """
    This function will extract text from the PDF file using PDF Plumber or PyTesseract OCR.
    It will then call the appropriate prompt function based on the type of document (INV for Invoice, DO for Delivery Order).
    Then pass the extracted text to the respective prompt function, which will send it to the Mistral LLM using the Mistral API.
    """
    try:
        text = plumber_extract(pdf_path)
    except Exception as e:
        text = ""

    ocr_response = mistral_ocr(pdf_path)
    tes = tessaract_ocr(pdf_path)

    # print(f"pdf_plumber: \n{text}\n mistral ocr: \n{ocr_response}")

    if(type=="INV"):
        return get_invoice_prompt(text, ocr_response, tes)
    elif (type=="DO"):
        return do_prompt(text, ocr_response, tes)
    elif (type=="POP"):
        return pop_prompt(text, ocr_response, tes)

# def get_bl_prompt(
#         pdf_path, 
#         email_subject: Optional[str] = "",
#         tes = None):
#     """
#     This function will extract text from the PDF file using PDF Plumber or PyTesseract OCR.
#     It will then call the appropriate BL prompt function based on the type of document (MBL or HBL).
#     Then pass the extracted text to the respective prompt function, which will send it to the Mistral LLM using the Mistral API.
#     """
#     try:
#         text = plumber_extract(pdf_path)
#     except Exception as e:
#         text = ""
    
#     tes = tessaract_ocr(pdf_path)
#     # json_file_path = run_rapidocr.run_rapidocr_main(pdf_path, "output/", dpi=300)
#     json_file_path = run_rapid4.run_ocr_pipeline(
#         input_path=pdf_path,
#         output_dir="output/",
#         dpi=300,  
#         annotate=False 
#     )
#     if not tes:
#         # ocr_response = mistral_ocr(pdf_path)
#         ocr_response = ""
#         document_range = str(sanitize_json(extract(bl_splitting_prompt(text, email_subject, tes, ocr_response))))
#     else:
#         ocr_response = ""
#         document_range = str(sanitize_json(extract(bl_splitting_prompt(text, email_subject, tes, ocr_response))))
    
#     logging.info(f"Document Range:\n{document_range}")
#     with open(rf"{json_file_path}", "r") as f:
#         rapidocr_json = f.read()
#     return bl_prompt(text, document_range, rapidocr_json, ocr_response, tes, email_subject)

# def get_bl_prompt(
#         pdf_path, 
#         email_subject: Optional[str] = "",
#         tes = None):
#     """
#     Build and return the final BL prompt string without benchmarking/metrics.
#     """
#     try:
#         text = plumber_extract(pdf_path)
#     except Exception as e:
#         text = ""
    
#     tes = tessaract_ocr(pdf_path)
#     json_file_path = run_rapid4.run_ocr_pipeline(
#         input_path=pdf_path,
#         output_dir="output/",
#         dpi=300,  
#         annotate=False 
#     )

#     ocr_response = ""
#     document_range = str(sanitize_json(extract(bl_splitting_prompt(text, email_subject, tes, ocr_response))))
#     logging.info(f"Document Range:\n{document_range}")
#     with open(rf"{json_file_path}", "r") as f:
#         rapidocr_json = f.read()
#     return bl_prompt(text, document_range, rapidocr_json, ocr_response, tes, email_subject)


def get_bl_prompt_groq(
        pdf_path, 
        email_subject: Optional[str] = "",
        tes = None):
    """
    This function will extract text from the PDF file using PDF Plumber or PyTesseract OCR.
    It will then call the appropriate BL prompt function based on the type of document (MBL or HBL).
    Then pass the extracted text to the respective prompt function, which will send it to the Mistral LLM using the Mistral API.
    """
    try:
        text = plumber_extract(pdf_path)
    except Exception as e:
        text = ""
    
    tes = tessaract_ocr(pdf_path)
    # json_file_path = run_rapidocr.run_rapidocr_main(pdf_path, "output/", dpi=300)
    json_file_path = run_rapid4.run_ocr_pipeline(
        input_path=pdf_path,
        output_dir="output/",
        dpi=300,  
        annotate=False 
    )

    if not tes:
        # ocr_response = mistral_ocr(pdf_path)
        ocr_response = ""
        document_range = str(sanitize_json(extract_groq(groq_bl_splitting_prompt(text, email_subject, tes, ocr_response))))
    else:
        ocr_response = ""
        document_range = str(sanitize_json(extract_groq(groq_bl_splitting_prompt(text, email_subject, tes, ocr_response))))
    
    logging.info(f"Document Range:\n{document_range}")
    with open(rf"{json_file_path}", "r") as f:
        rapidocr_json = f.read()
    return bl_prompt(text, document_range, rapidocr_json, ocr_response, tes, email_subject)

def get_bl_prompt(
        pdf_path, 
        email_subject: Optional[str] = "",
        tes = None):
    """
    Build final BL prompt; identical flow to GROQ variant but intended for Mistral.
    """
    try:
        text = plumber_extract(pdf_path)
    except Exception as e:
        text = ""
    
    tes = tessaract_ocr(pdf_path)
    json_file_path = run_rapid4.run_ocr_pipeline(
        input_path=pdf_path,
        output_dir="output/",
        dpi=300,  
        annotate=False 
    )

    ocr_response = ""
    document_range = str(sanitize_json(extract(groq_bl_splitting_prompt(text, email_subject, tes, ocr_response))))
    
    logging.info(f"Document Range:\n{document_range}")
    with open(rf"{json_file_path}", "r") as f:
        rapidocr_json = f.read()
    return bl_prompt(text, document_range, rapidocr_json, ocr_response, tes, email_subject)

def get_bl_prompt_gemini(
        pdf_path, 
        email_subject: Optional[str] = "",
        tes=None):
    try:
        text = plumber_extract(pdf_path)
    except Exception:
        text = ""
    
    tes = tessaract_ocr(pdf_path)
    json_file_path = run_rapid4.run_ocr_pipeline(
        input_path=pdf_path,
        output_dir="output/",
        dpi=300,
        annotate=False
    )

    ocr_response = ""
    document_range = str(sanitize_json(extract_gemini(bl_splitting_prompt(text, email_subject, tes, ocr_response))))
    
    logging.info(f"Document Range:\n{document_range}")

    with open(rf"{json_file_path}", "r") as f:
        rapidocr_json = f.read()

    return bl_prompt(text, document_range, rapidocr_json, ocr_response, tes, email_subject)


def get_bl_prompt_cohere(
        pdf_path, 
        email_subject: Optional[str] = "",
        tes=None):
    try:
        text = plumber_extract(pdf_path)
    except Exception:
        text = ""
    
    tes = tessaract_ocr(pdf_path)
    json_file_path = run_rapid4.run_ocr_pipeline(
        input_path=pdf_path,
        output_dir="output/",
        dpi=300,
        annotate=False
    )

    ocr_response = ""
    document_range = str(sanitize_json(extract_cohere_llm(bl_splitting_prompt(text, email_subject, tes, ocr_response))))
    
    logging.info(f"Document Range:\n{document_range}")

    with open(rf"{json_file_path}", "r") as f:
        rapidocr_json = f.read()

    return bl_prompt(text, document_range, rapidocr_json, ocr_response, tes, email_subject)


def get_bl_prompt_openai(
        pdf_path, 
        email_subject: Optional[str] = "",
        tes=None):
    try:
        text = plumber_extract(pdf_path)
    except Exception:
        text = ""
    
    tes = tessaract_ocr(pdf_path)
    json_file_path = run_rapid4.run_ocr_pipeline(
        input_path=pdf_path,
        output_dir="output/",
        dpi=300,
        annotate=False
    )

    ocr_response = ""
    document_range = str(sanitize_json(extract_openai(bl_splitting_prompt(text, email_subject, tes, ocr_response))))
    
    logging.info(f"Document Range:\n{document_range}")

    with open(rf"{json_file_path}", "r") as f:
        rapidocr_json = f.read()

    return bl_prompt(text, document_range, rapidocr_json, ocr_response, tes, email_subject)


  
# get_rag_prompt function will extract text from the PDF file using plumber_extract and OCR methods.
# It will then call the appropriate prompt function based on the type of document (INV for Invoice, DO for Delivery Order).
def get_rag_prompt(pdf_path, type : Optional[str]):
    """
    This function will extract text from the PDF file using PDF Plumber or PyTesseract OCR.
    Then it will then call the appropriate RAG Prompt function based on the type of document (INV for Invoice, DO for Delivery Order).
    Then pass the extracted text to the respective prompt function, which will send it to the Mistral LLM using the Mistral API.
    """
    try:
        text = plumber_extract(pdf_path)
    except Exception as e:
        text = ""
    tes=tessaract_ocr(pdf_path)  
    print(f"pdf_plumber: \n{text}")

    if(type=="INV"):
        return rag_invoice_prompt(text,tes)
    elif (type=="DO"):
        return rag_do_prompt(text,tes)

# This function is for Proof of Payments (POP). It will extract text from the PDF file using PDF Plumber or PyTesseract OCR.
def get_pop_prompt(pdf_path):
    """
    This function is for Proof of Payments (POP). It will extract text from the PDF file using PDF Plumber or PyTesseract OCR.
    """

    print(pdf_path)
    if pdf_path.lower().endswith(".pdf"):
        text = plumber_extract(pdf_path)
        if(len(text)<100):
            text = tessaract_ocr(pdf_path)
    else:
        text = tessaract_ocr(pdf_path)
    
    print(text)
    return pop_prompt(text)


def extract_groq(prompt):
    """
    This function selects the model from GROQ (gptoss-120B).
    Defines the messages for the chat, adds the prompt, initializes the GROQ client with the API key,
    Then sends the prompt to the GROQ API and returns the response.
    """
    client_groq = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
    )
    
    # model = "mistral-large-latest"

    chat_completion = client_groq.chat.completions.create(
    messages=[
        {
            "role": "user",
            "content": [{"type": "text", "text": prompt}],
        }
    ],
    model="openai/gpt-oss-120b",
    )
    
    # # Define the messages for the chat
    # messages = [{"role": "user", "content":
    #             [{"type": "text", "text": prompt}]}]

    # # Initialize the Mistral client (ensure you have API credentials set up)
    # client = Mistral(api_key=api_key)

    # # Get the chat response
    # chat_response = client.chat.complete(model=model, messages=messages)

    return chat_completion.choices[0].message.content

def extract_cohere(file: UploadFile) -> str:
    """
    Extract text from an uploaded file.
    Supports PDF and text files.
    """
    file_path = f"/tmp/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if file.filename.lower().endswith(".pdf"):
        text = extract_text_from_pdf(file_path)
    else:
        text = open(file_path, "r").read()

    os.remove(file_path)
    return text


def extract_gemini(prompt: str) -> str:
    """
    Sends the BL prompt to Google Gemini API and returns the response.
    """
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    # You can choose gemini-1.5-pro or gemini-1.5-flash depending on speed/accuracy needs
    model = genai.GenerativeModel("gemini-2.5-pro")

    response = model.generate_content(prompt)

    return response.text


def extract_cohere_llm(prompt: str) -> str:
    """
    Sends the BL prompt to Cohere API and returns the response.
    Uses cohere_utils.cohere_generate_text if available, otherwise calls Cohere directly.
    """
    # Prefer external helper if available
    try:
        if cohere_generate_text is not None:
            return cohere_generate_text(prompt)
    except Exception:
        pass

    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="COHERE_API_KEY not set in environment")

    client = cohere.Client(api_key)
    try:
        chat = client.chat(model="command-r-plus", message=prompt)
        return chat.text
    except Exception:
        chat = client.chat(model="command", message=prompt)
        return chat.text


def extract_openai(prompt: str) -> str:
    """
    Sends the BL prompt to OpenAI API and returns the response.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set in environment")
    
    client = openai.OpenAI(api_key=api_key)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1
        )
        return response.choicies[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {str(e)}")

# def extract(prompt):
#     """
#     This function selects the model (mistral-small-latest).
#     Defines the messages for the chat, adds the prompt, initializes the Mistral client with the API key,
#     Then sends the prompt to the Mistral API and returns the response.
#     """
#     model = "mistral-small-latest"

#     # Define the messages for the chat
#     messages = [{"role": "user", "content":
#                 [{"type": "text", "text": prompt}]}]

#     # Initialize the Mistral client (ensure you have API credentials set up)
#     client = Mistral(api_key=api_key)

#     # Get the chat response
#     chat_response = client.chat.complete(model=model, messages=messages)

#     return chat_response.choices[0].message.content

# def extract(prompt):
#     """
#     Send the prompt to Mistral API and return only the response content.
#     """
#     model = "mistral-small-latest"
#     messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
#     client = Mistral(api_key=api_key)
#     chat_response = client.chat.complete(model=model, messages=messages)
#     return chat_response.choices[0].message.content


# New Mistral helpers for BL-new flow
def extract(prompt: str) -> str:
    """
    Use Mistral small model to generate response for the provided prompt.
    """
    model = "mistral-small-latest"
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    client = Mistral(api_key=api_key)
    chat_response = client.chat.complete(model=model, messages=messages)
    return chat_response.choices[0].message.content


# Pydantic is a Python library for data validation and data parsing.
# It lets you define models (classes) that enforce data types, constraints, and default values — similar to schemas in databases or JSON schema validation.
# It represents a data schema with typed attributes.
# BaseModel is the base class from which all Pydantic models must inherit.


# PDFRequest and PDFOCRRequest are Pydantic models for request validation and enforcing data types for the respective variables.
class PDFRequest(BaseModel):
    pdfPath: str
    emailBody: Optional[str] = "" # Optional field for email body, default is "" (empty string)

class PDFOCRRequest(BaseModel):
    pdfPath: str
    ocr: str
    emailBody: Optional[str] = "" # Optional field for email body, default is "" (empty string)

class BLRequest(BaseModel):
    pdfPath: str
    source: Optional[str] = "EMAIL"
    emailSubject: Optional[str] = "" # Optional field for email subject, default is "" (empty string)

    #Data Passed from Frontend
    parentBlNumber: Optional[str] = ""
    vesselName: Optional[str] = ""
    voyageId: Optional[str] = ""
    issuingPartyName: Optional[str] = ""
    issuingPartyMpciId: Optional[str] = ""
    mblIssuingPartyName: Optional[str] = ""
    mblIssuingPartyMpciId: Optional[str] = ""
    ffPartyName: Optional[str] = ""
    ffPartyMpciId: Optional[str] = ""

    groundTruth: Optional[Dict[str, Any]] = None # Optional: provide ground-truth JSON to compute benchmarking metrics


class MPCIExcel(BaseModel):
    xlsxName:str
    inputJson:str

#-----------------------------------------------------------------------
# These endpoints are defined to handle various PDF processing tasks.
#-----------------------------------------------------------------------

# This endpoint (/process-pdf) processes a PDF file, extracts its content, and returns the result in JSON format.
@app.post("/process-pdf")
async def process_pdf_endpoint(data: PDFRequest):
    pdf_path = data.pdfPath

    try:
        # Check if the pdf_path is an S3 URL or path pattern you accept
        if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)

            # Get the PDF file from S3
            file_name = "parsing_invoice.pdf"
            local_file_path = os.path.join(os.getcwd(), file_name)
            s3_client.download_file(bucket_name, object_key, local_file_path)

        else:
            raise HTTPException(status_code=400, detail="Invalid file path provided")

        # Process the PDF and return the result
        result=extract(get_prompt(file_name))
        if os.path.exists(file_name):
            os.remove(file_name)

        result_json = sanitize_json(result)

        if isinstance(result_json, dict):
            add_doc_type(result_json, "INV")
            return result_json
        elif isinstance(result_json, list):
            for item in result_json:
                if isinstance(item, dict):
                    add_doc_type(result_json, "INV")
                else:
                    raise ValueError("List item is not a dictionary")

            return result_json
        else:
            raise ValueError("JSON is neither dict nor list")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# DO (Delivery Order) endpoint processes a PDF file for Delivery Orders.
# It extracts the content and returns the result in JSON format.
@app.post("/do")
async def do_endpoint(data: PDFRequest):
    pdf_path = data.pdfPath
    email_body = data.emailBody

    try:
        if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)
            file_name = "parsing_do.pdf"
            s3_client.download_file(bucket_name, object_key, file_name)
        else:
            raise HTTPException(status_code=400, detail="Invalid file path provided")

        result=extract(get_prompt(file_name,"DO"))
        if os.path.exists(file_name):
            os.remove(file_name)

        result_json = sanitize_json(result)
        add_doc_type(result_json, "DO")

        return result_json

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# This endpoint processes a PDF file for Proof of Payment (POP).
# It extracts the content and returns the result in JSON format.
@app.post("/ocr")
async def ocr_endpoint(data: PDFOCRRequest):
    pdf_path = data.pdfPath
    ocr = data.ocr

    try:
        if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)
            file_name = "ocr_file.pdf"
            s3_client.download_file(bucket_name, object_key, file_name)
        else:
            raise HTTPException(status_code=400, detail="Invalid file path provided")

        if ocr == "MIS":
            o_result = mistral_ocr(file_name)
            result = ""
            for page in o_result.pages:
                result += f"Page {page.index + 1}:\n{page.markdown}\n{'-'*50}\n"
            return {"text": result}

        elif ocr == "TES":
            return {"text": tessaract_ocr(file_name)}
        else:
            raise HTTPException(status_code=400, detail="Invalid OCR type provided")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# The main and crrent working endpoint for classifying documents and extracting information from them.
# It detects the document type (INV or DO) and processes it accordingly.
@app.post("/classify")
async def classify_endpoint(data: PDFRequest):
    """
    This endpoint classifies the document type (INV or DO) based on the content of the
    """
    pdf_path = data.pdfPath
    email_body = data.emailBody
    doc_type = data.docType

    logger.info(f"Received PDF path: {pdf_path}")
    # logger.info(f"Received email body: {email_body}")
    logger.info("Starting document classification and extraction...")
    start_time = time.time()
    logger.info(f"Start time: {start_time}")

    try:
        if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)
            file_name = "parsing_file.pdf"
            s3_client.download_file(bucket_name, object_key, file_name)
            doc_type = detect_document_type(file_name)
        else:
            raise HTTPException(status_code=400, detail="Invalid file path provided")

        if doc_type == "INV":
            result=extract(get_prompt(file_name,"INV"))
            if os.path.exists(file_name):
                os.remove(file_name)
            result_json = sanitize_json(result)
            result_json["docType"] = "INV"
            return result_json

        elif doc_type == "DO":
            result=extract(get_prompt(file_name,"DO"))
            if os.path.exists(file_name):
                os.remove(file_name)
            result_json = sanitize_json(result)
            result_json["docType"] = "DO"
            return result_json
        
        # elif doc_type == "POP":
        #     result=extract(get_pop_prompt(file_name))
        #     if os.path.exists(file_name):
        #         os.remove(file_name)
        #     result_json = sanitize_json(result)
        #     result_json["docType"] = "POP"
        #     return result_json

        elif doc_type == "BL":
            result = extract(get_prompt(file_name, "BL", email_body))
            if os.path.exists(file_name):
                os.remove(file_name)
            result_json = sanitize_json(result)
            result_json["docType"] = "BL"
            return result_json
        
        else:
            raise HTTPException(status_code=400, detail="Unknown document type")

    except Exception as e:
        end_time = time.time()
        logger.info(f"Time taken: {end_time - start_time} seconds")
        raise HTTPException(status_code=500, detail=str(e))

# @app.post("/bl")
# async def bl_endpoint(data: BLRequest, request: Request):
#     pdf_path = data.pdfPath
#     email_subject = data.emailSubject
#     source = data.source

#     excel_template_path_url = r"s3://odex-warehouse-document-qc/manifest/TEMPLATES/MPCI Bulk Excel.xlsx"
#     excel_file_name = "Excel_Template.xlsx"

#     if source == "WEB_APP":
#         # Get the MBL Number from file name of the PDF from the S3 link
#         # Extract filename from S3 path
#         filename = os.path.basename(pdf_path)
#         # Remove .pdf extension
#         filename_without_ext = os.path.splitext(filename)[0]
#         # Extract MBL number (part after underscore)
#         if '_' in filename_without_ext:
#             MBL_NUMBER = filename_without_ext.split('_', 1)[1]
#         else:
#             # Fallback to full filename without extension if no underscore found
#             MBL_NUMBER = filename_without_ext
#         logging.info(f"MBL Number extracted from PDF file name from S3 Link is: {MBL_NUMBER}")

#     try:
#         logging.info("Starting BL Extraction Process...")
#         raw_body = await request.body()
#         print("RAW REQUEST BODY:\n", raw_body.decode())
#         # data = BLRequest.model_validate_json(raw_body)

#         # Getting File Name of the PDF from the PDF Path for Final Excel File Name.
#         temp = os.path.basename(pdf_path)
#         parsing_pdf_filename = os.path.splitext(temp)[0]

#         # Getting PDF File from AWS S3 Bucket (streaming bytes instead of direct download).
#         # Previous approach (kept for reference):
#         logging.info("Downloading PDF from AWS S3 Bucket...")
#         if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
#             bucket_name, object_key = parse_s3_url(pdf_path)
#             file_name = "parsing_bl.pdf"
#             s3_client.download_file(bucket_name, object_key, file_name)
#         else:
#             raise HTTPException(status_code=400, detail="Invalid file path provided")

#         # New approach: stream the object from S3 and persist to a temporary file for downstream processors.
#         # logging.info("Streaming PDF bytes from AWS S3 Bucket...")
#         # if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
#         #     bucket_name, object_key = parse_s3_url(pdf_path)
#         #     s3_response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
#         #     pdf_bytes = s3_response["Body"].read()
#         #     # Write to a temporary file path expected by existing processing utilities
#         #     tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
#         #     try:
#         #         tmp_file.write(pdf_bytes)
#         #         tmp_file.flush()
#         #         file_name = tmp_file.name
#         #     finally:
#         #         tmp_file.close()
#         # else:
#         #     raise HTTPException(status_code=400, detail="Invalid file path provided")
        
#         # size_bytes = len(pdf_bytes)
#         # sha256 = hashlib.sha256(pdf_bytes).hexdigest()
#         # head_b64 = base64.b64encode(pdf_bytes[:64]).decode()

#         # logging.info(f"Saved temp PDF: {file_name}")
#         # logging.info(f"Size: {size_bytes} bytes, SHA256: {sha256}")
#         # logging.info(f"First 64 bytes (base64): {head_b64}")
#         # logging.info(f"Exists on disk: {os.path.exists(file_name)}")

#         # If source is WEB_APP, include MBL number as context in email_subject
#         if source == "WEB_APP":
#             # Include MBL number as context in the email subject for the prompt
#             enhanced_email_subject = f"{email_subject} | MBL_NUMBER: {MBL_NUMBER}"
#             result = extract(get_bl_prompt(file_name, enhanced_email_subject))
#         else:
#             result = extract(get_bl_prompt(file_name, email_subject))


#         # Calling the parsing function to extract data from the BL PDF.
#         result=extract(get_bl_prompt(file_name, email_subject))

#         # As you noted, use the intermediate JSON for comparison
#         result_json = sanitize_json(result)


#         if os.path.exists(file_name):
#             os.remove(file_name)

#         # result_json = sanitize_json(result)
#         dict_json = json.dumps(result_json, indent=2)
#         final_json = mapper(dict_json, parsing_pdf_filename)
#         try:
#             result = sanitize_json(final_json)
#         except Exception as e:
#             result = final_json

#         # Attempt to remove the 'output' folder before completing
#         try:
#             shutil.rmtree("output", ignore_errors=True)
#         except Exception as e:
#             logging.warning(f"Could not remove 'output' directory: {e}")
#         logging.info("BL Extraction Process Completed.")
#         return result

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# @app.post("/bl")
# async def bl_endpoint(data: BLRequest, request: Request):
#     pdf_path = data.pdfPath
#     email_subject = data.emailSubject
#     source = data.source

#     excel_template_path_url = r"s3://odex-warehouse-document-qc/manifest/TEMPLATES/MPCI Bulk Excel.xlsx"
#     excel_file_name = "Excel_Template.xlsx"
#     if source == "WEB_APP":
#         # Get the MBL Number from file name of the PDF from the S3 link
#         # Extract filename from S3 path
#         filename = os.path.basename(pdf_path)
#         # Remove .pdf extension
#         filename_without_ext = os.path.splitext(filename)[0]
#         # Extract MBL number (part after underscore)
#         if '_' in filename_without_ext:
#             MBL_NUMBER = filename_without_ext.split('_', 1)[1]
#         else:
#             # Fallback to full filename without extension if no underscore found
#             MBL_NUMBER = filename_without_ext
#         logging.info(f"MBL Number extracted from PDF file name from S3 Link is: {MBL_NUMBER}")


#     try:
#         # --- MODIFICATION: Start timer at the beginning of the process ---
#         start_time = time.time()
        
#         logging.info("Starting BL Extraction Process...")
#         raw_body = await request.body()
#         print("RAW REQUEST BODY:\n", raw_body.decode())

#         # Getting File Name of the PDF from the PDF Path for Final Excel File Name.
#         temp = os.path.basename(pdf_path)
#         parsing_pdf_filename = os.path.splitext(temp)[0]

#         # Getting PDF File from AWS S3 Bucket
#         logging.info("Downloading PDF from AWS S3 Bucket...")
#         if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
#             bucket_name, object_key = parse_s3_url(pdf_path)
#             file_name = "parsing_bl.pdf"
#             s3_client.download_file(bucket_name, object_key, file_name)
#         else:
#             raise HTTPException(status_code=400, detail="Invalid file path provided")

#         # Build final prompt and extract without benchmarking/metrics
#         if source == "WEB_APP":
#             enhanced_email_subject = f"{email_subject} | MBL_NUMBER: {MBL_NUMBER}"
#             # logging.info("Enhanced Email Subject:", enhanced_email_subject)
#             result_json = extract(get_bl_prompt(file_name, enhanced_email_subject))
#         else:
#             result_json = extract(get_bl_prompt(file_name, email_subject))
        
#         # if os.path.exists(file_name):
#         #     os.remove(file_name)

#         # result_json = sanitize_json(result)
#         # dict_json = json.dumps(result_json, indent=2)
#         # final_json = mapper(dict_json, parsing_pdf_filename)
#         # try:
#         #     result = sanitize_json(final_json)
#         # except Exception as e:
#         #     result = final_json
        
#         # # Attempt to remove the 'output' folder before completing
#         # try:
#         #     shutil.rmtree("output", ignore_errors=True)
#         # except Exception as e:
#         #     logging.warning(f"Could not remove 'output' directory: {e}")
            
#         # logging.info("BL Extraction Process Completed.")
#         # return result

#         if os.path.exists(file_name):
#             os.remove(file_name)

#         result_json = sanitize_json(result)
#         dict_json = json.dumps(result_json, indent=2)
#         final_json = mapper(dict_json, parsing_pdf_filename)
#         try:
#             result = sanitize_json(final_json)
#         except Exception as e:
#             result = final_json
#         # Attempt to remove the 'output' folder before completing
#         try:
#             shutil.rmtree("output", ignore_errors=True)
#         except Exception as e:
#             logging.warning(f"Could not remove 'output' directory: {e}")
#         logging.info("BL Extraction Process Completed.")
#         return result

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

def compare_extractions(ground_truth: dict, extracted: dict):
    """
    Compares the extracted JSON with the ground truth JSON and returns precision, recall, and f1-score.
    """
    # Flatten both dictionaries to a single level for easier comparison
    gt_flat = pd.json_normalize(ground_truth, sep='_').to_dict(orient='records')[0]
    ext_flat = pd.json_normalize(extracted, sep='_').to_dict(orient='records')[0]

    # Get the sets of keys
    gt_keys = set(gt_flat.keys())
    ext_keys = set(ext_flat.keys())

    # Identify keys that were correctly extracted with the correct value
    correctly_extracted_keys = {k for k in ext_keys if k in gt_keys and str(gt_flat[k]).strip() == str(ext_flat[k]).strip()}

    # True Positives (TP): Correctly identified and extracted
    tp = len(correctly_extracted_keys)

    # False Positives (FP): Extracted but incorrect (wrong key or wrong value)
    fp = len(ext_keys) - tp

    # False Negatives (FN): In ground truth but not extracted
    fn = len(gt_keys) - tp

    # Calculate metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    error_rate = 1 - f1_score # A simple way to represent error

    return {
        "precision": precision,
        "recall": recall,
        "f1_score": f1_score,
        "error_rate": error_rate,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn
    }

@app.post("/bl-groq")
async def bl_endpoint(data: BLRequest, request: Request):
    pdf_path = data.pdfPath
    email_subject = data.emailSubject
    source = data.source

    #Data passed from frontend
    parentBlNumber = data.parentBlNumber
    vesselName = data.vesselName
    voyageId = data.voyageId
    issuingPartyName = data.issuingPartyName
    issuingPartyMpciId = data.issuingPartyMpciId
    mblIssuingPartyName = data.mblIssuingPartyName
    mblIssuingPartyMpciId = data.mblIssuingPartyMpciId
    ffPartyName = data.ffPartyName
    ffPartyMpciId = data.ffPartyMpciId
    data_dict = {"parentBlNumber":parentBlNumber,
                 "vesselName": vesselName, 
                 "voyageId": voyageId, 
                 "issuingPartyName": issuingPartyName, 
                 "issuingPartyMpciId": issuingPartyMpciId, 
                 "mblIssuingPartyName": mblIssuingPartyName, 
                 "mblIssuingPartyMpciId": mblIssuingPartyMpciId,
                 "ffPartyName": ffPartyName,
                 "ffPartyMpciId": ffPartyMpciId}
    data_dict = sanitize_json_dict(data_dict)
    logging.info(f"Data Passed from Frontend: {data_dict}")


    # if source == "WEB_APP":
    #     # Get the MBL Number from file name of the PDF from the S3 link
    #     # Extract filename from S3 path
    #     filename = os.path.basename(pdf_path)
    #     # Remove .pdf extension
    #     filename_without_ext = os.path.splitext(filename)[0]
    #     # Extract MBL number (part after underscore)
    #     if '_' in filename_without_ext:
    #         MBL_NUMBER = filename_without_ext.split('_', 1)[1]
    #     else:
    #         # Fallback to full filename without extension if no underscore found
    #         MBL_NUMBER = filename_without_ext
    #     logging.info(f"MBL Number extracted from PDF file name from S3 Link is: {MBL_NUMBER}")
    try:
        logging.info("Starting BL Extraction Process...")
        raw_body = await request.body()
        print("RAW REQUEST BODY:\n", raw_body.decode())
        # data = BLRequest.model_validate_json(raw_body)

        # Getting File Name of the PDF from the PDF Path for Final Excel File Name.
        temp = os.path.basename(pdf_path)
        parsing_pdf_filename = os.path.splitext(temp)[0]

        # Getting PDF File from AWS S3 Bucket (streaming bytes instead of direct download).
        # Previous approach (kept for reference):
        logging.info("Downloading PDF from AWS S3 Bucket...")
        if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)
            file_name = "parsing_bl.pdf"
            s3_client.download_file(bucket_name, object_key, file_name)
        else:
            raise HTTPException(status_code=400, detail="Invalid file path provided")

        # New approach: stream the object from S3 and persist to a temporary file for downstream processors.
        # logging.info("Streaming PDF bytes from AWS S3 Bucket...")
        # if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
        #     bucket_name, object_key = parse_s3_url(pdf_path)
        #     s3_response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        #     pdf_bytes = s3_response["Body"].read()
        #     # Write to a temporary file path expected by existing processing utilities
        #     tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        #     try:
        #         tmp_file.write(pdf_bytes)
        #         tmp_file.flush()
        #         file_name = tmp_file.name
        #     finally:
        #         tmp_file.close()
        # else:
        #     raise HTTPException(status_code=400, detail="Invalid file path provided")
        
        # size_bytes = len(pdf_bytes)
        # sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        # head_b64 = base64.b64encode(pdf_bytes[:64]).decode()

        # logging.info(f"Saved temp PDF: {file_name}")
        # logging.info(f"Size: {size_bytes} bytes, SHA256: {sha256}")
        # logging.info(f"First 64 bytes (base64): {head_b64}")
        # logging.info(f"Exists on disk: {os.path.exists(file_name)}")

        # Calling the parsing function to extract data from the BL PDF.
        # result=extract(get_bl_prompt(file_name, email_subject))

        # If source is WEB_APP, include MBL number as context in email_subject
        # if source == "WEB_APP":
        #     # Include MBL number as context in the email subject for the prompt
        #     enhanced_email_subject = f"{email_subject} | MBL_NUMBER: {MBL_NUMBER}"
        #     result = extract_groq(get_bl_prompt_groq(file_name, enhanced_email_subject))
        # else:
        #     result = extract_groq(get_bl_prompt_groq(file_name, email_subject))
        
        result = extract_groq(get_bl_prompt_groq(file_name, email_subject))

        if os.path.exists(file_name):
            os.remove(file_name)

        result_json = sanitize_json(result)
        dict_json = json.dumps(result_json, indent=2)
        # final_json = mapper(dict_json, parsing_pdf_filename)
        final_json = mapper(dict_json, parsing_pdf_filename, data_dict, source)

        try:
            result = sanitize_json(final_json)
        except Exception as e:
            result = final_json
        
        # Attempt to remove the 'output' folder before completing
        try:
            shutil.rmtree("output", ignore_errors=True)
            if os.path.exists("Excel_Template.xlsx"):
                os.remove("Excel_Template.xlsx")
        except Exception as e:
            logging.warning(f"Could not remove 'output' directory: {e}")
        
        logging.info("BL Extraction Process Completed.")
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/bl")
async def bl_new_endpoint(data: BLRequest, request: Request):
    pdf_path = data.pdfPath
    email_subject = data.emailSubject
    source = data.source

    try:
        logging.info("Starting BL Extraction Process (Mistral)...")
        raw_body = await request.body()
        print("RAW REQUEST BODY:\n", raw_body.decode())

        temp = os.path.basename(pdf_path)
        parsing_pdf_filename = os.path.splitext(temp)[0]

        logging.info("Downloading PDF from AWS S3 Bucket...")
        if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)
            file_name = "parsing_bl.pdf"
            s3_client.download_file(bucket_name, object_key, file_name)
        else:
            raise HTTPException(status_code=400, detail="Invalid file path provided")

        if source == "WEB_APP":
            filename = os.path.basename(pdf_path)
            filename_without_ext = os.path.splitext(filename)[0]
            if '_' in filename_without_ext:
                MBL_NUMBER = filename_without_ext.split('_', 1)[1]
            else:
                MBL_NUMBER = filename_without_ext
            logging.info(f"MBL Number extracted from PDF file name from S3 Link is: {MBL_NUMBER}")
            enhanced_email_subject = f"{email_subject} | MBL_NUMBER: {MBL_NUMBER}"
            result = extract(get_bl_prompt(file_name, enhanced_email_subject))
        else:
            result = extract(get_bl_prompt(file_name, email_subject))

        if os.path.exists(file_name):
            os.remove(file_name)

        result_json = sanitize_json(result)
        dict_json = json.dumps(result_json, indent=2)
        final_json = mapper(dict_json, parsing_pdf_filename)
        try:
            result = sanitize_json(final_json)
        except Exception as e:
            result = final_json
        try:
            shutil.rmtree("output", ignore_errors=True)
        except Exception as e:
            logging.warning(f"Could not remove 'output' directory: {e}")
        logging.info("BL Extraction Process Completed (Mistral).")
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/bl-gemini")
async def bl_gemini_endpoint(data: BLRequest, request: Request):
    pdf_path = data.pdfPath
    email_subject = data.emailSubject
    ground_truth = data.groundTruth

    try:
        logging.info("Starting BL Extraction Process (Gemini)...")
        t0 = time.time()
        raw_body = await request.body()
        print("RAW REQUEST BODY:\n", raw_body.decode())

        temp = os.path.basename(pdf_path)
        parsing_pdf_filename = os.path.splitext(temp)[0]

        logging.info("Downloading PDF from AWS S3 Bucket...")
        if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)
            file_name = "parsing_bl.pdf"
            s3_client.download_file(bucket_name, object_key, file_name)
        else:
            raise HTTPException(status_code=400, detail="Invalid file path provided")

        # Count pages for per-page latency
        page_count = count_pdf_pages(file_name)

        # Call Gemini
        t1 = time.time()
        result = extract_gemini(get_bl_prompt_gemini(file_name, email_subject))
        t2 = time.time()

        if os.path.exists(file_name):
            os.remove(file_name)

        result_json = sanitize_json(result)
        dict_json = json.dumps(result_json, indent=2)
        final_json = mapper(dict_json, parsing_pdf_filename)

        try:
            result = sanitize_json(final_json)
        except Exception:
            result = final_json

        shutil.rmtree("output", ignore_errors=True)
        logging.info("BL Extraction Process Completed (Gemini).")

        # Metrics
        wall_ms = int(round((time.time() - t0) * 1000))
        model_ms = int(round((t2 - t1) * 1000))
        per_page_ms = (wall_ms // page_count) if page_count else None

        extraction_metrics = compute_extraction_metrics(result if isinstance(result, dict) else {}, ground_truth)
        schema_metrics = compute_schema_adherence(result if isinstance(result, dict) else {}, ground_truth)
        error_rate_pct = compute_error_rate(schema_metrics)

        response_payload = {
            "data": result,
            "metrics": {
                "extractionAccuracyPct": extraction_metrics.get("extractionAccuracyPct"),
                "fieldLevel": extraction_metrics.get("fieldLevel"),
                "latencyMs": {
                    "totalRequest": wall_ms,
                    "modelCall": model_ms,
                    "perPage": per_page_ms,
                    "pageCount": page_count
                },
                "errorRatePct": error_rate_pct,
                "schemaAdherence": schema_metrics,
            }
        }

        return response_payload

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/bl-cohere")
async def bl_cohere_endpoint(data: BLRequest, request: Request):
    pdf_path = data.pdfPath
    email_subject = data.emailSubject
    ground_truth = data.groundTruth

    try:
        logging.info("Starting BL Extraction Process (Cohere)...")
        t0 = time.time()
        raw_body = await request.body()
        print("RAW REQUEST BODY:\n", raw_body.decode())

        temp = os.path.basename(pdf_path)
        parsing_pdf_filename = os.path.splitext(temp)[0]

        logging.info("Downloading PDF from AWS S3 Bucket...")
        if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)
            file_name = "parsing_bl.pdf"
            s3_client.download_file(bucket_name, object_key, file_name)
        else:
            raise HTTPException(status_code=400, detail="Invalid file path provided")

        page_count = count_pdf_pages(file_name)

        # Call Cohere
        t1 = time.time()
        result = extract_cohere_llm(get_bl_prompt_cohere(file_name, email_subject))
        t2 = time.time()

        if os.path.exists(file_name):
            os.remove(file_name)

        result_json = sanitize_json(result)
        dict_json = json.dumps(result_json, indent=2)
        final_json = mapper(dict_json, parsing_pdf_filename)

        try:
            result = sanitize_json(final_json)
        except Exception:
            result = final_json

        shutil.rmtree("output", ignore_errors=True)
        logging.info("BL Extraction Process Completed (Cohere).")

        wall_ms = int(round((time.time() - t0) * 1000))
        model_ms = int(round((t2 - t1) * 1000))
        per_page_ms = (wall_ms // page_count) if page_count else None

        extraction_metrics = compute_extraction_metrics(result if isinstance(result, dict) else {}, ground_truth)
        schema_metrics = compute_schema_adherence(result if isinstance(result, dict) else {}, ground_truth)
        error_rate_pct = compute_error_rate(schema_metrics)

        response_payload = {
            "data": result,
            "metrics": {
                "extractionAccuracyPct": extraction_metrics.get("extractionAccuracyPct"),
                "fieldLevel": extraction_metrics.get("fieldLevel"),
                "latencyMs": {
                    "totalRequest": wall_ms,
                    "modelCall": model_ms,
                    "perPage": per_page_ms,
                    "pageCount": page_count
                },
                "errorRatePct": error_rate_pct,
                "schemaAdherence": schema_metrics,
            }
        }

        return response_payload

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/bl-openai")
async def bl_openai_endpoint(data: BLRequest, request: Request):
    pdf_path = data.pdfPath
    email_subject = data.emailSubject
    ground_truth = data.groundTruth

    try:
        logging.info("Starting BL Extraction Process (OpenAI)...")
        t0 = time.time()
        raw_body = await request.body()
        print("RAW REQUEST BODY:\n", raw_body.decode())

        temp = os.path.basename(pdf_path)
        parsing_pdf_filename = os.path.splitext(temp)[0]

        logging.info("Downloading PDF from AWS S3 Bucket...")
        if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)
            file_name = "parsing_bl.pdf"
            s3_client.download_file(bucket_name, object_key, file_name)
        else:
            raise HTTPException(status_code=400, detail="Invalid file path provided")

        page_count = count_pdf_pages(file_name)

        # Call OpenAI
        t1 = time.time()
        result = extract_openai(get_bl_prompt_openai(file_name, email_subject))
        t2 = time.time()

        if os.path.exists(file_name):
            os.remove(file_name)

        result_json = sanitize_json(result)
        dict_json = json.dumps(result_json, indent=2)
        final_json = mapper(dict_json, parsing_pdf_filename)

        try:
            result = sanitize_json(final_json)
        except Exception:
            result = final_json

        shutil.rmtree("output", ignore_errors=True)
        logging.info("BL Extraction Process Completed (OpenAI).")

        wall_ms = int(round((time.time() - t0) * 1000))
        model_ms = int(round((t2 - t1) * 1000))
        per_page_ms = (wall_ms // page_count) if page_count else None

        extraction_metrics = compute_extraction_metrics(result if isinstance(result, dict) else {}, ground_truth)
        schema_metrics = compute_schema_adherence(result if isinstance(result, dict) else {}, ground_truth)
        error_rate_pct = compute_error_rate(schema_metrics)

        response_payload = {
            "data": result,
            "metrics": {
                "extractionAccuracyPct": extraction_metrics.get("extractionAccuracyPct"),
                "fieldLevel": extraction_metrics.get("fieldLevel"),
                "latencyMs": {
                    "totalRequest": wall_ms,
                    "modelCall": model_ms,
                    "perPage": per_page_ms,
                    "pageCount": page_count
                },
                "errorRatePct": error_rate_pct,
                "schemaAdherence": schema_metrics,
            }
        }

        return response_payload

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mpci-excel")
async def mpci_excel_endpoint(data: MPCIExcel, request: Request):
    input_json_data = data.inputJson
    Excel_Final_file_name = data.xlsxName
    
    # Add .xlsx extension if not present
    if not Excel_Final_file_name.endswith('.xlsx'):
        Excel_Final_file_name += '.xlsx'

    excel_template_path_url = r"s3://odex-warehouse-document-qc/manifest/TEMPLATES/MPCI Bulk Excel.xlsx"
    excel_file_name = "Excel_Template.xlsx"

    try:
        logging.info("Starting Reverse Transformation & Excel Generation Process...")
        raw_body = await request.body()
        print("RAW REQUEST BODY:\n", raw_body.decode())
        # data = BLRequest.model_validate_json(raw_body)

        # Handle double-escaped JSON string
        try:
            # First parse: convert escaped string to JSON string
            parsed_json_string = json.loads(input_json_data)
            # Second parse: convert JSON string to dict
            parsed_json_dict = json.loads(parsed_json_string)
            transformed_output = sanitize_json_dict(reverse_transform_json(parsed_json_dict))
        except json.JSONDecodeError:
            # If double parsing fails, try single parsing (for backward compatibility)
            transformed_output = sanitize_json_dict(reverse_transform_json(input_json_data))

        file_path = os.path.join(os.getcwd(), "ODeX_json.json")
        temp_json = sanitize_json(transformed_output) # String

        with open(file_path, "w", encoding="utf-8-sig") as f:
            json.dump(temp_json, f, indent=2, ensure_ascii=False)
        print(f"✅ JSON written to {file_path}")

        # --- EXCEL GENERATION ---
        # Download the template
        excel_template_file_path = excel_template_downlaoder()
        
        # Call the modified function which returns the output path AND the data with row numbers
        output_file_path, data_with_rows = process_json_to_excel(
            file_path, 
            r"Excel_Template.xlsx", 
            Excel_Final_file_name
        )
        if not output_file_path:
             raise Exception("Failed to generate the Excel file.")
        
        excel_s3_link = upload_to_s3(Excel_Final_file_name, output_file_path)
        logger.info(f"Excel file uploaded to S3: {excel_s3_link}")

        if os.path.exists(Excel_Final_file_name):
            os.remove(Excel_Final_file_name)
        if os.path.exists(excel_template_file_path):
            os.remove(excel_template_file_path)
        if os.path.exists(r"ODeX_json.json"):
            os.remove(r"ODeX_json.json")
        result_json = {"xlsxPath": f"{excel_s3_link}"}
        return result_json
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))





@app.post("/pop")
async def pop_endpoint(data: PDFRequest):
    pdf_path = data.pdfPath

    try:
        if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)
            file_name = "parsing_pop.pdf" if pdf_path.lower().endswith(".pdf") else "parsing_pop"
            s3_client.download_file(bucket_name, object_key, file_name)
        else:
            raise HTTPException(status_code=400, detail="Invalid file path provided")
        
        result=extract(get_pop_prompt(file_name))
        if os.path.exists(file_name):
            os.remove(file_name)

        result_json = sanitize_json(result)
        add_doc_type(result_json, "POP")
        return result_json

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/invoice-rag")
async def invoice_rag_endpoint(data: PDFRequest):
    pdf_path = data.pdfPath
    try:
        # Check if the pdf_path is an S3 URL or path pattern you accept
        if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)

            # Get the PDF file from S3
            file_name = "parsing_invoice.pdf"
            local_file_path = os.path.join(os.getcwd(), file_name)
            s3_client.download_file(bucket_name, object_key, local_file_path)

        else:
            raise HTTPException(status_code=400, detail="Invalid file path provided")

        # Process the PDF and return the result
        result=extract(get_rag_prompt(file_name,"INV"))
        if os.path.exists(file_name):
            os.remove(file_name)

        result_json = sanitize_json(result)

        if isinstance(result_json, dict):
            add_doc_type(result_json, "INV")
            return result_json
        elif isinstance(result_json, list):
            for item in result_json:
                if isinstance(item, dict):
                    add_doc_type(result_json, "INV")
                else:
                    raise ValueError("List item is not a dictionary")

            return result_json
        else:
            raise ValueError("JSON is neither dict nor list")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/do-rag")
async def do_rag_endpoint(data: PDFRequest):
    pdf_path = data.pdfPath
    try:
        # Check if the pdf_path is an S3 URL or path pattern you accept
        if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)

            # Get the PDF file from S3
            file_name = "parsing_do.pdf"
            local_file_path = os.path.join(os.getcwd(), file_name)
            s3_client.download_file(bucket_name, object_key, local_file_path)

        else:
            raise HTTPException(status_code=400, detail="Invalid file path provided")

        # Process the PDF and return the result
        result=extract(get_rag_prompt(file_name,"DO"))
        
        if os.path.exists(file_name):
            os.remove(file_name)

        result_json=extract_so_do_entries(result)

        if isinstance(result_json, dict):
            add_doc_type(result_json, "DO")
            return result_json
        elif isinstance(result_json, list):
            for item in result_json:
                if isinstance(item, dict):
                    add_doc_type(result_json, "DO")
                else:
                    raise ValueError("List item is not a dictionary")

            return JSONResponse(content=result_json)
        else:
            raise ValueError("JSON is neither dict nor list")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/classify-rag")
async def classify_rag_endpoint(data: PDFRequest):
    pdf_path = data.pdfPath
    start_time = time.time()

    try:
        if pdf_path.startswith(bucket_name_1) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)
            file_name = "ocr_file.pdf"
            s3_client.download_file(bucket_name, object_key, file_name)
            doc_type = detect_document_type(file_name)
        else:
            raise HTTPException(status_code=400, detail="Invalid file path provided")

        if doc_type == "INV":
            result=extract(get_rag_prompt(file_name,"INV"))
            if os.path.exists(file_name):
                os.remove(file_name)
            result_json = sanitize_json(result)
            if isinstance(result_json, dict):
                add_doc_type(result_json, "INV")
                return result_json
            elif isinstance(result_json, list):
                for item in result_json:
                    if isinstance(item, dict):
                        add_doc_type(result_json, "INV")
                    else:
                        raise ValueError("List item is not a dictionary")
            else:
                raise ValueError("JSON is neither dict nor list")



        elif doc_type == "DO":
            result=extract(get_rag_prompt(file_name,"DO"))
            if os.path.exists(file_name):
                os.remove(file_name)
            result_json = extract_so_do_entries(result)
            if isinstance(result_json, dict):
                add_doc_type(result_json, "DO")
                return JSONResponse(content=result_json)
            elif isinstance(result_json, list):
                for item in result_json:
                    if isinstance(item, dict):
                        add_doc_type(result_json, "DO")
            else:
                raise ValueError("List item is not a dictionary")

            return JSONResponse(content=result_json)

        else:
            raise HTTPException(status_code=400, detail="Unknown document type")

    except Exception as e:
        end_time = time.time()
        print(f"Time taken: {end_time - start_time} seconds")
        raise HTTPException(status_code=500, detail=str(e))



# ------------------------------
# ✅ Helper functions
# ------------------------------

def sanitize_json(result_str):
    """
    Cleans and parses the extracted JSON string.
    """
    cleaned = result_str.strip().replace("```json", "").replace("```", "").strip()
    result_json = json.loads(cleaned)
    return result_json

def add_doc_type(result_json, doc_type):
    """
    Adds docType to either dict or each dict inside list.
    """
    if isinstance(result_json, dict):
        result_json["docType"] = doc_type
    elif isinstance(result_json, list):
        for item in result_json:
            if isinstance(item, dict):
                item["docType"] = doc_type
            else:
                raise ValueError("List item is not a dictionary")
    else:
        raise ValueError("JSON is neither dict nor list")

def extract_so_do_entries(json_data):
    """
    Extracts first entries from 'DO' (Storing Order) and 'DO' (Delivery Order) lists in a JSON string or dict,
    and returns a flat list with those entries.
    """
    # If input is a string, parse it
    if isinstance(json_data, str):
        try:
            cleaned = json_data.strip().replace("```json", "").replace("```", "").strip()
            json_data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string: {e}")

    result = []
    if "so" in json_data and isinstance(json_data["so"], list) and json_data["so"]:
        result.append(json_data["so"][0])

    if "do" in json_data and isinstance(json_data["do"], list) and json_data["do"]:
        result.append(json_data["do"][0])
    
    else:
        result=json_data
        
    return result


# ------------------------------
# 🧮 Benchmarking utilities
# ------------------------------

def _normalize_value(value: Any) -> str:
    try:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, sort_keys=True, ensure_ascii=False).strip()
        return str(value).strip().lower()
    except Exception:
        return str(value)


def _flatten_json(data: Any, prefix: str = "") -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            flat.update(_flatten_json(v, key))
    elif isinstance(data, list):
        for idx, v in enumerate(data):
            key = f"{prefix}[{idx}]"
            flat.update(_flatten_json(v, key))
    else:
        flat[prefix] = data
    return flat


def _compare_fields(pred: Dict[str, Any], gt: Dict[str, Any]) -> Tuple[int, int, int, int]:
    pred_flat = _flatten_json(pred)
    gt_flat = _flatten_json(gt)

    total_gt = len(gt_flat)
    extracted_non_empty = 0
    correct = 0

    for k, v in pred_flat.items():
        norm_v = _normalize_value(v)
        if norm_v != "":
            extracted_non_empty += 1
        if k in gt_flat:
            if _normalize_value(v) == _normalize_value(gt_flat[k]):
                correct += 1

    return correct, total_gt, extracted_non_empty, len(pred_flat)


def compute_extraction_metrics(pred: Dict[str, Any], gt: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(pred, dict) or gt is None or not isinstance(gt, dict):
        return {
            "extractionAccuracyPct": None,
            "fieldLevel": {"precisionPct": None, "recallPct": None},
        }

    correct, total_gt, extracted_non_empty, total_pred = _compare_fields(pred, gt)

    recall = (correct / total_gt) * 100.0 if total_gt else 0.0
    precision = (correct / extracted_non_empty) * 100.0 if extracted_non_empty else 0.0
    accuracy = recall

    return {
        "extractionAccuracyPct": round(accuracy, 2),
        "fieldLevel": {
            "precisionPct": round(precision, 2),
            "recallPct": round(recall, 2),
        },
    }


def compute_schema_adherence(pred: Dict[str, Any], gt: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(pred, dict):
        return {"adherencePct": 0.0, "presentKeys": 0, "missingKeys": 0, "extraKeys": 0, "typeMatches": 0}

    if gt is None or not isinstance(gt, dict):
        # Without ground truth, we can only say the structure is a dict
        return {"adherencePct": None, "presentKeys": None, "missingKeys": None, "extraKeys": None, "typeMatches": None}

    pred_flat = _flatten_json(pred)
    gt_flat = _flatten_json(gt)

    present = sum(1 for k in gt_flat.keys() if k in pred_flat)
    missing = sum(1 for k in gt_flat.keys() if k not in pred_flat)
    extra = sum(1 for k in pred_flat.keys() if k not in gt_flat)

    type_matches = 0
    for k in gt_flat.keys():
        if k in pred_flat:
            if isinstance(pred_flat[k], type(gt_flat[k])) or _normalize_value(pred_flat[k]) == _normalize_value(gt_flat[k]):
                type_matches += 1

    adherence = (type_matches / len(gt_flat)) * 100.0 if gt_flat else 0.0

    return {
        "adherencePct": round(adherence, 2),
        "presentKeys": present,
        "missingKeys": missing,
        "extraKeys": extra,
        "typeMatches": type_matches,
    }


def compute_error_rate(schema_adherence: Dict[str, Any]) -> Optional[float]:
    if schema_adherence.get("adherencePct") is None:
        return None
    return round(100.0 - float(schema_adherence["adherencePct"]), 2)


def count_pdf_pages(pdf_path: str) -> int:
    try:
        import fitz  # PyMuPDF
        with fitz.open(pdf_path) as doc:
            return doc.page_count
    except Exception:
        return 0


# @app.get("/healthz", response_model=HealthResponse)
# async def healthz():
#     uptime = int(time.time() - MetricsState.started_at)
#     return HealthResponse(status="ok", uptimeSec=uptime, totalRequests=MetricsState.total_requests)

# @app.get("/metrics")
# async def metrics():
#     uptime = int(time.time() - MetricsState.started_at)
#     return {"uptimeSec": uptime, "totalRequests": MetricsState.total_requests}
    