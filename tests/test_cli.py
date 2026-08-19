from rrb.cli import main


def test_make_data_and_brief(tmp_path, capsys):
    db = tmp_path / "rrb.sqlite"
    labels = tmp_path / "labels.yaml"
    main(["make-data", "--seed", "42", "--accounts", "25",
          "--db", str(db), "--labels", str(labels)])
    assert db.exists() and labels.exists()

    main(["brief", "acct_0003", "--db", str(db)])
    out = capsys.readouterr().out
    assert "# Renewal Risk Brief" in out


def test_brief_all_writes_files(tmp_path, capsys):
    db = tmp_path / "rrb.sqlite"
    main(["make-data", "--seed", "42", "--accounts", "10",
          "--db", str(db), "--labels", str(tmp_path / "l.yaml")])
    outdir = tmp_path / "briefs"
    main(["brief", "--all", "--db", str(db), "--out", str(outdir)])
    files = list(outdir.glob("acct_*.md"))
    assert len(files) == 10
