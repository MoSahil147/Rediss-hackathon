import os
import json
import time
from typing import Optional

import boto3
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from mistralai import Mistral

# file imports
from classification import detect_document_type
from document_processing_services import plumber_extract, mistral_ocr
from document_processing_services import tessaract_ocr
from prompts import get_invoice_prompt, do_prompt, pop_prompt

load_dotenv()

aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID_1")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY_1")
region_name = os.getenv("REGION_NAME")
api_key = os.getenv("API_KEY")


app = Flask(__name__)


s3_client = boto3.client(
    "s3",
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=region_name,
)


def get_prompt(pdf_path: str, email_body: Optional[str]):
    try:
        text = plumber_extract(pdf_path)
    except Exception as e:
        text = ""

    ocr_response = mistral_ocr(pdf_path)
    tes = tessaract_ocr(pdf_path)

    print(f"pdf_plumber: \n{text}\n mistral ocr: \n{ocr_response}")

    return get_invoice_prompt(text, ocr_response, email_body, tes)


def get_do_prompt(pdf_path: str, email_body: Optional[str]) -> str:
    text = plumber_extract(pdf_path)
    ocr_response = mistral_ocr(pdf_path)
    print(
        f"pdf_plumber output: \n{text}\n mistral: \n{ocr_response}"
    )

    return do_prompt(text, ocr_response)

def get_pop_prompt(pdf_path):
    
    print(pdf_path)
    if pdf_path.lower().endswith(".pdf"):
        text = plumber_extract(pdf_path)
        if(len(text)<100):
            text = tessaract_ocr(pdf_path)
    else:
        text = tessaract_ocr(pdf_path)
    
    print(text)
    return pop_prompt(text)


def extraction_invoice(pdf_path: str, email_body: Optional[str]) -> str:
    model = "mistral-small-latest"
    prompt = get_prompt(pdf_path, email_body)

    messages = [{"role": "user", "content":
                [{"type": "text", "text": prompt}]}]

    # Initialize the Mistral client (ensure you have API credentials set up)
    client = Mistral(
        api_key=api_key
    )  # Adjust this line based on the correct client initialization

    # Get the chat response
    chat_response = client.chat.complete(model=model, messages=messages)

    return chat_response.choices[0].message.content


def extraction_do(pdf_path: str, email_body: Optional[str]) -> str:
    model = "mistral-small-latest"

    # Define the messages for the chat

    prompt: str = get_do_prompt(pdf_path)

    messages = [{"role": "user", "content":
                [{"type": "text", "text": prompt}]}]

    # Initialize the Mistral client (ensure you have API credentials set up)
    client = Mistral(api_key=api_key)

    # Get the chat response
    chat_response = client.chat.complete(model=model, messages=messages)

    return chat_response.choices[0].message.content


def extraction_pop(pdf_path):
    model = "mistral-small-latest"

    # Define the messages for the chat

    prompt = get_pop_prompt(pdf_path)

    messages = [{"role": "user", "content":
                [{"type": "text", "text": prompt}]}]

    # Initialize the Mistral client (ensure you have API credentials set up)
    client = Mistral(api_key=api_key)

    # Get the chat response
    chat_response = client.chat.complete(model=model, messages=messages)

    return chat_response.choices[0].message.content


