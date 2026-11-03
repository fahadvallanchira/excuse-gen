import memory


def db(tmp_path):
    return str(tmp_path / "t.db")


def test_save_and_recall(tmp_path):
    p = db(tmp_path)
    memory.save_excuse("my manager", "dentist", 2, p)
    memory.save_excuse("my manager", "flood", 3, p)
    assert memory.past_excuses_for("my manager", p) == ["dentist", "flood"]


def test_recall_is_per_recipient(tmp_path):
    p = db(tmp_path)
    memory.save_excuse("my manager", "dentist", 2, p)
    memory.save_excuse("mum", "busy", 1, p)
    assert memory.past_excuses_for("mum", p) == ["busy"]


def test_recipient_is_normalized(tmp_path):
    p = db(tmp_path)
    memory.save_excuse("  My Manager ", "dentist", 2, p)
    assert memory.past_excuses_for("my manager", p) == ["dentist"]


def test_normalize():
    assert memory.normalize("  My Manager ") == "my manager"


def test_init_db_is_idempotent(tmp_path):
    p = db(tmp_path)
    memory.init_db(p)
    memory.init_db(p)


def test_init_db_creates_parent_dir(tmp_path):
    p = str(tmp_path / "sub" / "t.db")
    memory.init_db(p)
    assert (tmp_path / "sub" / "t.db").exists()
