INVOICE_JSON_SCHEMA = """
        {
            "blNumber": "value",
            "invoiceNumber": "value",
            "totalAmount": "value",
            "currency": "value",
            "totalAmount2": "value",(Optional output field only if it exists,,if null dont display as output)
            "currency2": "value",(Optional output field only if it exists only capture if different from Currency,if null dont display as output)
            "shippingLineName": "value",
            "customerName": "value",
            "invoiceDate": "value",
            "dueDate": "value  (optional if present)",
            "customerCode": "value  (optional if present)",
            "portOfLoading": "value",
            "portOfDispatch": "value",
            "exchangeRate": "value",
            "bankAccountDetails": [{
                bankName: "value",
                accNo: "value",
                ifscCode: "value"
            }],
            "invoiceType":"value",
            "customerTaxId": "value",
            "shippingTaxId": "value",
            "containerList": [{
                containerSize:"value",
                containerNo:"value",
                containerType:"value",
                truckerCode:"value",
                releaseDate:"value",
                releaseStatus:"value",
                lastFreeDate:"value",
                releasePin:"value",
                releaseLoc:"value"
            }]
        }
"""


DO_JSON_SCHEMA = """
        {
            "blNumber": "value",
            "consignee": "value",
            "consigneeAddress": "value",
            "date": "value",(Output in DD-MM-YYYY format)
            "descriptionOfGoods": "value",(Optional output field only if it exists)
            "doNumber":"value",
            "shippingLineName": "value",
            "issuedTo": "value",
            "issuedToAddress": "value",
            "portOfLoading": "value",
            "portOfDispatch": "value",
            "email": "value",
            "grossWeight": "value",
            "hsCode": "value",
            "igmNumber": "value",
            "lineNumber": "value",
            "marksAndNumbers": "value",
            "type: "value (storing or delivery)",
            "validUpto": "value",
            "vesselName": "value",
            "volume": "value",
            "voyage": "value",
            "containerList": [{
                containerSize:"value",
                containerNo:"value",
                sealNo:"value",
                seqNo:"value",
            }]
        }
"""
MPCI_JSON_SCHEMA = """
{
  "blDetails": [
    {
      "filingFor": "value",
      "partyName": "value",
      "partyMpciId": "value",
      "blNumber": "value",
      "blDate": "value",
      "parentBlNumber": "value",
      "parentBlIssuingPartyName": "value",
      "parentBlIssuingPartyMpciId": "value",
      "newSplitBlFiling": "value",
      "originalBlNumber": "value",
      "furtherConsolidation": "value",
      "consoleForwardersMpciId": "value",
      "vesselName": "value",
      "voyageNumber": "value",
      "movementType": "value",
      "portOfAcceptance": "value",
      "portOfLoading": "value",
      "portOfTranshipment": "value",
      "portOfUnloading": "value",
      "endDestination": "value",
      "emirate": "value",
      "natureOfCargo": "value",
      "placeOfBillIssue": "value",
      "placeOfFreightPayment": "value",
      "typeOfBl": "value",
      "freightPrepaid": "value",
      "invoiceAmountOfTheCosginment": "value",
      "currency": "value",
      "serviceRequirement": "value",
      "remarks": "value",
      "shipperName": "value",
      "shipperTaxId": "value",
      "shipperAddress": "value",
      "shipperCity": "value",
      "shipperCountry": "value",
      "consigneeName": "value",
      "consigneeTaxID": "value",
      "consigneeAddress": "value",
      "consigneeCity": "value",
      "consigneeCountry": "value",
      "consigneeType": "value",
      "contactName": "value",
      "contactPartyType": "value",
      "phoneNumber": "value",
      "emailId": "value",
      "notifyPartyName": "value",
      "notifyPartyTaxID": "value",
      "notifyPartyAddress": "value",
      "notifyPartyCity": "value",
      "notifyPartyCountry": "value",
      "deliveryAgentName": "value",
      "deliveryAgentTaxID": "value",
      "deliveryAgentAddress": "value",
      "deliveryAgentCity": "value",
      "deliveryAgentCountry": "value",
      "freightForwardingAgentName": "value",
      "freightForwardingAgentTaxID": "value",
      "freightForwardingAgentAddress": "value",
      "freightForwardingAgentCity": "value",
      "freightForwardingAgentCountry": "value",
      "shippingLineAgentName": "value",
      "shippingLineAgentTaxID": "value",
      "shippingLineAgentAddress": "value",
      "shippingLineAgentCity": "value",
      "shippingLineAgentCountry": "value",
      "updateFilingReason": "value",
      "updateFilingRemarks": "value",
      "newSwitchBlNumber": "value"
    }
  ],
  "containerDetails": [
    {
      "blNumber": "value",
      "containerNumber": "value",
      "containerSize": "value",
      "containerStatus": "value",
      "shipperSeal": "value",
      "shipperSealType": "value",
      "carrierSeal": "value",
      "carrierSealType": "value",
      "customsSeal": "value",
      "customsSealType": "value",
      "sealingPartyName": "value",
      "temperature": "value",
      "temperatureUnit": "value",
      "numberOfPackages": "value",
      "packageType": "value",
      "vgmWeight": "value",
      "removeContainerForSplitFiling": "value",
      "newSplitBlNumber": "value",
      "newParentBlNumber": "value",
      "newVesselName": "value",
      "newVoyageNumber": "value"
    }
  ],
  "itemDetails": [
    {
      "blNumber": "value",
      "containerNumber": "value",
      "hsCode": "value",
      "numberOfPackages": "value",
      "packageType": "value",
      "packageRelatedDescriptionCode": "value",
      "cargoGrossWeight": "value",
      "cargoNetWeight": "value",
      "volumeInMtq": "value",
      "imoClass": "value",
      "unCode": "value",
      "itemDescription": "value",
      "marksAndNumbers": "value",
      "handlingInstructions": "value",
      "goodsItemCountryOfOrigin": "value",
      "removeItem": "value"
    }
  ]
}
"""