from collections import OrderedDict
import logging
import uuid
from django import forms
from django.conf import settings
from django.http import HttpRequest
from django.template.loader import get_template
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from paystackapi.paystack import Paystack as PaystackApi
from pretix.base.models.orders import OrderPayment
from pretix.base.payment import BasePaymentProvider, PaymentException
from pretix.multidomain.urlreverse import build_absolute_uri
from pretix.presale.views.cart import cart_session

logger = logging.getLogger(__name__)


class Paystack(BasePaymentProvider):
    identifier = "paystack"
    verbose_name = _("Paystack")
    public_name = _("Paystack")
    priority = 101
    execute_payment_needs_user = True

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

    def payment_form(self, request: HttpRequest) -> forms.Form:
        initial = {
            k.replace("payment_%s_" % self.identifier, ""): v
            for k, v in request.session.items()
            if k.startswith("payment_%s_" % self.identifier)
        }

        if not initial.get("email"):
            cs = cart_session(request)
            if cs and cs.get("contact_form_data", {}).get("email"):
                initial["email"] = cs["contact_form_data"]["email"]

        form = self.payment_form_class(
            data=(
                request.POST
                if request.method == "POST"
                and request.POST.get("payment") == self.identifier
                else None
            ),
            prefix="payment_%s_" % self.identifier,
            initial=initial,
        )
        form.fields = {
            "email": forms.EmailField(
                label=_("Email address"),
                required=True,
            )
        }

        for k, v in form.fields.items():
            v._required = v.required
            v.required = False
            v.widget.is_required = False

        return form

    def payment_is_valid_session(self, request: HttpRequest) -> bool:
        return bool(request.session.get("payment_%s_email" % self.identifier))

    def checkout_confirm_render(self, request: HttpRequest) -> str:
        template = get_template("pretix_paystack/checkout_payment_confirm.html")
        ctx = {
            "request": request,
            "event": self.event,
            "settings": self.settings,
            "email": request.session["payment_%s_email" % self.identifier],
        }
        return template.render(ctx)

    def _update_payment(self, payment: OrderPayment) -> None:
        reference = payment.info_data["reference"]
        paystackApi = PaystackApi(secret_key=self.settings.secret_key)
        try:
            r = paystackApi.transaction.verify(reference=reference)
            if not r["status"]:
                raise Exception(r["message"])
        except Exception as e:
            logger.exception("could not update payment state.")
        else:
            d = r["data"]
            if d["status"] == "success":
                payment.info_data = {**payment.info_data, **d}
                payment.confirm()
            else:
                payment.fail(
                    info={
                        "reference": reference,
                        "error": str(e),
                    }
                )

    def execute_payment(self, request: HttpRequest, payment: OrderPayment) -> str:
        paystackApi = PaystackApi(secret_key=self.settings.secret_key)
        email = request.session["payment_%s_email" % self.identifier]
        refid = str(uuid.uuid4())
        payment.info_data = {"reference": refid}
        payment.save(update_fields=["info"])

        kwargs = {}
        if request.resolver_match and "cart_namespace" in request.resolver_match.kwargs:
            kwargs["cart_namespace"] = request.resolver_match.kwargs["cart_namespace"]

        return_url = (
            build_absolute_uri(
                request.event, "plugins:pretix_paystack:return", kwargs=kwargs
            )
            + "?payment=%s" % payment.pk
        )
        cancel_url = build_absolute_uri(request.event, "plugins:pretix_paystack:abort", kwargs=kwargs) + "?payment=%s" % payment.pk
        try:
            response = paystackApi.transaction.initialize(
                reference=refid,
                email=email,
                amount=int(payment.amount * 100),
                callback_url=return_url,
                metadata={"cancel_action": cancel_url},
            )

            if not response["status"]:
                raise Exception(response["message"])
        except Exception as e:
            payment.fail(
                info={
                    "reference": refid,
                    "error": str(e),
                }
            )
            raise PaymentException(
                _(
                    "We had trouble communicating with the payment service. Please try again and"
                    "get in touch with us if this problem persists."
                )
            )
        else:
            return response["data"]["authorization_url"]

    def test_mode_message(self) -> str:
        return mark_safe(_("Make sure you also see 'Testing' in the Paystack interface."))
