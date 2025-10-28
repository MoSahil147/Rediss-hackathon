from mistralai import Mistral
import pytesseract
import pdfplumber
import os
import io
from dotenv import load_dotenv
import fitz  # PyMuPDF
from PyPDF2 import PdfReader, PdfWriter # For PDF manipulation
from PIL import Image

# Loading the .env file to get the API key
load_dotenv()
api_key = os.getenv("API_KEY")

# PDF Plumber extract function
def plumber_extract(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(
            [page.extract_text() for page in pdf.pages if page.extract_text()]
        )
    return text

# PyMuPDF extract function
def pymupdf_extract(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = ""
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        full_text += page.get_text()
    return full_text

# Mistral OCR extract function
def mistral_ocr(pdf_path):
    client = Mistral(api_key=api_key)

    # Open file using 'with' so it closes after use
    with open(pdf_path, "rb") as f:
        uploaded_pdf = client.files.upload(
            file={
                "file_name": "PDF",
                "content": f,
            },
            purpose="ocr",
        )

    # File is now closed, safe to continue
    client.files.retrieve(file_id=uploaded_pdf.id)
    signed_url = client.files.get_signed_url(file_id=uploaded_pdf.id)

    ocr_response = client.ocr.process(
        model="mistral-ocr-latest",
        document={
            "type": "document_url",
            "document_url": signed_url.url,
        },
    )

    return ocr_response

# PyTesseract OCR extract functiopdftotextn
def tessaract_ocr(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    full_text: str = ""

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=300)  # high resolution for better OCR
        img_data = pix.tobytes("png")

        image = Image.open(io.BytesIO(img_data))
        text = pytesseract.image_to_string(image, lang="eng")

        full_text += f"\n--- Page {page_num + 1} ---\n{text}"

    return full_text

def bl_extraction(pdf_path: str) -> str:
    # Try different extraction methods
    text = plumber_extract(pdf_path)
    if text.strip():
        return text

    text = tessaract_ocr(pdf_path)
    if text.strip():
        return text

def split_pdf_into_pages(input_pdf_path, output_dir):
    """
    Splits a multi-page PDF into individual pages.

    Args:
        input_pdf_path (str): The path to the input PDF file.
        output_dir (str): The directory where the single-page PDFs will be saved.
    """
    # Create the output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Open the input PDF file
    try:
        with open(input_pdf_path, "rb") as file:
            reader = PdfReader(file)
            num_pages = len(reader.pages)
            print(f"The document '{os.path.basename(input_pdf_path)}' has {num_pages} pages.")

            # Get the base name of the input file to use for output files
            base_filename = os.path.splitext(os.path.basename(input_pdf_path))[0]

            # Loop through all the pages and save each as a new PDF
            for i in range(num_pages):
                writer = PdfWriter()
                writer.add_page(reader.pages[i])

                output_filename = f"{base_filename}_page_{i + 1}.pdf"
                output_filepath = os.path.join(output_dir, output_filename)

                with open(output_filepath, "wb") as output_pdf:
                    writer.write(output_pdf)
                
                print(f"Saved: {output_filepath}")

    except FileNotFoundError:
        print(f"Error: The file '{input_pdf_path}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

# --- Example Usage ---
if __name__ == "__main__":
    # Replace 'consolidated_document.pdf' with the path to your actual PDF file
    input_file = "consolidated_document.pdf" 
    
    # The split pages will be saved in a folder named 'split_pages'
    output_folder = "split_pages"

    split_pdf_into_pages(input_file, output_folder)
