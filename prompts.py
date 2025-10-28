from typing import Optional
from schemas import INVOICE_JSON_SCHEMA, DO_JSON_SCHEMA, MPCI_JSON_SCHEMA
from rag_setup import comparison


def get_invoice_prompt(
        text: str,
        ocr_response: str,
        email_body: Optional[str] = "",
        tes=None
):
    """Generate prompt for invoice extraction based on available text sources"""

    base_prompt = f"""
    You are an intelligent document parser. Extract the following fields from the text:

    First Identify the Shipping Line the Document Belongs Too.These could be
    Hapag-Lloyd,PIL,CMA,MSC or others

    Extract shipping document values from the document text of the Shipping Lines and from the email body.

    Find exactly these fields in the text:
    1. Bill of Lading (BL) Number
    2. Export Invoice Number
    3. Total Amount (as a float)
    4. Currency (in ISO 4217 format or convert to that format if found in
       normal text format)
    5. Shipping Line Name
    6. Customer Name(Always the Name of a Company)
    7. Invoice Date
    8. Port of Loading
    9. Port of Dispatch
    10. Bank Account Details (as an array if multiple accounts exist)
    11. Customer Tax ID
    12. Shipping Tax ID
    13. Container List (if available,it will include container dimensions as well)
    14. Total Amount 2(in some PIL invoices there is a total invoice in
        another currency,will only be present in the final total amount field,
        if null dont include in output)
    15. Currency 2(in some PIL invoice the bill is in 2 currencies,will only
        be present in the final total amount field,if null dont include in output)
    16. Exchange Rate (capture only if value is more than 1)

    mark fields as null if no information is available.
    Return ONLY this JSON format:
    {INVOICE_JSON_SCHEMA}


    If the Document is of Hapag-Lloyd:
    -The Shipping Line Name and TaxID(TIN) are usually located at the top or
     start of the document
    -The Customer Name is the Company Name and not numerical with their
     TaxID(TIN) being located near the company name
    -The Invoice Data is usually located right next to the Invoice Number
    -An example invoice date is DEC. 17,2023 convert this to DD-MM-YYYY format
    -The POL is usally where the cargo is coming from and the POD is where it
     is going to ignore the Port it is via
    -The Bank Details are usually located towards the end and all the
     information needs to be stored.
    -In some documents the total amount might be negatice cpatue the - sign
     as well
    -In some invoices Credit note no. contains the Export Invoice No.
    -In the Vietnamese Invoice the Invoice Number is Next to Ref No.

    If the Document is of PIL:
    -If the TaxID or number is not clearly psecified leave it as null
    -The Customer Name is the Name of the Company and not an actual name
    -In some documents there are 2 total amounts each with different
     currencies capture both the total amounts and both currencies in the
     resepctive fields

    If the Document is of CMA:
    -The Shipping Line Name is the one to whom the Invoice is Payable and is
     typically mentioned along with the address header.
    -The Tax ID (TRN) is usually labeled with "TRN" or
     "Tax Registration Number".
    -The Customer Name is the entity mentioned under "Invoice To".
    -The Invoice Number can appear next to or below labels like
     "Bill of Lading" or "Your Ref". It typically has an alphanumeric pattern
     starting with AEEX or INKL or anything, and is NOT "COPY 1 OF 1".
    -The correct Invoice Number is the alphanumeric string following the Bill
     of Lading number (e.g., AEEX0967374). Disregard any label such as
     “COPY 1 OF 1”.
    -The BL (Bill of Lading) number is the first alphanumeric string after the
     label “Bill of Lading”, often starting with DXB or similar port codes.
     If there are two numbers, select the first one only.
    -The Shipping Line TRN should be set to null unless it appears within 6
     lines of the Shipping Line Name.


    If the Document is Of MSC-
    -Customer name is the Details of Reciever the company name and TAXID(GSTIN)
     is below it
    -The Bank Account details is usually towards the end capture all details
    -The Bill of Lading Number is a lone alphanumeric number and does not
     contain seperators
    -The currency is given in full words with the total amount in words
     convert it to the three code format


    General Rules-
    - "name" is the exact field label found in text
    - "value" is the corresponding value
    - Each field must have exactly one value
    -For Bank Account Details Consider the entire text containing bank details
     and address usually located at the bottom of the pdf.
    -Shipping Line Name may be who the Invoice is Payable To
    -Shipping Line TaxID is usually near the Shipping Line Name Itself
    -Currency May not always be next to the total amount
    -Total Amount is the final Invoice Total
    -BL Number is also called as Bill of Lading or SWB Number
    -Customer Name is always the Company Name
    -Date should be converted to DD-MM-YYYY format
    -If TaxID not specified with value as TaxID or GSTIN or anything similar
     leave it null,don't consider it as PAN No.
    -Invoice Number is usally a single alphanumeric string without any spaces
    -Container Size should only contain dimensions of the Container
     (Example-32' X 8'7") and Container Type should only contain type of the
     container(text)
    -If a single PDF contains multiple invoices extract the json for each of the
     invoices.
    -The Exchange rate is normally under the header Ex Rate or something similar and is located next to currency
    -In invoice charges list, If there is a key "Freight" (ignore case) then set invoiceType value as "FREIGHT"
    else "NON-FREIGHT"
    """

    if text:
        # If text is available from pdfplumber, use it as primary source
        prompt = f"""{base_prompt}
        -If the BL ID and number are both returned consider only the BL number part
        -In the Container List if some fields are null do not display those

        If the shipping line is not one of the five,try to extract the filed by
        generalzing the information given above

        NO explanations. JSON ONLY.

        The text to be analyzed from the document is below-
        {text}


        If any fields are coming as null consider the following OCR output from
        the signed URL as well,but if not explicitly found leave the fields as
        null
        {ocr_response}
        """
    else:
        # If no text from pdfplumber, use tesseract OCR output
        prompt = f"""{base_prompt}

        If the shipping line is not one of the five,try to extract the filed by
        generalzing the information given above

        NO explanations. JSON ONLY.

        The text to be analyzed from the document is below-
        {tes}
        """

    if email_body:
        prompt = f"""{prompt}
`
        The text to be analyzed from the email body is below:
        {email_body}
        """

    print(prompt)
    return prompt


