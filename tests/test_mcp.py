"""Tests for the Helix MCP server (stdio JSON-RPC)."""

import io
import json

from helix.mcp.server import TOOLS, build_response, serve

SEQ = "ACCTGCACGTAGCTGCTAGCTAGCTGGCGT" * 5


def _call(name, arguments, msg_id=1):
    return build_response({
        "jsonrpc": "2.0", "id": msg_id, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })


def _text(resp):
    return resp["result"]["content"][0]["text"]


def _ko_spec(count=2):
    return (f'helix "T" {{ organism: human(GRCh38) '
            f'target: gene(TP53) {{ goal: knockout; sequence: "{SEQ}" }} '
            f'strategy {{ modality: crispr_ko; enzyme: SpCas9 }} '
            f'constraints {{ guides.count: {count} }} '
            f'simulate {{ sequence_provider: inline; on_target: heuristic_gc; '
            f'off_target: mock_seed; repair_outcome: mock_indel }} }}')


# ---- protocol handshake ----

def test_initialize_echoes_protocol_and_server_info():
    r = build_response({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05"}})
    assert r["result"]["protocolVersion"] == "2024-11-05"
    assert r["result"]["serverInfo"]["name"] == "helix"
    assert "tools" in r["result"]["capabilities"]


def test_initialized_notification_gets_no_response():
    assert build_response({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_notification_form_of_any_method_gets_no_response():
    # A JSON-RPC message with no "id" is a notification and must never get a response,
    # even for request-style methods (else id:null replies corrupt stdio correlation).
    for method in ("ping", "initialize", "tools/list", "tools/call"):
        assert build_response({"jsonrpc": "2.0", "method": method}) is None
    assert build_response({"jsonrpc": "2.0", "id": 5, "method": "ping"}) is not None


def test_ping_and_unknown_method():
    assert build_response({"jsonrpc": "2.0", "id": 2, "method": "ping"})["result"] == {}
    r = build_response({"jsonrpc": "2.0", "id": 3, "method": "does/not/exist"})
    assert r["error"]["code"] == -32601


def test_invalid_jsonrpc_envelope():
    assert build_response({"id": 1, "method": "ping"})["error"]["code"] == -32600


def test_tools_list_advertises_the_four_tools():
    r = build_response({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {t["name"] for t in r["result"]["tools"]}
    assert names == {"helix_reference", "helix_compile", "helix_resolve_gene", "helix_list_models"}
    for t in r["result"]["tools"]:  # every tool has a JSON-schema input
        assert t["inputSchema"]["type"] == "object"


# ---- tools ----

def test_compile_returns_design_summary():
    r = _call("helix_compile", {"source": _ko_spec()})
    assert not r["result"].get("isError")
    d = json.loads(_text(r))
    assert d["spec_name"] == "T" and d["modality"] == "crispr_ko"
    assert d["feasible"] is True and d["safety"]["allowed"] is True
    assert d["top_guides"] and "spacer" in d["top_guides"][0]
    assert "adapters" in d["provenance"]


def test_compile_full_returns_whole_design():
    d = json.loads(_text(_call("helix_compile", {"source": _ko_spec(), "full": True})))
    assert "guides" in d and "provenance" in d and isinstance(d["guides"], list)


def test_compile_bad_spec_is_iserror_with_clean_message():
    r = _call("helix_compile", {"source": 'helix "B" { organism: human(GRCh38) '
              'target: gene(TP53){goal:knockout} strategy{modality:crispr_ko; enzyme: banana} }'})
    assert r["result"]["isError"] is True
    txt = _text(r)
    assert "banana" in txt and "SpCas9" in txt and "pydantic" not in txt


def test_compile_syntax_error_reports_line():
    r = _call("helix_compile", {"source": 'helix "B" {\n  target: gene(TP53) { goal: knockout\n}'})
    assert r["result"]["isError"] is True
    assert "line" in _text(r)


def test_compile_missing_source_is_iserror():
    assert _call("helix_compile", {})["result"]["isError"] is True


def test_compile_malformed_yaml_is_clean_error_not_internal():
    r = _call("helix_compile", {"source": "foo: [1, 2", "format": "yaml"})
    txt = _text(r)
    assert r["result"]["isError"] is True
    assert txt.startswith("Error:") and "invalid YAML" in txt
    assert "Internal error" not in txt and "<unicode string>" not in txt


def test_compile_author_valueerror_is_clean_error_not_internal():
    # base_edit without strategy.editor: parses fine, compile_spec raises a plain ValueError.
    spec = (f'helix "b" {{ organism: human(GRCh38) '
            f'target: gene(TP53) {{ goal: knockout; sequence: "{SEQ}" }} '
            f'strategy {{ modality: base_edit; enzyme: SpCas9 }} simulate {{ sequence_provider: inline }} }}')
    r = _call("helix_compile", {"source": spec})
    txt = _text(r)
    assert r["result"]["isError"] is True
    assert txt.startswith("Error:") and "editor" in txt and "Internal error" not in txt


def test_compile_unknown_adapter_is_clean_error():
    spec = (f'helix "k" {{ organism: human(GRCh38) '
            f'target: gene(TP53) {{ goal: knockout; sequence: "{SEQ}" }} '
            f'strategy {{ modality: crispr_ko; enzyme: SpCas9 }} '
            f'simulate {{ sequence_provider: inline; on_target: bogus }} }}')
    txt = _text(_call("helix_compile", {"source": spec}))
    assert txt.startswith("Error:") and "bogus" in txt and '"' not in txt.split("bogus")[0]


def test_deletion_summary_includes_the_excised_region():
    from pathlib import Path
    spec = Path(__file__).resolve().parents[1] / "examples" / "tp53_deletion.hx"
    d = json.loads(_text(_call("helix_compile", {"source": spec.read_text()})))
    assert d["modality"] == "deletion"
    assert "deletion" in d and d["deletion"]["deletion_size"] > 0 and d["deletion"]["junction"]


def test_list_models_reports_roles_and_keys():
    d = json.loads(_text(_call("helix_list_models", {})))
    assert "off_target" in d["roles"] and "mock_seed" in d["roles"]["off_target"]
    assert "sequence_provider" in d["roles"]


def test_reference_includes_grammar_and_examples():
    txt = _text(_call("helix_reference", {}))
    assert "Writing a Helix spec" in txt and "helix \"" in txt  # guide + an example spec


def test_unknown_tool_is_iserror():
    r = _call("helix_nonexistent", {})
    assert r["result"]["isError"] is True


# ---- stdio loop ----

def test_serve_loop_handles_notifications_and_parse_errors():
    lines = [
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}',
        '{"jsonrpc":"2.0","method":"notifications/initialized"}',  # no response
        'garbage',                                                  # parse error
        '{"jsonrpc":"2.0","id":2,"method":"tools/list"}',
    ]
    out = io.StringIO()
    serve(stdin=io.StringIO("\n".join(lines) + "\n"), stdout=out)
    responses = [json.loads(x) for x in out.getvalue().splitlines() if x.strip()]
    ids = [r.get("id") for r in responses]
    assert ids == [1, None, 2]  # initialize, parse-error(id=None), tools/list — notification skipped
    assert responses[1]["error"]["code"] == -32700
