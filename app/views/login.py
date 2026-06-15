from app.views.layout import layout, escape_html, csrf_field


def render_login(csrf=None, error=None, username=""):
    error_block = f'<div role="alert"><p>{escape_html(error)}</p></div>' if error else ""
    body = (
        f'{error_block}\n'
        f'<form method="POST" action="/login">\n'
        f'{csrf_field(csrf)}\n'
        f'<p>\n'
        f'<label for="field-username">Username</label><br>\n'
        f'<input id="field-username" name="username" type="text" value="{escape_html(username)}" required autocomplete="username">\n'
        f'</p>\n'
        f'<p>\n'
        f'<label for="field-password">Password</label><br>\n'
        f'<input id="field-password" name="password" type="password" required autocomplete="current-password">\n'
        f'</p>\n'
        f'<p><button type="submit">Sign in</button></p>\n'
        f'</form>'
    )
    return {
        "status": 401 if error else 200,
        "html": layout(title="Sign in", body=body),
    }
