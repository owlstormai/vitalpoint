from rrb.cli import main as cli_main
from evals.run_evals import run_evals


def test_evals_pass_on_generated_dataset(tmp_path):
    db = tmp_path / "rrb.sqlite"
    labels = tmp_path / "labels.yaml"
    cli_main(["make-data", "--seed", "42", "--accounts", "150",
              "--db", str(db), "--labels", str(labels)])
    report = run_evals(str(db), str(labels))
    assert report["isolation_leaks"] == 0
    assert report["risk_accuracy"] >= 0.75
    assert report["satisfaction_accuracy"] >= 0.75
    assert report["citation_faithfulness"] == 1.0
    assert report["recall_at_5"] >= 0.75
    assert report["abstention_accuracy"] >= 0.9
    assert report["passed"] is True
