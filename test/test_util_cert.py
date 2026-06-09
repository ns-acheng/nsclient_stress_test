from unittest.mock import patch, MagicMock

import pytest

from util_cert import check_url_cert


class TestCheckUrlCert:
    @patch("util_cert.crypto.load_certificate")
    @patch("util_cert.ssl.create_default_context")
    @patch("util_cert.socket.socket")
    def test_returns_issuer_cn(self, mock_sock_cls, mock_ctx, mock_load):
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        mock_wrapped = MagicMock()
        mock_ctx.return_value.wrap_socket.return_value = mock_wrapped
        mock_wrapped.getpeercert.return_value = b"certdata"

        mock_x509 = MagicMock()
        mock_issuer = MagicMock()
        mock_issuer.get_components.return_value = [
            (b"C", b"US"),
            (b"CN", b"TestCA"),
            (b"emailAddress", b"ca@test.com"),
        ]
        mock_x509.get_issuer.return_value = mock_issuer
        mock_load.return_value = mock_x509

        result = check_url_cert("https://example.com/page")
        assert "CN=TestCA" in result
        assert "emailAddress=ca@test.com" in result

    @patch("util_cert.crypto.load_certificate")
    @patch("util_cert.ssl.create_default_context")
    @patch("util_cert.socket.socket")
    def test_only_cn_and_email(self, mock_sock_cls, mock_ctx, mock_load):
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        mock_wrapped = MagicMock()
        mock_ctx.return_value.wrap_socket.return_value = mock_wrapped
        mock_wrapped.getpeercert.return_value = b"cert"

        mock_x509 = MagicMock()
        mock_issuer = MagicMock()
        mock_issuer.get_components.return_value = [
            (b"C", b"US"),
            (b"O", b"OrgName"),
            (b"CN", b"MyCN"),
        ]
        mock_x509.get_issuer.return_value = mock_issuer
        mock_load.return_value = mock_x509

        result = check_url_cert("https://example.com")
        assert "CN=MyCN" in result
        assert "O=" not in result
        assert "C=" not in result

    @patch("util_cert.socket.socket")
    def test_connection_error(self, mock_sock_cls):
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        mock_sock.connect.side_effect = ConnectionRefusedError("refused")
        assert check_url_cert("https://example.com") == ""

    def test_empty_url(self):
        assert check_url_cert("") == ""

    @patch("util_cert.socket.socket")
    def test_timeout(self, mock_sock_cls):
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        mock_sock.connect.side_effect = TimeoutError("timed out")
        assert check_url_cert("https://example.com") == ""

    @patch("util_cert.crypto.load_certificate")
    @patch("util_cert.ssl.create_default_context")
    @patch("util_cert.socket.socket")
    def test_no_cn_or_email(self, mock_sock_cls, mock_ctx, mock_load):
        mock_sock = MagicMock()
        mock_sock_cls.return_value = mock_sock
        mock_wrapped = MagicMock()
        mock_ctx.return_value.wrap_socket.return_value = mock_wrapped
        mock_wrapped.getpeercert.return_value = b"cert"

        mock_x509 = MagicMock()
        mock_issuer = MagicMock()
        mock_issuer.get_components.return_value = [
            (b"C", b"US"),
            (b"O", b"SomeOrg"),
        ]
        mock_x509.get_issuer.return_value = mock_issuer
        mock_load.return_value = mock_x509

        result = check_url_cert("https://example.com")
        assert result == ""