def do_prompt(
        text: str,
        ocr_response: str,
        email_body: Optional[str],
        tes=None
):
    """Generate prompt for DO extraction"""

    base_prompt = f"""
    The following kinds of fields are to be extracted from the document and the email body.
    The rules for finding these fields are as follows:
      1. Extract all header fields individually
      2. Extract all fields and values from the equipment table
      3. If no equipment table exists, extract all the fields and values from container number column.
      4. Container number column will have container number and seal numbers below/nearby (don't count seal numbers as separate containers)
      5. Container size is often a two-digit code (e.g., C2) in a column near container numbers
      6. Look for "valid upto", "DO Validity" or similar fields for validity date
      7. BL Number should only be alphanumeric without additional characters
      8. "Issued to" field contains company details below field name (not adjacent)
      9. "To" and "Issued to" are different fields - extract "Issued to"
      10. Classify document type as "storing" or "delivery" (depot allocation = storing)
      11. If a document has both types perform the extraction for each of the documents and display only those fields present for each of respective documents.

    GENERAL RULES:
    - Return null for unavailable fields
    - Extract only clearly marked key-value pairs
    - Format date fields as DD-MM-YYYY
    - Output keys should be in camelCase format
    - Omit fields that aren't available in the document
    - If document includes description of goods, include it
    - If fields are unavailable from the document, fetch from the email body

    NO explanations. JSON ONLY.
    Return ONLY this JSON format:
    {DO_JSON_SCHEMA}
    The text from OCR to be analyzed from the document is below-
    {ocr_response}
    Validate the text results with this other OCR, check if any field is missing:
    {text}
    """
    if(text):
         prompt = f"""{base_prompt}
            The text to be analyzed from the document is below-
            {ocr_response}
            Validate the text results from this other OCR, check if any field is missing:
            {text}
            """
    else:
        prompt = f"""{base_prompt}
                The text to be analyzed from the document is below-
                {ocr_response}
                Validate the text results from this other OCR, check if any field is missing:
                {tes}
                """

    if email_body:
        prompt = f"""{prompt}
`
        The text to be analyzed from the email body is below:
        {email_body}
        """

    return prompt


def pop_prompt(text):
   prompt_pop=f""""
   Extract all Key and Value information in Key-Value JSON format.
   Ensure that the Keys follow camelCase.
   Use only the Keys from the headers given in the text. Don't create your own
   Use only fields in the document
   Don't repeat fields if values are same
   The text to be analyzed is given below. JSON output ONLY, no additional text.
   -If the field values are N/A or not found dont display them
   {text}
   """
   return prompt_pop


