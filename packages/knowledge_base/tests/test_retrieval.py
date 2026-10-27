from rubies_knowledge_base.retrieval import search_policies


def test_blank_query_returns_no_results():
    result = search_policies("   ")

    assert result["found"] is False
    assert result["results"] == []


def test_relevant_query_returns_source_and_section(tmp_path):
    policy_file = tmp_path / "transfer-policy.md"
    policy_file.write_text(
        "# Transfer Policy\n\n"
        "## Failed transfer reversal\n\n"
        "Customers should report failed transfers for investigation "
        "and reversal where applicable.\n",
        encoding="utf-8",
    )

    result = search_policies(
        "failed transfer reversal",
        policy_dir=tmp_path,
        min_score=0.35,
    )

    assert result["found"] is True
    assert result["results"]

    first_result = result["results"][0]
    assert first_result["source"] == "transfer-policy.md"
    assert first_result["section"] == "Failed transfer reversal"


def test_unrelated_question_abstains(tmp_path):
    policy_file = tmp_path / "transfer-policy.md"
    policy_file.write_text(
        "# Transfer Policy\n\n"
        "## Failed transfer reversal\n\n"
        "Customers should report failed transfers for investigation.\n",
        encoding="utf-8",
    )

    result = search_policies(
        "What is the bank's policy on purple elephants?",
        policy_dir=tmp_path,
        min_score=0.35,
    )

    assert result["found"] is False
    assert result["results"] == []
    assert "Do not invent a policy answer" in result["message"]


def test_empty_policy_directory_abstains(tmp_path):
    result = search_policies(
        "failed transfer reversal",
        policy_dir=tmp_path,
    )

    assert result["found"] is False
    assert result["results"] == []


def test_invalid_top_k_raises_value_error():
    try:
        search_policies("transfer fees", top_k=0)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for top_k=0")


def test_invalid_min_score_raises_value_error():
    try:
        search_policies("transfer fees", min_score=1.1)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError for min_score=1.1")