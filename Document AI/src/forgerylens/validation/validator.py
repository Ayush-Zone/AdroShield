from typing import List, Optional, Any, Dict
from decimal import Decimal, InvalidOperation

from forgerylens.contracts.normalized import NormalizedInvoice, NormalizedField, NormalizationStatus
from forgerylens.contracts.structured import DocumentType
from forgerylens.contracts.validation import ValidationResult, ValidationFinding, ValidationStatus, ValidationSeverity


def _as_decimal(value: Optional[float]) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        # Convert float to string first to avoid precision issues (e.g. 1.1 -> 1.10000000000000008)
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _format_currency(val: Decimal) -> str:
    return f"{val:.2f}"


def _create_finding(
    rule_name: str,
    status: ValidationStatus,
    severity: ValidationSeverity,
    message: str,
    expected: Optional[str] = None,
    observed: Optional[str] = None,
    difference: Optional[str] = None,
    involved_fields: Optional[Dict[str, Any]] = None
) -> ValidationFinding:
    return ValidationFinding(
        rule_name=rule_name,
        status=status,
        severity=severity,
        message=message,
        expected=expected,
        observed=observed,
        difference=difference,
        involved_fields=involved_fields or {}
    )


def _field_to_dict(field: Optional[NormalizedField]) -> Dict[str, Any]:
    """Helper to convert a field to a dict for provenance tracking."""
    if not field:
        return {"status": "missing"}
    return {
        "raw_value": field.raw_value,
        "normalized_value": str(field.normalized_value) if field.normalized_value else None,
        "status": field.status.value,
        "region": field.region.model_dump() if field.region else None
    }


def _validate_required_fields(invoice: NormalizedInvoice) -> List[ValidationFinding]:
    findings = []
    
    # Define required fields based on document type. 
    # Currently we only strictly validate INVOICE
    if invoice.document_type == DocumentType.INVOICE:
        required_fields = {
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date,
            "vendor_name": invoice.vendor_name,
            "grand_total": invoice.grand_total
        }
        
        for field_name, field_obj in required_fields.items():
            if not field_obj:
                findings.append(
                    _create_finding(
                        rule_name=f"required_field_{field_name}",
                        status=ValidationStatus.MISSING,
                        severity=ValidationSeverity.WARNING,
                        message=f"Required field '{field_name}' is missing."
                    )
                )
            elif field_obj.status == NormalizationStatus.AMBIGUOUS:
                findings.append(
                    _create_finding(
                        rule_name=f"required_field_{field_name}_ambiguous",
                        status=ValidationStatus.UNABLE_TO_VERIFY,
                        severity=ValidationSeverity.WARNING,
                        message=f"Required field '{field_name}' is ambiguous and could not be safely normalized.",
                        involved_fields={field_name: _field_to_dict(field_obj)}
                    )
                )
                
    return findings


def _validate_line_item_arithmetic(invoice: NormalizedInvoice) -> List[ValidationFinding]:
    findings = []
    
    for idx, item in enumerate(invoice.line_items):
        rule_name = f"line_item_arithmetic_{idx}"
        
        # If any of the required fields are missing, we cannot verify
        if not item.quantity or not item.unit_price or not item.amount:
            continue
            
        # If any are ambiguous, we cannot verify
        if (item.quantity.status == NormalizationStatus.AMBIGUOUS or 
            item.unit_price.status == NormalizationStatus.AMBIGUOUS or 
            item.amount.status == NormalizationStatus.AMBIGUOUS):
            findings.append(
                _create_finding(
                    rule_name=rule_name,
                    status=ValidationStatus.UNABLE_TO_VERIFY,
                    severity=ValidationSeverity.INFO,
                    message=f"Line item {idx} has ambiguous values; arithmetic cannot be verified.",
                    involved_fields={
                        "quantity": _field_to_dict(item.quantity),
                        "unit_price": _field_to_dict(item.unit_price),
                        "amount": _field_to_dict(item.amount)
                    }
                )
            )
            continue
            
        qty = _as_decimal(item.quantity.normalized_value)
        up = _as_decimal(item.unit_price.normalized_value.amount if item.unit_price.normalized_value else None)
        amt = _as_decimal(item.amount.normalized_value.amount if item.amount.normalized_value else None)
        
        if qty is None or up is None or amt is None:
            continue
            
        expected_amt = qty * up
        diff = abs(expected_amt - amt)
        
        # Precision handling: allow up to 0.01 tolerance for rounding differences
        if diff > Decimal("0.01"):
            findings.append(
                _create_finding(
                    rule_name=rule_name,
                    status=ValidationStatus.INVALID,
                    severity=ValidationSeverity.CRITICAL,
                    message=f"Line item {idx} amount discrepancy: {qty} * {up} = {expected_amt}, but observed {amt}.",
                    expected=_format_currency(expected_amt),
                    observed=_format_currency(amt),
                    difference=_format_currency(diff),
                    involved_fields={
                        "quantity": _field_to_dict(item.quantity),
                        "unit_price": _field_to_dict(item.unit_price),
                        "amount": _field_to_dict(item.amount)
                    }
                )
            )
        else:
            findings.append(
                _create_finding(
                    rule_name=rule_name,
                    status=ValidationStatus.VALID,
                    severity=ValidationSeverity.INFO,
                    message=f"Line item {idx} arithmetic is valid.",
                    involved_fields={
                        "quantity": _field_to_dict(item.quantity),
                        "unit_price": _field_to_dict(item.unit_price),
                        "amount": _field_to_dict(item.amount)
                    }
                )
            )
            
    return findings


