from typing import List

from forgerylens.contracts.structured import StructuredInvoice, InvoiceLineItem
from forgerylens.contracts.normalized import NormalizedInvoice, NormalizedLineItem

from .currency import normalize_currency, normalize_numeric
from .dates import normalize_date
from .text import normalize_text, normalize_identifier


def _normalize_line_items(line_items: List[InvoiceLineItem]) -> List[NormalizedLineItem]:
    normalized_items = []
    for item in line_items:
        normalized_items.append(
            NormalizedLineItem(
                description=normalize_text(item.description),
                quantity=normalize_numeric(item.quantity),
                unit_price=normalize_currency(item.unit_price),
                amount=normalize_currency(item.amount)
            )
        )
    return normalized_items


def normalize_document(invoice: StructuredInvoice) -> NormalizedInvoice:
    """Normalize a StructuredInvoice into a NormalizedInvoice.
    
    This preserves all original extraction provenance while attempting
    to parse dates, amounts, and identifiers into canonical representations.
    """
    return NormalizedInvoice(
        document_id=invoice.document_id,
        document_type=invoice.document_type,
        
        # Basic Fields
        invoice_number=normalize_identifier(invoice.invoice_number),
        invoice_date=normalize_date(invoice.invoice_date),
        vendor_name=normalize_text(invoice.vendor_name),
        customer_name=normalize_text(invoice.customer_name),
        
        # Claim / Vehicle Fields
        vehicle_number=normalize_identifier(invoice.vehicle_number),
        registration_number=normalize_identifier(invoice.registration_number),
        claim_number=normalize_identifier(invoice.claim_number),
        policy_number=normalize_identifier(invoice.policy_number),
        vin_chassis_number=normalize_identifier(invoice.vin_chassis_number),
        
        # Financial Fields
        subtotal=normalize_currency(invoice.subtotal),
        taxes=normalize_currency(invoice.taxes),
        discounts=normalize_currency(invoice.discounts),
        additional_charges=normalize_currency(invoice.additional_charges),
        grand_total=normalize_currency(invoice.grand_total),
        
        # Line Items
        line_items=_normalize_line_items(invoice.line_items)
    )
