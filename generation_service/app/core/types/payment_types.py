from enum import StrEnum


class PaymentOutcome(StrEnum):
    CREDITED = "credited"
    DUPLICATE = "duplicate"
    IGNORED = "ignored"
