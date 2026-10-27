"""Login limits, proxy headers, password change, cookies and CSRF guard."""
from conftest import PASSWORD

from tiroir.access import Store
from tiroir.auth import Password, PasswordError
from tiroir.config import parse_proxies


def test_five_wrong_passwords_then_blocked(server):
    for _ in range(5):
        assert server.call("POST", "/login", form={"password": "nope nope nope"}).code == 401
    assert server.call("POST", "/login", form={"password": PASSWORD}).code == 429


def test_spoofed_proxy_header_is_ignored_by_default(server):
    for i in range(5):
        server.call("POST", "/login", form={"password": "nope nope nope"}, headers={"CF-Connecting-IP": f"10.0.0.{i}"})
    assert server.call("POST", "/login", form={"password": PASSWORD}, headers={"CF-Connecting-IP": "10.9.9.9"}).code == 429


def test_trusted_proxy_header_is_used_from_loopback(make):
    s = make(trust_proxy=parse_proxies("1"))
    for _ in range(5):
        s.call("POST", "/login", form={"password": "nope nope nope"}, headers={"X-Forwarded-For": "203.0.113.7"})
    assert s.call("POST", "/login", form={"password": PASSWORD}, headers={"X-Forwarded-For": "203.0.113.8"}).code == 303


def test_new_password_logs_out_every_admin(server):
    admin = server.login()
    Password(server.data).set("a brand new password")
    assert server.call("GET", "/api/notes", admin).code == 401
    assert server.call("POST", "/login", form={"password": PASSWORD}).code == 401
    assert server.login("a brand new password")


def test_short_password_refused(tmp_path):
    try:
        Password(tmp_path).set("short")
    except PasswordError:
        return
    raise AssertionError("a short password was accepted")


def test_logout_all(server):
    admin = server.login()
    assert Store(server.data).drop_all() >= 1
    assert server.call("GET", "/api/notes", admin).code == 401


def test_cookie_secure_on_localhost_not_on_lan(server):
    r = server.call("POST", "/login", form={"password": PASSWORD})
    assert "Secure" in r.headers["Set-Cookie"] and "HttpOnly" in r.headers["Set-Cookie"]
    r = server.call("POST", "/login", form={"password": PASSWORD}, headers={"Host": "192.168.1.20:5950"})
    assert "Secure" not in r.headers["Set-Cookie"]


def test_csrf_guard(server):
    admin = server.login()
    assert server.call("PUT", "/api/notes/n1", admin, {"title": "x"}, headers={"X-Tiroir": None}).code == 403
    assert server.call("PUT", "/api/notes/n1", admin, {"title": "x"}, headers={"Sec-Fetch-Site": "cross-site"}).code == 403
    assert server.call("POST", "/login", form={"password": PASSWORD}, headers={"Sec-Fetch-Site": "cross-site"}).code == 403


def test_security_headers_and_private_scripts(server):
    r = server.call("GET", "/")
    assert "default-src 'none'" in r.headers["Content-Security-Policy"] and r.headers["X-Frame-Options"] == "DENY"
    assert server.call("GET", "/static/app.js").code == 404  # the app code is served only after login
    assert server.call("GET", "/static/login.css").code == 200
    assert server.call("GET", "/static/../server.py").code == 404


def test_proxy_networks_setting():
    assert parse_proxies("") == () and parse_proxies("0") == ()
    assert [str(n) for n in parse_proxies("1")] == ["127.0.0.0/8", "::1/128"]
    assert [str(n) for n in parse_proxies("172.16.0.0/12, 10.0.0.5")] == ["172.16.0.0/12", "10.0.0.5/32"]


def test_untrusted_network_headers_ignored(make):
    s = make(trust_proxy=parse_proxies("10.0.0.0/8"))  # the test client is 127.0.0.1, not in 10/8
    for i in range(5):
        s.call("POST", "/login", form={"password": "nope nope nope"}, headers={"X-Forwarded-For": f"203.0.113.{i}"})
    assert s.call("POST", "/login", form={"password": PASSWORD}, headers={"X-Forwarded-For": "203.0.113.99"}).code == 429
