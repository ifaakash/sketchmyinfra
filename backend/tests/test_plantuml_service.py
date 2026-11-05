"""Tests for the PlantUML service: include localisation and error reporting."""

import asyncio

import httpx
import pytest

from app.config import settings
from app.services import plantuml
from app.services.plantuml import PlantUMLError, _localize_includes, render_puml

AWS_URL = "https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/v20.0/dist"
AZURE_URL = "https://raw.githubusercontent.com/plantuml-stdlib/Azure-PlantUML/master/dist"
GCP_URL = "https://raw.githubusercontent.com/Crashedmind/PlantUML-icons-GCP/master/dist"


@pytest.fixture
def lib_dir(monkeypatch):
    monkeypatch.setattr(settings, "plantuml_lib_dir", "/opt/plantuml-libs")


class TestLocalizeIncludes:
    def test_rewrites_all_providers(self, lib_dir):
        puml = (
            f"!define AWSPuml {AWS_URL}\n"
            f"!define AzurePuml {AZURE_URL}\n"
            f"!define GCPPuml {GCP_URL}\n"
        )
        out = _localize_includes(puml)
        assert "githubusercontent" not in out
        assert "!define AWSPuml /opt/plantuml-libs/aws\n" in out
        assert "!define AzurePuml /opt/plantuml-libs/azure\n" in out
        assert "!define GCPPuml /opt/plantuml-libs/gcp\n" in out

    def test_rewrites_full_url_include(self, lib_dir):
        out = _localize_includes(f"!include {AWS_URL}/Compute/EC2Instance.puml")
        assert out == "!include /opt/plantuml-libs/aws/Compute/EC2Instance.puml"

    def test_any_aws_ref_maps_to_vendored_copy(self, lib_dir):
        old = AWS_URL.replace("v20.0", "v18.0")
        assert _localize_includes(f"!define AWSPuml {old}") == "!define AWSPuml /opt/plantuml-libs/aws"

    def test_unknown_urls_untouched(self, lib_dir):
        puml = "!include https://example.com/foo.puml"
        assert _localize_includes(puml) == puml

    def test_disabled_when_lib_dir_empty(self, monkeypatch):
        monkeypatch.setattr(settings, "plantuml_lib_dir", "")
        puml = f"!define AWSPuml {AWS_URL}"
        assert _localize_includes(puml) == puml


def _mock_server(monkeypatch, handler):
    """Route render_puml's httpx client through a MockTransport."""
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        plantuml.httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw)
    )


class TestRenderErrors:
    def test_400_reports_header_error_and_line(self, monkeypatch, lib_dir):
        def handler(request):
            return httpx.Response(
                400,
                headers={
                    "content-type": "image/svg+xml",
                    "X-PlantUML-Diagram-Error": "Cannot open URL",
                    "X-PlantUML-Diagram-Error-Line": "2",
                },
                content=b"<svg></svg>",
            )

        _mock_server(monkeypatch, handler)
        with pytest.raises(PlantUMLError, match=r"Cannot open URL \(line 2\)"):
            asyncio.run(render_puml("@startuml\nA\n@enduml"))

    def test_400_without_headers_keeps_status(self, monkeypatch, lib_dir):
        _mock_server(monkeypatch, lambda request: httpx.Response(400, content=b""))
        with pytest.raises(PlantUMLError, match="returned 400"):
            asyncio.run(render_puml("@startuml\nA\n@enduml"))

    def test_sends_localized_code(self, monkeypatch, lib_dir):
        seen = {}

        def handler(request):
            seen["body"] = request.content.decode()
            return httpx.Response(200, headers={"content-type": "image/svg+xml"}, content=b"<svg></svg>")

        _mock_server(monkeypatch, handler)
        result = asyncio.run(render_puml(f"@startuml\n!define AWSPuml {AWS_URL}\n@enduml"))
        assert result.startswith("data:image/svg+xml;base64,")
        assert "!define AWSPuml /opt/plantuml-libs/aws" in seen["body"]
        assert "githubusercontent" not in seen["body"]
