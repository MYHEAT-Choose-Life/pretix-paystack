from collections import OrderedDict
from django import forms
from django.http import HttpRequest
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from paystackapi.paystack import Paystack
from pretix.base.models.orders import OrderPayment
from pretix.base.payment import BasePaymentProvider


class Paystack(BasePaymentProvider):
    identifier = "paystack"
    verbose_name = _("Paystack")
    public_name = _("Paystack")
    priority = 101

    @property
    def settings_form_fields(self) -> dict:
        fields = [
            (
                "secret_key",
                forms.CharField(
                    label=_("API secret key"),
                    required=True,
                    help_text=_(
                        "You can find your API keys in your Paystack dashboard."
                    ),
                ),
            )
        ]

        d = OrderedDict(fields + list(super().settings_form_fields.items()))
        d.move_to_end("_enabled", last=False)
        return d

    @property
    def payment_form_fields(self) -> dict:

        return {}

    @property
    def is_enabled(self) -> bool:
        return self.settings.get("_enabled", as_type=bool) and self.settings.get(
            "secret_key"
        )

    def payment_is_valid_session(self, rest: HttpRequest) -> bool:
        return True

    def checkout_confirm_render(self, request) -> str:
        return r"""We deving, we still cooking🧑🏾‍🍳 Stay tuned📻..."""

    def execute_payment(self, request: HttpRequest, payment: OrderPayment) -> str:
        payment.confirm()

    def test_mode_message(self) -> str:
        return mark_safe(_("It's all good, we're still cooking🧑🏾‍🍳. Stay tuned📻..."))
