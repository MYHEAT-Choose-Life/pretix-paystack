import logging
from django.contrib import messages
from django.http import HttpResponse
from django.utils.translation import gettext_lazy as _
from pretix.base.models import OrderPayment, OrderRefund
from pretix.base.models.orders import Order
from pretix.helpers.http import redirect_to_url
from pretix.multidomain.urlreverse import eventreverse

logger = logging.getLogger("pretix.plugins.paystack")


def success(request, *args, **kwargs):
    if "payment" in request.GET:
        for op in OrderPayment.objects.filter(
            provider="paystack", pk=request.GET.get("payment")
        ):
            op.payment_provider._update_payment(op)

            return_url = (
                eventreverse(
                    request.event,
                    "presale:event.order",
                    kwargs={"order": op.order.code, "secret": op.order.secret},
                )
                + ("?paid=yes"
                if op.order.status == Order.STATUS_PAID
                else "")
            )

            return redirect_to_url(return_url)
    else:
        return redirect_to_url(eventreverse(request.event, 'presale:event.checkout', kwargs={'step': 'confirm'}))

def abort(request, *args, **kwargs):
    messages.error(request, _("It looks like you canceled the Paystack payment"))
    if "payment" in request.GET:
        for op in OrderPayment.objects.filter(
            provider="paystack", pk=request.GET.get("payment")
        ):
            return redirect_to_url(eventreverse(request.event, 'presale:event.order', kwargs={
                'order': op.order.code,
                'secret': op.order.secret
            }) + ('?paid=yes' if op.order.status == Order.STATUS_PAID else ''))
    else:
        return redirect_to_url(eventreverse(request.event, 'presale:event.checkout', kwargs={'step': 'payment'}))