def bl_splitting_prompt(
        text: str,
        email_subject: Optional[str] = "",
        ocr_response: Optional[str] = "",
        tes = None
    ):
    prompt_bl_split = f"""
    You are a document analysis agent. 
    Your task is to split a Bill of Lading (BL) document into its constituent parts: Master BL (MBL), House BL (HBL), and other pages.

    Rules:
    1. MBLs are issued by carriers (Maersk, Hapag-Lloyd, CMA CGM, etc.) and usually show 'B/L No.'.
    2. HBLs are issued by freight forwarders (AA&S Shipping LLC, CSSLine, etc.) and may appear as 'House B/L', 'Consignor Bill/Lading Number'.
    3. A new BL document begins whenever a **new BL Number** (or House BL Number) appears. If the BL Number repeats across pages, treat as continuation.
    4. For all HBLs, `mblNumber` must be the parent MBL number. `shippingLineName` must be the carrier name from the parent MBL.
    5. Pages without a BL number but containing freight tables, manifests, or terms must be counted under "others".
    6. Output MUST be JSON only, strictly in this schema:
    {{
    "total_pages": <int>,
    "bl_details": [
        {{
        "blType": "MBL" or "HBL",
        "startPage": <int>,
        "endPage": <int>,
        "mblNumber": "<string or null>",
        "hblNumber": "<string or null>",
        "shippingLineName": "<string or null>"
        }}
    ],
    "others": <int>
    }}

    Email Subject: {email_subject}
    Document Text: {text if text else ocr_response}
    OCR Text: {tes}
    """

    return prompt_bl_split

def groq_bl_splitting_prompt(
        text: str,
        email_subject: Optional[str] = "",
        ocr_response: Optional[str] = "",
        tes = None
    ):
    prompt_bl_split = f"""
    You are a document analysis agent. 
    Your task is to split a Bill of Lading (BL) document into its constituent parts: Master BL (MBL), House BL (HBL), and other pages.
    
    Follow these rules:
    1.  **MBL vs. HBL:** MBLs are issued by major shipping lines (e.g., KMTC LINE, Maersk, Hapag-Lloyd, CMA CGM, etc). HBLs are issued by freight forwarders (e.g., CONSOLE SHIPPING SERVICES, CSSLine).
        Normally if any carrier (like KMTC, Maersk, Hapag-Lloyd, CMA CGMA, PIL, etc) is there in the page its an MBL.
    2.  **Document Break:** A new document (MBL or HBL) starts on a page with a new, distinct Bill of Lading number. Sometimes one MBL or HBL might span across pages look for the bl number in each page if its a new bl means a new start of a document. if its the same bl number as the previous page or no bl number mentioned then its the same bl document.
    3.  **Other Pages:** Pages that are export or cargo manifests, tables, or lack a clear BL structure are "others".
    4. **EMAIL SUBJECT:** {email_subject} (Capture MBL Number, Parent BL Issuing Party Name (Shipping Line Name)) from email subject. Now this Parent BL Issuing Party Name is the shippingLineName for the MBL & HBLs .
    5. IF IN EMAIL SUBJECT, MBL Num and Shipping Line Name is mentioned then that means the document attached is an HBL. 


    Your output MUST be a single JSON object and nothing else, conforming to this exact structure:
    {{
        "total_pages": <integer>,
        "bl_details": [
            {{
                "blType": "MBL" or "HBL",
                "startPage": <integer>,
                "endPage": <integer>,
                "mblNumber": "<string>", (if blType is MBL then return MBL Number from email subject if mentioned, or else find it in the document text for MBL, else if blType is HBL and no MBL then return null)
                "hblnumber" : "<string>" (if blType is HBL then return HBL Number else if blType is MBL then return null)
                "shippingLineName": "<string>" (Capture shipping line name or parent bl issuing party name from email subject return it here for both blType MBL and HBL)
            }}
        ],
        "others": <integer>
    }}

    Example Outputs:
    {{
        "total_pages": 12,
        "bl_details": [
            {{"blType": "MBL", "startPage": 1, "endPage": 3, "mblNumber": "KMTCDLH0933776", "hblNumber": None, "shippingLineName": "KMTC LINE"}},
            {{"blType": "HBL", "startPage": 5, "endPage": 5, "mblNumber": "KMTCDLH0933776", "hblNumber": "DEL/JEA/CSSI/166370", "shippingLineName": "KMTC LINE"}},
            {{"blType": "HBL", "startPage": 6, "endPage": 6, "mblNumber": "KMTCDLH0933776", "hblNumber": "DEL/JEA/CSSI/166387", "shippingLineName": "KMTC LINE"}}
        ],
        "others": 2
    }}

    NO explanations. JSON ONLY.

    ## INPUT DATA TO ANALYZE:

    Email Subject:
    {email_subject}
    
    Document Text:
    {text if text else ocr_response}

    The OCR Text from the document to be analyzed is below-
    {tes}

    """
    return prompt_bl_split


