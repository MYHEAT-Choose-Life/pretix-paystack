from django.urls import include, re_path

from .views import success, abort

event_patterns = [
    re_path(
        r"^paystack/",
        include(
            [
                re_path(r"^return/$", success, name="return"),
                re_path(r"^abort/$", abort, name="abort"),
            ]
        ),
    ),
]
