from src.etl.spark_etl import run_spark_etl


def test_run_spark_etl(capsys):
    run_spark_etl("input.csv", "output.parquet")
    captured = capsys.readouterr()
    assert (
        "[Spark ETL] Would process input.csv and write to output.parquet"
        in captured.out
    )