def bl_prompt(
        text: str,
        email_subject: Optional[str] = "",
        document_range: Optional[str] = "",
        rapid_ocr_json: Optional[str] = "",
        ocr_response: Optional[str] = "",
        tes=None
    ):
    #MPCI Styled BL Prompt
    """Generate prompt for BL extraction"""
    prompt_bl = f"""
        You are a data extraction specialist. 
        This document is a Bill of Lading (BL) document. There are 2 kinds of BL documents (Master Bill of Lading (MBL) & House Bill of Lading (HBL)).
        Your task is to populate a JSON schema for each House Bill of Lading (HBL) using the provided text.
        
        ## CONTEXT
        -   **EMAIL SUBJECT**: {email_subject} 
        -   **Document Info:** {document_range} (Capture the MBL Number and the Parent BL issuing part name or shipping line name from here.)
        -   Use the MBL number and shipping line from the context(either Email Subject or Document Info) as the 'parentBlNumber' and 'parentBlIssuingPartyName' for the HBL.
        -   **LOGIC:** if anything is menitoned in the email subject that is primary context. Look for MBL NUMBER AND SHIPPING LINE NAME from EMAIL SUBJECT.
                        If not then look for Document Info.
                        If in the doucment info you are going to see hbl documents then its repective shipping line is not parentBlIssuingPartyName. In that case look for only email subject. if nothing is mentioned the return null.
                        ALSO Look for if MBL NUMBER AND HBL NUMBER AND SHIPPING LINE NAMES of both MBL AND HBL Match then its wrong only return HBL data in that case.

        ## OUTPUT REQUIREMENTS
        -   Your output MUST be a JSON. Group the results based on the HBLs
        -   Make sure to group all the multiple hbl details under "blDetails", all the multiple item details under "itemDetails" and container details under "containerDetails".
        -   Make sure that the blDetails section contains only the multiple HBLs data, the containerDetails section contains only the container details data and itemDetails seciton contains only the item details data. Make sure its separate but grouped with their respective type irrespective of the order.
        -   Each object MUST strictly follow their respective schema from this main schema: {MPCI_JSON_SCHEMA}
        -   If a value for a field cannot be found, the value for that key MUST be null.
        -   For now focus on the fields that are to be extracted not the fields that are null. I have mentioned which fields can be null under each section.

        
        ## EXTRACTION RULES

        ## Fields to be STIRCTLY RETURNED NULL. EVEN IF YOU FIND ANYTHING DO NOT MAP THEM LEAVE THEM NULL. THIS IS A STRICT ORDER.
        1. - "Party Name", "Party MPCI ID", "parentBlIssuingPartyMpciId", "newSplitBLFiling", "originalBLNumber", "furtherConsolidation",  "freightPrepaid", 
            "Console Forwarder's MPCI ID", "movementType", "natureOfCargo", "placeOfBillIssue", "placeOfFreightPayment", "currency", "serviceRequirement", "remarks", 
            "shippingLineAgentName", "shippingLineAgentTaxId", "shippingLineAgentAddress", "shippingLineAgentCity", "shippingLineAgentCountry", 
            "updateFilingReason", "updateFilingRemarks", "newSwitchBlNumber" return always null.
            - "serviceRequirement" even if mentioned RETURN NULL
        2.  - "customsSeal" and "customsSealType", "sealingPartyName", "temperature", "temperatureUnit", "handlingInstruction", "vgmWeight", "removeContainerForSplitFiling", "newSplitBlNumber", "newParentBlNumber", "newVesselName", "newVoyageNumber" return null
        3.  - "shipperSealType" & "carrierSealType" always return null.
        4.  - "packingRelatedDescriptionCode", "imoClass", "unCode", "markingInstructions", "goodsItemCountryOfOrigin", "removeItem" return null.

        ### General Rules:
        Follow these rules strictly when filling the json schema:
        1.  **Dates:** Format all dates as DD-MM-YYYY.
        2. **Floats:** Convert these following fields to floats (eg: Amount = 1,809.00 should be 1809.00):
            Fields are: (If not found return null)
            1. "invoiceAmountOfTheCosginment"
            2. "temperature"
            3. "cargoGrossWeight"
            4. "vgmWeight"
            5. container & item's "numberOfPackages"
            6. container & item's "cargoGrossWeight"
            7. "cargoNetWeight"
            8. "volumeInMtq"
        3. Always look for the respetive data in the close vicnity of its peer fields, for example, an hs code for a container number would be in its close vicinty similary for other fields do the same. DO NOT FILL IN RANDOM DATA FOUND IN THE TEXT OF THE DOCUMENT.

        FOR BL Details
        - "Party Name", "Party MPCI ID", "parentBlIssuingPartyMpciId", "newSplitBLFiling", "originalBLNumber", "furtherConsolidation",  "freightPrepaid", 
            "Console Forwarder's MPCI ID", "movementType", "natureOfCargo", "placeOfBillIssue", "placeOfFreightPayment", "currency", "serviceRequirement", "remarks", 
            "shippingLineAgentName", "shippingLineAgentTaxId", "shippingLineAgentAddress", "shippingLineAgentCity", "shippingLineAgentCountry", 
            "updateFilingReason", "updateFilingRemarks", "newSwitchBlNumber" return always null.
        - "serviceRequirement" even if mentioned RETURN NULL
        - "consigneeTaxId" make sure to get this tax id from the Consignee Details, dont use any other tax id and return it as the value for this key.
        - "shipperCity" is a mandatory field return the shipper city name from the shipper address, as it is always mentioned. Return both the city and the capital/state if mentioned. (eg: Masdar City Abu Dhabi, Maadi Cairo (return the enitre field))
        - Shipping Line is not the same Shipping Line Agent so return always null even if found, for "shippingLineAgentName", "shippingLineAgentTaxId", "shippingLineAgentAddress", "shippingLineAgentCity", "shippingLineAgentCountry",
        - "filingFor" field should be one of the following values: "Self", "Shipping Line/NVOCC", "Partner/UAE Freight Forwarder". if not found return "Self"
        - For "portOfAcceptance", "portOfUnloading", "portofTranshipment", "portOfUnloading", "endDestination" fields capture only the port not the country or any other info (eg: MUNDRA, JEBEL ALI). STICK TO THIS FORMAT RETURN ONLY PORT NAME. NO COUNTRY.
        - "portOfAcceptance" can be place of receipt Only return the port (eg: for "ICD TUGHLAKABAD" just STRICTLY return TUGHLAKABAD). if not found return null
        - "portOfUnloading" is port of discharge. if not found return null.
        - "endDestination" is mostly place of delivery or port of destination. if not found return null.
        - When you are returning any of the port names, ONLY RETURN THE PORT NAME NOTHING ELSE. (eg: for JEBEL ALI Port Dubai, just return JEBEL ALI, or ICD (INTKD)_TUGHALAKABAD, THESE ARE SOME RANDOME EXAMPLES BUT POINT BEING RETURN ONLY THE NAME OF THE PORT NOTHING ELSE. ).
        - "blNumber" should be the bl or booking number mostly.
        - DO NOT HAVE ANY CONFUSION IN THE CONSIGNEE ADDRESS. THIS DATA IS MOSTLY MENTIONED IN ONE BLOCK. IF ADDRESS READS SUDDENLY FROM INDIA TO UAE. DO NOT RETURN IT. ANY ADDRESS IS NORMALLY A PO BOX NUMBER/PHONE NUMBER/EMAIL ID OR ANY OTHER INFO FOLLOWED BY ADDRESS.""
        - if in Notfiy part Name its written "same as consignee" then this means map the same consignee details to notify details also do not return "same As consignee".
        - "vesselName" should be the name of the ocean vessel. Its clearly mentioned as vessel name or vessel. (eg: Wantai)
        - "voyageNumber" is mostly found beside vessel name. (eg: 25008W, 023W)
        - "emirate" should be one of these values: "AZ-Abu Dhabi", "DU-Dubai", "SH-Sharjah", "AJ-Ajman", "FU-Fujairah", "RK-Ras Al Khaimah", "UM-Umm Al Quwain". if not found, return null
        - if "contactName" not found, then the value of "consgineeName" is also the value of "contactName"
        - "typeofBl" if not found return "NON-Non-Negotiable"
        - "currency" return the currency codes only in ISO 4217 format. if not found return null
        - "contactPartyType" if not found retrun default value "COM-Company"
        - The fields "shipperCountry", "consigneeCountry", "notifyPartyCountry", "deliveryAgentCountry", "freightForwardingAgentCountry", "shippingLineAgentCountry" should be the country code in "ISO 3166-1 alpha-2 format". if not found, return null.
        - For Frieght Forwarding Agent Name, Freight Forwarding Agent Address, Freight Forwarding Agent City, Freight Forwarding Agent Country, return the same details as Delivery Agent Name, Delivery Agent address and country and city also.
        
        FOR CONTAINER DETAILS
        - "customsSeal" and "customsSealType", "sealingPartyName", "temperature", "temperatureUnit", "handlingInstruction", "vgmWeight", "removeContainerForSplitFiling", "newSplitBlNumber", "newParentBlNumber", "newVesselName", "newVoyageNumber" return null
        - For "containerSize" field, this is mostly found beside container number or seal number (eg: 20GP, 20DQ, 20DRY, 20""DRY, 20', 40HC, 40'HIGHCUBE, 40FT HI Cube, 40'HQ, etc). For the most part it will something like this. 
            So accoridngly for these conaitner sizes if you enocunter any of these values (20GP, 20DQ, 20DRY, 20""DRY, 20') then map it to "20G1-20GP-GP CONTAINER" and if you encounter any of these values (40HC, 40'HIGHCUBE, 40FT HI Cube, 40'HQ) map it to "45G1-45GP-HIGH CUBE CONT.". So return exaclty whats there in the quotes. if notfound return null.
        - "containerStatus" will be in the container section as fcl or lcl, mostly lcl as hbl documents. Possible values to return: ("0-FCL", "1-LCL", "2-EMPTY"). if not found return null.
        - "shipperSealType" & "carrierSealType" always return null.
        - "Shipper Seal" can be found as "A/Seal No", "Agent Seal", "A SEAL", "A.S.No:", "L/SEAL - value". Return the value mentioned after the keys dont return the key itself. Moslty Seal number is Carrier Seal.
        - "carrierSeal" can be found as "C/Seal No" or "C.S.No:". Anything with carrier/c is carrier seal. Return the value mentioned after the keys dont return the key itself. (eg: C.S.No:12334, A.S.No: 4567, return 12334 & 4567 respectively) Return just the value.
        - "numberOfPackages" & "packageType" is always together. "packageType" can be Packages or Pallets or Cartons, etc.
        - "volume in mtq" is mostly Measurement
        - "grossWeight" is usually found return it (eg: 800.000 KGS etc) look for for Gross Weight Value Do not return Net weight value for Gross Weight.
        - For most of the cases, if its an hbl and there multiple hs codes that means its LCL/LCL
        - "containerNumber" should contain the container number nothing else. (eg: for SEGU1850570 /20GP, return SEGU1850570, eg2: TCNU 400696/0, return TCNU4006960) . Its normally a character of 4 letters and 7 numbers. So try to read the container number which will be 4 letters and 7numbers. thats it
        - For Number of Packages, Package Type, Gross weight, volume in mtq and item description, look for the data nearby the respective hbl number and hs code. Do not pick data from anywhere else. If you cannot find the data in the close vicinity of these fields return null.
        - number of packages will always be in the page with that hbl number do nto pick it up from anywhere else. Do not pick number of packages from mbl document info.
        - Container Status look for lcl/lcl or fcl/fcl in the close vicinity of their respective fields container number and blnumber. Do not fill in random data that you find here and there.
            If you dont find any lcl/lcl or lcl and find fcl/fcl or fcl mentioned somewhere return that.
        
        FOR ITEM DETAILS
        - If in the case where there are multiple Container numbers and only one HS Code, check for the total number of packages or total Gross Weight. If they match that means each container has the item with the same hscode. So repeat the same details for the hs code according to the number of packages and return its individual weight and package count accordingly.
        - Make sure in the case where there are multiple containers and single hs code you return multiple hs codes with respect to each container number and its individual item data.
        - "packingRelatedDescriptionCode", "imoClass", "unCode", "markingInstructions", "goodsItemCountryOfOrigin", "removeItem" return null.
        - "hsCode" if not found return null. IF ONE HS CODE GET THAT INFO for that item. If Multiple HSCodes then return multiple ITEM DETAILS JSON OBJECTS.
        - "hscodes" might look sometimes like this "3815.12.00". if it comes like this remove the dots and return "38151200". 
        - Only one Hs code and its info for one item, always make sure that every item has only one hs code and its repective details/info.
        - "itemDescritpion" is mostly found in description of goods or packages section.
        - "marksAndNumbers" is any data like (eg: 01 to 20 Packages) if any data found like that return it, else return value "No Marks"
        - For Number of Packages, Package Type, Gross weight, volume in mtq and item description, look for the data nearby the respective hbl number and hs code. Do not pick data from anywhere else. If you cannot find the data in the close vicinity of these fields return null.
        - "numberOfPackages" since it will always be a whole number, always return this value as an int.
        - look for any weight value or any cargo gross weight nearby volume in mtq value. capture that and return it as "cargoGrossWeight"
        - "consigneeType" return null.

        Other Observations:
        - Sometimes the data appears in this format, if not found like this then ignore this:
            YMMU1326128/20'/YMAS946842/2,305.58 KGS/1.920 CBM/3 PLTS/LCL-LCL
            Here the first part is container number, second part is container size code (refer to containerSize field deatils in container details section above), third part is carrier seal number, fourth part is gross weight, fifth parth is measurement, sixth part is package information, and then seventh part is container status.(refer to container status section for mapping)

        Return everything from schema. Group the result based on the HBLs. if not found, return as null.

        ## INPUT DATA TO ANALYZE:
        I have extracted text from both OCR and normal PDF Plumber text extraction. The OCR Text will be in the form of a JSON String containing the bounding box information also.
        You are to compare both the normal text and the ocr text along with the bounding box cooridnates and group the right info together and then return it to the right key as a value.

        The text from the document to be analyzed is given below. JSON output ONLY, no additional text.
        Text:
        {text if text else tes} 

        Email Subject:
        {email_subject}

        The Rapid OCR text & bounding box information in JSON is as follows. It is a list and it will contain the text followed by the bbox info in integer format.
        Rapid OCR JSON:
        {rapid_ocr_json}

        """
        # - "consigneeType" should be either a company (COM-Establishment) or individual (IND-Individuals). This is based on the consignee name. Moslty it is company so return "COM-Establishment"
        # - "shipperSealType" can be Electronic ("1-Electronic") or Mechanical (2-Mechanical). If found then return in the format mentioned in the () else if not found return null. DO NOT GUESS IF NOT FOUND RETURN NULL
    return prompt_bl

