from src.etl.non_spark_etl import run_non_spark_etl


def test_run_non_spark_etl(capsys):
    run_non_spark_etl("input.csv", "output.parquet")
    captured = capsys.readouterr()
    assert (
        "[Non-Spark ETL] Would process input.csv and write to output.parquet"
        in captured.out
    )
