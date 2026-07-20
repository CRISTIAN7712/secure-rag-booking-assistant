from src.services.loaders import load_text


def test_load_txt(tmp_path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("hello", encoding="utf-8")
    assert load_text(path) == "hello"