@app.route("/process-pdf", methods=["POST"])
def process_pdf_endpoint():
    data = request.get_json()

    # Check if pdf_path is provided
    if not data or "pdfPath" not in data:
        return jsonify({"error": "Missing pdfPath in request"}), 400
    if "emailBody" not in data:
        return jsonify({"error": "Missing emailBody in request"}), 400

    pdf_path = data["pdfPath"]
    email_body: Optional[str] = data["emailBody"]

    try:
        bucket_name = "odex-warehouse-document-dev"
        # Check if the pdf_path is an S3 URL
        if pdf_path.startswith(bucket_name) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)

            # Get the PDF file from S3
            file_name = "parsing_invoice.pdf"
            local_file_path = os.path.join(os.getcwd(), file_name)
            s3_client.download_file(bucket_name, object_key, local_file_path)

        else:
            return jsonify({"error": "Invalid file path provided"}), 400

        # Process the PDF and return the result
        result: str = extraction_invoice(file_name, email_body)

        if os.path.exists(file_name):
            os.remove(file_name)

        json_content: str = (result.strip().
                        replace("```json", "").
                        replace("```", "").
                        strip())
        result_json = json.loads(json_content)
        if isinstance(result_json, dict):
            result_json["docType"] = "INV"
            return jsonify(result_json)
        elif isinstance(result_json, list):
    # If it's a list of dicts, add to each dict
            for item in result_json:
                if isinstance(item, dict):
                    item["docType"] = "INV"
                else:
                    raise ValueError("List item is not a dictionary")
        else:
            raise ValueError("JSON is neither dict nor list")
        return jsonify(result_json)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/do", methods=["POST"])
def do_endpoint():
    data = request.get_json()

    # Check if pdf_path is provided
    if not data or "pdfPath" not in data:
        return jsonify({"error": "Missing pdfPath in request"}), 400
    
    if 'emailBody' not in data:
        return jsonify({'error': 'Missing emailBody in request'}), 400

    pdf_path = data["pdfPath"]
    email_body: Optional[str] = data["emailBody"]

    try:
        bucket_name = "odex-warehouse-document-dev"
        # Check if the pdf_path is an S3 URL
        if pdf_path.startswith(bucket_name) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)

            # Get the PDF file from S3
            file_name = "parsing_do.pdf"
            local_file_path = os.path.join(os.getcwd(), file_name)
            s3_client.download_file(bucket_name, object_key, local_file_path)

        else:
            return jsonify({"error": "Invalid file path provided"}), 400

        # Process the PDF and return the result
        result: str = extraction_do(file_name, email_body)
        if os.path.exists(file_name):
            os.remove(file_name)
        json_content = (result.strip().
                        replace("```json", "").
                        replace("```", "").
                        strip()
                        )
        result_json = json.loads(json_content)
        if isinstance(result_json, dict):
            result_json["docType"] = "DO"
            return jsonify(result_json)
        elif isinstance(result_json, list):
    # If it's a list of dicts, add to each dict
            for item in result_json:
                if isinstance(item, dict):
                    item["docType"] = "DO"
                else:
                    raise ValueError("List item is not a dictionary")
        else:
            raise ValueError("JSON is neither dict nor list")
        return jsonify(result_json)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/ocr", methods=["POST"])
def ocr_endpoint():
    data = request.get_json()

    # Check if pdf_path is provided
    if not data or "pdfPath" not in data:
        return jsonify({"error": "Missing pdfPath in request"}), 400
    if "emailBody" not in data:
        return jsonify({"error": "Missing emailBody in request"}), 400

    pdf_path: str = data["pdfPath"]
    email_body: Optional[str] = data["emailBody"]
    ocr = data["ocr"]

    try:
        bucket_name = "odex-warehouse-document-dev"
        # Check if the pdf_path is an S3 URL
        if pdf_path.startswith(bucket_name) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)

            # Get the PDF file from S3
            file_name = "ocr_file.pdf"
            local_file_path = os.path.join(os.getcwd(), file_name)
            s3_client.download_file(bucket_name, object_key, local_file_path)

        else:
            return jsonify({"error": "Invalid file path provided"}), 400

        # Process the PDF and return the result
        if ocr == "MIS":
            o_result = mistral_ocr(file_name)
            result = ""
            for page in o_result.pages:
                result += f"Page {page.index + 1}:\n"
                result += f"{page.markdown}\n"
                result += "-" * 50 + "\n"
            return result

        if ocr == "TES":
            return tessaract_ocr(file_name)
        # return jsonify({'text': result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/classify", methods=["POST"])