def bl_prompt_groq(
        text: str,
        email_subject: Optional[str] = "",
        document_range: Optional[str] = "",
        rapid_ocr_json: Optional[str] = "",
        ocr_response: Optional[str] = "",
        tes=None
    ):
    """Generate prompt for BL extraction using GPT models"""
    prompt_bl = f"""
    You are an expert document extraction agent.  
    The input is a Bill of Lading (BL) document.  
    BLs are of two types: Master BL (MBL) and House BL (HBL).  

    GOAL  
    Extract only HBL details and populate the provided JSON schema.  

    ---

    ## CONTEXT SOURCES
    - EMAIL SUBJECT: {email_subject}  
    - DOCUMENT INFO: {document_range}  
      - Extract MBL Number and Parent BL Issuing Party / Shipping Line from here.  
      - Priority for parent BL context:  
        1. Email Subject  
        2. Document Info  
        3. Else return null.  
      - If MBL Number and HBL Number match, discard MBL data and keep only HBL.  

    ---

    ## OUTPUT FORMAT (STRICT)
    - Output valid JSON only.  
    - Group results into:  
      - "blDetails" → all HBL info  
      - "containerDetails" → all container info  
      - "itemDetails" → all item info  
    - Each object MUST strictly follow this schema:  
      {MPCI_JSON_SCHEMA}  
    - If a field is not found, return null.  
    - Do not include any explanatory text outside the JSON.  

    ---

    ## RULES FOR EXTRACTION

    ### Always NULL (even if present in text)
    - Party Name, Party MPCI ID, parentBlIssuingPartyMpciId  
    - newSplitBLFiling, originalBLNumber, furtherConsolidation  
    - freightPrepaid, Console Forwarder's MPCI ID, movementType  
    - natureOfCargo, placeOfBillIssue, placeOfFreightPayment, currency  
    - serviceRequirement, remarks, shippingLineAgent* (all fields)  
    - updateFilingReason, updateFilingRemarks, newSwitchBlNumber  
    - customsSeal, customsSealType, sealingPartyName, vgmWeight  
    - temperature, temperatureUnit, handlingInstruction  
    - shipperSealType, carrierSealType  
    - packingRelatedDescriptionCode, imoClass, unCode, markingInstructions  
    - goodsItemCountryOfOrigin, removeItem  

    ### Formatting Rules
    - Dates: Always DD-MM-YYYY.  
    - Floats: Return as numeric (no commas). Applies to:  
      invoiceAmountOfTheCosginment, temperature, cargoGrossWeight, cargoNetWeight,  
      vgmWeight, volumeInMtq, numberOfPackages (if numeric).  
    - Ports: Return ONLY the port name (no country).  
      Example: "ICD TUGHLAKABAD" → "TUGHLAKABAD".  
    - Country codes: ISO 3166-1 alpha-2.  
    - Currency: ISO 4217.  

    ### BL Details
    - Consignee Tax ID → from Consignee block only.  
    - Shipper City → must return full "City, State" string.  
    - filingFor → one of ["Self", "Shipping Line/NVOCC", "Partner/UAE Freight Forwarder"], else "Self".  
    - endDestination = place of delivery (port only).  
    - vesselName = ship name (clear label).  
    - voyageNumber = numeric code next to vesselName.  
    - contactName = consigneeName if no explicit contact.  
    - typeOfBl = default "NON-Non-Negotiable" if not present.  
    - contactPartyType = "COM-Company" by default.  

    ### Container Details
    - containerNumber = 4 letters + 7 digits (normalize).  
    - containerSize mapping:  
      - 20GP/20DRY/20DQ → "20G1-20GP-GP CONTAINER"  
      - 40HC/40HQ/40FT HIGHCUBE → "45G1-45GP-HIGH CUBE CONT."  
    - containerStatus → "0-FCL" | "1-LCL" | "2-EMPTY"  
    - shipperSeal → text after A/Seal, Agent Seal, A.S.No etc.  
    - carrierSeal → text after C/Seal, C.S.No.  
    - Packages/GrossWeight/Volume → must come from vicinity of container/HS code.  

    ### Item Details
    - One HS code per item. If multiple HS codes, create multiple items.  
    - If multiple containers share one HS code, duplicate item per container with correct splits.  
    - marksAndNumbers → e.g. "01 to 20 Packages", else "No Marks".  
    - cargoGrossWeight → closest numeric value near HS code / volume.  
    - numberOfPackages → must be int.  

    ---

    ## INPUT DATA
    - Document Text:  
      {text if text else tes}  

    - Email Subject:  
      {email_subject}  

    - Rapid OCR JSON (with bounding boxes):  
      {rapid_ocr_json}  

    IMPORTANT: Output JSON ONLY. No explanations.
    """
    return prompt_bl



