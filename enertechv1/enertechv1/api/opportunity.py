def validate(doc, method=None):
    if doc.status == "Converted":
        doc.custom_latest_inquiry_status = "Converted"