def classify_endpoint():
    data = request.get_json()

    # Check if pdf_path is provided
    if not data or "pdfPath" not in data:
        return jsonify({"error": "Missing pdfPath in request"}), 400
    if "emailBody" not in data:
        return jsonify({"error": "Missing emailBody in request"}), 400

    pdf_path = data["pdfPath"]
    email_body: Optional[str] = data["emailBody"]

    try:
        bucket_name = "odex-warehouse-document-dev"
        # Check if the pdf_path is an S3 URL
        if pdf_path.startswith(bucket_name) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)

            # Get the PDF file from S3
            file_name = "ocr_file.pdf"
            local_file_path = os.path.join(os.getcwd(), file_name)
            s3_client.download_file(bucket_name, object_key, local_file_path)
            doc_type = detect_document_type(local_file_path)

        else:
            return jsonify({"error": "Invalid file path provided"}), 400

        start_time = time.time()
        # Process the PDF and return the result
        if doc_type == "INV":
            result = extraction_invoice(local_file_path, email_body)
            if os.path.exists(file_name):
                os.remove(file_name)
            json_content = (
                result.strip().
                replace("```json", "").
                replace("```", "").strip()
            )
            result_json = json.loads(json_content)

            result_json["docType"] = "INV"

            print(f"\n\n\n\n\n\n\nJSON output: {str(result_json) }")
            return jsonify(result_json)

        if doc_type == "DO":
            result = extraction_do(local_file_path, email_body)

            if os.path.exists(file_name):
                os.remove(file_name)

            json_content = (
                result.strip().
                replace("```json", "").
                replace("```", "").strip()
            )
            result_json = json.loads(json_content)

            result_json["docType"] = "DO"

            print(f"JSON output: {str(result_json) }")
            return jsonify(result_json)

    except Exception as e:
        end_time = time.time()
        print(f"Time taken: {end_time-start_time} seconds")
        return jsonify({"error": str(e)}), 500


@app.route("/pop", methods=["POST"])
def pop_endpoint():
    
    data = request.get_json()

    # Check if pdf_path is provided
    if not data or "pdfPath" not in data:
        return jsonify({"error": "Missing pdfPath in request"}), 400

    pdf_path = data["pdfPath"]
    print(pdf_path)
    try:
        bucket_name = "odex-warehouse-document-dev"
        # Check if the pdf_path is an S3 URL
        if pdf_path.startswith(bucket_name) or "/" in pdf_path:
            bucket_name, object_key = parse_s3_url(pdf_path)

            # Get the PDF file from S3
            if pdf_path.lower().endswith(".pdf"):
                file_name = "parsing_pop.pdf"
            else:
                file_name = "parsing_pop"

            local_file_path = os.path.join(os.getcwd(), file_name)
            s3_client.download_file(bucket_name, object_key, local_file_path)

        else:
            return jsonify({"error": "Invalid file path provided"}), 400

        # Process the PDF and return the result
        result = extraction_pop(file_name)
        if os.path.exists(file_name):
            os.remove(file_name)
            
        
        json_content = (result.strip().
                        replace("```json", "").
                        replace("```", "").
                        strip()
                        )
        result_json = json.loads(json_content)
        if isinstance(result_json, dict):
            result_json["docType"] = "POP"
            return jsonify(result_json)
        elif isinstance(result_json, list):
    # If it's a list of dicts, add to each dict
            for item in result_json:
                if isinstance(item, dict):
                    item["docType"] = "POP"
                else:
                    raise ValueError("List item is not a dictionary")
        else:
            raise ValueError("JSON is neither dict nor list")
        return jsonify(result_json)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
        
def parse_s3_url(s3_url):
    # Remove extra slashes if they exist
    s3_url = s3_url.lstrip("/")

    # Split the URL into bucket name and object key at the first '/'
    bucket_name, object_key = s3_url.split("/", 1)

    return bucket_name, object_key


@app.route("/", methods=["GET"])
def index():
    return jsonify({"message": "PDF API is running"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=8080, threaded=True)