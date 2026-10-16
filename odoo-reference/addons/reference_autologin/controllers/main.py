from odoo import SUPERUSER_ID, api, http
from odoo.addons.web.controllers.home import Home
from odoo.http import request
from odoo.modules.registry import Registry


REFERENCE_DATABASE = "odoo_reference"


class ReferenceAutoLogin(Home):
    """Development-only entry point for the isolated local Odoo reference."""

    @http.route("/web/login", type="http", auth="none", sitemap=False)
    def web_login(self, redirect=None, **kwargs):
        if request.httprequest.method == "GET":
            with Registry(REFERENCE_DATABASE).cursor() as cursor:
                environment = api.Environment(cursor, SUPERUSER_ID, {})
                user = environment["res.users"].browse(SUPERUSER_ID)
                request.session.should_rotate = True
                request.session.update(
                    {
                        "db": REFERENCE_DATABASE,
                        "login": user.login,
                        "uid": user.id,
                        "context": dict(user.context_get()),
                        "session_token": user._compute_session_token(request.session.sid),
                    }
                )
            return request.redirect(redirect or "/web")
        return super().web_login(redirect=redirect, **kwargs)