def rag_invoice_prompt(new_ocr_text,tes):

    if new_ocr_text:
        results=comparison(new_ocr_text,collection_name="invoices")
        prompt_rag = f"""
            Refer to the previous similar invoices:
            1. {results['documents'][0][0]} (Fields: {results['metadatas'][0][0]})


            Give dates in DD-MM-YYYY format
            NO explanations. JSON ONLY
            Return ContainerList and BankAccountDeatails as a List of Dicitonaries like json format
            Only Extract the same fields as in similar documents nothing extra

            The text to be analyzed from the document is below-
            {new_ocr_text}
        """

    else:
        results=comparison(tes,collection_name="invoices")
        prompt_rag = f"""
            Refer to the previous similar invoices:
            1. {results['documents'][0][0]} (Fields: {results['metadatas'][0][0]})


            Give dates in DD-MM-YYYY format
            NO explanations. JSON ONLY
            Return ContainerList and BankAccountDeatails as a List of Dicitonaries like json format
            Only Extract the same fields as in similar documents nothing extra

            The text to be analyzed from the document is below-
            {tes}
        """

    print(prompt_rag)
    return prompt_rag




def rag_do_prompt(new_ocr_text,tes):

    if new_ocr_text:
        results=comparison(new_ocr_text,collection_name="dorag")
        prompt_rag = f"""
                Refer to the previous similar invoices:
            1. {results['documents'][0][0]} (Fields: {results['metadatas'][0][0]})

                Give dates in DD-MM-YYYY format
                NO explanations. JSON ONLY
                Return ContainerList as a List of Dicitonaries like json format
                The BL Number is a single alphanumeric number
                The Seal Number is located directly below the Container Number in the table
                Only Extract the same fields as in similar documents nothing extra

                Only display those fields which are present
                The text to be analyzed from the document is below-
                {new_ocr_text}
            """

    else:
        results=comparison(tes,collection_name="dorag")
        prompt_rag = f"""
            Refer to the previous similar invoices:
            1. {results['documents'][0][0]} (Fields: {results['metadatas'][0][0]})

                Give dates in DD-MM-YYYY format
                NO explanations. JSON ONLY
                Return ContainerList as a List of Dicitonaries like json format
                The BL Number is a single alphanumeric number
                The Seal Number is located directly below the Container Number in the table
                Only Extract the same fields as in similar documents nothing extra

                Only display those fields which are present
                The text to be analyzed from the document is below-
                {tes}
             """

    print(prompt_rag)
    return prompt_rag
