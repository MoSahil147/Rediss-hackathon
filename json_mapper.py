import os
import json
import re
import logging
import pandas as pd
from datetime import datetime
from rapidfuzz import process, fuzz

from openpyxl import load_workbook
from openpyxl.worksheet.datavalidation import DataValidation
from excel_generator import excel_template_downlaoder, process_json_to_excel, upload_to_s3

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # You can change to DEBUG, WARNING, etc.
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

def transform_json(input_data):
    """
    Transforms the input JSON to the desired output JSON format.

    Args:
        input_data (dict): The input JSON data.

    Returns:
        dict: The transformed JSON data.
    """
    if isinstance(input_data, str):
        try:
            input_data = json.loads(input_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string provided: {e}")

    if not isinstance(input_data, dict):
        raise TypeError("input_data must be a dict or a valid JSON string")

    output_data = {"file": [], "errors": [], "xlsxName": "null", "xlsxPath": "null"}

    bl_details = input_data.get("blDetails", [])
    container_details = input_data.get("containerDetails", [])
    item_details = input_data.get("itemDetails", [])

    for bl in bl_details:
        output_bl = {
            "blRow": bl.get("blRow"),
            "integrationResponseTimestamp": "null",
            "modifiedAt": "null",
            "portOfTranshipment": bl.get("portOfTranshipment"),
            "invoiceAmount": "null", #bl.get("invoiceAmountOfTheCosginment"),
            "requestorPartyMpciId": "null",
            "mblDate": "null", # No direct mapping from input
            "mblIssuingPartyName": bl.get("parentBlIssuingPartyName"), 
            "placeOfIssue": "null", #bl.get("placeOfBillIssue"),
            "portOfAcceptance": bl.get("portOfAcceptance"),
            "onBehalfOfDesc": bl.get("filingFor"),
            "movementType": bl.get("movementType"),
            "versionNo": "null",
            "marksNumbers": "null", #Change
            "updateReasonDesc": "null", #bl.get("updateFilingReason"),
            "natureOfCargoCode": "null", #check
            "placeOfFreightPayment": "null", #bl.get("placeOfFreightPayment"),
            "issuingPartyMpciId": "null", #bl.get("partyMpciId")
            "placeOfIssueDesc": "null", #check
            "mpciHblId": "null", #check
            "requestorPartyName": "null", #check
            "mblIssuingPartyMpciId": "null", #check
            "integrationEntityId": "null", #check
            "ffPartyId": "null", #check
            "forwardingAgentPartyDetails": {
                "country": bl.get("freightForwardingAgentCountry"), #check
                "address": bl.get("freightForwardingAgentAddress"), #check
                "city": bl.get("freightForwardingAgentCity"), #check
                "contactName": "null", # No direct mapping from input for contactName inside this party
                "partySubType": "null",
                "emailId": "null", # No direct mapping from input for emailId inside this party
                "partyType": "FA",
                "phoneNumber": "null", # No direct mapping from input for phoneNumber inside this party
                "mpciHblPartyDetailsId": "null",
                "taxId": bl.get("freightForwardingAgentTaxID"),
                "partyName": bl.get("freightForwardingAgentName"),
                "postCode": "null",
                "taxIdType": "null"
            },
            "ffPartyMpciId": "null",
            "mblNo": bl.get("parentBlNumber"), # Assuming parentBlNumber is the MBL
            "parentBlIssuingPartyName": bl.get("parentBlIssuingPartyName"),
            "parentBlDate": "null", # No direct mapping from input for parentBlDate
            "voyageId": "null",
            "integrationStatus": "null",
            "natureOfCargoDesc": "null", #bl.get("natureOfCargo") Not mandatory at the moment
            "serviceRequirement": "null", #bl.get("serviceRequirement") Not mandatory at the moment
            "vesselName": bl.get("vesselName"),
            "odexMpciId": "null",
            "status": "null",
            "equipmentDetails": [], # latermate
            "dataCountry": "null",
            "shippingAgentPartyDetails": {
                "country": "null", #bl.get("shippingLineAgentCountry"),
                "address": "null", #bl.get("shippingLineAgentAddress"),
                "city": "null", #bl.get("shippingLineAgentCity"),
                "contactName": "null",
                "partySubType": "null",
                "emailId": "null",
                "partyType": "SA",
                "phoneNumber": "null",
                "mpciHblPartyDetailsId": "null",
                "taxId": "null", #bl.get("shippingLineAgentTaxID"),
                "partyName": "null", #bl.get("shippingLineAgentName"),
                "postCode": "null",
                "taxIdType": "null"
            },
            "updateRemark": "null", #bl.get("updateFilingRemarks"),
            "placeOfFreightPaymentDesc": "null",
            "consolePartyMpciId": "null", #bl.get("consoleForwardersMpciId") # Customer has to fill
            "onBehalfOf": "null",
            "issuingPartyName": "null", #bl.get("partyName")
            "portOfUnloading": bl.get("portOfUnloading"),
            "partnerUaeFfName": "null",
            "partnerUaeFfMpciId": "null",
            "freightType": "null", #"Prepaid" if bl.get("freightPrepaid", "").lower() == 'y' else "Collect",
            "integrationRequestTimestamp": "null",
            "consolePartyName": "null",
            "submittedPartnerId": "null",
            "endDestination": bl.get("endDestination"),
            "hblDate": (
                datetime.strptime(bl.get("blDate"), "%d-%m-%Y").strftime("%Y-%m-%dT%H:%M:%SZ")
                if bl.get("blDate") else "null"
            ),
            "furtherConsolidation": bl.get("furtherConsolidation"), # Customer Has to Fill
            "isSplitBl": "null", #bl.get("newSplitBlFiling"),
            "currency": bl.get("currency"),
            "modifiedBy": "null",
            "deliveyAgentPartyDetails": {
                "country": bl.get("deliveryAgentCountry"),
                "address": bl.get("deliveryAgentAddress"),
                "city": bl.get("deliveryAgentCity"),
                "contactName": "null",
                "partySubType": "null",
                "emailId": "null",
                "partyType": "DA",
                "phoneNumber": "null",
                "mpciHblPartyDetailsId": "null",
                "taxId": bl.get("deliveryAgentTaxID"),
                "partyName": bl.get("deliveryAgentName"),
                "postCode": "null",
                "taxIdType": "null"
            },
            "goodsDescription": "null", # This seems to be at the item level
            "voyageNo": bl.get("voyageNumber"),
            "submittedBy": "null",
            "referenceNo": "null",
            "submittedOn": "null",
            "switchBLNum": "null", #bl.get("newSwitchBlNumber"),
            "ffPartyName": "null",
            "consigneePartyDetails": {
                "country": bl.get("consigneeCountry"),
                "address": bl.get("consigneeAddress"),
                "city": bl.get("consigneeCity"),
                "contactName": bl.get("contactName") ,
                "partySubType": "null",
                "emailId": bl.get("emailId"),
                "partyType": "CN",
                "contactSubType": bl.get("consigneeType"),
                "phoneNumber": bl.get("phoneNumber"),
                "mpciHblPartyDetailsId": "null",
                "taxId": bl.get("consigneeTaxID"),
                "partyName": bl.get("consigneeName"),
                "postCode": "null",
                "taxIdType": "null"
            },
            "emirate": bl.get("emirate"),
            "hblNo": bl.get("blNumber"),
            "emirateName": bl.get("emirate"),
            "processingInformation": bl.get("typeOfBl"),
            "shipperPartyDetails": {
                "country": bl.get("shipperCountry"),
                "address": bl.get("shipperAddress"),
                "city": bl.get("shipperCity"),
                "contactName": "null",
                "partySubType": "null",
                "emailId": "null",
                "partyType": "CZ",
                "phoneNumber": "null",
                "mpciHblPartyDetailsId": "null",
                "taxId": bl.get("shipperTaxId"),
                "partyName": bl.get("shipperName"),
                "postCode": "null",
                "taxIdType": "null"
            },
            "originalBlNo": "null", #bl.get("originalBlNumber"),
            "portOfLoading": bl.get("portOfLoading"),
            "parentBlNumber": bl.get("parentBlNumber"),
            "updateReasonCode": "null",
            "remarks": "null", #bl.get("remarks"),
            "notifyPartyDetails": {
                "country": bl.get("notifyPartyCountry"),
                "address": bl.get("notifyPartyAddress"),
                "city": bl.get("notifyPartyCity"),
                "contactName": "null",
                "partySubType": "null",
                "emailId": "null",
                "partyType": "NI",
                "phoneNumber": "null",
                "mpciHblPartyDetailsId": "null",
                "taxId": bl.get("notifyPartyTaxID"),
                "partyName": bl.get("notifyPartyName"),
                "postCode": "null",
                "taxIdType": "null"
            }
        }

        # Filter containers for the current BL
        bl_containers = [c for c in container_details if c.get("blNumber") == bl.get("blNumber")]
        
        for container in bl_containers:
            output_container = {
                "cntRow": container.get("cntRow"),
                "newVoyage": "null", #container.get("newVoyageNumber"),
                "newParentBL": "null", #container.get("newParentBlNumber"),
                "equipmentSize": container.get("containerSize"),
                "cargoGrossWt": "null", # This is at the item level
                "noOfPackages": container.get("numberOfPackages"),
                "packageType": container.get("packageType"),
                "isDeleted": "N",
                "temperatureUnit": "null", #container.get("temperatureUnit"),
                "vgmWeight": "null", #container.get("vgmWeight"),
                "shipperSeal": container.get("shipperSeal"),
                "newBL": "null",
                "temperature": "null", #container.get("temperature"),
                "containerStatus": container.get("containerStatus"),
                "sealingPartyName": "null", #container.get("sealingPartyName"),
                "carrierSealTp": "null", #container.get("carrierSealType"),
                "removeForSplit": "null", #container.get("removeContainerForSplitFiling"),
                "customsSeal": container.get("customsSeal"),
                "carrierSeal": container.get("carrierSeal"),
                "customsSealTp": "null", #container.get("customsSealType"),
                "equipmentNumber": container.get("containerNumber"),
                "volumnMtq": "null", # This seems to be at the item level
                "containerTareWeight": "null",
                "isoCode": "null",
                "shipperSealTp": "null", #container.get("shipperSealType"),
                "mpciHblEquipmentDetailsId": "null",
                "items": [],
                "handlingInstructions": "null", # This is at the item level
                "newVessel": "null", #container.get("newVesselName")
            }

            # Filter items for the current container on the current BL
            container_items = [
                i for i in item_details 
                if i.get("blNumber") == bl.get("blNumber") and i.get("containerNumber") == container.get("containerNumber")
            ]

            for item in container_items:
                # Some column names differ between intermediate JSON and Excel roundtrip.
                # Pick the first non-empty value among common variants.
                def pick_first(*keys):
                    for key in keys:
                        val = item.get(key)
                        if val not in [None, "", "null", "NULL", "None"]:
                            return val
                    return None

                output_item = {
                    "itmRow": item.get("itmRow"),
                    "mpciHblEquipmentItemDetailsId": "null",
                    "imoClass": "null", #item.get("imoClass"),
                    # Support multiple source keys for cargo gross weight
                    "cargoGrossWt": pick_first(
                        "cargoGrossWeight", "cargoGrossWt", "grossWeight", "cargo_gross_weight", "Cargo Gross Weight (KGM)"
                    ),
                    "noOfPackages": item.get("numberOfPackages"),
                    "packageType": item.get("packageType"),
                    "volume": pick_first("volumeInMtq", "volume", "volumnMtq"),
                    "unCode": "null", #item.get("unCode"),
                    "isDeleted": "Y" if item.get("removeItem") == "Yes" else "N",
                    "hsCode": item.get("hsCode"),
                    "countryCode": item.get("goodsItemCountryOfOrigin"),
                    # Support multiple source keys for marks & numbers (Excel header variant included)
                    "marksNumbers": pick_first(
                        "marksAndNumbers",
                        "marksNumbers",
                        "Marks & Numbers",
                        "marks & numbers",
                        "Marks & numbers",
                        "marks_numbers"
                    ),
                    "markingInstructions": "null",
                    "itemDescription": item.get("itemDescription"),
                    "packageDescriptionCode": item.get("packageRelatedDescriptionCode"),
                    "cargoNetWt": item.get("cargoNetWeight")
                }
                output_container["items"].append(output_item)
                
                # Handling instructions can be aggregated at the container level if needed
                if item.get("handlingInstructions"):
                    if output_container["handlingInstructions"]:
                        output_container["handlingInstructions"] += f'; {item.get("handlingInstructions")}'
                    else:
                        output_container["handlingInstructions"] = item.get("handlingInstructions")

            output_bl["equipmentDetails"].append(output_container)
        
        # Aggregate goods description from all items
        all_item_descriptions = [
            item.get("itemDescription") for item in item_details if item.get("blNumber") == bl.get("blNumber") and item.get("itemDescription")
        ]
        if all_item_descriptions:
            output_bl["goodsDescription"] = "; ".join(all_item_descriptions)


        output_data["file"].append(output_bl)
    
    return output_data


def reverse_transform_json(input_data):
    """
    Reverse Transforms the input JSON (ODeX JSON) to the desired output JSON format (Excel JSON).

    Args:
        input_data (dict): The input JSON data.

    Returns:
        dict: The transformed JSON data.
    """

    if isinstance(input_data, str):
        try:
            input_data = json.loads(input_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON string provided: {e}")

    if not isinstance(input_data, dict):
        raise TypeError("input_data must be a dict or a valid JSON string")

    files = input_data.get("file", []) or []

    bl_details = []
    container_details = []
    item_details = []

    for bl in files:
        # Helper getters
        def g(obj, key, default=None):
            if obj is None:
                return default
            val = obj.get(key)
            return None if isinstance(val, str) and val.strip().lower() in ["null", "none", ""] else val

        # Parse BL date back to DD-MM-YYYY if present
        bl_date_raw = g(bl, "hblDate")
        bl_date = None
        if isinstance(bl_date_raw, str):
            try:
                # Expecting YYYY-MM-DDTHH:MM:SSZ
                dt = datetime.strptime(bl_date_raw, "%Y-%m-%dT%H:%M:%SZ")
                bl_date = dt.strftime("%d-%m-%Y")
            except Exception:
                # If format unknown, keep as-is
                bl_date = bl_date_raw

        # Prefer parentBlIssuingPartyName, fallback to mblIssuingPartyName
        parent_issuing_party = g(bl, "parentBlIssuingPartyName") or g(bl, "mblIssuingPartyName")

        bl_details.append({
            "filingFor": g(bl, "onBehalfOfDesc"),
            "partyName": g(bl, "issuingPartyName"),
            "partyMpciId": g(bl, "issuingPartyMpciId"),
            "blNumber": g(bl, "hblNo"),
            "blDate": bl_date,
            "parentBlNumber": g(bl, "parentBlNumber") or g(bl, "mblNo"),
            "parentBlIssuingPartyName": parent_issuing_party,
            "parentBlIssuingPartyMpciId": g(bl, "mblIssuingPartyMpciId"),
            "newSplitBlFiling": g(bl, "isSplitBl"),
            "originalBlNumber": g(bl, "originalBlNo"),
            "furtherConsolidation": g(bl, "furtherConsolidation"),
            "consoleForwardersMpciId": g(bl, "consolePartyMpciId"),
            "vesselName": g(bl, "vesselName"),
            "voyageNumber": g(bl, "voyageNo"),
            "movementType": g(bl, "movementType"),
            "portOfAcceptance": g(bl, "portOfAcceptance"),
            "portOfLoading": g(bl, "portOfLoading"),
            "portOfTranshipment": g(bl, "portOfTranshipment"),
            "portOfUnloading": g(bl, "portOfUnloading"),
            "endDestination": g(bl, "endDestination"),
            "emirate": g(bl, "emirate"),
            "natureOfCargo": g(bl, "natureOfCargoDesc"),
            "placeOfBillIssue": g(bl, "placeOfIssueDesc") or g(bl, "placeOfIssue"), #check
            "placeOfFreightPayment": g(bl, "placeOfFreightPaymentDesc") or g(bl, "placeOfFreightPayment"), #check
            "typeOfBl": g(bl, "processingInformation"),
            "freightPrepaid": g(bl, "freightType"),
            "invoiceAmountOfTheCosginment": g(bl, "invoiceAmount"),
            "currency": g(bl, "currency"),
            "serviceRequirement": g(bl, "serviceRequirement"),
            "remarks": g(bl, "remarks"),
            # Shipper
            "shipperName": g(g(bl, "shipperPartyDetails") or {}, "partyName"),
            "shipperTaxId": g(g(bl, "shipperPartyDetails") or {}, "taxId"),
            "shipperAddress": g(g(bl, "shipperPartyDetails") or {}, "address"),
            "shipperCity": g(g(bl, "shipperPartyDetails") or {}, "city"),
            "shipperCountry": g(g(bl, "shipperPartyDetails") or {}, "country"),
            # Consignee
            "consigneeName": g(g(bl, "consigneePartyDetails") or {}, "partyName"),
            "consigneeTaxID": g(g(bl, "consigneePartyDetails") or {}, "taxId"),
            "consigneeAddress": g(g(bl, "consigneePartyDetails") or {}, "address"),
            "consigneeCity": g(g(bl, "consigneePartyDetails") or {}, "city"),
            "consigneeCountry": g(g(bl, "consigneePartyDetails") or {}, "country"),
            "consigneeType": g(g(bl, "consigneePartyDetails") or {}, "contactSubType"),
            "contactName": g(g(bl, "consigneePartyDetails") or {}, "contactName"),
            "contactPartyType": None, #check
            "phoneNumber": g(g(bl, "consigneePartyDetails") or {}, "phoneNumber"),
            "emailId": g(g(bl, "consigneePartyDetails") or {}, "emailId"),
            # Notify Party
            "notifyPartyName": g(g(bl, "notifyPartyDetails") or {}, "partyName"),
            "notifyPartyTaxID": g(g(bl, "notifyPartyDetails") or {}, "taxId"),
            "notifyPartyAddress": g(g(bl, "notifyPartyDetails") or {}, "address"),
            "notifyPartyCity": g(g(bl, "notifyPartyDetails") or {}, "city"),
            "notifyPartyCountry": g(g(bl, "notifyPartyDetails") or {}, "country"),
            # Delivery Agent
            "deliveryAgentName": g(g(bl, "deliveyAgentPartyDetails") or {}, "partyName"),
            "deliveryAgentTaxID": g(g(bl, "deliveyAgentPartyDetails") or {}, "taxId"),
            "deliveryAgentAddress": g(g(bl, "deliveyAgentPartyDetails") or {}, "address"),
            "deliveryAgentCity": g(g(bl, "deliveyAgentPartyDetails") or {}, "city"),
            "deliveryAgentCountry": g(g(bl, "deliveyAgentPartyDetails") or {}, "country"),
            # Freight Forwarding Agent
            "freightForwardingAgentName": g(g(bl, "forwardingAgentPartyDetails") or {}, "partyName"),
            "freightForwardingAgentTaxID": g(g(bl, "forwardingAgentPartyDetails") or {}, "taxId"),
            "freightForwardingAgentAddress": g(g(bl, "forwardingAgentPartyDetails") or {}, "address"),
            "freightForwardingAgentCity": g(g(bl, "forwardingAgentPartyDetails") or {}, "city"),
            "freightForwardingAgentCountry": g(g(bl, "forwardingAgentPartyDetails") or {}, "country"),
            # Shipping Line Agent
            "shippingLineAgentName": g(g(bl, "shippingAgentPartyDetails") or {}, "partyName"),
            "shippingLineAgentTaxID": g(g(bl, "shippingAgentPartyDetails") or {}, "taxId"),
            "shippingLineAgentAddress": g(g(bl, "shippingAgentPartyDetails") or {}, "address"),
            "shippingLineAgentCity": g(g(bl, "shippingAgentPartyDetails") or {}, "city"),
            "shippingLineAgentCountry": g(g(bl, "shippingAgentPartyDetails") or {}, "country"),
            # Update reasons
            "updateFilingReason": g(bl, "updateReasonDesc"),
            "updateFilingRemarks": g(bl, "updateRemark"),
            "newSwitchBlNumber": g(bl, "switchBLNum"),
        })

        # Containers and Items
        for cont in (g(bl, "equipmentDetails") or []):
            container_details.append({
                "blNumber": g(bl, "hblNo"),
                "containerNumber": g(cont, "equipmentNumber"),
                "containerSize": g(cont, "equipmentSize"),
                "containerStatus": g(cont, "containerStatus"),
                "shipperSeal": g(cont, "shipperSeal"),
                "shipperSealType": g(cont, "shipperSealTp"),
                "carrierSeal": g(cont, "carrierSeal"),
                "carrierSealType": g(cont, "carrierSealTp"),
                "customsSeal": g(cont, "customsSeal"),
                "customsSealType": g(cont, "customsSealTp"),
                "sealingPartyName": g(cont, "sealingPartyName"),
                "temperature": g(cont, "temperature"),
                "temperatureUnit": g(cont, "temperatureUnit"),
                "numberOfPackages": g(cont, "noOfPackages"),
                "packageType": g(cont, "packageType"),
                "vgmWeight": g(cont, "vgmWeight"),
                "removeContainerForSplitFiling": g(cont, "removeForSplit"),
                "newSplitBlNumber": g(cont, "newBL"),
                "newParentBlNumber": g(cont, "newParentBL"),
                "newVesselName": g(cont, "newVessel"),
                "newVoyageNumber": g(cont, "newVoyage"),
            })

            for item in (g(cont, "items") or []):
                # Map isDeleted -> removeItem
                is_deleted = g(item, "isDeleted")
                remove_item = "Yes" if isinstance(is_deleted, str) and is_deleted.upper() == "Y" else None

                item_details.append({
                    "blNumber": g(bl, "hblNo"),
                    "containerNumber": g(cont, "equipmentNumber"),
                    "hsCode": g(item, "hsCode"),
                    "numberOfPackages": g(item, "noOfPackages"),
                    "packageType": g(item, "packageType"),
                    "packageRelatedDescriptionCode": g(item, "packageDescriptionCode"),
                    "cargoGrossWeight": g(item, "cargoGrossWt"),
                    "cargoNetWeight": g(item, "cargoNetWt"),
                    "volumeInMtq": g(item, "volume"),
                    "imoClass": g(item, "imoClass"),
                    "unCode": g(item, "unCode"),
                    "itemDescription": g(item, "itemDescription"),
                    "marksAndNumbers": g(item, "marksNumbers"),
                    "handlingInstructions": g(cont, "handlingInstructions"),
                    "goodsItemCountryOfOrigin": g(item, "countryCode"),
                    "removeItem": remove_item,
                })

    output = {
        "blDetails": bl_details,
        "containerDetails": container_details,
        "itemDetails": item_details,
    }

    return json.dumps(output, ensure_ascii=False)



def map_port_codes(main_json, data_codes_file="data_codes.json"):
    """
    Reads the port codes from the JSON file ("data_codes.json") 
    and maps specified fields in main_json to their corresponding 
    CODE-UPPERCASE LABEL format using a robust fuzzy matching strategy.
    
    Args:
        main_json (dict): The main JSON containing shipping data.
        data_codes_file (str): Path to the JSON file with port codes.
    
    Returns:
        dict: Updated main_json with mapped port codes.
    """

    # Load port codes mapping
    try:
        with open(data_codes_file, "r", encoding="utf-8-sig") as f:
            port_data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Data codes file not found at '{data_codes_file}'")
        return main_json

    # Create dictionary mapping: LABEL (uppercase) -> CODE-LABEL (uppercase)
    port_mapping = {
        entry["label"].upper(): f'{entry["code"]}-{entry["label"].upper()}'
        for entry in port_data.get("port_codes", [])
    }
    port_labels = list(port_mapping.keys())

    # Fields to update (camelCase)
    fields_to_update = [
        "portOfAcceptance",
        "portOfLoading",
        "portOfTranshipment",
        "portOfUnloading",
        "endDestination"
    ]

    def find_best_match(value):
        """
        Cleans the input string and returns the best fuzzy match using token_set_ratio.
        """
        if not value:
            return None
        
        # 1. Pre-process the string: make uppercase, remove punctuation.
        value_upper = value.upper().strip()
        # This regex removes anything that is not a letter, number, or whitespace
        processed_value = re.sub(r'[^A-Z0-9\s]', '', value_upper)

        # --- THE KEY CHANGE IS HERE ---
        # 2. Use token_set_ratio for matching. It's excellent at handling extra words.
        match, score, _ = process.extractOne(
            processed_value, port_labels, scorer=fuzz.token_set_ratio
        )
        
        threshold = 85 # You can keep this threshold
        if score >= threshold:
            return port_mapping[match]
        
        # print(f"DEBUG: No confident match for '{value}'. Best guess '{match}' had score {score}%.")
        return None

    # Update main_json recursively
    def update_fields(obj):
        if isinstance(obj, dict):
            for field, value in obj.items():
                # Ensure the value is a non-empty string before processing
                if field in fields_to_update and isinstance(value, str) and value:
                    best_match = find_best_match(value)
                    if best_match:
                        obj[field] = best_match
                else:
                    update_fields(value)
        elif isinstance(obj, list):
            for item in obj:
                update_fields(item)

    update_fields(main_json)
    return main_json

def map_country_codes(main_json, data_codes_file="data_codes.json"):
    """
    Reads the country codes from the JSON file ("data_codes.json") 
    and maps specified fields in main_json (camelCase) to their 
    corresponding CODE-UPPERCASE LABEL format.

    Example: "IN" -> "IN-INDIA"
             "AE" -> "AE-UNITED ARAB EMIRATES"
    
    Args:
        main_json (dict): The main JSON containing shipping data.
        data_codes_file (str): Path to the JSON file with country codes.
    
    Returns:
        dict: Updated main_json with mapped country codes.
    """

    # Load country codes mapping
    with open(data_codes_file, "r", encoding="utf-8-sig") as f:
        country_data = json.load(f)

    # Create dictionary mapping: CODE (uppercase) -> CODE-LABEL (uppercase)
    country_mapping = {
        entry["code"].upper(): f'{entry["code"].upper()}-{entry["label"].title()}'
        for entry in country_data["country_codes"]
    }

    # Fields to update (camelCase)
    fields_to_update = [
        "shipperCountry",
        "consigneeCountry",
        "notifyPartyCountry",
        "deliveryAgentCountry",
        "freightForwardingAgentCountry",
        "shippingLineAgentCountry"
    ]

    # Update main_json recursively
    def update_fields(obj):
        if isinstance(obj, dict):
            for field, value in obj.items():
                if field in fields_to_update and value:
                    value_upper = value.upper().strip()
                    if value_upper in country_mapping:
                        obj[field] = country_mapping[value_upper]
                else:
                    update_fields(value)
        elif isinstance(obj, list):
            for item in obj:
                update_fields(item)

    update_fields(main_json)
    return main_json

def map_movement_type(main_json):
    """
    Determines movementType for each record in blDetails
    based on port codes using regex for AE detection.
    """

    if "blDetails" not in main_json:
        return main_json  # nothing to do

    for item in main_json["blDetails"]:
        if (
            re.search(r"^AE", item.get("portOfUnloading", "") or "")
            and re.search(r"^AE", item.get("endDestination", "") or "")
        ):
            item["movementType"] = "23-Import"
            #POUL and ENDEST = Blank = Leave It Blank
        elif (
            re.search(r"^AE", item.get("portOfUnloading", "") or "")
            and not re.search(r"^AE", item.get("endDestination", "") or "")
        ):
            item["movementType"] = "24-Transit"

        elif re.search(r"^AE", item.get("portOfTranshipment", "") or ""):
            item["movementType"] = "28-Transhipment"

        elif not any(
            re.search(r"^AE", item.get(field, "") or "")
            for field in [
                "portOfAcceptance",
                "portOfLoading",
                "portOfUnloading",
                "endDestination",
            ]
        ):  #NOT EMPTY
            item["movementType"] = "165-FROB"

    return main_json

def map_container_codes():
    pass

def map_package_types(main_json, data_codes_file="data_codes.json"):
    """
    Reads package types from the JSON file ("data_codes.json") 
    and maps packageType fields in containerDetails and itemDetails 
    to their corresponding CODE-UPPERCASE LABEL format.
    
    Args:
        main_json (dict): The main JSON containing shipping data.
        data_codes_file (str): Path to the JSON file with package type codes.
    
    Returns:
        dict: Updated main_json with mapped package types.
    """

    # Load package type mapping
    try:
        with open(data_codes_file, "r", encoding="utf-8-sig") as f:
            package_data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Data codes file not found at '{data_codes_file}'")
        return main_json

    # Create dictionary mapping: LABEL (uppercase) -> CODE-LABEL (uppercase)
    package_mapping = {
        entry["label"].upper(): f'{entry["code"]}-{entry["label"].upper()}'
        for entry in package_data.get("package_types", [])
    }
    package_labels = list(package_mapping.keys())

    def find_best_match(value):
        """
        Cleans the input string and finds the best fuzzy match if it's above a confidence threshold.
        """
        if not value:
            return None
        
        # --- START OF IMPROVEMENT ---
        # 1. Pre-process the input string to remove common plurals.
        value_upper = value.upper().strip()
        # Remove a trailing '(S)' if it exists
        processed_value = re.sub(r'\s*\(\s*S\s*\)$', '', value_upper)
        # Remove a trailing 'S' if it exists
        processed_value = re.sub(r'S$', '', processed_value)
        # --- END OF IMPROVEMENT ---
        
        # 2. Perform the fuzzy match using the cleaned string
        match, score, _ = process.extractOne(
            processed_value, package_labels, scorer=fuzz.token_sort_ratio
        )
        
        # 3. Check against the threshold
        threshold = 85
        if score >= threshold:
            # Return the correct mapping value (e.g., "PX-PALLET")
            return package_mapping[match]
        
        # Optional: Add a debug message for failed matches
        # print(f"DEBUG: No confident match for '{value}'. Best guess '{match}' had score {score}%.")
        return None

    # Update relevant fields recursively
    def update_fields(obj):
        if isinstance(obj, dict):
            for field, value in obj.items():
                # specifically look for packageType field
                if field == "packageType" and isinstance(value, str) and value:
                    best_match = find_best_match(value)
                    if best_match:
                        obj[field] = best_match
                else:
                    update_fields(value)
        elif isinstance(obj, list):
            for item in obj:
                update_fields(item)

    update_fields(main_json)
    return main_json

def pass_null_values():
    pass

def sanitize_json(result_str):
    """
    Cleans and parses the extracted JSON string.
    """
    cleaned = result_str.strip().replace("```json", "").replace("```", "").strip()
    result_json = json.loads(cleaned)
    return result_json

def sanitize_json_dict(data):
    """
    Recursively cleans a Python dictionary or list:
    - Converts None -> JSON null
    - Converts "None" (any case/with spaces) -> JSON null
    - Converts "null" (any case/with spaces) -> JSON null
    """
    if isinstance(data, dict):
        return {k: sanitize_json_dict_new(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_json_dict_new(v) for v in data]
    elif isinstance(data, str):
        return None if data.strip().lower() in ["none", "null"] else data
    elif data is None:
        return None
    else:
        return data

def sanitize_json_dict_new(data):
    """
    Recursively cleans a Python dictionary or list:
    - Converts None -> JSON null
    - Converts "None" (any case/with spaces) -> JSON null
    - Converts "null" (any case/with spaces) -> JSON null
    """
    if isinstance(data, dict):
        return {k: sanitize_json_dict(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_json_dict(v) for v in data]
    elif isinstance(data, str):
        stripped = data.strip()
        return None if stripped == "" or stripped.lower() in ["none", "null"] else data
    elif data is None:
        return None
    else:
        return data

def mapper(input_json_data, excel_filename, data_dict, source):
    try:
        file_path = os.path.join(os.getcwd(), "intermediate_json.json")
        temp_json = sanitize_json(input_json_data) # String

        dict_json = temp_json
        dict_json = map_port_codes(dict_json)
        dict_json = map_country_codes(dict_json)
        dict_json = map_movement_type(dict_json)
        dict_json = map_package_types(dict_json)

        
        with open(file_path, "w", encoding="utf-8-sig") as f:
            json.dump(temp_json, f, indent=2, ensure_ascii=False)
        print(f"✅ JSON written to {file_path}")

        logging.info("Starting JSON to Excel Transformation...")

        # --- EXCEL GENERATION ---
        # Download the template
        excel_template_file_path = excel_template_downlaoder()
        
        # Call the modified function which returns the output path AND the data with row numbers
        output_file_path, data_with_rows = process_json_to_excel(
            file_path,
            source,
            data_dict,
            r"Excel_Template.xlsx", 
            f"{excel_filename}.xlsx"
        )
        if not output_file_path:
             raise Exception("Failed to generate the Excel file.")
        
        # === REVERSE COLUMN RENAMING TO ORIGINAL KEYS FOR itemDetails BEFORE transform_json ===
        item_df = data_with_rows["Item Details"]
        reverse_mapping = {
            "Cargo Gross Weight (KGM)": "cargoGrossWeight",
            "Cargo Net Weight (KGM)": "cargoNetWeight",
            "Marks & Numbers": "marksAndNumbers",
        }
        item_df.rename(columns=reverse_mapping, inplace=True)
        data_with_rows["Item Details"] = item_df
        
        # Upload to S3
        excel_s3_link = upload_to_s3(excel_filename, output_file_path)
        logger.info(f"Excel file uploaded to S3: {excel_s3_link}")

        # --- FINAL JSON TRANSFORMATION ---
        # Convert the DataFrames (which now have the row numbers) back to a dict
        final_input_data = {
            "blDetails": data_with_rows["BL Details"].to_dict(orient="records"),
            "containerDetails": data_with_rows["Container Details"].to_dict(orient="records"),
            "itemDetails": data_with_rows["Item Details"].to_dict(orient="records")
        }

        transformed_output = sanitize_json_dict(transform_json(final_input_data))
        if source == "WEB_APP":
            for item in transformed_output["file"]:
                # Helper function to check if a value is truthy and not empty/null
                def is_valid_value(val):
                    if val is None:
                        return False
                    if isinstance(val, str):
                        stripped = val.strip().lower()
                        return stripped not in ["", "null", "none"]
                    return bool(val)
                
                parent_bl_number = data_dict.get("parentBlNumber")
                if is_valid_value(parent_bl_number):
                    item["parentBlNumber"] = parent_bl_number
                    item["mblNo"] = parent_bl_number
                vessel_name = data_dict.get("vesselName")
                if is_valid_value(vessel_name):
                    item["vesselName"] = vessel_name
                voyage_id = data_dict.get("voyageId")
                if is_valid_value(voyage_id):
                    item["voyageId"] = voyage_id
                issuing_party_name = data_dict.get("issuingPartyName")
                if is_valid_value(issuing_party_name):
                    item["issuingPartyName"] = issuing_party_name
                issuing_party_mpci_id = data_dict.get("issuingPartyMpciId")
                if is_valid_value(issuing_party_mpci_id):
                    item["issuingPartyMpciId"] = issuing_party_mpci_id
                mbl_issuing_party_name = data_dict.get("mblIssuingPartyName")
                if is_valid_value(mbl_issuing_party_name):
                    item["mblIssuingPartyName"] = mbl_issuing_party_name
                mbl_issuing_party_mpci_id = data_dict.get("mblIssuingPartyMpciId")
                if is_valid_value(mbl_issuing_party_mpci_id):
                    item["mblIssuingPartyMpciId"] = mbl_issuing_party_mpci_id
                ff_party_name = data_dict.get("ffPartyName")
                if is_valid_value(ff_party_name):
                    item["ffPartyName"] = ff_party_name
                ff_party_mpci_id = data_dict.get("ffPartyMpciId")
                if is_valid_value(ff_party_mpci_id):
                    item["ffPartyMpciId"] = ff_party_mpci_id

        transformed_new_output = sanitize_json_dict_new(transformed_output)

        output_filename = "final_json.json"
        with open(output_filename, 'w') as f:
            json.dump(transformed_new_output, f, indent=2)
        
        # Open and load the JSON data
        with open(output_filename, "r", encoding="utf-8-sig") as f:
            final_json = json.load(f)
        
        final_json["xlsxName"] = f"{excel_filename}.xlsx"
        final_json["xlsxPath"] = excel_s3_link if excel_s3_link else "null"

        if os.path.exists(rf"{excel_filename}.xlsx"):
            os.remove(rf"{excel_filename}.xlsx")
        
        if os.path.exists(r"intermediate_json.json"):
            os.remove(r"intermediate_json.json")
        
        if os.path.exists(r"final_json.json"):
            os.remove(r"final_json.json")
        
        return json.dumps(final_json, indent=2)
    
    except json.JSONDecodeError as e:
        return ("JSON decoding failed:", e)
    
    except Exception as e:
        return {"file": [], "errors": [str(e)], "xlsxName": f"{excel_filename}.xlsx", "xlsxPath": excel_s3_link}
    
    finally:
        logging.info("JSON transformation process completed.")

# if __name__ == "__main__":
#     with open(r"temp.json", "r", encoding = "utf-8-sig") as f:
#         main_json = json.load(f)
#     main_json = map_port_codes(main_json)
#     main_json = map_country_codes(main_json)
#     main_json = map_movement_type(main_json)
#     print(json.dumps(main_json, indent=2))