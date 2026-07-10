"""Tests for the server-side run store."""

from helix.server.store import RunStore

_D = {"spec_name": "x", "modality": "crispr_ko", "feasible": True, "delivery": {"recommended": "rnp"}}


def test_add_summary_and_full(tmp_path):
    s = RunStore(str(tmp_path / "r.json"))
    sm = s.add(_D, "# proto")
    assert sm["name"] == "x" and sm["modality"] == "crispr_ko"
    assert sm["feasible"] is True and sm["delivery"] == "rnp" and sm["id"]
    assert "design" not in sm  # summary is light
    full = s.get(sm["id"])
    assert full["design"]["spec_name"] == "x" and full["protocol"] == "# proto"


def test_newest_first():
    s = RunStore()
    s.add({**_D, "spec_name": "a"}, "p")
    s.add({**_D, "spec_name": "b"}, "p")
    assert [r["name"] for r in s.list()] == ["b", "a"]


def test_persistence_reloads_from_file(tmp_path):
    path = str(tmp_path / "r.json")
    RunStore(path).add(_D, "p")
    assert len(RunStore(path).list()) == 1  # a fresh store reads the file


def test_delete_and_clear(tmp_path):
    s = RunStore(str(tmp_path / "r.json"))
    a = s.add({**_D, "spec_name": "a"}, "p")
    s.add({**_D, "spec_name": "b"}, "p")
    assert s.delete(a["id"]) is True and len(s.list()) == 1
    assert s.delete("missing") is False
    s.clear()
    assert s.list() == []


def test_coalesces_repeat_runs_of_one_design(tmp_path):
    s = RunStore(str(tmp_path / "r.json"))
    first = s.add({**_D, "spec_name": "x", "feasible": False}, "p1")
    again = s.add({**_D, "spec_name": "x", "feasible": True}, "p2")  # same design, iterated
    # one entry, same id, updated to the latest state
    assert again["id"] == first["id"]
    assert len(s.list()) == 1
    assert s.list()[0]["feasible"] is True
    assert s.get(first["id"])["protocol"] == "p2"


def test_distinct_designs_stay_separate_and_reorder(tmp_path):
    s = RunStore(str(tmp_path / "r.json"))
    s.add({**_D, "spec_name": "a"}, "p")
    s.add({**_D, "spec_name": "b"}, "p")
    assert [r["name"] for r in s.list()] == ["b", "a"]
    s.add({**_D, "spec_name": "a"}, "p")  # re-touch 'a' -> coalesces and moves to front
    assert [r["name"] for r in s.list()] == ["a", "b"]
    # different modality of the same name is a different design
    s.add({**_D, "spec_name": "a", "modality": "base_edit"}, "p")
    assert len(s.list()) == 3


def test_corrupt_file_starts_empty(tmp_path):
    path = tmp_path / "r.json"
    path.write_text("{not valid json")
    assert RunStore(str(path)).list() == []