def _validate_subtotal(invoice: NormalizedInvoice) -> List[ValidationFinding]:
    findings = []
    
    if not invoice.subtotal:
        return findings
        
    if invoice.subtotal.status == NormalizationStatus.AMBIGUOUS:
        findings.append(
            _create_finding(
                rule_name="subtotal_arithmetic",
                status=ValidationStatus.UNABLE_TO_VERIFY,
                severity=ValidationSeverity.INFO,
                message="Subtotal is ambiguous; arithmetic cannot be verified.",
                involved_fields={"subtotal": _field_to_dict(invoice.subtotal)}
            )
        )
        return findings
        
    if not invoice.line_items:
        findings.append(
            _create_finding(
                rule_name="subtotal_arithmetic",
                status=ValidationStatus.UNABLE_TO_VERIFY,
                severity=ValidationSeverity.INFO,
                message="Subtotal is present but no line items found to verify against.",
                involved_fields={"subtotal": _field_to_dict(invoice.subtotal)}
            )
        )
        return findings
        
    # Sum line items
    calculated_subtotal = Decimal("0.0")
    line_item_fields = {}
    
    for idx, item in enumerate(invoice.line_items):
        if not item.amount or item.amount.status == NormalizationStatus.AMBIGUOUS:
            findings.append(
                _create_finding(
                    rule_name="subtotal_arithmetic",
                    status=ValidationStatus.UNABLE_TO_VERIFY,
                    severity=ValidationSeverity.INFO,
                    message=f"Line item {idx} amount is missing or ambiguous; subtotal cannot be fully verified.",
                    involved_fields={"subtotal": _field_to_dict(invoice.subtotal), f"line_item_{idx}": _field_to_dict(item.amount)}
                )
            )
            return findings
            
        amt = _as_decimal(item.amount.normalized_value.amount if item.amount.normalized_value else None)
        if amt is not None:
            calculated_subtotal += amt
        line_item_fields[f"line_item_{idx}"] = _field_to_dict(item.amount)
            
    observed_subtotal = _as_decimal(invoice.subtotal.normalized_value.amount if invoice.subtotal.normalized_value else None)
    
    if observed_subtotal is None:
        return findings
        
    diff = abs(calculated_subtotal - observed_subtotal)
    involved = {"subtotal": _field_to_dict(invoice.subtotal)}
    involved.update(line_item_fields)
    
    if diff > Decimal("0.01"):
        findings.append(
            _create_finding(
                rule_name="subtotal_arithmetic",
                status=ValidationStatus.INVALID,
                severity=ValidationSeverity.CRITICAL,
                message=f"Subtotal discrepancy: calculated {_format_currency(calculated_subtotal)}, observed {_format_currency(observed_subtotal)}.",
                expected=_format_currency(calculated_subtotal),
                observed=_format_currency(observed_subtotal),
                difference=_format_currency(diff),
                involved_fields=involved
            )
        )
    else:
        findings.append(
            _create_finding(
                rule_name="subtotal_arithmetic",
                status=ValidationStatus.VALID,
                severity=ValidationSeverity.INFO,
                message="Subtotal matches the sum of line items.",
                involved_fields=involved
            )
        )
        
    return findings


