from rapidfuzz import fuzz, process
from document_processing_services import plumber_extract, tessaract_ocr
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
import logging
import joblib

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # You can change to DEBUG, WARNING, etc.
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Extended keyword lists with abbreviations
invoice_keywords = {
    "Invoice No",
    "Invoice Number",
    "Inv No",
    "Inv#",
    "Tax Invoice",
    "Bill No",
    "Serial number of invoice",
    "Serial no of invoice",
    "Import Proforma Invoice",
    "Draft Inv No"
}
do_keywords = {
    "DO No",
    "Delivery Order",
    "Dispatch Order",
    "Delivery Note",
    "D.O."}

mbl_keywords = {
    "MBL No",
    "Master Bill of Lading",
    "Master BL No",
    "MBL Number",
    "MBL#",
    "MBL No.",
    "MBL Number.",
    "Master BL Number"
}
hbl_keywords = {
    "HBL No",
    "House Bill of Lading",
    "House BL No",
    "HBL Number",
    "HBL#",
    "HBL No.",
    "HBL Number.",
    "House BL Number"
}
bl_keywords = {
    "consignee",
    "shipper"
    "BL No",
    "Bill of Lading",
    "BL Number",
    "BL#",
    "BL No.",
    "BL Number.",
    "Bill of Lading Number",
        "MBL No",
    "Master Bill of Lading",
    "Master BL No",
    "MBL Number",
    "MBL#",
    "MBL No.",
    "MBL Number.",
    "Master BL Number",
        "HBL No",
    "House Bill of Lading",
    "House BL No",
    "HBL Number",
    "HBL#",
    "HBL No.",
    "HBL Number.",
    "House BL Number"
}
pop_keywords = {
    "POP No",
    "Proof of Payment",
    "POP Number",
    "POP#",
    "POP No.",
    "POP Number."
}

"""Text trimming if required"""
# len_text = len(scanned_text)
# print(len_text)
# scanned_text = scanned_text[: int(0.1*len_text)]
# print(len(scanned_text))


def detect_document_type(pdf_path, threshold=50):
    scanned_text = plumber_extract(pdf_path)
    if not scanned_text:
        scanned_text = tessaract_ocr(pdf_path)
        
    scanned_text_lower = scanned_text.lower()

    best_invoice = process.extractOne(
        scanned_text_lower, invoice_keywords, scorer=fuzz.partial_ratio
    )
    best_do = process.extractOne(
        scanned_text_lower, do_keywords, scorer=fuzz.partial_ratio
    )
    best_bl = process.extractOne(
        scanned_text_lower, bl_keywords, scorer=fuzz.partial_ratio
    )

    invoice_score = best_invoice[1] if best_invoice else 0
    do_score = best_do[1] if best_do else 0
    bl_score = best_bl[1] if best_bl else 0

    logging.info(f"Invoice match: {best_invoice}")
    logging.info(f"DO match: {best_do}")
    logging.info(f"BL match: {best_bl}")

    if max(invoice_score, do_score, bl_score) < threshold:
        return "Unclear"

    if invoice_score > do_score and invoice_score > bl_score:
        return "INV"
    elif do_score > invoice_score and do_score > bl_score:
        return "DO"
    elif bl_score > invoice_score and bl_score > do_score:
        return "BL"
    else:
        # If scores are equal, return the one with the highest score
        if invoice_score == do_score:
            return "INV" if invoice_score > bl_score else "DO"
        elif invoice_score == bl_score:
            return "INV" if invoice_score > do_score else "BL"
        elif do_score == bl_score:
            return "DO" if do_score > invoice_score else "BL"
    # return "INV" if invoice_score > do_score else "DO"

# def detect_bl_document_type():
#     """ This will split between MBL and MHBL."""
#     scanned_text = plumber_extract(pdf_path)
#     if not scanned_text:
#         scanned_text = tessaract_ocr(pdf_path)
        
#     scanned_text_lower = scanned_text.lower()
    
#     pass


# # -----------------------------
# # EMBEDDINGS + ML CLASSIFIER
# # -----------------------------
# class HybridClassifier:
#     def __init__(self, model_name="all-MiniLM-L6-v2"):
#         self.model = SentenceTransformer(model_name)
#         self.clf = None

#     def train(self, docs, labels):
#         embeddings = self.model.encode(docs)
#         self.clf = LogisticRegression(max_iter=500)
#         self.clf.fit(embeddings, labels)

#     def predict(self, text):
#         if not self.clf:
#             raise ValueError("Classifier not trained!")
#         embedding = self.model.encode([text])
#         return self.clf.predict(embedding)[0], self.clf.predict_proba(embedding).max()

#     def save(self, path):
#         joblib.dump(self.clf, path)

#     def load(self, path):
#         self.clf = joblib.load(path)



# # -----------------------------
# # NEW CLASSIFICATION FUNCTION
# # -----------------------------
# def new_classification(pdf_path, classifier: HybridClassifier, conf_threshold=0.6):
#     scanned_text = plumber_extract(pdf_path)
#     if not scanned_text:
#         scanned_text = tessaract_ocr(pdf_path)

#     scanned_text_lower = scanned_text.lower()


#     # Predict using trained classifier
#     predicted_label, confidence = classifier.predict(scanned_text_lower)


#     if confidence < conf_threshold:
#         return f"Uncertain ({predicted_label})"
    
#     return predicted_label

# -----------------------------
# EXAMPLE USAGE
# -----------------------------
# if __name__ == "__main__":
# # Training dataset (example)
#     train_texts = [
#     "This is an invoice with invoice number 123",
#     "Delivery order for cargo XYZ",
#     "Storage order issued at port",
#     "Payment Successful, Transaction ID 876",
#     "Master Bill of Lading for shipment",
#     "House Bill of Lading issued by forwarder",
#     ]
#     train_labels = ["INV", "DO", "SO", "POP", "MBL", "HBL"]


#     classifier = HybridClassifier()
#     classifier.train(train_texts, train_labels)


#     test_file = "2502333 MBL.PDF" # replace with real file
#     result = new_classification(test_file, classifier)
#     print(f"Predicted class: {result}")

# if __name__ == "__main__":
#     # Example usage
#     pdf_path = "sample.pdf"  # Replace with your PDF file path
#     print(detect_document_type(pdf_path))
#     # classifier = HybridClassifier()
#     # classifier.train(train_texts, train_labels)
#     # print(new_classification(pdf_path, classifier))
