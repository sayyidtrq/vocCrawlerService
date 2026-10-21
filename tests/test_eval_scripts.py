from __future__ import annotations

import json

import pytest

from app.integrations import analysis_client
from scripts import eval_reply, eval_taxonomy


def result(expected, predicted, **extra):
    return {
        "expected_slug": expected, "predicted_slug": predicted, "corrected": False,
        "expected_tags": set(), "predicted_tags": [], **extra,
    }


def test_primary_metrics_per_aspect():
    report = eval_taxonomy.evaluate(
        [
            result("takaran_bbm", "takaran_bbm"),
            result("takaran_bbm", "lainnya", corrected=True),
            result("waktu_tunggu", "takaran_bbm"),
            result("lainnya", "lainnya"),
        ]
    )

    assert report["reviews"] == 4 and report["primary_accuracy"] == 0.5
    assert report["fallback_share"] == 0.5 and report["corrected_rate"] == 0.25
    assert report["per_aspect"]["takaran_bbm"] == {"support": 2, "predicted": 2, "precision": 0.5, "recall": 0.5}
    assert report["per_aspect"]["waktu_tunggu"]["recall"] == 0.0
    assert "tags" not in report  # nothing labelled with tags


def test_tag_metrics_cover_multi_label_quality():
    report = eval_taxonomy.evaluate(
        [
            result("waktu_tunggu", "waktu_tunggu", expected_tags={"waktu_tunggu", "pelayanan_petugas"},
                   predicted_tags=["waktu_tunggu", "pelayanan_petugas", "kebersihan"]),
            result("takaran_bbm", "takaran_bbm", expected_tags={"takaran_bbm"}, predicted_tags=["parkir", "takaran_bbm"]),
        ]
    )
    tags = report["tags"]

    assert tags["labelled"] == 2
    assert tags["over_tag_rate"] == 1.0  # (3-2 + 2-1) / 2
    assert tags["primary_is_top_tag"] == 0.5
    assert tags["per_aspect"]["kebersihan"] == {"support": 0, "predicted": 1, "precision": 0.0, "recall": None}
    assert tags["per_aspect"]["pelayanan_petugas"]["recall"] == 1.0


def test_reply_metrics_precision_coverage_and_safety_recall():
    rows = [
        {"expected_preset": "a", "critical": False, "mode": "preset", "preset_id": "a", "tokens_used": 10},
        {"expected_preset": "a", "critical": False, "mode": "none", "preset_id": None, "tokens_used": 10},
        {"expected_preset": "b", "critical": False, "mode": "preset", "preset_id": "a", "tokens_used": 10},
        {"expected_preset": "none", "critical": True, "mode": "escalate", "preset_id": None, "tokens_used": 10},
        {"expected_preset": "none", "critical": True, "mode": "preset", "preset_id": "a", "tokens_used": 10},
    ]
    report = eval_reply.evaluate(rows)

    assert report["preset_precision"] == round(1 / 3, 4)  # 3 answered, 1 right
    assert report["coverage"] == round(1 / 3, 4)  # 3 labelled with a preset, 1 answered right
    assert report["safety_recall"] == 0.5  # one critical review was offered a preset
    assert report["wrongly_offered"] == 1 and report["tokens_total"] == 50


def test_empty_inputs_do_not_divide_by_zero():
    assert eval_reply.evaluate([])["preset_precision"] is None
    assert eval_taxonomy.evaluate([])["primary_accuracy"] is None


def test_the_taxonomy_cli_scores_a_csv_end_to_end(tmp_path, tx_fixture, monkeypatch, capsys):
    class FakeProvider:
        model_name = "fake"

        def analyze_review(self, review):
            text = review["review_text"]
            return {
                "sentiment": "negative", "sentiment_score": 0.9, "urgency": "low", "summary": "s",
                "recommended_action": "a", "keywords": [], "is_potential_viral": False, "is_safety_issue": False,
                "issue_category": "takaran_bbm" if "takaran" in text.lower() else "tidak_ada",
            }

    monkeypatch.setattr(analysis_client, "create_analysis_client", lambda settings, provider=None: FakeProvider())
    fixture = tmp_path / "wl.json"
    fixture.write_text(json.dumps(tx_fixture), encoding="utf-8")
    csv_path = tmp_path / "labelled.csv"
    csv_path.write_text(
        "review_text,expected_slug,rating\nTakaran kurang,takaran_bbm,1\nPompa mati,ketersediaan_bbm,2\n", encoding="utf-8"
    )

    args = eval_taxonomy.build_parser().parse_args([str(csv_path), "--taxonomy", str(fixture), "--key", "spbu:6285c2fa"])
    report = eval_taxonomy.run(args)

    assert report["reviews"] == 2 and report["primary_accuracy"] == 0.5
    assert report["corrected_rate"] == 0.5  # "tidak_ada" is not in the SPBU taxonomy
    assert report["fallback_share"] == 0.5


def test_a_fixture_with_several_taxonomies_needs_a_key(tmp_path, tx_fixture):
    fixture = tmp_path / "wl.json"
    fixture.write_text(json.dumps(tx_fixture), encoding="utf-8")
    with pytest.raises(SystemExit):
        eval_taxonomy.load_snapshot(str(fixture))