def _validate_grand_total(invoice: NormalizedInvoice) -> List[ValidationFinding]:
    findings = []
    
    if not invoice.grand_total:
        return findings
        
    if invoice.grand_total.status == NormalizationStatus.AMBIGUOUS:
        findings.append(
            _create_finding(
                rule_name="grand_total_arithmetic",
                status=ValidationStatus.UNABLE_TO_VERIFY,
                severity=ValidationSeverity.INFO,
                message="Grand total is ambiguous; arithmetic cannot be verified.",
                involved_fields={"grand_total": _field_to_dict(invoice.grand_total)}
            )
        )
        return findings

    if not invoice.subtotal or invoice.subtotal.status == NormalizationStatus.AMBIGUOUS:
        findings.append(
            _create_finding(
                rule_name="grand_total_arithmetic",
                status=ValidationStatus.UNABLE_TO_VERIFY,
                severity=ValidationSeverity.INFO,
                message="Subtotal is missing or ambiguous; grand total cannot be verified.",
                involved_fields={
                    "grand_total": _field_to_dict(invoice.grand_total),
                    "subtotal": _field_to_dict(invoice.subtotal)
                }
            )
        )
        return findings
        
    observed_grand_total = _as_decimal(invoice.grand_total.normalized_value.amount if invoice.grand_total.normalized_value else None)
    subtotal = _as_decimal(invoice.subtotal.normalized_value.amount if invoice.subtotal.normalized_value else None)
    
    if observed_grand_total is None or subtotal is None:
        return findings
        
    expected_total = subtotal
    involved = {
        "grand_total": _field_to_dict(invoice.grand_total),
        "subtotal": _field_to_dict(invoice.subtotal)
    }
    
    # Add Taxes
    if invoice.taxes:
        if invoice.taxes.status == NormalizationStatus.AMBIGUOUS:
            findings.append(
                _create_finding(
                    rule_name="grand_total_arithmetic",
                    status=ValidationStatus.UNABLE_TO_VERIFY,
                    severity=ValidationSeverity.INFO,
                    message="Tax is ambiguous; grand total cannot be verified.",
                    involved_fields=involved
                )
            )
            return findings
        tax = _as_decimal(invoice.taxes.normalized_value.amount if invoice.taxes.normalized_value else None)
        if tax is not None:
            expected_total += tax
            involved["taxes"] = _field_to_dict(invoice.taxes)
            
    # Add Additional Charges
    if invoice.additional_charges:
        if invoice.additional_charges.status == NormalizationStatus.AMBIGUOUS:
            findings.append(
                _create_finding(
                    rule_name="grand_total_arithmetic",
                    status=ValidationStatus.UNABLE_TO_VERIFY,
                    severity=ValidationSeverity.INFO,
                    message="Additional charges are ambiguous; grand total cannot be verified.",
                    involved_fields=involved
                )
            )
            return findings
        charges = _as_decimal(invoice.additional_charges.normalized_value.amount if invoice.additional_charges.normalized_value else None)
        if charges is not None:
            expected_total += charges
            involved["additional_charges"] = _field_to_dict(invoice.additional_charges)
            
    # Subtract Discounts
    if invoice.discounts:
        if invoice.discounts.status == NormalizationStatus.AMBIGUOUS:
            findings.append(
                _create_finding(
                    rule_name="grand_total_arithmetic",
                    status=ValidationStatus.UNABLE_TO_VERIFY,
                    severity=ValidationSeverity.INFO,
                    message="Discounts are ambiguous; grand total cannot be verified.",
                    involved_fields=involved
                )
            )
            return findings
        discount = _as_decimal(invoice.discounts.normalized_value.amount if invoice.discounts.normalized_value else None)
        if discount is not None:
            expected_total -= discount
            involved["discounts"] = _field_to_dict(invoice.discounts)
            
    diff = abs(expected_total - observed_grand_total)
    
    if diff > Decimal("0.01"):
        findings.append(
            _create_finding(
                rule_name="grand_total_arithmetic",
                status=ValidationStatus.INVALID,
                severity=ValidationSeverity.CRITICAL,
                message=f"Grand total discrepancy: calculated {_format_currency(expected_total)}, observed {_format_currency(observed_grand_total)}.",
                expected=_format_currency(expected_total),
                observed=_format_currency(observed_grand_total),
                difference=_format_currency(diff),
                involved_fields=involved
            )
        )
    else:
        findings.append(
            _create_finding(
                rule_name="grand_total_arithmetic",
                status=ValidationStatus.VALID,
                severity=ValidationSeverity.INFO,
                message="Grand total arithmetic is valid.",
                involved_fields=involved
            )
        )
        
    return findings


def validate_document(invoice: NormalizedInvoice) -> ValidationResult:
    """Perform deterministic mathematical and logical validation on an invoice."""
    findings = []
    
    findings.extend(_validate_required_fields(invoice))
    findings.extend(_validate_line_item_arithmetic(invoice))
    findings.extend(_validate_subtotal(invoice))
    findings.extend(_validate_grand_total(invoice))
    
    return ValidationResult(
        document_id=invoice.document_id,
        findings=findings
    )
